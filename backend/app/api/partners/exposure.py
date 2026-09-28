import secrets

import uuid

from datetime import datetime, timezone, time, timedelta

from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Header, Query

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

@router.get('/{partner_id}/exposures', dependencies=[Depends(require_admin)])
async def list_exposures(partner_id:str,website_id:str|None=Query(default=None),session=Depends(get_session),admin=Depends(require_admin)):
    p=await session.get(Partner,partner_id)
    if not p: raise AppError('NOT_FOUND','Partner not found.',404)
    conditions=[PartnerCruiseExposure.partner_id==p.id]
    if website_id:
        try: wid=uuid.UUID(website_id)
        except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid website identifier.',422) from exc
        website=await session.scalar(select(PartnerWebsite).where(PartnerWebsite.id==wid,PartnerWebsite.partner_id==p.id))
        if not website: raise AppError('NOT_FOUND','Partner website not found.',404)
        conditions.append(PartnerCruiseExposure.partner_website_id==wid)
    else:
        conditions.append(PartnerCruiseExposure.partner_website_id.is_(None))
    rows=(await session.execute(select(PartnerCruiseExposure,Cruise).join(Cruise,Cruise.id==PartnerCruiseExposure.cruise_id).where(*conditions).order_by(Cruise.name))).all()
    return [{'id':str(e.id),'cruise_id':str(e.cruise_id),'cruise_name':c.name,'enabled':e.enabled} for e,c in rows]


@router.put('/{partner_id}/exposures/{cruise_id}')
async def set_exposure(partner_id:str,cruise_id:str,data:ExposureUpdate,website_id:str|None=Query(default=None),admin=Depends(require_admin),session=Depends(get_session)):
    p=await session.get(Partner,partner_id); c=await session.get(Cruise,cruise_id)
    if not p or p.status != PartnerStatus.active or not c or c.approval_status!=ApprovalStatus.approved:
        raise AppError('NOT_FOUND','Active approved partner/cruise not found.',404)
    if c.partner_id != p.id:
        raise AppError('FORBIDDEN','A partner website can only expose cruises owned by that partner.',403)
    target_website_id=None
    if website_id:
        try: target_website_id=uuid.UUID(website_id)
        except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid website identifier.',422) from exc
        website=await session.scalar(select(PartnerWebsite).where(PartnerWebsite.id==target_website_id,PartnerWebsite.partner_id==p.id))
        if not website: raise AppError('NOT_FOUND','Partner website not found.',404)
    e=await session.scalar(select(PartnerCruiseExposure).where(PartnerCruiseExposure.partner_id==p.id,PartnerCruiseExposure.cruise_id==c.id,PartnerCruiseExposure.partner_website_id==target_website_id))
    if not e: e=PartnerCruiseExposure(partner_id=p.id,partner_website_id=target_website_id,cruise_id=c.id,enabled=data.enabled); session.add(e)
    else: e.enabled=data.enabled
    await session.commit(); return {'cruise_id':str(c.id),'website_id':str(target_website_id) if target_website_id else None,'enabled':e.enabled}


