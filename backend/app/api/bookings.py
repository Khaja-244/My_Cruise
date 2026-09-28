"""Traveler booking endpoints.

Routes stay intentionally thin: validation and inventory rules live in
`booking_service.py`, while this module translates HTTP requests to service
calls and formats responses for the frontend.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session
from app.core.deps import get_current_user, idempotency_key
from app.core.exceptions import AppError
from app.models import (
    Booking,
    BookingCabin,
    BookingGuest,
    BookingStatus,
    Cabin,
    CancellationRequest,
    CancellationStatus,
    Cruise,
    RefundPolicy,
    RefundPolicyRule,
    Sailing,
    User,
    UserRole,
    NotificationType,
)
from app.schemas.booking import BookingOut, CancelIn, HoldIn, RefundPreview
from app.services.booking_service import hold_booking
from app.services.notification_service import notify
from app.services.rate_limit_service import check_rate_limit

router = APIRouter(tags=["Bookings"])


def booking_to_response(booking: Booking) -> BookingOut:
    """Convert the SQLAlchemy booking model to the small public response."""
    return BookingOut(
        reference=booking.booking_reference,
        status=booking.status.value,
        sailing_id=str(booking.sailing_id),
        guest_count=booking.guest_count,
        subtotal_cents=booking.subtotal_cents,
        tax_cents=booking.tax_cents,
        total_cents=booking.total_cents,
        currency=booking.currency,
        hold_expires_at=(
            booking.hold_expires_at.isoformat()
            if booking.hold_expires_at
            else None
        ),
    )


@router.post("/bookings/hold", response_model=BookingOut)
async def hold(
    data: HoldIn,
    user=Depends(get_current_user),
    idem=Depends(idempotency_key),
    session=Depends(get_session),
):
    """Create a temporary cabin hold before payment."""
    await check_rate_limit(session, f"booking-hold:user:{user.id}", 10, 60)

    try:
        booking = await hold_booking(session, user, data, idem)
        await session.commit()
        return booking_to_response(booking)
    except IntegrityError:
        # A retry can reach the unique idempotency constraint. If the same
        # authenticated user already created the booking, return it safely.
        await session.rollback()
        existing = await session.scalar(
            select(Booking).where(
                Booking.idempotency_key == idem,
                Booking.user_id == user.id,
            )
        )
        if existing:
            return booking_to_response(existing)

        raise AppError(
            "DUPLICATE_REQUEST",
            "The booking request could not be safely repeated.",
            409,
        )
    except AppError:
        await session.rollback()
        raise


@router.get("/bookings")
async def my_bookings(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Return the authenticated traveler's bookings with simple pagination."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    statement = select(Booking).where(Booking.user_id == user.id)
    if status:
        statement = statement.where(Booking.status == status)

    total = await session.scalar(
        select(func.count()).select_from(statement.subquery())
    )
    rows = (
        await session.scalars(
            statement
            .order_by(Booking.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    sailing_ids = {booking.sailing_id for booking in rows}
    sailings = {}
    if sailing_ids:
        sailings = {
            sailing.id: sailing
            for sailing in (
                await session.scalars(
                    select(Sailing).where(Sailing.id.in_(sailing_ids))
                )
            ).all()
        }

    cruise_ids = {sailing.cruise_id for sailing in sailings.values()}
    cruises = {}
    if cruise_ids:
        cruises = {
            cruise.id: cruise
            for cruise in (
                await session.scalars(
                    select(Cruise).where(Cruise.id.in_(cruise_ids))
                )
            ).all()
        }

    items = []
    for booking in rows:
        item = booking_to_response(booking).model_dump()
        sailing = sailings.get(booking.sailing_id)
        cruise = cruises.get(sailing.cruise_id) if sailing else None
        item["sailing_name"] = (
            f"{cruise.name} — {sailing.departure_date}"
            if cruise and sailing
            else str(booking.sailing_id)
        )
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/bookings/{reference}")
async def booking(
    reference: str,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Return one booking with its cabins and guests."""
    booking_row = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.user_id == user.id,
        )
    )
    if not booking_row:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    cabins = (
        await session.scalars(
            select(BookingCabin).where(BookingCabin.booking_id == booking_row.id)
        )
    ).all()
    guests = (
        await session.scalars(
            select(BookingGuest).where(BookingGuest.booking_id == booking_row.id)
        )
    ).all()

    cabin_ids = [cabin.cabin_id for cabin in cabins]
    cabin_rows = (
        await session.scalars(select(Cabin).where(Cabin.id.in_(cabin_ids)))
    ).all() if cabin_ids else []
    cabin_numbers = {cabin.id: cabin.cabin_number for cabin in cabin_rows}

    return {
        **booking_to_response(booking_row).model_dump(),
        "cabins": [
            {
                "cabin_id": str(cabin.cabin_id),
                "cabin_number": cabin_numbers.get(cabin.cabin_id),
                "occupancy": cabin.occupancy,
                "price_cents": cabin.price_cents,
            }
            for cabin in cabins
        ],
        "guests": [
            {
                "cabin_id": str(guest.cabin_id),
                "full_name": guest.full_name,
                "date_of_birth": guest.date_of_birth,
                "gender": guest.gender,
                "nationality": guest.nationality,
                "passport_number": guest.passport_number,
                "is_lead_guest": guest.is_lead_guest,
            }
            for guest in guests
        ],
    }


