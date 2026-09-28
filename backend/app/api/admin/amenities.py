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


router = APIRouter(prefix='/admin', tags=['Admin - Amenities'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.post('/amenities')
async def create_amenity(data: dict, admin=Depends(require_admin), session=Depends(get_session)):
    if not data.get('name'): raise AppError('VALIDATION_ERROR', 'Amenity name is required.', 422)
    x = Amenity(name=data['name'].strip(), icon_key=data.get('icon_key'), category=data.get('category')); session.add(x); await session.flush(); audit(session, admin, 'create', 'amenity', x.id, data); await session.commit(); return {'id': str(x.id)}


@router.get('/amenities')
async def admin_amenities(admin=Depends(require_admin), session=Depends(get_session)):
    return [{'id': str(x.id), 'name': x.name, 'icon_key': x.icon_key, 'category': x.category} for x in (await session.scalars(select(Amenity).order_by(Amenity.name))).all()]


@router.delete('/amenities/{id}')
async def delete_amenity(id: str, admin=Depends(require_admin), session=Depends(get_session)):
    x = await session.get(Amenity, id)
    if not x: raise AppError('NOT_FOUND', 'Amenity not found.', 404)
    await session.delete(x); audit(session, admin, 'delete', 'amenity', x.id); await session.commit(); return {'message': 'Deleted.'}




@router.patch('/amenities/{id}')
async def patch_amenity(id: str, data: dict, admin=Depends(require_admin), session=Depends(get_session)):
    x = await session.get(Amenity, id)
    if not x:
        raise AppError('NOT_FOUND', 'Amenity not found.', 404)
    if not str(data.get('name', x.name)).strip():
        raise AppError('VALIDATION_ERROR', 'Amenity name is required.', 422)
    x.name = str(data.get('name', x.name)).strip()
    x.icon_key = data.get('icon_key', x.icon_key)
    x.category = data.get('category', x.category)
    audit(session, admin, 'update', 'amenity', x.id, data)
    await session.commit()
    return {'message': 'Updated.'}
