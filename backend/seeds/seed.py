"""Idempotent starter dataset for local and reviewer environments.

Run from the backend directory:
    python -m seeds.seed

The seed accounts are for local development and review only.
"""
import asyncio
import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Amenity, ApprovalStatus, Booking, BookingCabin, BookingChannel, BookingGuest,
    BookingStatus, Cabin, CabinInventory, CabinType, CabinTypeAmenity,
    CancellationRequest, CancellationStatus, CommissionType, Cruise, CruiseImage,
    CruiseItinerary, CruiseStatus, Deck, IntegrationStatus, InventoryStatus,
    Notification, NotificationType, Partner, PartnerApiKey, PartnerApplication,
    PartnerApplicationStatus, PartnerCruiseExposure, PartnerStatus, PartnerWebsite,
    Payment, PaymentStatus, Port, Refund, RefundPolicy, RefundPolicyRule,
    RefundStatus, Sailing, SailingStatus, SavedCruise, Ship, User, UserRole,
)
from app.core.partner_auth import generate_partner_api_key


DEMO_PASSWORD = "DemoTraveler@12345"
DEMO_PARTNER_PASSWORD = "DemoPartner@12345"
DEMO_ADMIN_PASSWORD = "DemoAdmin@12345"
DEMO_PARTNER_API_KEY = "mc_demo_partner_api_2026"

PORTS = [
    ("Miami Cruise Port", "Miami", "USA", "MIA", "America/New_York"),
    ("Barcelona Cruise Port", "Barcelona", "Spain", "BCN", "Europe/Madrid"),
    ("Civitavecchia Port", "Rome", "Italy", "ROM", "Europe/Rome"),
    ("Piraeus Port", "Athens", "Greece", "ATH", "Europe/Athens"),
    ("Lisbon Cruise Terminal", "Lisbon", "Portugal", "LIS", "Europe/Lisbon"),
    ("Dubai Harbour", "Dubai", "UAE", "DXB", "Asia/Dubai"),
]

AMENITIES = [
    ("Wi-Fi", "wifi", "Connectivity"),
    ("Ocean View", "view", "Cabin"),
    ("Private Balcony", "balcony", "Cabin"),
    ("Room Service", "service", "Service"),
    ("Mini Bar", "drink", "Cabin"),
    ("Accessible Cabin", "accessibility", "Accessibility"),
]

PLATFORM_CRUISES = [
    ("demo-sunset-caribbean", "caribbean-sunset-escape", "Caribbean Sunset Escape", 7),
    ("demo-mediterranean-discovery", "mediterranean-discovery", "Mediterranean Discovery", 8),
    ("demo-gulf-horizon", "gulf-horizon-voyage", "Gulf Horizon Voyage", 6),
    ("greek-isles-escape", "greek-isles-escape", "Greek Isles Escape", 7),
    ("dubai-arabian-sea-journey", "dubai-arabian-sea-journey", "Dubai & Arabian Sea Journey", 8),
]

PARTNER_CRUISES = [
    ("demo-partner-pending", "oceanic-pending-submission", "Oceanic Coast Explorer — Pending Review", "pending"),
    ("demo-partner-approved", "azure-coast-escape", "Azure Coast Escape", "approved"),
    ("demo-partner-rejected", "atlantic-breeze-voyage", "Atlantic Breeze Voyage", "rejected"),
]


async def get_or_create(session, model, filters, values):
    obj = await session.scalar(select(model).filter_by(**filters))
    if obj is None:
        obj = model(**values)
        session.add(obj)
        await session.flush()
    return obj


async def ensure_user(session, email, name, password, role):
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            full_name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_email_verified=True,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.flush()
    else:
        user.full_name = name
        user.role = role
        user.is_active = True
        user.is_email_verified = True
        user.must_change_password = False
    return user


async def ensure_ship(session, name, owner_type="platform", partner_id=None, legacy_name=None):
    names = [name] if legacy_name is None else [name, legacy_name]
    ship = await session.scalar(select(Ship).where(Ship.name.in_(names)))
    if ship is None:
        ship = Ship(
            name=name,
            operator_name="My Cruise Fleet",
            deck_count=3,
            description="Passenger ship used by the my_cruise catalog.",
            owner_type=owner_type,
            partner_id=partner_id,
            is_active=True,
        )
        session.add(ship)
        await session.flush()
    else:
        ship.name = name
        ship.owner_type = owner_type
        ship.partner_id = partner_id
        ship.deck_count = 3
        ship.is_active = True

    for deck_number in range(1, 4):
        await get_or_create(
            session,
            Deck,
            {"ship_id": ship.id, "deck_number": deck_number},
            {"ship_id": ship.id, "deck_number": deck_number, "name": f"Deck {deck_number}"},
        )
    return ship


