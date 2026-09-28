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


router = APIRouter(prefix='/admin', tags=['Admin - Bookings'])

from app.api.admin.helpers import audit

@router.get('/bookings')
async def bookings(status:str|None=None,partner_id:str|None=None,cruise_id:str|None=None,start_date:date|None=None,end_date:date|None=None,page:int=1,page_size:int=50,admin=Depends(require_admin),session=Depends(get_session)):
    page=max(1,page); page_size=min(max(1,page_size),100)
    stmt=select(Booking,User,Cruise,Sailing,Partner).join(User,User.id==Booking.user_id).join(Sailing,Sailing.id==Booking.sailing_id).join(Cruise,Cruise.id==Sailing.cruise_id).outerjoin(Partner,Partner.id==Booking.partner_id)
    if status: stmt=stmt.where(Booking.status==status)
    if partner_id: stmt=stmt.where(Booking.partner_id==partner_id)
    if cruise_id: stmt=stmt.where(Cruise.id==cruise_id)
    if start_date: stmt=stmt.where(Sailing.departure_date>=start_date)
    if end_date: stmt=stmt.where(Sailing.departure_date<=end_date)
    count_stmt=select(func.count()).select_from(stmt.subquery()); total=await session.scalar(count_stmt)
    rows=(await session.execute(stmt.order_by(Booking.created_at.desc()).offset((page-1)*page_size).limit(page_size))).all()
    items=[]
    for x,u,c,sailing,partner in rows:
        cabins=(await session.execute(select(BookingCabin,Cabin).join(Cabin,Cabin.id==BookingCabin.cabin_id).where(BookingCabin.booking_id==x.id))).all()
        items.append({'reference':x.booking_reference,'status':x.status.value,'total_cents':x.total_cents,'guest_count':x.guest_count,'created_at':x.created_at,'traveler':{'id':str(u.id),'full_name':x.customer_name or u.full_name,'email':x.customer_email or u.email,'phone':x.customer_phone or u.phone},'partner':{'id':str(partner.id),'business_name':partner.business_name,'email':partner.email} if partner else None,'commission_cents':x.commission_cents,'channel':x.channel.value,'cruise':{'id':str(c.id),'name':c.name,'slug':c.slug},'sailing':{'id':str(sailing.id),'departure_date':sailing.departure_date,'return_date':sailing.return_date},'cabins':[{'cabin_id':str(bc.cabin_id),'cabin_number':cab.cabin_number,'occupancy':bc.occupancy,'price_cents':bc.price_cents} for bc,cab in cabins]})
    return {'items':items,'total':int(total or 0),'page':page,'page_size':page_size,'total_pages':(int(total or 0)+page_size-1)//page_size}


@router.get('/bookings/{reference}')
async def booking(reference:str,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.scalar(select(Booking).where(Booking.booking_reference==reference))
    if not x: raise AppError('NOT_FOUND','Booking not found.',404)
    user=await session.get(User,x.user_id); sailing=await session.get(Sailing,x.sailing_id); cruise=await session.get(Cruise,sailing.cruise_id)
    cabins=(await session.execute(select(BookingCabin,Cabin).join(Cabin,Cabin.id==BookingCabin.cabin_id).where(BookingCabin.booking_id==x.id))).all()
    guests=(await session.scalars(select(BookingGuest).where(BookingGuest.booking_id==x.id))).all()
    cabin_numbers={str(cab.id): cab.cabin_number for _, cab in cabins}
    payments=(await session.scalars(select(Payment).where(Payment.booking_id==x.id).order_by(Payment.created_at.desc()))).all()
    cancellations=(await session.scalars(select(CancellationRequest).where(CancellationRequest.booking_id==x.id).order_by(CancellationRequest.requested_at.desc()))).all()
    refunds=(await session.scalars(select(Refund).where(Refund.booking_id==x.id).order_by(Refund.processed_at.desc().nullslast()))).all()
    partner=await session.get(Partner,x.partner_id) if x.partner_id else None
    return {'reference':x.booking_reference,'status':x.status.value,'subtotal_cents':x.subtotal_cents,'tax_cents':x.tax_cents,'total_cents':x.total_cents,'currency':x.currency,'guest_count':x.guest_count,'commission_cents':x.commission_cents,'channel':x.channel.value,'traveler':{'full_name':x.customer_name or user.full_name,'email':x.customer_email or user.email,'phone':x.customer_phone or user.phone} if user else None,'partner':{'id':str(partner.id),'business_name':partner.business_name,'email':partner.email} if partner else None,'cruise':{'id':str(cruise.id),'name':cruise.name} if cruise else None,'sailing':{'id':str(sailing.id),'departure_date':sailing.departure_date,'return_date':sailing.return_date} if sailing else None,'cabins':[{'cabin_id':str(bc.cabin_id),'cabin_number':cab.cabin_number,'occupancy':bc.occupancy,'price_cents':bc.price_cents} for bc,cab in cabins],'guests':[{'full_name':g.full_name,'date_of_birth':g.date_of_birth,'nationality':g.nationality,'is_lead_guest':g.is_lead_guest,'cabin_id':str(g.cabin_id),'cabin_number':cabin_numbers.get(str(g.cabin_id))} for g in guests],'payments':[{'id':str(p.id),'status':p.status.value,'amount_cents':p.amount_cents,'currency':p.currency,'stripe_payment_intent_id':p.stripe_payment_intent_id,'stripe_charge_id':p.stripe_charge_id} for p in payments],'cancellations':[{'id':str(c.id),'status':c.status.value,'reason':c.reason,'calculated_refund_cents':c.calculated_refund_cents,'final_refund_cents':c.final_refund_cents,'admin_note':c.admin_note,'requested_at':c.requested_at,'reviewed_at':c.reviewed_at} for c in cancellations],'refunds':[{'id':str(r.id),'payment_id':str(r.payment_id),'stripe_refund_id':r.stripe_refund_id,'amount_cents':r.amount_cents,'status':r.status.value,'failure_reason':r.failure_reason,'processed_at':r.processed_at} for r in refunds]}


