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


router = APIRouter(prefix='/admin', tags=['Admin - Cabin Types'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.get('/cabin-types')
async def all_cabin_types(admin=Depends(require_admin),session=Depends(get_session)):
    rows=(await session.execute(select(CabinType,Cruise).join(Cruise,Cruise.id==CabinType.cruise_id).where(Cruise.deleted_at.is_(None)).order_by(Cruise.name,CabinType.name))).all()
    return [{'id':str(x.id),'cruise_id':str(c.id),'cruise_name':c.name,'name':x.name,'max_occupancy':x.max_occupancy,'base_price_cents':x.base_price_cents,'price_per_extra_guest_cents':x.price_per_extra_guest_cents} for x,c in rows]


@router.get('/cruises/{id}/cabin-types')
async def types(id:str,admin=Depends(require_admin),session=Depends(get_session)): return [{'id':str(x.id),'name':x.name,'max_occupancy':x.max_occupancy,'base_price_cents':x.base_price_cents,'price_per_extra_guest_cents':x.price_per_extra_guest_cents} for x in (await session.scalars(select(CabinType).where(CabinType.cruise_id==id))).all()]


@router.post('/cruises/{id}/cabin-types')
async def type_create(id:str,data:CabinTypeCreate,admin=Depends(require_admin),session=Depends(get_session)): x=CabinType(cruise_id=id,**data.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','cabin_type',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.patch('/cruises/{id}/cabin-types/{ct_id}')
async def type_patch(id: str, ct_id: str, data: CabinTypeCreate, admin=Depends(require_admin), session=Depends(get_session)):
    x = await session.scalar(select(CabinType).where(CabinType.id == ct_id, CabinType.cruise_id == id))
    if not x: raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    for key, value in data.model_dump().items(): setattr(x, key, value)
    audit(session, admin, 'update', 'cabin_type', x.id, data.model_dump())
    await session.commit()
    return {'message': 'Updated.'}


@router.delete('/cruises/{id}/cabin-types/{ct_id}')
async def delete_cabin_type(id: str, ct_id: str, admin=Depends(require_admin), session=Depends(get_session)):
    ct = await session.scalar(select(CabinType).where(CabinType.id == ct_id, CabinType.cruise_id == id))
    if not ct: raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    used = await session.scalar(select(func.count()).select_from(Cabin).where(Cabin.cabin_type_id == ct.id))
    if used: raise AppError('VALIDATION_ERROR', 'Cabin type is assigned to physical cabins.', 409)
    await session.delete(ct); audit(session, admin, 'delete', 'cabin_type', ct.id); await session.commit(); return {'message': 'Deleted.'}


@router.put('/cruises/{id}/cabin-types/{ct_id}/amenities')
async def replace_amenities(id: str, ct_id: str, amenity_ids: list[str], admin=Depends(require_admin), session=Depends(get_session)):
    ct = await session.scalar(select(CabinType).where(CabinType.id == ct_id, CabinType.cruise_id == id))
    if not ct: raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    ids = [uuid.UUID(x) for x in amenity_ids]
    found = (await session.scalars(select(Amenity).where(Amenity.id.in_(ids)))).all()
    if len(found) != len(set(ids)): raise AppError('NOT_FOUND', 'One or more amenities were not found.', 404)
    await session.execute(__import__('sqlalchemy').delete(CabinTypeAmenity).where(CabinTypeAmenity.cabin_type_id == ct.id))
    for aid in ids: session.add(CabinTypeAmenity(cabin_type_id=ct.id, amenity_id=aid))
    audit(session, admin, 'replace', 'cabin_type_amenities', ct.id, {'amenity_ids': amenity_ids}); await session.commit(); return {'message': 'Amenities updated.'}


