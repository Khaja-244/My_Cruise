from datetime import datetime,timezone,date

from fastapi import APIRouter,Depends,BackgroundTasks

from sqlalchemy import select,func,and_

from app.core.database import get_session

from app.core.deps import require_admin

from app.core.exceptions import AppError

from app.models import *

from app.schemas.booking import AdminCancelReview,AdminReject

from app.schemas.admin import RefundPolicyCreate,RefundPolicyPatch,AdminUserStatus

from app.services.refund_service import issue_refund

from app.services.notification_service import notify


from app.services.email_service import send_email


router = APIRouter(prefix='/admin', tags=['Admin - Audit Logs'])

from app.api.admin.helpers import audit

@router.get('/audit-logs')
async def audits(admin=Depends(require_admin),session=Depends(get_session)): return [{'id':str(x.id),'action':x.action,'entity_type':x.entity_type,'entity_id':str(x.entity_id) if x.entity_id else None,'created_at':x.created_at} for x in (await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))).all()]


