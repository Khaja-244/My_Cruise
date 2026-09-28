from datetime import datetime, timezone
import asyncio
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import AppError
from app.models import Refund, RefundStatus, Payment

async def issue_refund(session: AsyncSession, refund: Refund, booking_reference: str):
    if refund.stripe_refund_id:
        return refund
    if not settings.STRIPE_SECRET_KEY:
        refund.status = RefundStatus.failed; refund.failure_reason = 'Stripe is not configured.'
        await session.commit(); raise AppError('PAYMENT_FAILED','Stripe is not configured.',503)
    payment = await session.get(Payment, refund.payment_id)
    if not payment: raise AppError('NOT_FOUND','Payment record not found.',404)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        result = await asyncio.to_thread(stripe.Refund.create, payment_intent=payment.stripe_payment_intent_id, amount=refund.amount_cents, idempotency_key=f'refund_{refund.cancellation_request_id}')
        refund.stripe_refund_id = result.id; refund.status = RefundStatus.processing
        await session.commit()
    except Exception as exc:
        # Keep the refund retryable. The scheduler will retry transient Stripe
        # failures rather than leaving a customer permanently stuck in FAILED.
        refund.status = RefundStatus.pending
        refund.failure_reason = str(exc)[:500]
        await session.commit()
        raise
    return refund
