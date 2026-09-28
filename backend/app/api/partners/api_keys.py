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

@router.get('/{partner_id}/api-keys', dependencies=[Depends(require_admin)])
async def list_keys(partner_id:str,session=Depends(get_session),admin=Depends(require_admin)):
    rows=(await session.scalars(select(PartnerApiKey).where(PartnerApiKey.partner_id==partner_id).order_by(PartnerApiKey.created_at.desc()))).all()
    return [{'id':str(k.id),'prefix':k.key_prefix,'active':k.active,'rate_limit_per_minute':k.rate_limit_per_minute,'created_at':k.created_at,'revoked_at':k.revoked_at} for k in rows]


@router.post('/api-keys')
async def issue_key(partner_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    p=await session.get(Partner,partner_id)
    if not p: raise AppError('NOT_FOUND','Partner not found.',404)
    raw,digest,prefix=generate_partner_api_key(); session.add(PartnerApiKey(partner_id=p.id,key_hash=digest,key_prefix=prefix)); p.integration_status=IntegrationStatus.connected; await session.commit(); return {'api_key':raw,'warning':'Store this key now. The full secret is never stored or shown again.'}


@router.post('/api-keys/{key_id}/revoke')
async def revoke_key(key_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    k=await session.get(PartnerApiKey,key_id)
    if not k: raise AppError('NOT_FOUND','API key not found.',404)
    k.active=False; k.revoked_at=datetime.now(timezone.utc); await session.commit(); return {'message':'API key revoked.'}


