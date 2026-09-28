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

from app.services.email_service import send_email, wrap_email
from app.core.config import settings as app_settings

from app.services.booking_service import hold_booking


router = APIRouter(prefix='/partners', tags=['Partner Management'])

from app.api.partners.helpers import partner_for_user, owned_cruise

@router.post('/applications')
async def apply(data: PartnerApplicationCreate, user=Depends(get_current_user), session=Depends(get_session)):
    # Only a normal traveler account can submit a self-service partner application.
    # The application email is always tied to the authenticated account so an
    # administrator can never receive an application that points at the wrong user.
    if user.role != UserRole.traveler:
        raise AppError('FORBIDDEN', 'Only traveler accounts can submit a partner application.', 403)

    account_email = str(user.email).strip().lower()
    submitted_email = str(data.email).strip().lower()
    if submitted_email != account_email:
        raise AppError(
            'VALIDATION_ERROR',
            'Application email must match the logged-in account email.',
            422,
        )

    existing = await session.scalar(
        select(PartnerApplication).where(
            PartnerApplication.applicant_user_id == user.id,
            PartnerApplication.status == PartnerApplicationStatus.pending,
        )
    )
    if existing:
        raise AppError('DUPLICATE_REQUEST', 'You already have a pending partner application.', 409)

    values = data.model_dump()
    values['email'] = account_email
    x = PartnerApplication(applicant_user_id=user.id, **values)
    session.add(x)
    await session.commit()
    return {'id': str(x.id), 'status': x.status.value}


@router.get('/application/me')
async def my_application(user=Depends(get_current_user), session=Depends(get_session)):
    x = await session.scalar(select(PartnerApplication).where(PartnerApplication.applicant_user_id == user.id).order_by(PartnerApplication.created_at.desc()))
    return None if not x else {'id': str(x.id), 'business_name': x.business_name, 'status': x.status.value, 'reason': x.review_reason}


@router.get('/applications', dependencies=[Depends(require_admin)])
async def applications(session=Depends(get_session), admin=Depends(require_admin)):
    rows=(await session.scalars(select(PartnerApplication).order_by(PartnerApplication.created_at.desc()))).all()
    return [{'id':str(x.id),'business_name':x.business_name,'contact_name':x.contact_name,'email':x.email,'phone':x.phone,'status':x.status.value,'reason':x.review_reason,'created_at':x.created_at} for x in rows]


@router.post('/applications/{application_id}/review')
async def review(application_id:str,data:ReviewApplication,admin=Depends(require_admin),session=Depends(get_session)):
    x = await session.get(PartnerApplication, application_id)
    if not x:
        raise AppError('NOT_FOUND', 'Application not found.', 404)
    if x.status != PartnerApplicationStatus.pending:
        raise AppError('VALIDATION_ERROR', 'Application has already been reviewed.', 409)

    # Rejection does not need an applicant account. Approval does, because the
    # partner dashboard must be attached to the person who submitted the application.
    u = None
    normalized_email = str(x.email).strip().lower()
    if data.approved:
        u = await session.get(User, x.applicant_user_id)
        if not u or str(u.email).strip().lower() != normalized_email:
            # Repair legacy applications that were created before the email/account
            # relationship was enforced. This also fixes applications created by an
            # administrator while testing an older build.
            u = await session.scalar(select(User).where(User.email == normalized_email))
            if not u:
                raise AppError(
                    'VALIDATION_ERROR',
                    'Application email does not match an existing applicant account.',
                    409,
                )
            x.applicant_user_id = u.id

        if u.role == UserRole.admin:
            raise AppError('VALIDATION_ERROR', 'An administrator account cannot become a partner through a self-service application.', 409)

        p = await session.scalar(select(Partner).where(Partner.email == normalized_email))
        if p and p.user_id and p.user_id != u.id:
            raise AppError('DUPLICATE_REQUEST', 'A partner account already exists for this email.', 409)
        if not p:
            p = Partner(
                business_name=x.business_name,
                contact_name=x.contact_name,
                email=normalized_email,
                phone=x.phone,
                status=PartnerStatus.active,
                integration_status=IntegrationStatus.suspended,
            )
            session.add(p)
            await session.flush()

        password = secrets.token_urlsafe(10) + 'A1'
        validate_password_strength(password)
        u.role = UserRole.partner
        u.must_change_password = True
        u.password_hash = hash_password(password)
        u.is_active = True
        u.is_email_verified = True
        if x.phone:
            u.phone = x.phone
        p.user_id = u.id
        p.status = PartnerStatus.active
        p.business_name = x.business_name
        p.contact_name = x.contact_name
        p.email = normalized_email
        p.phone = x.phone

    x.status = PartnerApplicationStatus.approved if data.approved else PartnerApplicationStatus.rejected
    x.reviewer_id = admin.id
    x.review_reason = data.reason
    x.reviewed_at = datetime.now(timezone.utc)
    await session.commit()

    if data.approved:
        approval_body = f'''<p>Congratulations — your partner application has been approved. Your Partner Dashboard
        account is ready.</p>
        <table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">
          <tr><td style="padding:8px 0;color:#8a97a6;width:150px">Login email</td><td style="padding:8px 0;font-weight:700">{normalized_email}</td></tr>
          <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#8a97a6">Temporary password</td>
              <td style="padding:8px 0;font-weight:800;font-family:monospace;font-size:16px">{password}</td></tr>
        </table>
        <p style="color:#b45309;background:#fffbeb;border-radius:10px;padding:10px 14px;font-size:13.5px">
          For security, please change this temporary password immediately after your first login.</p>'''
        await send_email(normalized_email, 'Your my_cruise partner account is approved',
            wrap_email('Partner account approved', approval_body,
                       preheader='Your my_cruise partner account is ready',
                       cta_label='Log in to Partner Dashboard', cta_url=f'{app_settings.FRONTEND_URL}/login'))

    return {'message':'Application reviewed.','status':x.status.value}


