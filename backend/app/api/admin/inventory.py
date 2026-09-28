from datetime import datetime,timezone

import uuid

from fastapi import APIRouter,Depends,BackgroundTasks

from sqlalchemy import select,func

from app.core.database import get_session

from app.core.deps import require_admin

from app.core.exceptions import AppError

from app.core.redis import get_redis

from app.services.notification_service import notify

from app.models import *

from app.schemas.cruise import *


router = APIRouter(prefix='/admin', tags=['Admin - Inventory'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.get('/sailings/{id}/inventory')
async def inv(id:str,admin=Depends(require_admin),session=Depends(get_session)):
    rows=(await session.execute(select(CabinInventory,Cabin).join(Cabin,Cabin.id==CabinInventory.cabin_id).where(CabinInventory.sailing_id==id).order_by(Cabin.cabin_number))).all()
    return [{'cabin_id':str(x.cabin_id),'cabin_number':c.cabin_number,'status':x.status.value,'price_cents':x.price_cents,'hold_expires_at':x.hold_expires_at} for x,c in rows]


@router.patch('/sailings/{sailing_id}/cabins/{cabin_id}')
async def patch_inventory(sailing_id:str,cabin_id:str,data:dict,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.scalar(select(CabinInventory).where(CabinInventory.sailing_id==sailing_id,CabinInventory.cabin_id==cabin_id).with_for_update())
    if not x: raise AppError('NOT_FOUND','Inventory row not found.',404)
    if x.status in (InventoryStatus.booked,InventoryStatus.held): raise AppError('CABIN_UNAVAILABLE','Booked/held cabins cannot be changed.',409)
    if 'price_cents' in data:
        try: price=int(data['price_cents'])
        except (TypeError,ValueError): raise AppError('VALIDATION_ERROR','price_cents must be an integer.',422)
        if price < 0: raise AppError('VALIDATION_ERROR','price_cents cannot be negative.',422)
        x.price_cents=price
    if 'status' in data:
        status=data['status']
        if status not in (InventoryStatus.available.value, InventoryStatus.blocked.value):
            raise AppError('VALIDATION_ERROR','Only available or blocked status can be set by this endpoint.',422)
        x.status=InventoryStatus(status)
    x.version += 1
    audit(session,admin,'update','cabin_inventory',x.id,data); await session.commit(); return {'message':'Inventory updated.','version':x.version}


@router.patch('/sailings/{sailing_id}/cabins/{cabin_id}/unblock')
async def unblock(sailing_id:str,cabin_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.scalar(select(CabinInventory).where(CabinInventory.sailing_id==sailing_id,CabinInventory.cabin_id==cabin_id).with_for_update())
    if not x: raise AppError('NOT_FOUND','Inventory row not found.',404)
    if x.status != InventoryStatus.blocked: raise AppError('VALIDATION_ERROR','Cabin is not blocked.',409)
    x.status=InventoryStatus.available; x.version += 1; audit(session,admin,'unblock','cabin_inventory',x.id,{'sailing_id':sailing_id,'cabin_id':cabin_id}); await session.commit(); return {'message':'Cabin unblocked.','version':x.version}


@router.patch('/sailings/{sailing_id}/cabins/{cabin_id}/block')
async def block(sailing_id:str,cabin_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.scalar(select(CabinInventory).where(CabinInventory.sailing_id==sailing_id,CabinInventory.cabin_id==cabin_id).with_for_update())
    if not x: raise AppError('NOT_FOUND','Inventory row not found.',404)
    if x.status in (InventoryStatus.booked,InventoryStatus.held): raise AppError('CABIN_UNAVAILABLE','Booked/held cabins cannot be blocked.',409)
    x.status=InventoryStatus.blocked; x.version += 1; audit(session,admin,'block','cabin_inventory',x.id,{'sailing_id':sailing_id,'cabin_id':cabin_id}); await session.commit(); return {'message':'Cabin blocked.','version':x.version}


