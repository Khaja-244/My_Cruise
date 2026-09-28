"""Core booking-hold logic.

This service is intentionally separate from the API route so direct traveler
bookings and partner-website bookings can use exactly the same inventory rules.
"""

from datetime import datetime, timedelta, timezone
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models import (
    ApprovalStatus,
    Booking,
    BookingChannel,
    BookingStatus,
    Cabin,
    CabinType,
    CommissionType,
    Cruise,
    CruiseStatus,
    InventoryStatus,
    Partner,
    PartnerCruiseExposure,
    PartnerStatus,
    IntegrationStatus,
    Sailing,
    SailingStatus,
    User,
    BookingCabin,
    BookingGuest,
)
from app.services.inventory_service import get_locked_inventory
from app.services.pricing_service import calculate_price

BOOKING_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def booking_ref() -> str:
    """Create a short human-friendly booking reference."""
    return "".join(secrets.choice(BOOKING_REF_ALPHABET) for _ in range(10))


def calculate_commission_cents(booking: Booking, cruise: Cruise) -> int:
    """Calculate partner commission for a partner-channel booking."""
    if (
        booking.channel != BookingChannel.partner
        or not cruise.commission_type
        or cruise.commission_value is None
    ):
        return 0

    if cruise.commission_type == CommissionType.percent:
        commission = booking.total_cents * float(cruise.commission_value) / 100
        return min(booking.total_cents, int(round(commission)))

    # Flat commission values are stored in dollars in the current database model.
    commission = float(cruise.commission_value) * 100
    return min(booking.total_cents, int(round(commission)))


