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

@router.get('/dashboard')
async def dashboard(user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session)
    cruises = (await session.scalars(select(Cruise).where(Cruise.partner_id == p.id, Cruise.deleted_at.is_(None)).order_by(Cruise.created_at.desc()))).all()
    first_sailing = {}
    if cruises:
        sailing_rows = (await session.scalars(select(Sailing).where(Sailing.cruise_id.in_([c.id for c in cruises])).order_by(Sailing.departure_date))).all()
        for s in sailing_rows:
            first_sailing.setdefault(s.cruise_id, s)
    bookings = (await session.scalars(select(Booking).where(Booking.partner_id == p.id).order_by(Booking.created_at.desc()).limit(100))).all()
    keys = (await session.scalars(select(PartnerApiKey).where(PartnerApiKey.partner_id == p.id).order_by(PartnerApiKey.created_at.desc()))).all()
    websites = (await session.scalars(select(PartnerWebsite).where(PartnerWebsite.partner_id == p.id).order_by(PartnerWebsite.created_at.desc()))).all()
    earnings = sum(int(b.commission_cents or 0) for b in bookings)
    return {'partner': {'id': str(p.id), 'business_name': p.business_name, 'status': p.status.value, 'integration_status': p.integration_status.value},
            'cruises': [
                {
                    'id': str(c.id),
                    'name': c.name,
                    'slug': c.slug,
                    'description': c.description,
                    'ship_id': str(c.ship_id) if c.ship_id else None,
                    'embark_port_id': str(c.embark_port_id) if c.embark_port_id else None,
                    'disembark_port_id': str(c.disembark_port_id) if c.disembark_port_id else None,
                    'sailing_days': c.sailing_days,
                    'base_price_cents': c.base_price_cents,
                    'start_sailing_date': first_sailing.get(c.id).departure_date if first_sailing.get(c.id) else None,
                    'return_date': first_sailing.get(c.id).return_date if first_sailing.get(c.id) else None,
                    'status': c.status.value,
                    'approval_status': c.approval_status.value,
                    'commission_type': c.commission_type.value if c.commission_type else None,
                    'commission_value': float(c.commission_value) if c.commission_value is not None else None,
                }
                for c in cruises
            ],
            'bookings': [{'reference': b.booking_reference, 'status': b.status.value, 'total_cents': b.total_cents, 'commission_cents': b.commission_cents, 'customer_name': b.customer_name, 'customer_email': b.customer_email} for b in bookings],
            'earnings_cents': earnings,
            'api_keys': [{'id': str(k.id), 'prefix': k.key_prefix, 'active': k.active, 'rate_limit_per_minute': k.rate_limit_per_minute, 'created_at': k.created_at, 'revoked_at': k.revoked_at} for k in keys],
            'websites': [{'id': str(w.id), 'name': w.name, 'website_url': w.website_url, 'integration_status': w.integration_status.value, 'created_at': w.created_at} for w in websites]}


