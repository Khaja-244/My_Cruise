"""Stripe payment endpoints used by the traveler checkout."""

import asyncio

import stripe
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.models import Booking, Payment, PaymentStatus, BookingStatus
from app.schemas.booking import PaymentIntentIn, PaymentIntentOut
from app.services.rate_limit_service import check_rate_limit


router = APIRouter(tags=["Payments"])


def build_payment_intent_options(booking: Booking) -> dict:
    """Return the Stripe options for one cruise booking.

    Phase 1 intentionally supports card payments only. Keeping one payment
    method makes local testing predictable and avoids displaying Stripe
    methods that are not enabled on the test account.
    """
    return {
        "amount": booking.total_cents,
        "currency": booking.currency.lower(),
        "payment_method_types": ["card"],
        "metadata": {
            "booking_reference": booking.booking_reference,
        },
    }


async def get_existing_client_secret(payment: Payment) -> str | None:
    """Return the client secret when an existing Stripe payment is reusable."""
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        payment_intent = await asyncio.to_thread(
            stripe.PaymentIntent.retrieve,
            payment.stripe_payment_intent_id,
        )

        # A PaymentIntent can be confirmed again while it is waiting for a
        # payment method, processing, or customer action.
        reusable_statuses = {
            "requires_payment_method",
            "requires_confirmation",
            "requires_action",
            "processing",
        }
        if payment_intent.status in reusable_statuses:
            return payment_intent.client_secret
    except stripe.error.StripeError:
        # If the old Stripe object cannot be reused, the caller will create a
        # fresh PaymentIntent below.
        return None

    return None


@router.post("/payments/intent", response_model=PaymentIntentOut)
async def create_payment_intent(
    data: PaymentIntentIn,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Create or reuse the Stripe PaymentIntent for a pending booking."""
    await check_rate_limit(
        session,
        f"payment-intent:user:{user.id}",
        10,
        60,
    )

    booking = await session.scalar(
        select(Booking)
        .where(
            Booking.booking_reference == data.booking_reference,
            Booking.user_id == user.id,
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

    from datetime import datetime, timezone

    if booking.hold_expires_at and booking.hold_expires_at <= datetime.now(timezone.utc):
        raise AppError(
            "HOLD_EXPIRED",
            "The cabin hold has expired. Please select a cabin again.",
            409,
        )

    if not settings.STRIPE_SECRET_KEY:
        raise AppError(
            "PAYMENT_FAILED",
            "Stripe is not configured. Add STRIPE_SECRET_KEY to backend/.env.",
            503,
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Reuse an unfinished PaymentIntent instead of creating duplicates when
    # the traveler refreshes the payment step.
    existing_payment = await session.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .order_by(Payment.created_at.desc())
    )

    if existing_payment and existing_payment.status in {
        PaymentStatus.requires_payment,
        PaymentStatus.processing,
    }:
        client_secret = await get_existing_client_secret(existing_payment)
        if client_secret:
            return PaymentIntentOut(client_secret=client_secret)

    try:
        payment_intent = await asyncio.to_thread(
            stripe.PaymentIntent.create,
            **build_payment_intent_options(booking),
            idempotency_key=f"payment_{booking.id}",
        )
    except stripe.error.StripeError as exc:
        message = getattr(exc, "user_message", None) or "Stripe could not start the payment."
        raise AppError("PAYMENT_FAILED", message, 502) from exc

    session.add(
        Payment(
            booking_id=booking.id,
            stripe_payment_intent_id=payment_intent.id,
            amount_cents=booking.total_cents,
            currency=booking.currency,
            status=PaymentStatus.requires_payment,
            raw_payload={
                "id": payment_intent.id,
                "status": payment_intent.status,
            },
        )
    )
    await session.commit()

    return PaymentIntentOut(client_secret=payment_intent.client_secret)


@router.get("/payments/{booking_reference}/status")
async def get_payment_status(
    booking_reference: str,
    user=Depends(get_current_user),
    session=Depends(get_session),
):
    """Return the latest booking/payment status for the logged-in traveler."""
    booking = await session.scalar(
        select(Booking).where(
            Booking.booking_reference == booking_reference,
            Booking.user_id == user.id,
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