async def hold_booking(
    session: AsyncSession,
    user: User,
    data,
    idem_key: str,
    channel: BookingChannel = BookingChannel.direct,
    partner: Partner | None = None,
    partner_website_id=None,
):
    """Atomically hold the requested cabins and create a pending booking.

    Important safety rules:
    1. The same idempotency key cannot expose another user's booking.
    2. The sailing row and cabin inventory rows are locked before claiming them.
    3. All selected cabins are locked in deterministic order to reduce deadlocks.
    4. Partner bookings use the exact same inventory rows as direct bookings.
    """
    # FastAPI authentication/partner dependencies may already have executed a
    # query on this session, which starts SQLAlchemy's implicit transaction.
    # Therefore this service intentionally participates in the caller's
    # transaction instead of opening a second ``session.begin()`` block.
    # The endpoint commits after the service succeeds and rolls back on error.
    # This keeps the inventory hold atomic without triggering:
    # ``InvalidRequestError: A transaction is already begun on this Session``.
    # Idempotency is scoped to the authenticated traveler.
    existing = await session.scalar(
        select(Booking).where(
            Booking.idempotency_key == idem_key,
            Booking.user_id == user.id,
        )
    )
    if existing:
        return existing

    try:
        sailing_id = uuid.UUID(data.sailing_id)
        cabin_ids = [uuid.UUID(item.cabin_id) for item in data.cabins]
    except (ValueError, AttributeError) as exc:
        raise AppError(
            "VALIDATION_ERROR",
            "Invalid sailing or cabin identifier.",
            422,
        ) from exc

    # Lock the sailing before checking its booking window.
    sailing = await session.scalar(
        select(Sailing).where(Sailing.id == sailing_id).with_for_update()
    )
    now = datetime.now(timezone.utc)

    if (
        not sailing
        or sailing.status != SailingStatus.open
        or sailing.booking_closes_at <= now
    ):
        raise AppError(
            "SAILING_CLOSED",
            "This sailing is no longer open for booking.",
            409,
        )

    cruise = await session.scalar(
        select(Cruise).where(Cruise.id == sailing.cruise_id)
    )
    if (
        not cruise
        or cruise.deleted_at is not None
        or cruise.approval_status != ApprovalStatus.approved
        or cruise.status != CruiseStatus.published
    ):
        raise AppError(
            "CRUISE_UNAVAILABLE",
            "This cruise is not approved and bookable.",
            409,
        )

    # A confirmed ticket must always contain a real FROM and TO port.
    # Cruise configuration therefore cannot leave either route endpoint empty.
    if not cruise.embark_port_id or not cruise.disembark_port_id:
        raise AppError(
            "CRUISE_ROUTE_INCOMPLETE",
            "This cruise is missing its departure or arrival port. Please choose another sailing.",
            409,
        )

    # Partner websites must be active, connected, and explicitly allowed
    # to sell this cruise before they can create a hold.
    if channel == BookingChannel.partner:
        if (
            partner is None
            or partner.status != PartnerStatus.active
            or partner.integration_status != IntegrationStatus.connected
        ):
            raise AppError("FORBIDDEN", "Partner integration is inactive.", 403)

        exposure_conditions = [
            PartnerCruiseExposure.partner_id == partner.id,
            PartnerCruiseExposure.cruise_id == cruise.id,
            PartnerCruiseExposure.enabled.is_(True),
        ]
        if partner_website_id is not None:
            exposure_conditions.append(
                PartnerCruiseExposure.partner_website_id == partner_website_id
            )
        else:
            exposure_conditions.append(
                PartnerCruiseExposure.partner_website_id.is_(None)
            )

        exposed = await session.scalar(
            select(PartnerCruiseExposure.id).where(*exposure_conditions)
        )
        if not exposed:
            raise AppError("FORBIDDEN", "Cruise is not exposed to this partner.", 403)

    if len(set(cabin_ids)) != len(cabin_ids):
        raise AppError(
            "VALIDATION_ERROR",
            "A cabin cannot be selected twice.",
            422,
        )

    # This is the central inventory lock. Both direct and partner channels
    # eventually claim these same CabinInventory rows.
    inventory_rows = await get_locked_inventory(session, sailing.id, cabin_ids)
    if len(inventory_rows) != len(cabin_ids):
        raise AppError(
            "NOT_FOUND",
            "One or more selected cabins were not found.",
            404,
        )

    cabins = {
        cabin.id: cabin
        for cabin in (
            await session.scalars(select(Cabin).where(Cabin.id.in_(cabin_ids)))
        ).all()
    }
    if len(cabins) != len(cabin_ids):
        raise AppError(
            "NOT_FOUND",
            "One or more selected cabins were not found.",
            404,
        )

    physical_type_ids = {cabin.cabin_type_id for cabin in cabins.values()}
    physical_types = {
        cabin_type.id: cabin_type
        for cabin_type in (
            await session.scalars(
                select(CabinType).where(CabinType.id.in_(physical_type_ids))
            )
        ).all()
    }

    occupancy_by_cabin = {
        uuid.UUID(item.cabin_id): item.occupancy for item in data.cabins
    }

    # Validate every locked inventory row before changing any of them.
    for inventory in inventory_rows:
        cabin = cabins[inventory.cabin_id]
        occupancy = occupancy_by_cabin[inventory.cabin_id]

        # An old hold can safely be released when its expiration has passed.
        if (
            inventory.status == InventoryStatus.held
            and inventory.hold_expires_at
            and inventory.hold_expires_at <= now
        ):
            inventory.status = InventoryStatus.available
            inventory.held_by_user_id = None
            inventory.hold_expires_at = None
            inventory.booking_id = None

        claimable = inventory.status == InventoryStatus.available or (
            inventory.status == InventoryStatus.held
            and inventory.held_by_user_id == user.id
        )
        if not claimable:
            raise AppError(
                "CABIN_UNAVAILABLE",
                f"Cabin {cabin.cabin_number} is no longer available.",
                409,
                {"cabin_number": cabin.cabin_number},
            )

        if occupancy > cabin.max_occupancy:
            raise AppError(
                "VALIDATION_ERROR",
                f"Cabin {cabin.cabin_number} allows at most {cabin.max_occupancy} guests.",
                422,
            )

        physical_type = physical_types.get(cabin.cabin_type_id)
        if physical_type and occupancy > physical_type.max_occupancy:
            raise AppError(
                "VALIDATION_ERROR",
                f"Cabin type {physical_type.name} allows at most {physical_type.max_occupancy} guests.",
                422,
            )

    prices = [row.price_cents for row in inventory_rows]
    extra_prices = [
        physical_types[cabins[row.cabin_id].cabin_type_id].price_per_extra_guest_cents
        for row in inventory_rows
    ]
    occupancies = [occupancy_by_cabin[row.cabin_id] for row in inventory_rows]

    subtotal, tax, total = calculate_price(
        prices,
        extra_prices,
        occupancies,
        sailing.port_fee_per_guest_cents,
    )
    expires = now + timedelta(minutes=settings.CABIN_HOLD_MINUTES)

    booking = Booking(
        booking_reference=booking_ref(),
        user_id=user.id,
        sailing_id=sailing.id,
        status=BookingStatus.pending_payment,
        guest_count=sum(occupancies),
        subtotal_cents=subtotal,
        tax_cents=tax,
        total_cents=total,
        currency="USD",
        hold_expires_at=expires,
        idempotency_key=idem_key,
        channel=channel,
        partner_id=(
            partner.id if channel == BookingChannel.partner and partner else None
        ),
        customer_name=getattr(data, "customer_name", None),
        customer_email=getattr(data, "customer_email", None),
        customer_phone=getattr(data, "customer_phone", None),
    )
    session.add(booking)
    await session.flush()

    for inventory in inventory_rows:
        inventory.status = InventoryStatus.held
        inventory.held_by_user_id = user.id
        inventory.hold_expires_at = expires
        # Associating the hold with the booking immediately makes expiry
        # and webhook recovery deterministic.
        inventory.booking_id = booking.id
        inventory.version += 1

        session.add(
            BookingCabin(
                booking_id=booking.id,
                cabin_inventory_id=inventory.id,
                cabin_id=inventory.cabin_id,
                occupancy=occupancy_by_cabin[inventory.cabin_id],
                price_cents=inventory.price_cents,
            )
        )

    for guest in data.guests:
        guest_cabin = uuid.UUID(guest.cabin_id)
        if guest_cabin not in cabins:
            raise AppError(
                "VALIDATION_ERROR",
                "Guest references a cabin that was not selected.",
                422,
            )

        session.add(
            BookingGuest(
                booking_id=booking.id,
                cabin_id=guest_cabin,
                full_name=guest.full_name.strip(),
                date_of_birth=guest.date_of_birth,
                gender=guest.gender,
                nationality=guest.nationality,
                passport_number=guest.passport_number,
                is_lead_guest=guest.is_lead_guest,
            )
        )

    return booking
