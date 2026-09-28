"""Partner website booking endpoints.

Partner bookings intentionally reuse the same booking service as direct
traveler bookings. That is the key rule that keeps one central cabin inventory
from being double-booked across different sales channels.
"""

import asyncio
from datetime import datetime, timezone
import uuid

import stripe
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.exceptions import AppError
from app.core.partner_auth import require_partner_api_key
from app.models import (
    Booking,
    BookingCabin,
    BookingChannel,
    BookingGuest,
    BookingStatus,
    Cabin,
    CancellationRequest,
    CancellationStatus,
    Cruise,
    NotificationType,
    Partner,
    Payment,
    PaymentStatus,
    Port,
    Sailing,
    Ship,
    User,
    UserRole,
)
from app.schemas.booking import PaymentIntentOut
from app.schemas.partner import PartnerBookingCabin, PartnerBookingRequest
from app.services.booking_service import hold_booking
from app.services.notification_service import notify
from app.services.partner_validation import exposed_sailing
from app.services.ticket_service import ticket_pdf

router = APIRouter(prefix="/partner-api", tags=["Partner API"])


async def _build_booking_payload(data: PartnerBookingRequest, session: AsyncSession):
    """Normalize old and new partner booking payloads into one format."""
    selected = list(data.cabins)

    # Older integrations may send cabin_ids instead of explicit occupancies.
    # We keep supporting that contract while still validating total capacity.
    if not selected and data.cabin_ids:
        unique_ids = list(dict.fromkeys(data.cabin_ids))
        if len(unique_ids) != len(data.cabin_ids):
            raise AppError(
                "VALIDATION_ERROR",
                "A cabin cannot be selected twice.",
                422,
            )

        cabin_ids = [uuid.UUID(cabin_id) for cabin_id in unique_ids]
        cabin_rows = (
            await session.scalars(select(Cabin).where(Cabin.id.in_(cabin_ids)))
        ).all()
        capacity_by_id = {str(cabin.id): cabin.max_occupancy for cabin in cabin_rows}

        remaining_guests = data.guest_count
        selected = []

        for cabin_id in unique_ids:
            if remaining_guests <= 0:
                break

            capacity = capacity_by_id.get(cabin_id, 0)
            occupancy = min(capacity, remaining_guests)
            if occupancy <= 0:
                raise AppError(
                    "VALIDATION_ERROR",
                    "Selected cabin capacity is invalid.",
                    422,
                )

            selected.append(
                PartnerBookingCabin(cabin_id=cabin_id, occupancy=occupancy)
            )
            remaining_guests -= occupancy

        if remaining_guests:
            raise AppError(
                "VALIDATION_ERROR",
                "Selected cabins cannot accommodate guest_count.",
                422,
            )

    if not selected:
        raise AppError("VALIDATION_ERROR", "At least one cabin is required.", 422)

    if sum(item.occupancy for item in selected) != data.guest_count:
        raise AppError(
            "VALIDATION_ERROR",
            "Cabin occupancy total must equal guest_count.",
            422,
        )

    if len(data.guests) != data.guest_count:
        raise AppError(
            "VALIDATION_ERROR",
            "guest_count must equal the number of guest manifest entries.",
            422,
        )

    occupancy_by_cabin = {item.cabin_id: item.occupancy for item in selected}
    guest_counts = {cabin_id: 0 for cabin_id in occupancy_by_cabin}

    for guest in data.guests:
        if guest.cabin_id not in guest_counts:
            raise AppError(
                "VALIDATION_ERROR",
                "Guest references a cabin that was not selected.",
                422,
            )
        guest_counts[guest.cabin_id] += 1

    for cabin_id, occupancy in occupancy_by_cabin.items():
        if guest_counts[cabin_id] != occupancy:
            raise AppError(
                "VALIDATION_ERROR",
                f"Occupancy for cabin {cabin_id} does not match the guest manifest.",
                422,
            )

    # SimpleNamespace lets the shared booking service receive the same shape
    # as the direct traveler booking endpoint without duplicating business rules.
    from types import SimpleNamespace

    return SimpleNamespace(
        sailing_id=data.sailing_id,
        cabins=[
            SimpleNamespace(
                cabin_id=item.cabin_id,
                occupancy=item.occupancy,
            )
            for item in selected
        ],
        guests=[SimpleNamespace(**guest.model_dump()) for guest in data.guests],
        customer_name=data.customer_name,
        customer_email=str(data.customer_email),
        customer_phone=data.customer_phone,
    )