async def ensure_policy(session):
    policy = await session.scalar(select(RefundPolicy).where(RefundPolicy.name.in_(["Standard Flexible Refund Policy", "Standard Flexible Refund Policy"])))
    if policy is None:
        policy = RefundPolicy(
            name="Standard Flexible Refund Policy",
            description="Flexible cancellation policy with clear refund tiers.",
            is_default=True,
            is_active=True,
        )
        session.add(policy)
        await session.flush()
    else:
        policy.name = "Standard Flexible Refund Policy"
        policy.description = "Flexible cancellation policy with clear refund tiers."
        policy.is_default = True
        policy.is_active = True

    existing = (
        await session.scalars(
            select(RefundPolicyRule)
            .where(RefundPolicyRule.policy_id == policy.id)
            .order_by(RefundPolicyRule.min_days_before_departure)
        )
    ).all()
    if not existing:
        for minimum, maximum, percent, fee in [
            (30, None, Decimal("90.00"), 2500),
            (15, 29, Decimal("60.00"), 2500),
            (7, 14, Decimal("30.00"), 2500),
            (0, 6, Decimal("0.00"), 0),
        ]:
            session.add(
                RefundPolicyRule(
                    policy_id=policy.id,
                    min_days_before_departure=minimum,
                    max_days_before_departure=maximum,
                    refund_percent=percent,
                    flat_fee_cents=fee,
                )
            )
    return policy


async def ensure_cruise_structure(session, cruise, ship, ports, amenities, policy):
    # Every catalog cruise has three cabin types and each type has amenities.
    types = []
    type_specs = [
        ("Interior", 4, 89900),
        ("Ocean View", 4, 109900),
        ("Balcony", 4, 129900),
    ]
    for index, (name, occupancy, price) in enumerate(type_specs):
        cabin_type = await session.scalar(
            select(CabinType).where(CabinType.cruise_id == cruise.id, CabinType.name == name)
        )
        if cabin_type is None:
            cabin_type = CabinType(
                cruise_id=cruise.id,
                name=name,
                description=f"Comfortable {name.lower()} room with practical amenities for a relaxed cruise journey.",
                max_occupancy=occupancy,
                base_price_cents=price,
                price_per_extra_guest_cents=25000,
            )
            session.add(cabin_type)
            await session.flush()
        types.append(cabin_type)

        # Attach two generic amenities to every cabin type without duplicating
        # the composite primary-key rows on a later seed run.
        for amenity in amenities[:2]:
            exists = await session.scalar(
                select(CabinTypeAmenity).where(
                    CabinTypeAmenity.cabin_type_id == cabin_type.id,
                    CabinTypeAmenity.amenity_id == amenity.id,
                )
            )
            if exists is None:
                session.add(
                    CabinTypeAmenity(
                        cabin_type_id=cabin_type.id,
                        amenity_id=amenity.id,
                    )
                )
    # At least three decks already exist on every ship.
    decks = (
        await session.scalars(
            select(Deck).where(Deck.ship_id == ship.id).order_by(Deck.deck_number)
        )
    ).all()

    # Six physical cabins per deck is enough to make availability realistic while
    # keeping the reviewer database compact.
    for deck in decks:
        for slot in range(1, 7):
            cabin_number = f"{deck.deck_number}{slot:02d}"
            cabin = await session.scalar(
                select(Cabin).where(Cabin.ship_id == ship.id, Cabin.cabin_number == cabin_number)
            )
            if cabin is None:
                cabin_type = types[(slot - 1) % len(types)]
                cabin = Cabin(
                    ship_id=ship.id,
                    deck_id=deck.id,
                    cabin_type_id=cabin_type.id,
                    cabin_number=cabin_number,
                    max_occupancy=cabin_type.max_occupancy,
                    is_active=True,
                )
                session.add(cabin)

    await session.flush()

    # Build the itinerary for each sailing. The API contract remains the same.
    existing_itinerary = await session.scalar(
        select(CruiseItinerary).where(CruiseItinerary.cruise_id == cruise.id)
    )
    if existing_itinerary is None:
        for day_number in range(1, cruise.sailing_days + 1):
            port = None if day_number in (1, cruise.sailing_days) else ports[(day_number - 1) % len(ports)]
            session.add(
                CruiseItinerary(
                    cruise_id=cruise.id,
                    day_number=day_number,
                    port_id=port.id if port else None,
                    description="At sea" if port is None else f"Port visit: {port.name}",
                )
            )

    cruise_images = {
        "caribbean-sunset-escape": "https://images.pexels.com/photos/1079004/pexels-photo-1079004.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "mediterranean-discovery": "https://images.pexels.com/photos/1079004/pexels-photo-1079004.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "gulf-horizon-voyage": "https://images.pexels.com/photos/5579172/pexels-photo-5579172.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "greek-isles-escape": "https://images.pexels.com/photos/33880090/pexels-photo-33880090.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "dubai-arabian-sea-journey": "https://images.pexels.com/photos/13120671/pexels-photo-13120671.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "azure-coast-escape": "https://images.pexels.com/photos/1079004/pexels-photo-1079004.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "oceanic-pending-submission": "https://images.pexels.com/photos/33880090/pexels-photo-33880090.jpeg?auto=compress&cs=tinysrgb&w=1600",
        "atlantic-breeze-voyage": "https://images.pexels.com/photos/5579172/pexels-photo-5579172.jpeg?auto=compress&cs=tinysrgb&w=1600",
    }
    image_url = cruise_images.get(
        cruise.slug,
        "https://images.pexels.com/photos/1079004/pexels-photo-1079004.jpeg?auto=compress&cs=tinysrgb&w=1600",
    )
    image = await session.scalar(
        select(CruiseImage).where(CruiseImage.cruise_id == cruise.id, CruiseImage.is_cover.is_(True))
    )
    if image is None:
        session.add(
            CruiseImage(
                cruise_id=cruise.id,
                url=image_url,
                alt_text=f"{cruise.name} cruise ship",
                sort_order=0,
                is_cover=True,
            )
        )
    else:
        # Keep the catalog on curated real cruise imagery instead of placeholder images.
        image.url = image_url
        image.alt_text = f"{cruise.name} cruise ship"

    await session.flush()
    return types


