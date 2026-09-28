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
from app.services.partner_validation import exposed_sailing

router = APIRouter(prefix='/partner-api', tags=['Partner API'])

from app.core.partner_auth import require_partner_api_key

@router.get('/cruises')
async def api_cruises(request: Request, partner=Depends(require_partner_api_key),session=Depends(get_session)):
    website_condition = (PartnerCruiseExposure.partner_website_id == request.state.partner_website_id if request.state.partner_website_id is not None else PartnerCruiseExposure.partner_website_id.is_(None))
    rows=(await session.execute(select(Cruise).join(PartnerCruiseExposure,PartnerCruiseExposure.cruise_id==Cruise.id).where(
        Cruise.approval_status==ApprovalStatus.approved,
        Cruise.status==CruiseStatus.published,
        PartnerCruiseExposure.partner_id==partner.id,
        PartnerCruiseExposure.enabled.is_(True),
        website_condition,
    ))).scalars().unique().all()
    return [{'id':str(c.id),'name':c.name,'slug':c.slug,'sailing_days':c.sailing_days,'base_price_cents':c.base_price_cents} for c in rows]


@router.get('/cruises/{cruise_id}/sailings')
async def api_sailings(cruise_id:str,request: Request,partner=Depends(require_partner_api_key),session=Depends(get_session)):
    try: cid=uuid.UUID(cruise_id)
    except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid cruise identifier.',422) from exc
    cruise=await session.get(Cruise,cid)
    if not cruise or cruise.approval_status!=ApprovalStatus.approved or cruise.status!=CruiseStatus.published: raise AppError('NOT_FOUND','Cruise is not available.',404)
    website_condition = (PartnerCruiseExposure.partner_website_id == request.state.partner_website_id if request.state.partner_website_id is not None else PartnerCruiseExposure.partner_website_id.is_(None))
    exposed=await session.scalar(select(PartnerCruiseExposure.id).where(
        PartnerCruiseExposure.partner_id==partner.id,
        PartnerCruiseExposure.cruise_id==cruise.id,
        PartnerCruiseExposure.enabled.is_(True),
        website_condition,
    ))
    if not exposed: raise AppError('FORBIDDEN','Cruise is not exposed to this partner.',403)
    rows=(await session.scalars(select(Sailing).where(Sailing.cruise_id==cruise.id,Sailing.status.in_([SailingStatus.scheduled,SailingStatus.open])).order_by(Sailing.departure_date))).all()
    return [{'id':str(x.id),'departure_date':x.departure_date,'return_date':x.return_date,'status':x.status.value} for x in rows]


@router.get('/sailings/{sailing_id}/availability')
async def api_availability(sailing_id:str,request: Request,partner=Depends(require_partner_api_key),session=Depends(get_session)):
    sailing,_=await exposed_sailing(sailing_id,partner,session,request.state.partner_website_id)
    rows=(await session.scalars(select(CabinInventory).where(CabinInventory.sailing_id==sailing.id).order_by(CabinInventory.cabin_id))).all()
    return [{'cabin_id':str(r.cabin_id),'status':r.status.value,'price_cents':r.price_cents,'version':r.version} for r in rows]


