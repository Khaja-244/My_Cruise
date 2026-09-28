from datetime import datetime,timedelta,timezone
import uuid,secrets
from sqlalchemy import select,update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User,RefreshToken,OTPCode,OTTPurpose
from app.core.security import hash_password,verify_password,create_access_token,hash_token,generate_otp,validate_password_strength
from app.core.config import settings
from app.core.exceptions import AppError
from app.services.email_service import send_email, otp_email

async def register(session,email,full_name,password,phone=None):
    validate_password_strength(password)
    if await session.scalar(select(User).where(User.email==email.lower().strip())): raise AppError('VALIDATION_ERROR','An account with this email already exists.',409)
    user=User(email=email.lower().strip(),full_name=full_name.strip(),phone=phone,password_hash=hash_password(password)); session.add(user); await session.commit(); return user
async def login(session,email,password):
    user=await session.scalar(select(User).where(User.email==email.lower().strip()))
    if not user or not verify_password(password,user.password_hash): raise AppError('UNAUTHORIZED','Invalid email or password.',401)
    if not user.is_active: raise AppError('FORBIDDEN','This account is inactive.',403)
    jti=secrets.token_hex(16); token=create_access_token(str(user.id),user.role.value,jti)
    raw=secrets.token_urlsafe(48); session.add(RefreshToken(user_id=user.id,token_hash=hash_token(raw),expires_at=datetime.now(timezone.utc)+timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))); await session.commit(); return user,token,raw
async def create_otp(session,email,purpose):
    now=datetime.now(timezone.utc); code=generate_otp();
    prior=(await session.scalars(select(OTPCode).where(OTPCode.email==email,OTPCode.purpose==purpose,OTPCode.consumed_at.is_(None)))).all()
    for x in prior: x.consumed_at=now
    otp=OTPCode(email=email,purpose=purpose,code_hash=hash_password(code),expires_at=now+timedelta(minutes=settings.OTP_EXPIRY_MINUTES)); session.add(otp); await session.commit()
    subject, html = otp_email(code, purpose.value)
    await send_email(email, subject, html)
    return otp
