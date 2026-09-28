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


router = APIRouter(prefix='/admin', tags=['Admin - Cruises'])

from app.api.admin.helpers import audit, fanout_new_cruise
from app.services.partner_validation import validate_cruise_bookability

@router.get('/cruises')
async def admin_cruises(admin=Depends(require_admin), session=Depends(get_session)):
    rows = (await session.scalars(select(Cruise).where(Cruise.deleted_at.is_(None)).order_by(Cruise.created_at.desc()))).all()
    return [{'id': str(x.id), 'name': x.name, 'slug': x.slug, 'description': x.description,
             'status': x.status.value, 'approval_status': x.approval_status.value,
             'base_price_cents': x.base_price_cents, 'sailing_days': x.sailing_days,
             'ship_id': str(x.ship_id), 'embark_port_id': str(x.embark_port_id),
             'disembark_port_id': str(x.disembark_port_id), 'is_featured': x.is_featured,
             'partner_id': str(x.partner_id) if x.partner_id else None} for x in rows]


@router.post('/cruises')
async def create_cruise(data:CruiseCreate,admin=Depends(require_admin),session=Depends(get_session)):
    x=Cruise(**{**data.model_dump(), 'ship_id':uuid.UUID(data.ship_id),'embark_port_id':uuid.UUID(data.embark_port_id),'disembark_port_id':uuid.UUID(data.disembark_port_id),'created_by':admin.id}); session.add(x); await session.flush(); audit(session,admin,'create','cruise',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.patch('/cruises/{id}')
async def patch_cruise(id:str,data:CruisePatch,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.get(Cruise,id); 
    if not x: raise AppError('NOT_FOUND','Cruise not found.',404)
    values = data.model_dump(exclude_none=True)
    for key in ('ship_id', 'embark_port_id', 'disembark_port_id'):
        if key in values:
            try:
                values[key] = uuid.UUID(values[key])
            except ValueError as exc:
                raise AppError('VALIDATION_ERROR', f'Invalid {key} identifier.', 422) from exc
    for k, v in values.items():
        setattr(x, k, v)
    audit(session, admin, 'update', 'cruise', x.id, values)
    await session.commit()
    return {'message': 'Updated.'}


@router.post('/cruises/{id}/publish')
async def publish(id:str, background_tasks: BackgroundTasks, admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.get(Cruise,id)
    if not x: raise AppError('NOT_FOUND','Cruise not found.',404)
    missing=await validate_cruise_bookability(x,session,require_commission=bool(x.partner_id))
    if missing:
        raise AppError('VALIDATION_ERROR',f'Cruise is not ready for publishing. Missing: {", ".join(missing)}.',422,{'missing':missing})
    x.status=CruiseStatus.published; x.approval_status=ApprovalStatus.approved; audit(session,admin,'publish','cruise',x.id); await session.commit()
    cache=await get_redis()
    if cache: await cache.delete('featured_cruises:v1')
    background_tasks.add_task(fanout_new_cruise, x.id, x.name, x.slug)
    return {'message':'Published.'}


@router.post('/cruises/{id}/archive')
async def archive(id:str,admin=Depends(require_admin),session=Depends(get_session)):
    x=await session.get(Cruise,id); 
    if not x: raise AppError('NOT_FOUND','Cruise not found.',404)
    x.status=CruiseStatus.archived; x.deleted_at=datetime.now(timezone.utc); audit(session,admin,'archive','cruise',x.id); await session.commit(); return {'message':'Archived.'}


@router.post('/cruises/{id}/images/presign')
async def presign_image(id: str, data: dict, admin=Depends(require_admin), session=Depends(get_session)):
    """Return a short-lived object-storage PUT URL; image bytes never pass through FastAPI."""
    cruise = await session.get(Cruise, id)
    if not cruise or cruise.deleted_at is not None:
        raise AppError('NOT_FOUND', 'Cruise not found.', 404)
    content_type = str(data.get('content_type', 'image/jpeg')).lower()
    allowed = {'image/jpeg','image/png','image/webp'}
    if content_type not in allowed:
        raise AppError('VALIDATION_ERROR', 'Only JPEG, PNG and WebP images are supported.', 422)
    import secrets
    from app.services.storage_service import presign_put
    key = f"cruises/{cruise.id}/{secrets.token_hex(16)}"
    url = presign_put(key, content_type=content_type)
    if not url:
        raise AppError('INTERNAL_ERROR', 'Object storage is not configured.', 503)
    return {'upload_url': url, 'key': key, 'content_type': content_type}


@router.post('/cruises/{id}/images')
async def image(id:str,data:ImageCreate,admin=Depends(require_admin),session=Depends(get_session)): x=CruiseImage(cruise_id=id,**data.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','cruise_image',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.put('/cruises/{id}/itinerary')
async def itinerary(id:str,data:list[ItineraryItem],admin=Depends(require_admin),session=Depends(get_session)):
    await session.execute(__import__('sqlalchemy').delete(CruiseItinerary).where(CruiseItinerary.cruise_id==id))
    for i in data: session.add(CruiseItinerary(cruise_id=id,**i.model_dump()))
    audit(session,admin,'replace','cruise_itinerary',uuid.UUID(id),{'items':[i.model_dump() for i in data]}); await session.commit(); return {'message':'Itinerary replaced.'}


@router.delete('/cruises/{id}')
async def delete_cruise(id: str, admin=Depends(require_admin), session=Depends(get_session)):
    cruise = await session.get(Cruise, id)
    if not cruise or cruise.deleted_at is not None: raise AppError('NOT_FOUND', 'Cruise not found.', 404)
    confirmed = await session.scalar(select(func.count()).select_from(Booking).join(Sailing, Sailing.id == Booking.sailing_id).where(Sailing.cruise_id == cruise.id, Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested])))
    if confirmed: raise AppError('VALIDATION_ERROR', 'A cruise with confirmed bookings cannot be deleted.', 409)
    cruise.deleted_at = datetime.now(timezone.utc); cruise.status = CruiseStatus.archived
    audit(session, admin, 'soft_delete', 'cruise', cruise.id); await session.commit(); return {'message': 'Cruise deleted.'}


