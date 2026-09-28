import secrets

import uuid

from datetime import datetime, timezone, time, timedelta

from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Header

from sqlalchemy import select, delete

from app.core.database import get_session

from app.core.deps import get_current_user, require_admin

from app.core.exceptions import AppError

from app.core.partner_auth import require_partner_api_key, generate_partner_api_key

from app.core.security import hash_password, validate_password_strength

from app.models import *

from app.schemas.partner import *

from app.services.email_service import send_email

from app.services.booking_service import hold_booking


router = APIRouter(prefix='/partners', tags=['Partner Management'])

from app.api.partners.helpers import partner_for_user, owned_cruise

@router.get('/bookings')
async def partner_bookings(user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session)
    rows=(await session.scalars(select(Booking).where(Booking.partner_id==p.id,Booking.channel==BookingChannel.partner).order_by(Booking.created_at.desc()).limit(100))).all()
    result=[]
    for b in rows:
        sailing=await session.get(Sailing,b.sailing_id); cruise=await session.get(Cruise,sailing.cruise_id) if sailing else None
        cabins=(await session.execute(select(BookingCabin,Cabin).join(Cabin,Cabin.id==BookingCabin.cabin_id).where(BookingCabin.booking_id==b.id))).all()
        payments=(await session.scalars(select(Payment).where(Payment.booking_id==b.id).order_by(Payment.created_at.desc()))).all()
        result.append({'reference':b.booking_reference,'status':b.status.value,'channel':b.channel.value,'customer':{'name':b.customer_name,'email':b.customer_email,'phone':b.customer_phone},'cruise':{'id':str(cruise.id),'name':cruise.name} if cruise else None,'sailing':{'id':str(sailing.id),'departure_date':sailing.departure_date,'return_date':sailing.return_date} if sailing else None,'cabins':[{'id':str(bc.cabin_id),'number':cab.cabin_number,'occupancy':bc.occupancy,'price_cents':bc.price_cents} for bc,cab in cabins],'payment':{'status':payments[0].status.value,'amount_cents':payments[0].amount_cents,'currency':payments[0].currency} if payments else None,'total_cents':b.total_cents,'commission_cents':b.commission_cents})
    return result


