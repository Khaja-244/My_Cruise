import asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func, text
from app.core.database import SessionLocal
from app.models import *
from app.services.notification_service import dispatch_unsent_notifications, notify

# APScheduler is intentionally in-process per the brief. PostgreSQL advisory
# locks ensure only one Uvicorn/Gunicorn worker performs each periodic job.
EXPIRY_LOCK = 74001
REFUND_LOCK = 74002

async def expire():
    async with SessionLocal() as s:
        async with s.begin():
            await s.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': EXPIRY_LOCK})
            now = datetime.now(timezone.utc)
            bookings = (await s.scalars(
                select(Booking)
                .where(Booking.status == BookingStatus.pending_payment, Booking.hold_expires_at <= func.now())
                .order_by(Booking.hold_expires_at)
                .with_for_update()
            )).all()
            for booking in bookings:
                inventory = (await s.scalars(
                    select(CabinInventory)
                    .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
                    .where(BookingCabin.booking_id == booking.id)
                    .with_for_update()
                )).all()
                payment = await s.scalar(
                    select(Payment)
                    .where(Payment.booking_id == booking.id)
                    .order_by(Payment.created_at.desc())
                )

                # Cancel the intent before making the cabin sellable again.
                # A later succeeded webhook is handled as a late payment.
                if payment and payment.status in (PaymentStatus.requires_payment, PaymentStatus.processing):
                    try:
                        import stripe
                        from app.core.config import settings
                        if settings.STRIPE_SECRET_KEY:
                            stripe.api_key = settings.STRIPE_SECRET_KEY
                            pi = await asyncio.to_thread(stripe.PaymentIntent.retrieve, payment.stripe_payment_intent_id)
                            if pi.status not in ('succeeded', 'canceled'):
                                await asyncio.to_thread(stripe.PaymentIntent.cancel, pi.id)
                            if pi.status != 'succeeded':
                                payment.status = PaymentStatus.cancelled
                    except Exception:
                        payment.failure_reason = 'Hold expired; Stripe cancellation will be retried.'

                for row in inventory:
                    if row.status == InventoryStatus.held and row.held_by_user_id == booking.user_id:
                        row.status = InventoryStatus.available
                        row.held_by_user_id = None
                        row.hold_expires_at = None
                        row.booking_id = None
                        row.version += 1
                booking.status = BookingStatus.expired
                await notify(
                    s, booking.user_id, NotificationType.payment_failed,
                    'Payment window expired',
                    f'Your hold for booking {booking.booking_reference} expired before payment was completed.',
                    {'booking_reference': booking.booking_reference},
                )
        await dispatch_unsent_notifications(s)

async def process_pending_refunds():
    from app.services.refund_service import issue_refund
    async with SessionLocal() as s:
        await s.execute(text('SELECT pg_advisory_lock(:key)'), {'key': REFUND_LOCK})
        try:
            rows = (await s.scalars(
                select(Refund).where(Refund.status == RefundStatus.pending).order_by(Refund.id).limit(50)
            )).all()
            # issue_refund commits internally; a session-level advisory lock
            # remains held across those commits, preventing another worker from
            # entering this refund batch concurrently.
            for refund in rows:
                try:
                    await issue_refund(s, refund, '')
                except Exception:
                    await s.rollback()
        finally:
            await s.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': REFUND_LOCK})


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(expire, 'interval', seconds=60, id='expire-holds', replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(process_pending_refunds, 'interval', seconds=60, id='pending-refunds', replace_existing=True, max_instances=1, coalesce=True)
    async def dispatch_notifications():
        async with SessionLocal() as session:
            await dispatch_unsent_notifications(session)
    scheduler.add_job(dispatch_notifications, 'interval', seconds=15, id='notification-dispatch', replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler
