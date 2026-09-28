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


from app.services.email_service import send_email, wrap_email, cancellation_email


router = APIRouter(prefix='/admin', tags=['Admin - Cancellations'])

from app.api.admin.helpers import audit

@router.get('/cancellation-requests')
async def cancellations(status:str='pending',admin=Depends(require_admin),session=Depends(get_session)):
    rows=(await session.execute(select(CancellationRequest,Booking,User,Cruise).join(Booking,Booking.id==CancellationRequest.booking_id).join(User,User.id==Booking.user_id).join(Sailing,Sailing.id==Booking.sailing_id).join(Cruise,Cruise.id==Sailing.cruise_id).where(CancellationRequest.status==status).order_by(CancellationRequest.requested_at))).all()
    return [{'id':str(x.id),'booking_id':str(x.booking_id),'booking_reference':b.booking_reference,'traveler':{'full_name':b.customer_name or u.full_name,'email':b.customer_email or u.email,'phone':b.customer_phone or u.phone},'cruise':c.name,'reason':x.reason,'status':x.status.value,'policy_snapshot':x.policy_snapshot,'calculated_refund_cents':x.calculated_refund_cents,'final_refund_cents':x.final_refund_cents,'requested_at':x.requested_at} for x,b,u,c in rows]


@router.get('/cancellation-requests/{id}')
async def cancellation(id:str,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.get(CancellationRequest,id)
    if not x: raise AppError('NOT_FOUND','Cancellation request not found.',404)
    b=await session.get(Booking,x.booking_id)
    return {'id':str(x.id),'booking_id':str(x.booking_id),'booking_reference':b.booking_reference if b else None,'reason':x.reason,'status':x.status.value,'policy_snapshot':x.policy_snapshot,'calculated_refund_cents':x.calculated_refund_cents,'final_refund_cents':x.final_refund_cents,'admin_note':x.admin_note}


@router.post('/cancellation-requests/{id}/approve')
async def approve(id:str,data:AdminCancelReview,admin=Depends(require_admin),session=Depends(get_session),background_tasks: BackgroundTasks = None):
    x=await session.get(CancellationRequest,id); 
    if not x or x.status!=CancellationStatus.pending: raise AppError('NOT_FOUND','Pending cancellation request not found.',404)
    b=await session.get(Booking,x.booking_id); amount=data.final_refund_cents if data.final_refund_cents is not None else x.calculated_refund_cents or 0
    if amount<0 or amount>b.total_cents: raise AppError('VALIDATION_ERROR','Refund amount is outside the booking total.',422)
    calculated=x.calculated_refund_cents or 0
    if data.final_refund_cents is not None and amount != calculated and not data.admin_note:
        raise AppError('VALIDATION_ERROR','A refund override requires an admin note explaining the reason.',422)
    x.status=CancellationStatus.approved; x.reviewed_by=admin.id; x.reviewed_at=datetime.now(timezone.utc); x.final_refund_cents=amount; x.admin_note=data.admin_note; b.status=BookingStatus.cancelled; b.cancelled_at=datetime.now(timezone.utc)
    inv=(await session.scalars(select(CabinInventory).join(BookingCabin,BookingCabin.cabin_inventory_id==CabinInventory.id).where(BookingCabin.booking_id==b.id).with_for_update())).all()
    for r in inv: r.status=InventoryStatus.available; r.booking_id=None; r.held_by_user_id=None; r.hold_expires_at=None; r.version+=1
    payment = await session.scalar(select(Payment).where(Payment.booking_id == b.id).order_by(Payment.created_at.desc()))
    if b.channel == BookingChannel.direct:
        await notify(session,b.user_id,NotificationType.refund_approved,'Cancellation approved',f'Your cancellation for booking {b.booking_reference} was approved. Your refund is being processed.',{'booking_reference':b.booking_reference,'refund_cents':amount})
    if amount > 0 and payment:
        refund = Refund(booking_id=b.id, cancellation_request_id=x.id, payment_id=payment.id, amount_cents=amount, status=RefundStatus.pending)
        session.add(refund)
    audit(session,admin,'approve_cancellation','cancellation_request',x.id,{'calculated_refund_cents':calculated,'final_refund_cents':amount,'override_reason':data.admin_note})
    await session.commit()
    refund_error = None
    if amount > 0 and payment:
        try:
            await issue_refund(session, refund, b.booking_reference)
        except Exception as exc:
            refund_error = str(exc)[:300]
    # Direct travelers receive the durable notification email. Partner customers
    # do not have a my_cruise notification account, so send them a branded email.
    if b.channel == BookingChannel.partner and background_tasks is not None:
        recipient = b.customer_email
        if recipient:
            subject, html = cancellation_email(b.booking_reference, True, amount)
            background_tasks.add_task(send_email, recipient, subject, html)
    return {'message':'Cancellation approved; inventory released and refund queued for retry.' if refund_error else 'Cancellation approved; inventory released and refund initiated.','refund_cents':amount,'refund_error':refund_error}


@router.post('/cancellation-requests/{id}/reject')
async def reject(id:str,data:AdminReject,admin=Depends(require_admin),session=Depends(get_session),background_tasks: BackgroundTasks = None):
    x=await session.get(CancellationRequest,id); 
    if not x or x.status!=CancellationStatus.pending: raise AppError('NOT_FOUND','Pending cancellation request not found.',404)
    x.status=CancellationStatus.rejected; x.reviewed_by=admin.id; x.reviewed_at=datetime.now(timezone.utc); x.admin_note=data.admin_note; b=await session.get(Booking,x.booking_id); b.status=BookingStatus.confirmed
    if b.channel == BookingChannel.direct:
        await notify(session,b.user_id,NotificationType.refund_rejected,'Cancellation rejected',f'Your cancellation request for booking {b.booking_reference} was rejected.',{'booking_reference':b.booking_reference,'reason':data.admin_note})
    await session.commit();
    if b.channel == BookingChannel.partner and background_tasks is not None:
        recipient=b.customer_email
        if recipient:
            subject, html = cancellation_email(b.booking_reference, False, reason=data.admin_note)
            background_tasks.add_task(send_email, recipient, subject, html)
    return {'message':'Cancellation rejected.'}