@router.post("/bookings")
async def partner_create_booking(
    data: PartnerBookingRequest,
    request: Request,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    """Create a temporary partner booking hold against central inventory."""
    await exposed_sailing(
        data.sailing_id,
        partner,
        session,
        request.state.partner_website_id,
    )

    if not idempotency_key or len(idempotency_key) > 255:
        raise AppError(
            "VALIDATION_ERROR",
            "Idempotency-Key header is required and must be <=255 characters.",
            422,
        )

    partner_user = await session.scalar(
        select(User).where(
            User.id == partner.user_id,
            User.role == UserRole.partner,
        )
    )
    if not partner_user:
        raise AppError(
            "FORBIDDEN",
            "Partner booking account is not configured.",
            403,
        )

    payload = await _build_booking_payload(data, session)

    try:
        booking = await hold_booking(
            session=session,
            user=partner_user,
            data=payload,
            idem_key=idempotency_key,
            channel=BookingChannel.partner,
            partner=partner,
            partner_website_id=request.state.partner_website_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return {
        "booking_reference": booking.booking_reference,
        "status": booking.status.value,
        "total_cents": booking.total_cents,
        "commission_cents": booking.commission_cents,
        "currency": booking.currency,
        "customer": {
            "name": booking.customer_name,
            "email": booking.customer_email,
            "phone": booking.customer_phone,
        },
    }


@router.get("/bookings/{reference}")
async def partner_booking_status(
    reference: str,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Return a booking belonging to the authenticated partner."""
    booking = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.partner_id == partner.id,
            Booking.channel == BookingChannel.partner,
        )
    )
    if not booking:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    guests = (
        await session.scalars(
            select(BookingGuest).where(BookingGuest.booking_id == booking.id)
        )
    ).all()

    return {
        "booking_reference": booking.booking_reference,
        "status": booking.status.value,
        "total_cents": booking.total_cents,
        "commission_cents": booking.commission_cents,
        "currency": booking.currency,
        "customer": {
            "name": booking.customer_name,
            "email": booking.customer_email,
            "phone": booking.customer_phone,
        },
        "guests": [
            {
                "full_name": guest.full_name,
                "cabin_id": str(guest.cabin_id),
                "date_of_birth": guest.date_of_birth,
                "nationality": guest.nationality,
                "is_lead_guest": guest.is_lead_guest,
            }
            for guest in guests
        ],
    }


@router.post("/bookings/{reference}/payment-intent")
async def partner_payment_intent(
    reference: str,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Create or reuse a Stripe PaymentIntent for a partner booking."""
    booking = await session.scalar(
        select(Booking)
        .where(
            Booking.booking_reference == reference,
            Booking.partner_id == partner.id,
            Booking.channel == BookingChannel.partner,
        )
        .with_for_update()
    )
    if not booking:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    if booking.status != BookingStatus.pending_payment:
        raise AppError(
            "PAYMENT_FAILED",
            "Booking is not awaiting payment.",
            409,
        )

    if booking.hold_expires_at and booking.hold_expires_at <= datetime.now(timezone.utc):
        raise AppError(
            "HOLD_EXPIRED",
            "The cabin hold has expired. Please create a new booking.",
            409,
        )

    if not settings.STRIPE_SECRET_KEY:
        raise AppError(
            "PAYMENT_FAILED",
            "Stripe is not configured. Add STRIPE_SECRET_KEY to .env.",
            503,
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    existing_payment = await session.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .order_by(Payment.created_at.desc())
    )

    if existing_payment and existing_payment.status in (
        PaymentStatus.requires_payment,
        PaymentStatus.processing,
    ):
        try:
            payment_intent = await asyncio.to_thread(
                stripe.PaymentIntent.retrieve,
                existing_payment.stripe_payment_intent_id,
            )
            if payment_intent.client_secret:
                return PaymentIntentOut(client_secret=payment_intent.client_secret)
        except Exception:
            # If Stripe no longer has the old intent, create a fresh one below.
            pass

    payment_intent = await asyncio.to_thread(
        stripe.PaymentIntent.create,
        amount=booking.total_cents,
        currency="usd",
        metadata={
            "booking_reference": booking.booking_reference,
            "channel": "partner",
            "partner_id": str(partner.id),
        },
        payment_method_types=["card"],
        idempotency_key=f"payment_{booking.id}",
    )

    session.add(
        Payment(
            booking_id=booking.id,
            stripe_payment_intent_id=payment_intent.id,
            amount_cents=booking.total_cents,
            currency="USD",
            status=PaymentStatus.requires_payment,
            raw_payload={
                "id": payment_intent.id,
                "status": payment_intent.status,
            },
        )
    )
    await session.commit()

    return PaymentIntentOut(client_secret=payment_intent.client_secret)


@router.get("/bookings/{reference}/payment-status")
async def partner_payment_status(
    reference: str,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Return the latest booking/payment state for partner polling."""
    booking = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.partner_id == partner.id,
            Booking.channel == BookingChannel.partner,
        )
    )
    if not booking:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    payment = await session.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .order_by(Payment.created_at.desc())
    )

    return {
        "booking_status": booking.status.value,
        "payment_status": payment.status.value if payment else None,
    }


@router.get("/bookings/{reference}/ticket")
async def partner_ticket(
    reference: str,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Generate the confirmed partner booking's PDF ticket."""
    booking = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.partner_id == partner.id,
            Booking.channel == BookingChannel.partner,
        )
    )
    if not booking:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    allowed_statuses = {
        BookingStatus.confirmed,
        BookingStatus.refunded,
        BookingStatus.partially_refunded,
    }
    if booking.status not in allowed_statuses:
        raise AppError(
            "PAYMENT_FAILED",
            "A ticket is available after booking confirmation.",
            409,
        )

    guests = (
        await session.scalars(
            select(BookingGuest).where(BookingGuest.booking_id == booking.id)
        )
    ).all()
    cabins = (
        await session.scalars(
            select(BookingCabin).where(BookingCabin.booking_id == booking.id)
        )
    ).all()

    sailing = await session.get(Sailing, booking.sailing_id)
    cruise = await session.get(Cruise, sailing.cruise_id) if sailing else None
    ship = await session.get(Ship, cruise.ship_id) if cruise else None
    embark = await session.get(Port, cruise.embark_port_id) if cruise else None
    disembark = await session.get(Port, cruise.disembark_port_id) if cruise else None

    pdf = await ticket_pdf(
        booking,
        guests,
        cabins,
        cruise,
        ship,
        sailing,
        embark,
        disembark,
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{booking.booking_reference}.pdf"'
            )
        },
    )