async def ensure_sailing(session, cruise, departure_date):
    sailing = await session.scalar(
        select(Sailing).where(
            Sailing.cruise_id == cruise.id,
            Sailing.departure_date == departure_date,
        )
    )
    if sailing is None:
        sailing = Sailing(
            cruise_id=cruise.id,
            departure_date=departure_date,
            return_date=departure_date + timedelta(days=cruise.sailing_days),
            status=SailingStatus.open if cruise.status == CruiseStatus.published else SailingStatus.scheduled,
            booking_closes_at=datetime.combine(
                departure_date - timedelta(days=2),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ),
            port_fee_per_guest_cents=1500,
        )
        session.add(sailing)
        await session.flush()

    cruise_types = {
        item.id: item
        for item in (
            await session.scalars(select(CabinType).where(CabinType.cruise_id == cruise.id))
        ).all()
    }
    cabins = (
        await session.scalars(
            select(Cabin)
            .where(Cabin.ship_id == cruise.ship_id, Cabin.is_active.is_(True))
            .order_by(Cabin.cabin_number)
        )
    ).all()

    for cabin in cabins:
        # Each physical cabin belongs to one cabin type on the ship.
        cabin_type = cruise_types.get(cabin.cabin_type_id)
        if cabin_type is None:
            continue
        inventory = await session.scalar(
            select(CabinInventory).where(
                CabinInventory.sailing_id == sailing.id,
                CabinInventory.cabin_id == cabin.id,
            )
        )
        if inventory is None:
            session.add(
                CabinInventory(
                    sailing_id=sailing.id,
                    cabin_id=cabin.id,
                    price_cents=cabin_type.base_price_cents,
                    status=InventoryStatus.available,
                )
            )
    await session.flush()
    return sailing