@router.post('')
async def create_partner_direct(data: AdminPartnerCreate, admin=Depends(require_admin), session=Depends(get_session)):
    """Allow an administrator to onboard an agency without a self-service application."""
    email = str(data.email).lower().strip()
    existing_partner = await session.scalar(select(Partner).where(Partner.email == email))
    if existing_partner:
        raise AppError('DUPLICATE_REQUEST', 'A partner already exists for this email.', 409)
    user = await session.scalar(select(User).where(User.email == email))
    if user and user.role not in (UserRole.traveler, UserRole.partner):
        raise AppError('VALIDATION_ERROR', 'That email belongs to an incompatible account.', 409)
    password = secrets.token_urlsafe(10) + 'A1'
    validate_password_strength(password)
    if not user:
        user = User(full_name=data.contact_name, email=email, phone=data.phone, password_hash=hash_password(password),
                    role=UserRole.partner, is_active=True, must_change_password=True, is_email_verified=True)
        session.add(user); await session.flush()
    else:
        user.full_name=data.contact_name; user.phone=data.phone; user.password_hash=hash_password(password)
        user.role=UserRole.partner; user.is_active=True; user.must_change_password=True
    partner = Partner(business_name=data.business_name, contact_name=data.contact_name, email=email, phone=data.phone,
                      user_id=user.id, status=PartnerStatus.active, integration_status=IntegrationStatus.suspended)
    session.add(partner); await session.commit()
    created_body = f'''<p>An administrator has created a my_cruise Partner Dashboard account for you.</p>
    <table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">
      <tr><td style="padding:8px 0;color:#8a97a6;width:150px">Login email</td><td style="padding:8px 0;font-weight:700">{email}</td></tr>
      <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#8a97a6">Temporary password</td>
          <td style="padding:8px 0;font-weight:800;font-family:monospace;font-size:16px">{password}</td></tr>
    </table>
    <p style="color:#b45309;background:#fffbeb;border-radius:10px;padding:10px 14px;font-size:13.5px">
      For security, please change this temporary password immediately after your first login.</p>'''
    await send_email(email, 'Your my_cruise partner account has been created',
        wrap_email('Partner account created', created_body,
                   preheader='Your my_cruise partner account is ready',
                   cta_label='Log in to Partner Dashboard', cta_url=f'{app_settings.FRONTEND_URL}/login'))
    return {'id':str(partner.id), 'status':partner.status.value, 'temporary_password_sent':True}


@router.get('/list', dependencies=[Depends(require_admin)])
async def list_partners(session=Depends(get_session),admin=Depends(require_admin)):
    rows=(await session.scalars(select(Partner).order_by(Partner.created_at.desc()))).all()
    return [{'id':str(p.id),'business_name':p.business_name,'contact_name':p.contact_name,'email':p.email,'status':p.status.value,'integration_status':p.integration_status.value,'user_id':str(p.user_id) if p.user_id else None} for p in rows]


@router.patch('/{partner_id}/status')
async def set_partner_status(partner_id:str,data:PartnerStatusUpdate,admin=Depends(require_admin),session=Depends(get_session)):
    p=await session.get(Partner,partner_id)
    if not p: raise AppError('NOT_FOUND','Partner not found.',404)
    if data.status not in ('active','disabled','rejected'): raise AppError('VALIDATION_ERROR','Invalid partner status.',422)
    p.status=PartnerStatus(data.status)
    # Partner status must also control the linked dashboard account. This prevents a
    # disabled/rejected partner from continuing to sign in while still allowing an
    # administrator to re-enable the account later.
    if p.user_id:
        user = await session.get(User, p.user_id)
        if user:
            user.is_active = data.status == 'active'
    await session.commit()
    return {'status':p.status.value, 'user_active': bool(data.status == 'active')}

