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

async def partner_for_user(user, session):
    if user.role != UserRole.partner:
        raise AppError('FORBIDDEN', 'Partner access required.', 403)
    p = await session.scalar(select(Partner).where(Partner.user_id == user.id))
    if not p:
        raise AppError('NOT_FOUND', 'Partner profile not found.', 404)
    if p.status != PartnerStatus.active:
        raise AppError('FORBIDDEN', 'Partner account is inactive.', 403)
    return p

async def owned_cruise(cruise_id, partner, session):
    try: cid = uuid.UUID(cruise_id)
    except ValueError as exc: raise AppError('VALIDATION_ERROR', 'Invalid cruise identifier.', 422) from exc
    cruise = await session.scalar(select(Cruise).where(Cruise.id == cid, Cruise.partner_id == partner.id, Cruise.deleted_at.is_(None)))
    if not cruise: raise AppError('NOT_FOUND', 'Cruise not found.', 404)
    return cruise
