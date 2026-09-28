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


router = APIRouter(prefix='/admin', tags=['Admin - Ports'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.get('/ports')
async def ports(admin=Depends(require_admin),session=Depends(get_session)): return [{'id':str(x.id),'name':x.name,'city':x.city,'country':x.country,'code':x.code,'timezone':x.timezone} for x in (await session.scalars(select(Port).order_by(Port.name))).all()]


@router.post('/ports')
async def port(data:PortCreate,admin=Depends(require_admin),session=Depends(get_session)): x=Port(**data.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','port',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.patch('/ports/{id}')
async def patch_port(id: str, data: PortCreate, admin=Depends(require_admin), session=Depends(get_session)):
    port = await session.get(Port, id)
    if not port: raise AppError('NOT_FOUND', 'Port not found.', 404)
    for k, v in data.model_dump().items(): setattr(port, k, v)
    audit(session, admin, 'update', 'port', port.id, data.model_dump()); await session.commit(); return {'message': 'Updated.'}


@router.delete('/ports/{id}')
async def delete_port(id: str, admin=Depends(require_admin), session=Depends(get_session)):
    port = await session.get(Port, id)
    if not port: raise AppError('NOT_FOUND', 'Port not found.', 404)
    used = await session.scalar(select(func.count()).select_from(Cruise).where((Cruise.embark_port_id == port.id) | (Cruise.disembark_port_id == port.id)))
    if used: raise AppError('VALIDATION_ERROR', 'Port is used by a cruise and cannot be deleted.', 409)
    await session.delete(port); audit(session, admin, 'delete', 'port', port.id); await session.commit(); return {'message': 'Deleted.'}


