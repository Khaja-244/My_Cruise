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


router = APIRouter(prefix='/admin', tags=['Admin - Dashboard'])

from app.api.admin.helpers import audit

@router.get('/dashboard/stats')
async def stats(admin=Depends(require_admin),session=Depends(get_session)):
    revenue=await session.scalar(select(func.coalesce(func.sum(Booking.total_cents),0)).where(Booking.status.in_([BookingStatus.confirmed,BookingStatus.refunded,BookingStatus.partially_refunded])))
    bookings=await session.scalar(select(func.count()).select_from(Booking)); pending=await session.scalar(select(func.count()).select_from(CancellationRequest).where(CancellationRequest.status==CancellationStatus.pending)); return {'revenue_cents':int(revenue or 0),'bookings':bookings,'pending_cancellation_requests':pending}


