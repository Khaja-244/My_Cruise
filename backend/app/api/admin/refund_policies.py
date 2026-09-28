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


router = APIRouter(prefix='/admin', tags=['Admin - Refund Policies'])

from app.api.admin.helpers import audit

@router.get('/refund-policies')
async def policies(admin=Depends(require_admin),session=Depends(get_session)):
    result=[]
    for x in (await session.scalars(select(RefundPolicy))).all():
        rules=(await session.scalars(select(RefundPolicyRule).where(RefundPolicyRule.policy_id==x.id).order_by(RefundPolicyRule.min_days_before_departure))).all()
        result.append({'id':str(x.id),'name':x.name,'description':x.description,'is_default':x.is_default,'is_active':x.is_active,'rules':[{'min_days_before_departure':r.min_days_before_departure,'max_days_before_departure':r.max_days_before_departure,'refund_percent':float(r.refund_percent),'flat_fee_cents':r.flat_fee_cents} for r in rules]})
    return result


@router.post('/refund-policies')
async def policy(data:RefundPolicyCreate,admin=Depends(require_admin),session=Depends(get_session)):
    if data.is_default: await session.execute(__import__('sqlalchemy').update(RefundPolicy).values(is_default=False))
    p=RefundPolicy(name=data.name,description=data.description,is_default=data.is_default,is_active=data.is_active); session.add(p); await session.flush()
    for r in data.rules: session.add(RefundPolicyRule(policy_id=p.id,**r.model_dump()))
    await session.commit(); return {'id':str(p.id)}


@router.patch('/refund-policies/{id}')
async def patch_policy(id: str, data: RefundPolicyPatch, admin=Depends(require_admin), session=Depends(get_session)):
    policy = await session.get(RefundPolicy, id)
    if not policy: raise AppError('NOT_FOUND', 'Refund policy not found.', 404)
    values = data.model_dump(exclude_none=True)
    if values.get('is_default'):
        await session.execute(__import__('sqlalchemy').update(RefundPolicy).values(is_default=False))
    for key, value in values.items(): setattr(policy, key, value)
    audit(session, admin, 'update', 'refund_policy', policy.id, values)
    await session.commit()
    return {'message': 'Refund policy updated.'}


from app.schemas.admin import RefundRuleIn

@router.put('/refund-policies/{id}/rules')
async def replace_policy_rules(id: str, rules: list[RefundRuleIn], admin=Depends(require_admin), session=Depends(get_session)):
    policy = await session.get(RefundPolicy, id)
    if not policy: raise AppError('NOT_FOUND', 'Refund policy not found.', 404)
    validated = rules
    ordered = sorted(validated, key=lambda r: r.min_days_before_departure)
    for i, r in enumerate(ordered):
        if r.max_days_before_departure is not None and r.max_days_before_departure < r.min_days_before_departure: raise AppError('VALIDATION_ERROR','Invalid refund rule range.',422)
        if i and (ordered[i-1].max_days_before_departure is None or ordered[i-1].max_days_before_departure >= r.min_days_before_departure): raise AppError('VALIDATION_ERROR','Refund policy ranges overlap.',422)
    await session.execute(__import__('sqlalchemy').delete(RefundPolicyRule).where(RefundPolicyRule.policy_id == policy.id))
    for r in validated: session.add(RefundPolicyRule(policy_id=policy.id, **r.model_dump()))
    audit(session, admin, 'replace', 'refund_policy_rules', policy.id, {'rules': [r.model_dump() for r in validated]}); await session.commit(); return {'message': 'Rules replaced.'}


