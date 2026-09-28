from datetime import datetime,timezone
import uuid
from fastapi import APIRouter,Depends,BackgroundTasks
from sqlalchemy import select,func
from app.core.database import get_session
from app.core.deps import require_admin
from app.core.exceptions import AppError
from app.core.redis import get_redis
from app.services.notification_service import notify
from app.models import *
from app.schemas.cruise import *

def audit(session,admin,action,typ,id,after=None): session.add(AuditLog(actor_user_id=admin.id,action=action,entity_type=typ,entity_id=id,after=after))

async def fanout_new_cruise(cruise_id, cruise_name, cruise_slug):
    # Announcement fan-out is deliberately outside the publish transaction.
    # Notifications are durable rows; the normal dispatcher will deliver push.
    from app.core.database import SessionLocal
    async with SessionLocal() as s:
        travelers = (await s.scalars(select(User.id).where(User.role == UserRole.traveler, User.is_active == True))).all()
        for i in range(0, len(travelers), 500):
            for user_id in travelers[i:i + 500]:
                s.add(Notification(
                    user_id=user_id, type=NotificationType.new_cruise,
                    title='New cruise available',
                    body=f'{cruise_name} is now available to book.',
                    data={'cruise_id': str(cruise_id), 'slug': cruise_slug},
                ))
            await s.commit()
        from app.services.notification_service import dispatch_unsent_notifications
        await dispatch_unsent_notifications(s)
