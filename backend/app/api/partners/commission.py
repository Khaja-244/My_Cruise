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

@router.patch('/cruises/{cruise_id}/commission')
async def set_commission(cruise_id:str,data:CommissionUpdate,admin=Depends(require_admin),session=Depends(get_session)):
    c=await session.get(Cruise,cruise_id)
    if not c or not c.partner_id: raise AppError('NOT_FOUND','Partner cruise not found.',404)
    if data.commission_type not in ('percent','flat'): raise AppError('VALIDATION_ERROR','Commission type must be percent or flat.',422)
    if data.commission_type=='percent' and data.commission_value>100: raise AppError('VALIDATION_ERROR','Percentage commission cannot exceed 100.',422)
    c.commission_type=CommissionType(data.commission_type); c.commission_value=Decimal(str(data.commission_value)); await session.commit()
    return {'commission_type':c.commission_type.value,'commission_value':float(c.commission_value)}