async def ensure_payment(session, booking, status, suffix):
    payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id))
    if payment is None:
        payment = Payment(
            booking_id=booking.id,
            stripe_payment_intent_id=f"pi_demo_{suffix}",
            stripe_charge_id=f"ch_demo_{suffix}" if status == PaymentStatus.succeeded else None,
            amount_cents=booking.total_cents,
            currency="USD",
            status=status,
            raw_payload={"source": "starter-data", "purpose": "local review"},
        )
        session.add(payment)
        await session.flush()
    else:
        payment.status = status
    return payment


async def ensure_booking(
    session,
    reference,
    user,
    sailing,
    cabin,
    status,
    channel=BookingChannel.direct,
    partner=None,
    customer_name=None,
    customer_email=None,
    cancellation=None,
):
    booking = await session.scalar(select(Booking).where(Booking.booking_reference == reference))
    inventory = await session.scalar(
        select(CabinInventory).where(
            CabinInventory.sailing_id == sailing.id,
            CabinInventory.cabin_id == cabin.id,
        )
    )
    if inventory is None:
        raise RuntimeError(f"Missing inventory for seeded booking {reference}.")

    price = inventory.price_cents
    if booking is None:
        booking = Booking(
            booking_reference=reference,
            user_id=user.id,
            sailing_id=sailing.id,
            partner_id=partner.id if partner else None,
            channel=channel,
            status=status,
            guest_count=2,
            subtotal_cents=price,
            tax_cents=price // 10,
            total_cents=price + price // 10,
            currency="USD",
            customer_name=customer_name or user.full_name,
            customer_email=customer_email or user.email,
            customer_phone=user.phone,
            commission_cents=(price * 12 // 100) if partner else 0,
            idempotency_key=f"starter-{reference.lower()}",
            confirmed_at=datetime.now(timezone.utc) if status in {
                BookingStatus.confirmed,
                BookingStatus.cancellation_requested,
                BookingStatus.cancelled,
                BookingStatus.refunded,
            } else None,
        )
        session.add(booking)
        await session.flush()

        session.add(
            BookingCabin(
                booking_id=booking.id,
                cabin_inventory_id=inventory.id,
                cabin_id=cabin.id,
                occupancy=2,
                price_cents=price,
            )
        )
        session.add(
            BookingGuest(
                booking_id=booking.id,
                cabin_id=cabin.id,
                full_name=customer_name or user.full_name,
                date_of_birth=date(1990, 5, 20),
                nationality="United States",
                is_lead_guest=True,
            )
        )
        session.add(
            BookingGuest(
                booking_id=booking.id,
                cabin_id=cabin.id,
                full_name="Aarav Mehta",
                date_of_birth=date(1992, 8, 15),
                nationality="United States",
                is_lead_guest=False,
            )
        )
        await session.flush()

    booking.status = status
    booking.partner_id = partner.id if partner else None
    booking.channel = channel
    booking.commission_cents = (booking.subtotal_cents * 12 // 100) if partner else 0

    # The inventory state mirrors the booking state, as the real booking service does.
    if status in {BookingStatus.confirmed, BookingStatus.cancellation_requested}:
        inventory.status = InventoryStatus.booked
        inventory.booking_id = booking.id
        inventory.held_by_user_id = None
        inventory.hold_expires_at = None
    elif status in {BookingStatus.cancelled, BookingStatus.refunded, BookingStatus.partially_refunded}:
        inventory.status = InventoryStatus.available
        inventory.booking_id = None
        inventory.held_by_user_id = None
        inventory.hold_expires_at = None

    await session.flush()
    return booking, inventory


async def main():
    async with SessionLocal() as session:
        # ----- Users -----
        admin = await ensure_user(
            session, "admin123@mycruise.demo", "Demo Admin", DEMO_ADMIN_PASSWORD, UserRole.admin
        )
        travelers = []
        traveler_specs = [
            ("traveler123@mycruise.demo", "Aarav Mehta"),
            ("traveler456@mycruise.demo", "Priya Nair"),
            ("traveler789@mycruise.demo", "Rohan Kapoor"),
            ("traveler999@mycruise.demo", "Ananya Rao"),
        ]
        for email, name in traveler_specs:
            travelers.append(await ensure_user(session, email, name, DEMO_PASSWORD, UserRole.traveler))

        active_partner_user = await ensure_user(
            session,
            "partner123@mycruise.demo",
            "Oceanic Travel Partners",
            DEMO_PARTNER_PASSWORD,
            UserRole.partner,
        )
        pending_user = await ensure_user(
            session,
            "partnerpending123@mycruise.demo",
            "Blue Horizon Travel",
            DEMO_PARTNER_PASSWORD,
            UserRole.traveler,
        )
        rejected_user = await ensure_user(
            session,
            "partnerrejected123@mycruise.demo",
            "Seaside Voyager Travel",
            DEMO_PARTNER_PASSWORD,
            UserRole.traveler,
        )

        # ----- Ports / amenities / policy -----
        ports = []
        for name, city, country, code, tz in PORTS:
            ports.append(
                await get_or_create(
                    session,
                    Port,
                    {"code": code},
                    {
                        "name": name,
                        "city": city,
                        "country": country,
                        "code": code,
                        "timezone": tz,
                    },
                )
            )
        amenities = []
        for name, icon, category in AMENITIES:
            amenities.append(
                await get_or_create(
                    session,
                    Amenity,
                    {"name": name},
                    {"name": name, "icon_key": icon, "category": category},
                )
            )
        policy = await ensure_policy(session)

        # ----- Partners and applications -----
        active_partner = await get_or_create(
            session,
            Partner,
            {"email": "partner123@mycruise.demo"},
            {
                "user_id": active_partner_user.id,
                "business_name": "Oceanic Travel Partners",
                "contact_name": "Oceanic Travel Partners",
                "email": "partner123@mycruise.demo",
                "phone": "+1-555-0101",
                "status": PartnerStatus.active,
                "integration_status": IntegrationStatus.connected,
            },
        )
        active_partner.user_id = active_partner_user.id
        active_partner.business_name = "Oceanic Travel Partners"
        active_partner.contact_name = "Oceanic Travel Partners"
        active_partner.status = PartnerStatus.active
        active_partner.integration_status = IntegrationStatus.connected

        pending_partner = await get_or_create(
            session,
            Partner,
            {"email": "partnerpending123@mycruise.demo"},
            {
                "business_name": "Blue Horizon Travel",
                "contact_name": "Blue Horizon Travel",
                "email": "partnerpending123@mycruise.demo",
                "phone": "+1-555-0102",
                "status": PartnerStatus.pending,
                "integration_status": IntegrationStatus.suspended,
            },
        )
        pending_partner.business_name = "Blue Horizon Travel"
        pending_partner.contact_name = "Blue Horizon Travel"

        rejected_partner = await get_or_create(
            session,
            Partner,
            {"email": "partnerrejected123@mycruise.demo"},
            {
                "business_name": "Seaside Voyager Travel",
                "contact_name": "Seaside Voyager Travel",
                "email": "partnerrejected123@mycruise.demo",
                "phone": "+1-555-0103",
                "status": PartnerStatus.rejected,
                "integration_status": IntegrationStatus.suspended,
            },
        )

        rejected_partner.business_name = "Seaside Voyager Travel"
        rejected_partner.contact_name = "Seaside Voyager Travel"

        applications = [
            (
                "partner123@mycruise.demo",
                active_partner_user,
                "Oceanic Travel Partners",
                PartnerApplicationStatus.approved,
                "Partner application approved.",
            ),
            (
                "partnerpending123@mycruise.demo",
                pending_user,
                "Blue Horizon Travel",
                PartnerApplicationStatus.pending,
                None,
            ),
            (
                "partnerrejected123@mycruise.demo",
                rejected_user,
                "Seaside Voyager Travel",
                PartnerApplicationStatus.rejected,
                "Application did not meet the current partner requirements.",
            ),
        ]
        for email, applicant, business_name, status, reason in applications:
            app = await session.scalar(
                select(PartnerApplication).where(PartnerApplication.email == email)
            )
            if app is None:
                app = PartnerApplication(
                    applicant_user_id=applicant.id,
                    business_name=business_name,
                    contact_name=applicant.full_name,
                    email=email,
                    phone=applicant.phone,
                    status=status,
                    reviewer_id=admin.id if status != PartnerApplicationStatus.pending else None,
                    review_reason=reason,
                    reviewed_at=datetime.now(timezone.utc) if status != PartnerApplicationStatus.pending else None,
                )
                session.add(app)
            else:
                app.status = status
                app.reviewer_id = admin.id if status != PartnerApplicationStatus.pending else None
                app.review_reason = reason
        await session.flush()

        website = await session.scalar(
            select(PartnerWebsite).where(
                PartnerWebsite.partner_id == active_partner.id,
                PartnerWebsite.name.in_(["Oceanic Travel Website", "Oceanic Travel Website"]),
            )
        )
        if website is None:
            website = PartnerWebsite(
                partner_id=active_partner.id,
                name="Oceanic Travel Website",
                website_url="https://oceanic-travel.example",
                integration_status=IntegrationStatus.connected,
                last_connected_at=datetime.now(timezone.utc),
            )
            session.add(website)
        website.name = "Oceanic Travel Website"
        website.website_url = "https://oceanic-travel.example"
        website.integration_status = IntegrationStatus.connected

        raw_key = DEMO_PARTNER_API_KEY
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = await session.scalar(
            select(PartnerApiKey).where(PartnerApiKey.key_hash == digest)
        )
        if api_key is None:
            api_key = PartnerApiKey(
                partner_id=active_partner.id,
                key_hash=digest,
                key_prefix=raw_key[:16],
                active=True,
                rate_limit_per_minute=60,
            )
            session.add(api_key)
        else:
            api_key.active = True
        await session.flush()

        # ----- Ships -----
        platform_ships = []
        for index in range(1, 6):
            ship_names = [
                "Ocean Majesty",
                "Mediterranean Star",
                "Gulf Voyager",
                "Aegean Pearl",
                "Arabian Horizon",
            ]
            platform_ships.append(
                await ensure_ship(
                    session,
                    ship_names[index - 1],
                    "platform",
                    legacy_name=f"My Cruise Fleet Ship {index}",
                )
            )

        partner_ships = []
        for index in range(1, 4):
            partner_ships.append(
                await ensure_ship(
                    session,
                    f"Oceanic Partner Ship {index}",
                    "partner",
                    active_partner.id,
                    legacy_name=f"Oceanic Partner Ship {index}",
                )
            )

        # ----- Cruises -----
        cruises = {}
        for index, (legacy_slug, public_slug, name, sailing_days) in enumerate(PLATFORM_CRUISES):
            cruise = await session.scalar(select(Cruise).where(Cruise.slug.in_([legacy_slug, public_slug])))
            if cruise is None:
                cruise = Cruise(
                    name=name,
                    slug=public_slug,
                    description=f"{name} offers a carefully planned itinerary, comfortable passenger rooms and live room availability for every sailing.",
                    sailing_days=sailing_days,
                    ship_id=platform_ships[index].id,
                    embark_port_id=ports[index].id,
                    disembark_port_id=ports[index + 1].id,
                    status=CruiseStatus.published,
                    approval_status=ApprovalStatus.approved,
                    owner_type="platform",
                    is_featured=index < 2,
                    base_price_cents=89900 + index * 10000,
                    currency="USD",
                    created_by=admin.id,
                    refund_policy_id=policy.id,
                )
                session.add(cruise)
                await session.flush()
            else:
                cruise.slug = public_slug
                cruise.name = name
                cruise.status = CruiseStatus.published
                cruise.approval_status = ApprovalStatus.approved
                cruise.owner_type = "platform"
                cruise.partner_id = None
                cruise.is_featured = index < 2
                cruise.created_by = admin.id
                cruise.refund_policy_id = policy.id
            cruises[legacy_slug] = cruise
            types = await ensure_cruise_structure(
                session, cruise, platform_ships[index], ports, amenities, policy
            )
            departure = date.today() + timedelta(days=30 + index * 10)
            await ensure_sailing(session, cruise, departure)

        partner_status_map = {
            "pending": (ApprovalStatus.pending, CruiseStatus.draft),
            "approved": (ApprovalStatus.approved, CruiseStatus.published),
            "rejected": (ApprovalStatus.rejected, CruiseStatus.draft),
        }
        for index, (legacy_slug, public_slug, name, state) in enumerate(PARTNER_CRUISES):
            cruise = await session.scalar(select(Cruise).where(Cruise.slug.in_([legacy_slug, public_slug])))
            approval, status = partner_status_map[state]
            if cruise is None:
                cruise = Cruise(
                    name=name,
                    slug=public_slug,
                    description=f"{name} is available through the partner booking network after the required approval workflow.",
                    sailing_days=5 + index,
                    ship_id=partner_ships[index].id,
                    embark_port_id=ports[(index + 2) % len(ports)].id,
                    disembark_port_id=ports[(index + 3) % len(ports)].id,
                    status=status,
                    approval_status=approval,
                    owner_type="partner",
                    partner_id=active_partner.id,
                    is_featured=False,
                    base_price_cents=99900 + index * 5000,
                    currency="USD",
                    created_by=active_partner_user.id,
                    refund_policy_id=policy.id,
                    commission_type=CommissionType.percent,
                    commission_value=Decimal("12.50"),
                )
                session.add(cruise)
                await session.flush()
            else:
                cruise.slug = public_slug
                cruise.name = name
                cruise.status = status
                cruise.approval_status = approval
                cruise.owner_type = "partner"
                cruise.partner_id = active_partner.id
                cruise.commission_type = CommissionType.percent
                cruise.commission_value = Decimal("12.50")
                cruise.refund_policy_id = policy.id
            cruises[legacy_slug] = cruise
            await ensure_cruise_structure(
                session, cruise, partner_ships[index], ports, amenities, policy
            )
            departure = date.today() + timedelta(days=45 + index * 10)
            await ensure_sailing(session, cruise, departure)
            exposure = await session.scalar(
                select(PartnerCruiseExposure).where(
                    PartnerCruiseExposure.partner_id == active_partner.id,
                    PartnerCruiseExposure.cruise_id == cruise.id,
                )
            )
            if exposure is None:
                session.add(
                    PartnerCruiseExposure(
                        partner_id=active_partner.id,
                        cruise_id=cruise.id,
                        enabled=state == "approved",
                    )
                )
            else:
                exposure.enabled = state == "approved"

        await session.flush()

        # ----- Starter bookings -----
        # Use the first physical cabin on each relevant cruise's ship.
        async def first_cabin(slug):
            cruise = cruises[slug]
            return await session.scalar(
                select(Cabin)
                .where(Cabin.ship_id == cruise.ship_id, Cabin.is_active.is_(True))
                .order_by(Cabin.cabin_number)
            )

        # Keep an existing local database tidy when the seed script is run again.
        legacy_booking_references = {
            "MCDEMO001": "MC2026001",
            "MCDEMO002": "MC2026002",
            "MCDEMO003": "MC2026003",
            "MCDEMO004": "MC2026004",
        }
        for old_reference, new_reference in legacy_booking_references.items():
            existing_booking = await session.scalar(
                select(Booking).where(Booking.booking_reference == old_reference)
            )
            if existing_booking is not None:
                existing_booking.booking_reference = new_reference
                existing_booking.idempotency_key = f"starter-{new_reference.lower()}"

        confirmed_sailing = await session.scalar(
            select(Sailing).where(Sailing.cruise_id == cruises["demo-sunset-caribbean"].id)
        )
        refunded_sailing = await session.scalar(
            select(Sailing).where(Sailing.cruise_id == cruises["demo-mediterranean-discovery"].id)
        )
        cancellation_sailing = await session.scalar(
            select(Sailing).where(Sailing.cruise_id == cruises["demo-gulf-horizon"].id)
        )
        partner_sailing = await session.scalar(
            select(Sailing).where(Sailing.cruise_id == cruises["demo-partner-approved"].id)
        )

        confirmed_booking, _ = await ensure_booking(
            session,
            "MC2026001",
            travelers[0],
            confirmed_sailing,
            await first_cabin("demo-sunset-caribbean"),
            BookingStatus.confirmed,
        )
        await ensure_payment(session, confirmed_booking, PaymentStatus.succeeded, "confirmed_001")

        refunded_booking, refunded_inventory = await ensure_booking(
            session,
            "MC2026002",
            travelers[1],
            refunded_sailing,
            await first_cabin("demo-mediterranean-discovery"),
            BookingStatus.refunded,
        )
        refunded_payment = await ensure_payment(
            session, refunded_booking, PaymentStatus.succeeded, "refunded_002"
        )
        cancellation = await session.scalar(
            select(CancellationRequest).where(CancellationRequest.booking_id == refunded_booking.id)
        )
        if cancellation is None:
            cancellation = CancellationRequest(
                booking_id=refunded_booking.id,
                requested_by=travelers[1].id,
                reason="Traveler requested cancellation before departure.",
                status=CancellationStatus.approved,
                reviewed_by=admin.id,
                admin_note="Approved under the standard refund policy.",
                policy_snapshot={"name": policy.name, "refund_percent": 90, "flat_fee_cents": 2500},
                calculated_refund_cents=max(refunded_booking.total_cents * 90 // 100 - 2500, 0),
                final_refund_cents=max(refunded_booking.total_cents * 90 // 100 - 2500, 0),
                reviewed_at=datetime.now(timezone.utc),
            )
            session.add(cancellation)
            await session.flush()
        refund = await session.scalar(select(Refund).where(Refund.booking_id == refunded_booking.id))
        if refund is None:
            refund = Refund(
                booking_id=refunded_booking.id,
                cancellation_request_id=cancellation.id,
                payment_id=refunded_payment.id,
                stripe_refund_id="re_demo_refund_002",
                amount_cents=cancellation.final_refund_cents or 0,
                status=RefundStatus.succeeded,
                processed_at=datetime.now(timezone.utc),
            )
            session.add(refund)

        pending_booking, _ = await ensure_booking(
            session,
            "MC2026003",
            travelers[2],
            cancellation_sailing,
            await first_cabin("demo-gulf-horizon"),
            BookingStatus.cancellation_requested,
        )
        await ensure_payment(session, pending_booking, PaymentStatus.succeeded, "cancel_pending_003")
        pending_cancel = await session.scalar(
            select(CancellationRequest).where(CancellationRequest.booking_id == pending_booking.id)
        )
        if pending_cancel is None:
            pending_cancel = CancellationRequest(
                booking_id=pending_booking.id,
                requested_by=travelers[2].id,
                reason="Traveler requested cancellation before departure.",
                status=CancellationStatus.pending,
                policy_snapshot={"name": policy.name, "refund_percent": 90, "flat_fee_cents": 2500},
                calculated_refund_cents=max(pending_booking.total_cents * 90 // 100 - 2500, 0),
            )
            session.add(pending_cancel)

        partner_booking, _ = await ensure_booking(
            session,
            "MC2026004",
            active_partner_user,
            partner_sailing,
            await first_cabin("demo-partner-approved"),
            BookingStatus.confirmed,
            channel=BookingChannel.partner,
            partner=active_partner,
            customer_name="Partner Booking Customer",
            customer_email="partnercustomer123@mycruise.local",
        )
        await ensure_payment(session, partner_booking, PaymentStatus.succeeded, "partner_004")

        # Saved cruises for traveler 4.
        for cruise_slug in ("demo-sunset-caribbean", "demo-partner-approved"):
            cruise = cruises[cruise_slug]
            saved = await session.scalar(
                select(SavedCruise).where(
                    SavedCruise.user_id == travelers[3].id,
                    SavedCruise.cruise_id == cruise.id,
                )
            )
            if saved is None:
                session.add(SavedCruise(user_id=travelers[3].id, cruise_id=cruise.id))

        # Reviewer-visible notifications mirror the important workflow states.
        notification_specs = [
            (travelers[0], NotificationType.booking_confirmed, "Booking confirmed", "Your Caribbean Sunset Escape booking is confirmed."),
            (travelers[1], NotificationType.refund_completed, "Refund completed", "Your refund for MC2026002 has been completed."),
            (travelers[2], NotificationType.cancellation_requested, "Cancellation requested", "Your cancellation request is pending admin review."),
        ]
        for user, notification_type, title, body in notification_specs:
            exists = await session.scalar(
                select(Notification).where(
                    Notification.user_id == user.id,
                    Notification.type == notification_type,
                    Notification.title == title,
                )
            )
            if exists is None:
                session.add(
                    Notification(
                        user_id=user.id,
                        type=notification_type,
                        title=title,
                        body=body,
                        data={"source": "seed"},
                        sent_push=False,
                        sent_email=False,
                    )
                )

        await session.commit()

    print("\nStarter catalog seed complete.")
    print("Admin:    admin123@mycruise.demo / DemoAdmin@12345")
    print("Partner:  partner123@mycruise.demo / DemoPartner@12345")
    print("Travelers: traveler123@mycruise.demo .. traveler999@mycruise.demo / DemoTraveler@12345")
    print(f"Partner API key: {DEMO_PARTNER_API_KEY}")


if __name__ == "__main__":
    asyncio.run(main())
