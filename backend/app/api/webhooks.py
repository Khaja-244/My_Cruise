import asyncio
from datetime import datetime, timezone, timedelta
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import *
from app.services.notification_service import notify
from app.services.booking_service import calculate_commission_cents
from app.services.email_service import send_email, wrap_email, refund_email

router = APIRouter(tags=['Stripe Webhooks'])
log = logging.getLogger(__name__)

@router.post('/webhooks/stripe')
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    # Read raw bytes first: Stripe signatures must be verified against the
    # unmodified request body.
    body = await request.body()
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, 'Stripe webhook is not configured.')
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(
            body, request.headers.get('stripe-signature', ''), settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        raise HTTPException(400, 'Invalid Stripe signature') from exc

    async with SessionLocal() as session:
        try:
            session.add(WebhookEvent(
                stripe_event_id=event['id'],
                event_type=event['type'],
                payload=dict(event),
                received_at=datetime.now(timezone.utc),
            ))
            await session.flush()
            # Commit the idempotency ledger before business processing so a
            # later rollback cannot erase the event record.
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event['id']))
            if existing and existing.processed_at is not None:
                return {'received': True, 'duplicate': True}
            # A previous attempt recorded an error but did not complete the
            # business transaction. Re-enter the handler and retry it safely.

        obj = event['data']['object']
        ref = (obj.get('metadata') or {}).get('booking_reference')
        # Refund objects normally do not carry the booking metadata. Resolve
        # them through the stored Refund row before requiring a booking reference.
        if event['type'] == 'refund.updated':
            refund_for_event = await session.scalar(select(Refund).where(Refund.stripe_refund_id == obj.get('id')))
            if refund_for_event:
                booking_for_refund = await session.get(Booking, refund_for_event.booking_id)
                ref = booking_for_refund.booking_reference if booking_for_refund else None
        if event['type'] == 'charge.refunded' and not ref:
            payment_for_charge = await session.scalar(select(Payment).where(Payment.stripe_charge_id == obj.get('id')))
            if payment_for_charge:
                booking_for_charge = await session.get(Booking, payment_for_charge.booking_id)
                ref = booking_for_charge.booking_reference if booking_for_charge else None
        if not ref:
            ledger = await session.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event['id']))
            ledger.processed_at = datetime.now(timezone.utc)
            await session.commit()
            return {'received': True}

        booking = await session.scalar(
            select(Booking).where(Booking.booking_reference == ref).with_for_update()
        )
        if not booking:
            await session.commit()
            return {'received': True}

        payment = await session.scalar(
            select(Payment).where(Payment.booking_id == booking.id)
            .order_by(Payment.created_at.desc()).with_for_update()
        )
        now = datetime.now(timezone.utc)

        try:
            event_type = event['type']
            if event_type == 'payment_intent.succeeded':
                amount = int(obj.get('amount_received') or obj.get('amount') or 0)
                currency = str(obj.get('currency') or '').upper()
                if amount != booking.total_cents or currency != booking.currency:
                    raise ValueError('Stripe amount/currency does not match the booking.')

                inventory = (await session.scalars(
                    select(CabinInventory)
                    .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
                    .where(BookingCabin.booking_id == booking.id)
                    .order_by(CabinInventory.cabin_id)
                    .with_for_update()
                )).all()
                expired = booking.status == BookingStatus.expired or (
                    booking.hold_expires_at is not None and booking.hold_expires_at <= now
                )
                all_claimed = len(inventory) > 0 and all(
                    r.status == InventoryStatus.held and r.held_by_user_id == booking.user_id
                    for r in inventory
                )
                if expired or not all_claimed:
                    # The payment succeeded after the reservation became invalid.
                    # Do not keep the money or create a false confirmed booking.
                    if payment:
                        payment.status = PaymentStatus.succeeded
                    try:
                        await asyncio.to_thread(
                            stripe.Refund.create,
                            payment_intent=obj['id'],
                            amount=amount,
                            idempotency_key=f'late_success_{booking.id}',
                        )
                    except Exception:
                        log.exception('Late-payment refund failed for %s', booking.booking_reference)
                    if booking.status == BookingStatus.pending_payment:
                        booking.status = BookingStatus.expired
                else:
                    booking.status = BookingStatus.confirmed
                    booking.confirmed_at = now
                    booking.hold_expires_at = None
                    # Commission is frozen at confirmation time from the cruise
                    # configuration, so later commission edits cannot rewrite history.
                    cruise = await session.scalar(select(Cruise).where(Cruise.id == (await session.get(Sailing, booking.sailing_id)).cruise_id))
                    booking.commission_cents = calculate_commission_cents(booking, cruise) if cruise else 0
                    if payment:
                        payment.status = PaymentStatus.succeeded
                        payment.stripe_charge_id = obj.get('latest_charge') or payment.stripe_charge_id
                    for row in inventory:
                        row.status = InventoryStatus.booked
                        row.hold_expires_at = None
                        row.version += 1
                    # Direct bookings have a user account, while partner sales
                    # may represent a customer who has no my_cruise login.
                    if booking.channel == BookingChannel.direct:
                        await notify(session, booking.user_id, NotificationType.booking_confirmed,
                                      'Booking confirmed', f'Your cruise booking {booking.booking_reference} is confirmed.',
                                      {'booking_reference': booking.booking_reference})
                    # Partner customers receive the confirmation and PDF e-ticket
                    # from generate_ticket_after_commit, addressed to customer_email.
                    ticket_booking_id = booking.id

            elif event_type == 'payment_intent.payment_failed':
                booking.status = BookingStatus.payment_failed
                if payment:
                    payment.status = PaymentStatus.failed
                    payment.failure_reason = (obj.get('last_payment_error') or {}).get('message')
                if booking.channel == BookingChannel.direct:
                    await notify(session, booking.user_id, NotificationType.payment_failed,
                                  'Payment failed', f'Payment failed for booking {booking.booking_reference}.',
                                  {'booking_reference': booking.booking_reference})
                elif booking.customer_email:
                    background_tasks.add_task(
                        send_email,
                        booking.customer_email,
                        f'Payment failed — {booking.booking_reference}',
                        wrap_email(
                            'Payment failed',
                            f'<p>Payment for booking <b>{booking.booking_reference}</b> could not be completed.</p>'
                            f'<p>Your cabin hold has been released. You can start a new booking when you are ready.</p>',
                            preheader=f'Payment failed for booking {booking.booking_reference}',
                        ),
                    )
                # A failed/cancelled payment must release the inventory immediately.
                # Otherwise the booking is no longer payable but the cabin can remain
                # stuck in HELD until a scheduler run (or forever after status changes).
                inventory = (await session.scalars(
                    select(CabinInventory)
                    .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
                    .where(BookingCabin.booking_id == booking.id)
                    .with_for_update()
                )).all()
                for row in inventory:
                    if row.status == InventoryStatus.held:
                        row.status = InventoryStatus.available
                        row.held_by_user_id = None
                        row.hold_expires_at = None
                        row.booking_id = None
                        row.version += 1
                booking.hold_expires_at = None

            elif event_type == 'payment_intent.processing':
                if payment:
                    payment.status = PaymentStatus.processing

            elif event_type == 'payment_intent.requires_action':
                if payment:
                    payment.status = PaymentStatus.processing
                if booking.status == BookingStatus.pending_payment:
                    booking.hold_expires_at = max(
                        booking.hold_expires_at or now,
                        now + timedelta(minutes=5),
                    )
                    inventory = (await session.scalars(
                        select(CabinInventory)
                        .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
                        .where(BookingCabin.booking_id == booking.id)
                        .with_for_update()
                    )).all()
                    for row in inventory:
                        if row.status == InventoryStatus.held and row.held_by_user_id == booking.user_id:
                            row.hold_expires_at = booking.hold_expires_at

            elif event_type == 'payment_intent.canceled':
                if payment:
                    payment.status = PaymentStatus.cancelled
                if booking.status == BookingStatus.pending_payment:
                    booking.status = BookingStatus.payment_failed
                inventory = (await session.scalars(
                    select(CabinInventory)
                    .join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id)
                    .where(BookingCabin.booking_id == booking.id)
                    .with_for_update()
                )).all()
                for row in inventory:
                    if row.status == InventoryStatus.held:
                        row.status = InventoryStatus.available
                        row.held_by_user_id = None
                        row.hold_expires_at = None
                        row.booking_id = None
                        row.version += 1
                booking.hold_expires_at = None

            elif event_type in ('charge.refunded', 'refund.updated'):
                stripe_refund_id = obj.get('id')
                refund = None
                if event_type == 'refund.updated':
                    refund = await session.scalar(select(Refund).where(Refund.stripe_refund_id == stripe_refund_id).with_for_update())
                else:
                    # charge.refunded contains a Charge, not a Refund. Match the
                    # payment by charge id and use the pending refund for that booking.
                    charge_payment = await session.scalar(select(Payment).where(Payment.stripe_charge_id == stripe_refund_id).with_for_update())
                    if charge_payment:
                        refund = await session.scalar(select(Refund).where(Refund.payment_id == charge_payment.id).order_by(Refund.id.desc()).with_for_update())
                if refund:
                    if event_type == 'charge.refunded' and obj.get('amount_refunded') is not None:
                        refund.amount_cents = int(obj.get('amount_refunded') or refund.amount_cents)
                    stripe_refund_status = obj.get('status')
                    if stripe_refund_status == 'succeeded' or stripe_refund_status is None:
                        refund.status = RefundStatus.succeeded
                        refund.processed_at = now
                    elif stripe_refund_status in ('pending',):
                        refund.status = RefundStatus.processing
                        refund.processed_at = None
                    else:
                        refund.status = RefundStatus.failed
                        refund.processed_at = now
                    if refund.status == RefundStatus.succeeded:
                        booking.status = (
                            BookingStatus.refunded
                            if refund.amount_cents >= booking.total_cents
                            else BookingStatus.partially_refunded
                        )
                        if booking.channel == BookingChannel.direct:
                            await notify(session, booking.user_id, NotificationType.refund_completed,
                                          'Refund completed', f'Your refund for booking {booking.booking_reference} has been completed.',
                                          {'booking_reference': booking.booking_reference, 'refund_cents': refund.amount_cents})
                    elif refund.status == RefundStatus.failed and booking.channel == BookingChannel.direct:
                        await notify(session, booking.user_id, NotificationType.refund_failed,
                                      'Refund requires attention',
                                      f'We could not complete the refund for booking {booking.booking_reference}. The payment workflow will retry it.',
                                      {'booking_reference': booking.booking_reference, 'refund_cents': refund.amount_cents})

            ledger = await session.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event['id']))
            ledger.processed_at = now
            await session.commit()
            if event_type == 'payment_intent.succeeded' and 'ticket_booking_id' in locals() and booking.status == BookingStatus.confirmed:
                from app.services.ticket_service import generate_ticket_after_commit
                background_tasks.add_task(generate_ticket_after_commit, ticket_booking_id)
                log.info('Queued e-ticket PDF generation and email for booking %s', booking.booking_reference)
            if event_type in ('charge.refunded','refund.updated') and 'refund' in locals() and refund:
                user = await session.get(User, booking.user_id)
                recipient_email = booking.customer_email or (user.email if user else None)
                if recipient_email:
                    if refund.status == RefundStatus.succeeded:
                        subject, html = refund_email(booking.booking_reference, refund.amount_cents)
                    elif refund.status == RefundStatus.failed:
                        subject, html = refund_email(booking.booking_reference, refund.amount_cents, failed=True, reason=refund.failure_reason)
                    else:
                        subject, html = None, None
                    if subject and html:
                        background_tasks.add_task(send_email, recipient_email, subject, html)

        except Exception as exc:
            # The event is already recorded. Persist the error and return 200 so
            # Stripe does not create an uncontrolled retry storm. The periodic
            # job/ops workflow can retry the failed business side effect.
            await session.rollback()
            async with SessionLocal() as recovery:
                ledger = await recovery.scalar(select(WebhookEvent).where(WebhookEvent.stripe_event_id == event['id']).with_for_update())
                if ledger:
                    ledger.error = str(exc)[:1000]
                    await recovery.commit()
            log.exception('Stripe event %s processing failed', event['id'])
            return {'received': True, 'processed': False}
    return {'received': True}
