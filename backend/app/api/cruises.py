"""Public cruise, sailing, and availability endpoints.

The booking page uses the availability endpoint as its source of truth. The
endpoint returns the same cabin IDs that the booking hold endpoint accepts.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.models import (
    Amenity,
    ApprovalStatus,
    Booking,
    BookingStatus,
    Cabin,
    CabinInventory,
    CabinType,
    CabinTypeAmenity,
    Cruise,
    CruiseImage,
    CruiseItinerary,
    CruiseStatus,
    Deck,
    InventoryStatus,
    Port,
    Sailing,
    SailingStatus,
    Ship,
)
from app.schemas.cruise import (
    AvailabilityCabin,
    AvailabilityDeck,
    AvailabilityOut,
    AvailabilityType,
)

router = APIRouter(tags=["Cruises"])


@router.get("/ports")
async def ports(session=Depends(get_session)):
    """Return ports used by the public search/filter UI."""
    rows = (await session.scalars(select(Port).order_by(Port.name))).all()
    return [
        {
            "id": str(port.id),
            "name": port.name,
            "city": port.city,
            "country": port.country,
            "code": port.code,
            "timezone": port.timezone,
        }
        for port in rows
    ]


@router.get("/amenities")
async def amenities(session=Depends(get_session)):
    """Return cabin amenities for filters and detail pages."""
    rows = (await session.scalars(select(Amenity).order_by(Amenity.name))).all()
    return [
        {
            "id": str(amenity.id),
            "name": amenity.name,
            "icon_key": amenity.icon_key,
            "category": amenity.category,
        }
        for amenity in rows
    ]


@router.get("/cruises")
async def cruises(
    q: str | None = None,
    embark_port_id: str | None = None,
    departure_from: str | None = None,
    departure_to: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    cabin_type: str | None = None,
    guests: int | None = None,
    sailing_days_min: int | None = None,
    sailing_days_max: int | None = None,
    sort: str = "departure_asc",
    page: int = 1,
    page_size: int = 20,
    session=Depends(get_session),
):
    """List approved and published cruises with simple search/filter support."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    statement = select(Cruise).where(
        Cruise.status == CruiseStatus.published,
        Cruise.approval_status == ApprovalStatus.approved,
        Cruise.deleted_at.is_(None),
    )

    if q:
        # PostgreSQL full-text search keeps the public cruise search scalable.
        statement = statement.join(Port, Port.id == Cruise.embark_port_id).where(
            or_(
                func.to_tsvector(
                    "english",
                    func.coalesce(Cruise.name, "")
                    + " "
                    + func.coalesce(Cruise.description, ""),
                ).op("@@")(func.plainto_tsquery("english", q)),
                func.to_tsvector(
                    "english",
                    func.coalesce(Port.name, "")
                    + " "
                    + func.coalesce(Port.city, ""),
                ).op("@@")(func.plainto_tsquery("english", q)),
            )
        )

    if embark_port_id:
        statement = statement.where(Cruise.embark_port_id == embark_port_id)

    if departure_from:
        statement = statement.where(
            Cruise.id.in_(
                select(Sailing.cruise_id).where(
                    Sailing.departure_date >= date.fromisoformat(departure_from)
                )
            )
        )

    if departure_to:
        statement = statement.where(
            Cruise.id.in_(
                select(Sailing.cruise_id).where(
                    Sailing.departure_date <= date.fromisoformat(departure_to)
                )
            )
        )

    if cabin_type:
        statement = statement.where(
            Cruise.id.in_(
                select(CabinType.cruise_id).where(CabinType.name.ilike(cabin_type))
            )
        )

    if guests is not None:
        statement = statement.where(
            Cruise.id.in_(
                select(CabinType.cruise_id).where(CabinType.max_occupancy >= guests)
            )
        )

    if min_price is not None:
        statement = statement.where(Cruise.base_price_cents >= min_price)

    if max_price is not None:
        statement = statement.where(Cruise.base_price_cents <= max_price)

    if sailing_days_min is not None:
        statement = statement.where(Cruise.sailing_days >= sailing_days_min)

    if sailing_days_max is not None:
        statement = statement.where(Cruise.sailing_days <= sailing_days_max)

    if sort == "price_asc":
        statement = statement.order_by(Cruise.base_price_cents)
    elif sort == "price_desc":
        statement = statement.order_by(Cruise.base_price_cents.desc())
    elif sort == "popularity":
        statement = statement.order_by(Cruise.is_featured.desc(), Cruise.created_at.desc())
    elif sort == "departure_asc":
        first_departure = (
            select(func.min(Sailing.departure_date))
            .where(Sailing.cruise_id == Cruise.id)
            .scalar_subquery()
        )
        statement = statement.order_by(first_departure.asc().nullslast(), Cruise.created_at.desc())
    else:
        statement = statement.order_by(Cruise.created_at.desc())

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    items = []
    for cruise in rows:
        embark_port = await session.get(Port, cruise.embark_port_id)
        disembark_port = await session.get(Port, cruise.disembark_port_id)
        ship = await session.get(Ship, cruise.ship_id)
        image = await session.scalar(
            select(CruiseImage)
            .where(CruiseImage.cruise_id == cruise.id)
            .order_by(CruiseImage.is_cover.desc(), CruiseImage.sort_order)
        )
        next_sailing = await session.scalar(
            select(Sailing)
            .where(
                Sailing.cruise_id == cruise.id,
                Sailing.status.in_([SailingStatus.open, SailingStatus.scheduled]),
                Sailing.departure_date >= date.today(),
            )
            .order_by(Sailing.departure_date)
        )
        items.append(
            {
                "id": str(cruise.id),
                "name": cruise.name,
                "slug": cruise.slug,
                "description": cruise.description,
                "sailing_days": cruise.sailing_days,
                "from_price_cents": cruise.base_price_cents,
                "currency": cruise.currency,
                "embark_port": embark_port.name if embark_port else None,
                "embark_city": embark_port.city if embark_port else None,
                "disembark_port": disembark_port.name if disembark_port else None,
                "disembark_city": disembark_port.city if disembark_port else None,
                "ship": {
                    "id": str(ship.id),
                    "name": ship.name,
                    "operator_name": ship.operator_name,
                    "deck_count": ship.deck_count,
                    "description": ship.description,
                } if ship else None,
                "next_sailing": {
                    "id": str(next_sailing.id),
                    "departure_date": next_sailing.departure_date,
                    "return_date": next_sailing.return_date,
                } if next_sailing else None,
                "cover_image": image.url if image else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/cruises/featured")
async def featured(session=Depends(get_session)):
    """Return cruises ranked by confirmed bookings from the last 90 days."""
    cache = await get_redis()
    if cache:
        cached = await cache.get("featured_cruises:v1")
        if cached:
            import json

            return json.loads(cached)

    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=90)
    rows = (
        await session.execute(
            select(Cruise, func.count(Booking.id).label("count"))
            .join(Sailing, Sailing.cruise_id == Cruise.id)
            .outerjoin(
                Booking,
                and_(
                    Booking.sailing_id == Sailing.id,
                    Booking.status == BookingStatus.confirmed,
                    Booking.confirmed_at >= since,
                ),
            )
            .where(
                Cruise.status == CruiseStatus.published,
                Cruise.approval_status == ApprovalStatus.approved,
                Cruise.deleted_at.is_(None),
            )
            .group_by(Cruise.id)
            .order_by(func.count(Booking.id).desc(), Cruise.created_at.desc())
            .limit(12)
        )
    ).all()

    # If the demo database has no bookings yet, featured cruises still appear.
    if not rows or all(int(count) == 0 for _, count in rows):
        rows = [
            (cruise, 0)
            for cruise in (
                await session.scalars(
                    select(Cruise)
                    .where(
                        Cruise.is_featured.is_(True),
                        Cruise.status == CruiseStatus.published,
                        Cruise.approval_status == ApprovalStatus.approved,
                        Cruise.deleted_at.is_(None),
                    )
                    .order_by(Cruise.created_at.desc())
                    .limit(12)
                )
            ).all()
        ]

    output = []
    for cruise, count in rows:
        image = await session.scalar(
            select(CruiseImage)
            .where(CruiseImage.cruise_id == cruise.id)
            .order_by(CruiseImage.is_cover.desc(), CruiseImage.sort_order)
        )
        output.append(
            {
                "id": str(cruise.id),
                "name": cruise.name,
                "slug": cruise.slug,
                "sailing_days": cruise.sailing_days,
                "from_price_cents": cruise.base_price_cents,
                "booked_count": int(count),
                "cover_image": image.url if image else None,
            }
        )

    if cache:
        import json

        await cache.set("featured_cruises:v1", json.dumps(output), ex=300)

    return output


@router.get("/cruises/{slug}")
async def detail(slug: str, session=Depends(get_session)):
    """Return one published cruise with its itinerary and cabin types."""
    cruise = await session.scalar(
        select(Cruise).where(
            Cruise.slug == slug,
            Cruise.status == CruiseStatus.published,
            Cruise.approval_status == ApprovalStatus.approved,
            Cruise.deleted_at.is_(None),
        )
    )
    if not cruise:
        raise AppError("NOT_FOUND", "Cruise not found.", 404)

    ship = await session.get(Ship, cruise.ship_id)
    embark = await session.get(Port, cruise.embark_port_id)
    disembark = await session.get(Port, cruise.disembark_port_id)
    images = (
        await session.scalars(
            select(CruiseImage)
            .where(CruiseImage.cruise_id == cruise.id)
            .order_by(CruiseImage.sort_order)
        )
    ).all()
    itinerary = (
        await session.scalars(
            select(CruiseItinerary)
            .where(CruiseItinerary.cruise_id == cruise.id)
            .order_by(CruiseItinerary.day_number)
        )
    ).all()
    cabin_types = (
        await session.scalars(
            select(CabinType).where(CabinType.cruise_id == cruise.id)
        )
    ).all()

    itinerary_port_ids = {item.port_id for item in itinerary if item.port_id}
    itinerary_ports = {
        port.id: port
        for port in (
            await session.scalars(
                select(Port).where(Port.id.in_(itinerary_port_ids))
            )
        ).all()
    }

    return {
        "id": str(cruise.id),
        "name": cruise.name,
        "slug": cruise.slug,
        "description": cruise.description,
        "sailing_days": cruise.sailing_days,
        "base_price_cents": cruise.base_price_cents,
        "currency": cruise.currency,
        "ship": {"id": str(ship.id), "name": ship.name} if ship else None,
        "embark_port": (
            {"id": str(embark.id), "name": embark.name, "city": embark.city}
            if embark
            else None
        ),
        "disembark_port": (
            {"id": str(disembark.id), "name": disembark.name, "city": disembark.city}
            if disembark
            else None
        ),
        "images": [
            {"url": image.url, "alt_text": image.alt_text, "is_cover": image.is_cover}
            for image in images
        ],
        "itinerary": [
            {
                "day_number": item.day_number,
                "port_id": str(item.port_id) if item.port_id else None,
                "port": (
                    {
                        "id": str(itinerary_ports[item.port_id].id),
                        "name": itinerary_ports[item.port_id].name,
                        "city": itinerary_ports[item.port_id].city,
                    }
                    if item.port_id in itinerary_ports
                    else None
                ),
                "arrival_time": item.arrival_time,
                "departure_time": item.departure_time,
                "description": item.description,
            }
            for item in itinerary
        ],
        "cabin_types": [
            {
                "id": str(cabin_type.id),
                "name": cabin_type.name,
                "description": cabin_type.description,
                "max_occupancy": cabin_type.max_occupancy,
                "base_price_cents": cabin_type.base_price_cents,
                "price_per_extra_guest_cents": cabin_type.price_per_extra_guest_cents,
                "amenities": [
                    {"name": amenity.name, "icon_key": amenity.icon_key}
                    for amenity in (
                        await session.execute(
                            select(Amenity)
                            .join(
                                CabinTypeAmenity,
                                CabinTypeAmenity.amenity_id == Amenity.id,
                            )
                            .where(CabinTypeAmenity.cabin_type_id == cabin_type.id)
                        )
                    ).scalars().all()
                ],
            }
            for cabin_type in cabin_types
        ],
    }


@router.get("/cruises/{slug}/sailings")
async def sailings(slug: str, session=Depends(get_session)):
    """Return open sailings and their current available-cabin count."""
    cruise = await session.scalar(
        select(Cruise).where(
            Cruise.slug == slug,
            Cruise.status == CruiseStatus.published,
            Cruise.approval_status == ApprovalStatus.approved,
            Cruise.deleted_at.is_(None),
        )
    )
    if not cruise:
        raise AppError("NOT_FOUND", "Cruise not found.", 404)

    rows = (
        await session.scalars(
            select(Sailing)
            .where(
                Sailing.cruise_id == cruise.id,
                Sailing.status == SailingStatus.open,
            )
            .order_by(Sailing.departure_date)
        )
    ).all()

    output = []
    for sailing in rows:
        inventory = (
            await session.scalars(
                select(CabinInventory).where(
                    CabinInventory.sailing_id == sailing.id,
                    CabinInventory.status == InventoryStatus.available,
                )
            )
        ).all()
        output.append(
            {
                "id": str(sailing.id),
                "departure_date": sailing.departure_date,
                "return_date": sailing.return_date,
                "booking_closes_at": sailing.booking_closes_at,
                "from_price_cents": min(
                    [item.price_cents for item in inventory],
                    default=cruise.base_price_cents,
                ),
                "cabins_left": len(inventory),
            }
        )

    return output


@router.get("/sailings/{sailing_id}/availability", response_model=AvailabilityOut)
async def availability(sailing_id: str, session=Depends(get_session)):
    """Return live cabin inventory grouped by deck and cabin type.

    The booking UI uses each returned ``cabin_id`` when creating a hold. The
    backend locks the same inventory row again during checkout, so this screen
    is a live view and not a separate booking system.
    """
    sailing = await session.get(Sailing, sailing_id)
    if not sailing:
        raise AppError("NOT_FOUND", "Sailing not found.", 404)

    cruise = await session.get(Cruise, sailing.cruise_id)
    inventory = (
        await session.scalars(
            select(CabinInventory).where(CabinInventory.sailing_id == sailing.id)
        )
    ).all()

    cabin_ids = [item.cabin_id for item in inventory]
    cabins = (
        await session.scalars(select(Cabin).where(Cabin.id.in_(cabin_ids)))
    ).all()
    cabin_by_id = {cabin.id: cabin for cabin in cabins}

    physical_type_ids = [cabin.cabin_type_id for cabin in cabins]
    physical_types = (
        await session.scalars(
            select(CabinType).where(CabinType.id.in_(physical_type_ids))
        )
    ).all()
    physical_type_by_id = {item.id: item for item in physical_types}

    current_types = (
        await session.scalars(
            select(CabinType).where(CabinType.cruise_id == cruise.id)
        )
    ).all()

    decks = (
        await session.scalars(
            select(Deck).where(Deck.ship_id == cruise.ship_id).order_by(Deck.deck_number)
        )
    ).all()

    deck_output = []
    for deck in decks:
        type_output = []

        for cabin_type in current_types:
            matching_inventory = []

            for inventory_row in inventory:
                cabin = cabin_by_id.get(inventory_row.cabin_id)
                physical_type = (
                    physical_type_by_id.get(cabin.cabin_type_id) if cabin else None
                )

                if (
                    cabin
                    and cabin.deck_id == deck.id
                    and physical_type
                    and physical_type.name == cabin_type.name
                ):
                    matching_inventory.append(inventory_row)

            if not matching_inventory:
                continue

            amenities = (
                await session.execute(
                    select(Amenity)
                    .join(
                        CabinTypeAmenity,
                        CabinTypeAmenity.amenity_id == Amenity.id,
                    )
                    .where(CabinTypeAmenity.cabin_type_id == cabin_type.id)
                )
            ).scalars().all()

            type_output.append(
                AvailabilityType(
                    cabin_type_id=str(cabin_type.id),
                    name=cabin_type.name,
                    max_occupancy=cabin_type.max_occupancy,
                    base_price_cents=cabin_type.base_price_cents,
                    price_per_extra_guest_cents=cabin_type.price_per_extra_guest_cents,
                    amenities=[
                        {"name": amenity.name, "icon_key": amenity.icon_key}
                        for amenity in amenities
                    ],
                    cabins=[
                        AvailabilityCabin(
                            cabin_id=str(row.cabin_id),
                            cabin_number=cabin_by_id[row.cabin_id].cabin_number,
                            status=(
                                "unavailable"
                                if row.status == InventoryStatus.held
                                else row.status.value
                            ),
                            price_cents=row.price_cents,
                            max_occupancy=cabin_by_id[row.cabin_id].max_occupancy,
                        )
                        for row in matching_inventory
                    ],
                )
            )

        if type_output:
            deck_output.append(
                AvailabilityDeck(
                    deck_id=str(deck.id),
                    deck_number=deck.deck_number,
                    name=deck.name,
                    cabin_types=type_output,
                )
            )

    return AvailabilityOut(
        sailing_id=str(sailing.id),
        departure_date=sailing.departure_date,
        return_date=sailing.return_date,
        booking_closes_at=sailing.booking_closes_at,
        port_fee_per_guest_cents=sailing.port_fee_per_guest_cents,
        tax_rate=float(settings.TAX_RATE),
        decks=deck_output,
        summary={
            "total_cabins": len(inventory),
            "available": sum(
                row.status == InventoryStatus.available for row in inventory
            ),
            "held": sum(row.status == InventoryStatus.held for row in inventory),
            "booked": sum(row.status == InventoryStatus.booked for row in inventory),
        },
    )
