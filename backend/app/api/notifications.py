from datetime import datetime,timezone
from fastapi import APIRouter,Depends
from sqlalchemy import select,func,update
from app.core.database import get_session
from app.core.deps import get_current_user
from app.models import *
from app.schemas.notification import DeviceIn
router=APIRouter(tags=['Notifications'])
@router.get('/notifications')
async def notifications(unread_only:bool=False,user=Depends(get_current_user),session=Depends(get_session)):
    stmt=select(Notification).where(Notification.user_id==user.id); 
    if unread_only: stmt=stmt.where(Notification.is_read==False)
    rows=(await session.scalars(stmt.order_by(Notification.created_at.desc()))).all(); return [{'id':str(x.id),'type':x.type.value,'title':x.title,'body':x.body,'data':x.data,'is_read':x.is_read,'created_at':x.created_at.isoformat()} for x in rows]
@router.patch('/notifications/{id}/read')
async def read(id:str,user=Depends(get_current_user),session=Depends(get_session)):
    await session.execute(update(Notification).where(Notification.id==id,Notification.user_id==user.id).values(is_read=True,read_at=datetime.now(timezone.utc))); await session.commit(); return {'message':'Marked as read.'}
@router.patch('/notifications/read-all')
async def read_all(user=Depends(get_current_user),session=Depends(get_session)):
    await session.execute(update(Notification).where(Notification.user_id==user.id,Notification.is_read==False).values(is_read=True,read_at=datetime.now(timezone.utc))); await session.commit(); return {'message':'All notifications marked as read.'}
@router.get('/notifications/unread-count')
async def unread_count(user=Depends(get_current_user),session=Depends(get_session)): return {'count':await session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==user.id,Notification.is_read==False))}
@router.post('/devices/token')
async def token(data:DeviceIn,user=Depends(get_current_user),session=Depends(get_session)):
    x=await session.scalar(select(DeviceToken).where(DeviceToken.fcm_token==data.fcm_token));
    if x: x.user_id=user.id; x.platform=data.platform; x.is_active=True; x.last_seen_at=datetime.now(timezone.utc)
    else: session.add(DeviceToken(user_id=user.id,fcm_token=data.fcm_token,platform=data.platform,last_seen_at=datetime.now(timezone.utc)))
    await session.commit(); return {'message':'Device registered.'}
@router.delete('/devices/token')
async def token_delete(data:DeviceIn,user=Depends(get_current_user),session=Depends(get_session)): await session.execute(update(DeviceToken).where(DeviceToken.user_id==user.id,DeviceToken.fcm_token==data.fcm_token).values(is_active=False)); await session.commit(); return {'message':'Device removed.'}