@router.post("/bookings/{reference}/cancel-request")
async def partner_cancel_request(
    reference: str,
    data: dict,
    partner: Partner = Depends(require_partner_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Create a partner cancellation request for admin review."""
    booking = await session.scalar(
        select(Booking)
        .where(
            Booking.booking_reference == reference,
            Booking.partner_id == partner.id,
            Booking.channel == BookingChannel.partner,
        )
        .with_for_update()
    )
    if not booking:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    allowed_statuses = {
        BookingStatus.confirmed,
        BookingStatus.pending_payment,
    }
    if booking.status not in allowed_statuses:
        raise AppError(
            "VALIDATION_ERROR",
            "Booking cannot be cancelled in its current state.",
            409,
        )

    existing = await session.scalar(
        select(CancellationRequest).where(
            CancellationRequest.booking_id == booking.id,
            CancellationRequest.status == CancellationStatus.pending,
        )
    )
    if existing:
        return {"id": str(existing.id), "status": existing.status.value}

    reason = str(data.get("reason", "Partner cancellation request")).strip()
    reason = reason or "Partner cancellation request"

    cancellation = CancellationRequest(
        booking_id=booking.id,
        requested_by=partner.user_id,
        reason=reason,
    )
    session.add(cancellation)
    booking.status = BookingStatus.cancellation_requested
    await session.flush()

    admins = (
        await session.scalars(
            select(User).where(
                User.role == UserRole.admin,
                User.is_active.is_(True),
            )
        )
    ).all()

    for admin_user in admins:
        await notify(
            session,
            admin_user.id,
            NotificationType.cancellation_requested,
            "New partner cancellation request",
            f"Partner requested cancellation for booking {booking.booking_reference}.",
            {
                "booking_reference": booking.booking_reference,
                "cancellation_request": str(cancellation.id),
                "partner_id": str(partner.id),
            },
        )

    await session.commit()
    return {"id": str(cancellation.id), "status": cancellation.status.value}
