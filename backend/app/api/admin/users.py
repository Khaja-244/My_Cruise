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


router = APIRouter(prefix='/admin', tags=['Admin - Users'])

from app.api.admin.helpers import audit

@router.get('/users')
async def users(role:str|None=None,is_active:bool|None=None,admin=Depends(require_admin),session=Depends(get_session)):
    stmt=select(User); 
    if role: stmt=stmt.where(User.role==role)
    if is_active is not None: stmt=stmt.where(User.is_active==is_active)
    return [{'id':str(x.id),'full_name':x.full_name,'email':x.email,'role':x.role.value,'is_active':x.is_active} for x in (await session.scalars(stmt.order_by(User.created_at.desc()))).all()]


@router.patch('/users/{id}/status')
async def user_status(id:str,data:AdminUserStatus,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.get(User,id)
    if not x: raise AppError('NOT_FOUND','User not found.',404)
    x.is_active=data.is_active; audit(session,admin,'update','user',x.id,data.model_dump()); await session.commit(); return {'message':'User status updated.'}


@router.post('/users')
async def create_admin_user(data: dict, admin=Depends(require_admin), session=Depends(get_session)):
    # Admin accounts cannot be created through public registration.
    email = str(data.get('email','')).strip().lower(); name = str(data.get('full_name','')).strip(); password = str(data.get('password',''))
    if not email or not name or len(password) < 8: raise AppError('VALIDATION_ERROR','full_name, email and an 8+ character password are required.',422)
    if await session.scalar(select(User).where(User.email == email)): raise AppError('VALIDATION_ERROR','An account with this email already exists.',409)
    user = User(full_name=name,email=email,password_hash=__import__('app.core.security',fromlist=['hash_password']).hash_password(password),role=UserRole.admin,is_email_verified=False,must_change_password=True)
    session.add(user); await session.flush(); audit(session, admin, 'create', 'user', user.id, {'email':email,'role':'admin'}); await session.commit(); return {'id':str(user.id),'message':'Admin created; password change is required at first login.'}


