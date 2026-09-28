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

@router.get('/websites/admin', dependencies=[Depends(require_admin)])
async def admin_websites(session=Depends(get_session),admin=Depends(require_admin)):
    rows=(await session.execute(select(PartnerWebsite,Partner).join(Partner,Partner.id==PartnerWebsite.partner_id).order_by(PartnerWebsite.created_at.desc()))).all()
    return [{'id':str(w.id),'partner_id':str(w.partner_id),'partner_name':p.business_name,'name':w.name,'website_url':w.website_url,'integration_status':w.integration_status.value,'created_at':w.created_at} for w,p in rows]


@router.patch('/websites/{website_id}/status')
async def admin_website_status(website_id:str,data:WebsiteStatusUpdate,admin=Depends(require_admin),session=Depends(get_session)):
    w=await session.get(PartnerWebsite,website_id)
    if not w: raise AppError('NOT_FOUND','Website integration not found.',404)
    if data.integration_status not in ('connected','suspended'): raise AppError('VALIDATION_ERROR','Invalid integration status.',422)
    w.integration_status=IntegrationStatus(data.integration_status); w.updated_at=datetime.now(timezone.utc); await session.commit(); return {'integration_status':w.integration_status.value}


@router.get('/websites')
async def own_websites(user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session); rows=(await session.scalars(select(PartnerWebsite).where(PartnerWebsite.partner_id==p.id))).all()
    return [{'id':str(w.id),'name':w.name,'website_url':w.website_url,'integration_status':w.integration_status.value} for w in rows]


@router.post('/websites')
async def register_website(data:WebsiteCreate,user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session); w=PartnerWebsite(partner_id=p.id,name=data.name,website_url=str(data.website_url),integration_status=IntegrationStatus.suspended); session.add(w); await session.commit(); return {'id':str(w.id),'integration_status':w.integration_status.value,'message':'Website registered. Admin must activate the integration.'}


