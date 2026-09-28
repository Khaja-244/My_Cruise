"""Server-side Stripe payment reconciliation used when a webhook is delayed.

The Stripe webhook remains the normal source of truth. This service is a safe
fallback for local development and for short webhook delivery delays: the
server asks Stripe for the PaymentIntent status and confirms the booking only
when the paid amount/currency and the locked cabin inventory still match.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booking,
    BookingCabin,
    BookingChannel,
    BookingStatus,
    CabinInventory,
    Cruise,
    InventoryStatus,
    Payment,
    PaymentStatus,
    Sailing,
    NotificationType,
)
from app.services.booking_service import calculate_commission_cents
from app.services.notification_service import notify


async def reconcile_succeeded_payment(session: AsyncSession, booking: Booking, stripe_intent, background_tasks=None) -> bool:
    """Confirm a pending booking after Stripe reports a successful PaymentIntent."""
    if booking.status == BookingStatus.confirmed:
        return True

    if booking.status != BookingStatus.pending_payment:
        return False

    amount = int(getattr(stripe_intent, "amount_received", 0) or getattr(stripe_intent, "amount", 0) or 0)
    currency = str(getattr(stripe_intent, "currency", "") or "").upper()
    if amount != booking.total_cents or currency != booking.currency:
        return False

    payment = await session.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .order_by(Payment.created_at.desc())
        .with_for_update()
    )
    if not payment or payment.stripe_payment_intent_id != stripe_intent.id:
        return False

    inventory = (await session.scalars(
        select(CabinInventory)
        .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
        .where(BookingCabin.booking_id == booking.id)
        .order_by(CabinInventory.cabin_id)
        .with_for_update()
    )).all()

    now = datetime.now(timezone.utc)
    expired = booking.hold_expires_at is not None and booking.hold_expires_at <= now
    all_claimed = bool(inventory) and all(
        row.status == InventoryStatus.held and row.held_by_user_id == booking.user_id
        for row in inventory
    )
    if expired or not all_claimed:
        return False

    sailing = await session.get(Sailing, booking.sailing_id)
    cruise = await session.get(Cruise, sailing.cruise_id) if sailing else None

    booking.status = BookingStatus.confirmed
    booking.confirmed_at = now
    booking.hold_expires_at = None
    booking.commission_cents = calculate_commission_cents(booking, cruise) if cruise else 0
    payment.status = PaymentStatus.succeeded
    payment.stripe_charge_id = getattr(stripe_intent, "latest_charge", None) or payment.stripe_charge_id

    for row in inventory:
        row.status = InventoryStatus.booked
        row.hold_expires_at = None
        row.version += 1

    if booking.channel == BookingChannel.direct:
        await notify(
            session,
            booking.user_id,
            NotificationType.booking_confirmed,
            "Booking confirmed",
            f"Your cruise booking {booking.booking_reference} is confirmed.",
            {"booking_reference": booking.booking_reference},
        )

    await session.commit()

    if background_tasks is not None:
        from app.services.ticket_service import generate_ticket_after_commit
        background_tasks.add_task(generate_ticket_after_commit, booking.id)

    return True