@router.post("/bookings/{reference}/cancel-request")
async def cancel(
    reference: str,
    data: CancelIn,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Create a cancellation request for a confirmed booking."""
    booking_row = await session.scalar(
        select(Booking)
        .where(
            Booking.booking_reference == reference,
            Booking.user_id == user.id,
        )
        .with_for_update()
    )
    if not booking_row or booking_row.status != BookingStatus.confirmed:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "Only confirmed bookings can be cancelled.",
            409,
        )

    sailing = await session.get(Sailing, booking_row.sailing_id)
    days_before_departure = (sailing.departure_date - date.today()).days
    if days_before_departure < 0:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "This sailing has already departed.",
            409,
        )

    existing = await session.scalar(
        select(CancellationRequest).where(
            CancellationRequest.booking_id == booking_row.id,
            CancellationRequest.status == CancellationStatus.pending,
        )
    )
    if existing:
        raise AppError(
            "DUPLICATE_REQUEST",
            "A cancellation request is already pending.",
            409,
        )

    cruise = await session.get(Cruise, sailing.cruise_id)
    policy = (
        await session.get(RefundPolicy, cruise.refund_policy_id)
        if cruise.refund_policy_id
        else await session.scalar(
            select(RefundPolicy).where(
                RefundPolicy.is_default.is_(True),
                RefundPolicy.is_active.is_(True),
            )
        )
    )
    if not policy:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "No active refund policy is configured.",
            409,
        )

    rules = (
        await session.scalars(
            select(RefundPolicyRule).where(
                RefundPolicyRule.policy_id == policy.id
            )
        )
    ).all()
    rule = next(
        (
            item
            for item in rules
            if days_before_departure >= item.min_days_before_departure
            and (
                item.max_days_before_departure is None
                or days_before_departure <= item.max_days_before_departure
            )
        ),
        None,
    )
    if not rule:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "No refund policy rule applies.",
            409,
        )

    refund = max(
        0,
        int(
            (
                Decimal(booking_row.total_cents)
                * Decimal(rule.refund_percent)
                / Decimal(100)
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        - rule.flat_fee_cents,
    )

    policy_snapshot = {
        "policy": policy.name,
        "min_days_before_departure": rule.min_days_before_departure,
        "max_days_before_departure": rule.max_days_before_departure,
        "refund_percent": float(rule.refund_percent),
        "flat_fee_cents": rule.flat_fee_cents,
    }

    cancellation = CancellationRequest(
        booking_id=booking_row.id,
        requested_by=user.id,
        reason=data.reason,
        status=CancellationStatus.pending,
        policy_snapshot=policy_snapshot,
        calculated_refund_cents=refund,
    )
    booking_row.status = BookingStatus.cancellation_requested
    session.add(cancellation)
    await session.flush()

    # Notify every active admin that a new cancellation needs review.
    admins = (
        await session.scalars(
            select(User).where(
                User.role == UserRole.admin,
                User.is_active.is_(True),
            )
        )
    ).all()
    for admin in admins:
        await notify(
            session,
            admin.id,
            NotificationType.cancellation_requested,
            "New cancellation request",
            f"Booking {booking_row.booking_reference} has a new cancellation request.",
            {
                "booking_reference": booking_row.booking_reference,
                "cancellation_request": str(cancellation.id),
            },
        )

    await session.commit()
    return {
        "message": "Cancellation request submitted.",
        "calculated_refund_cents": refund,
    }


@router.get("/bookings/{reference}/refund-preview", response_model=RefundPreview)
async def preview(
    reference: str,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Preview the refund amount without creating a cancellation request."""
    booking_row = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.user_id == user.id,
        )
    )
    if not booking_row:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    sailing = await session.get(Sailing, booking_row.sailing_id)
    days_before_departure = (sailing.departure_date - date.today()).days
    cruise = await session.get(Cruise, sailing.cruise_id)

    policy = (
        await session.get(RefundPolicy, cruise.refund_policy_id)
        if cruise.refund_policy_id
        else await session.scalar(
            select(RefundPolicy).where(
                RefundPolicy.is_default.is_(True),
                RefundPolicy.is_active.is_(True),
            )
        )
    )
    if not policy:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "No active refund policy is configured.",
            409,
        )

    rules = (
        await session.scalars(
            select(RefundPolicyRule).where(RefundPolicyRule.policy_id == policy.id)
        )
    ).all()
    rule = next(
        (
            item
            for item in rules
            if days_before_departure >= item.min_days_before_departure
            and (
                item.max_days_before_departure is None
                or days_before_departure <= item.max_days_before_departure
            )
        ),
        None,
    )
    if not rule:
        raise AppError(
            "REFUND_NOT_ALLOWED",
            "No refund policy rule applies.",
            409,
        )

    refund = max(
        0,
        int(
            (
                Decimal(booking_row.total_cents)
                * Decimal(rule.refund_percent)
                / Decimal(100)
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        - rule.flat_fee_cents,
    )

    return RefundPreview(
        booking_reference=reference,
        total_cents=booking_row.total_cents,
        refund_cents=refund,
        refund_percent=float(rule.refund_percent),
        flat_fee_cents=rule.flat_fee_cents,
        days_before_departure=days_before_departure,
    )


@router.get("/bookings/{reference}/ticket")
async def ticket(
    reference: str,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Return the e-ticket PDF for a confirmed/refunded booking."""
    booking_row = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == reference,
            Booking.user_id == user.id,
        )
    )
    if not booking_row:
        raise AppError("NOT_FOUND", "Booking not found.", 404)

    allowed_statuses = {
        BookingStatus.confirmed,
        BookingStatus.refunded,
        BookingStatus.partially_refunded,
    }
    if booking_row.status not in allowed_statuses:
        raise AppError(
            "PAYMENT_FAILED",
            "A ticket is available after booking confirmation.",
            409,
        )

    from app.services.ticket_service import ticket_pdf

    # Always return the PDF directly from the API. Redirecting the browser to
    # object storage can produce a blank tab when the storage endpoint does not
    # expose browser CORS headers. The same PDF is still stored for email and
    # future server-side use.
    guests = (
        await session.scalars(
            select(BookingGuest).where(BookingGuest.booking_id == booking_row.id)
        )
    ).all()
    cabins = (
        await session.scalars(
            select(BookingCabin).where(BookingCabin.booking_id == booking_row.id)
        )
    ).all()
    sailing = await session.get(Sailing, booking_row.sailing_id)
    cruise = await session.get(Cruise, sailing.cruise_id)

    from app.models import Port, Ship

    ship = await session.get(Ship, cruise.ship_id)
    embark = await session.get(Port, cruise.embark_port_id)
    disembark = await session.get(Port, cruise.disembark_port_id)

    pdf = await ticket_pdf(
        booking_row,
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
            "Content-Disposition": f'inline; filename="my_cruise-{reference}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
