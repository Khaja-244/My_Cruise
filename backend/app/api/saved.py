from fastapi import APIRouter,Depends
from sqlalchemy import select
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.exceptions import AppError
from app.models import *
from app.schemas.saved import SavedCruiseIn
router=APIRouter(tags=['Saved Cruises'])
@router.get('/saved-cruises')
async def saved(user=Depends(get_current_user),session=Depends(get_session)):
    rows=(await session.scalars(select(SavedCruise).where(SavedCruise.user_id==user.id).order_by(SavedCruise.created_at.desc()))).all(); items=[]
    for x in rows:
        c=await session.get(Cruise,x.cruise_id)
        if c: items.append({'id':str(x.id),'cruise_id':str(x.cruise_id),'sailing_id':str(x.sailing_id) if x.sailing_id else None,'slug':c.slug,'name':c.name})
    return {'items':items,'total':len(items),'page':1,'page_size':len(items),'total_pages':1}
@router.post('/saved-cruises')
async def save(data:SavedCruiseIn,user=Depends(get_current_user),session=Depends(get_session)):
    x=SavedCruise(user_id=user.id,cruise_id=data.cruise_id,sailing_id=data.sailing_id); session.add(x)
    try: await session.commit()
    except Exception: await session.rollback(); raise AppError('DUPLICATE_REQUEST','Cruise is already saved.',409)
    return {'id':str(x.id)}
@router.delete('/saved-cruises/{id}')
async def unsave(id:str,user=Depends(get_current_user),session=Depends(get_session)):
    x=await session.scalar(select(SavedCruise).where(SavedCruise.id==id,SavedCruise.user_id==user.id));
    if not x: raise AppError('NOT_FOUND','Saved cruise not found.',404)
    await session.delete(x); await session.commit(); return {'message':'Removed.'}
