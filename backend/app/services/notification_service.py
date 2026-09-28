import logging
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Notification, DeviceToken, User, NotificationType
from app.core.config import settings
from app.services.email_service import send_email, wrap_email

log = logging.getLogger(__name__)
_firebase_initialized = False

def _firebase_app():
    global _firebase_initialized
    if _firebase_initialized:
        return True
    if not settings.FIREBASE_CREDENTIALS_JSON:
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(settings.FIREBASE_CREDENTIALS_JSON))
        _firebase_initialized = True
        return True
    except Exception:
        log.exception("Firebase initialization failed")
        return False

async def notify(session: AsyncSession, user_id, type: NotificationType, title: str, body: str, data=None):
    """Persist the notification inside the caller's transaction. Dispatch happens after commit."""
    session.add(Notification(user_id=user_id, type=type, title=title, body=body, data=data or {}))

async def dispatch_unsent_notifications(session: AsyncSession, limit: int = 100):
    """Deliver durable notifications. Failed push/email delivery remains pending for retry."""
    rows = (await session.scalars(
        select(Notification).where((Notification.sent_push == False) | (Notification.sent_email == False)).order_by(Notification.created_at).limit(limit)
    )).all()
    if not rows:
        return

    firebase_ready = _firebase_app()
    messaging = None
    if firebase_ready:
        from firebase_admin import messaging as firebase_messaging
        messaging = firebase_messaging

    email_types = {
        NotificationType.booking_confirmed, NotificationType.booking_cancelled,
        NotificationType.refund_approved, NotificationType.refund_rejected,
        NotificationType.refund_completed, NotificationType.refund_failed, NotificationType.payment_failed,
        NotificationType.cancellation_requested,
    }
    for row in rows:
        push_success = not firebase_ready
        tokens = (await session.scalars(
            select(DeviceToken).where(DeviceToken.user_id == row.user_id, DeviceToken.is_active == True)
        )).all()
        if firebase_ready:
            push_success = False
            for token in tokens:
                try:
                    await asyncio.to_thread(messaging.send, messaging.Message(
                        notification=messaging.Notification(title=row.title, body=row.body),
                        data={str(k): str(v) for k, v in (row.data or {}).items()},
                        token=token.fcm_token,
                    ))
                    push_success = True
                except Exception as exc:
                    msg = str(exc)
                    if "UNREGISTERED" in msg or "INVALID_ARGUMENT" in msg:
                        token.is_active = False
                    log.warning("FCM delivery failed: %s", exc)

        # Transactional email is a second durable delivery channel. A missing SMTP
        # configuration is treated as disabled, not as a business-transaction failure.
        if row.type in email_types and not row.sent_email:
            user = await session.get(User, row.user_id)
            if user and user.email and settings.SMTP_HOST:
                delivered = await send_email(user.email, row.title, wrap_email(row.title, f"<p>{row.body}</p>"))
                row.sent_email = delivered
            elif not settings.SMTP_HOST or not user or not user.email:
                # Email is optional for local/dev environments. Do not keep
                # reselecting a push-only notification because its email flag is false.
                row.sent_email = True
        elif row.type not in email_types:
            row.sent_email = True

        # When push is configured and a token exists, only mark the notification
        # delivered when at least one send succeeded. This allows transient failures to retry.
        row.sent_push = push_success
    await session.commit()
