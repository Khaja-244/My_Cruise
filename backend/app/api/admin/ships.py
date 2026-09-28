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


router = APIRouter(prefix='/admin', tags=['Admin - Ships'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.get('/ships')
async def ships(admin=Depends(require_admin),session=Depends(get_session)): return [{'id':str(x.id),'name':x.name,'operator_name':x.operator_name,'deck_count':x.deck_count,'description':x.description} for x in (await session.scalars(select(Ship).where(Ship.deleted_at.is_(None)).order_by(Ship.name))).all()]


@router.post('/ships')
async def ship(data:ShipCreate,admin=Depends(require_admin),session=Depends(get_session)): x=Ship(**data.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','ship',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.get('/ships/{ship_id}/decks')
async def list_decks(ship_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    return [{'id':str(x.id),'deck_number':x.deck_number,'name':x.name} for x in (await session.scalars(select(Deck).where(Deck.ship_id==ship_id).order_by(Deck.deck_number))).all()]


@router.get('/ships/{ship_id}/cabins')
async def list_cabins(ship_id:str,admin=Depends(require_admin),session=Depends(get_session)):
    rows=(await session.execute(select(Cabin,Deck,CabinType).join(Deck,Deck.id==Cabin.deck_id).join(CabinType,CabinType.id==Cabin.cabin_type_id).where(Cabin.ship_id==ship_id).order_by(Deck.deck_number,Cabin.cabin_number))).all()
    return [{'id':str(c.id),'deck_id':str(c.deck_id),'deck_number':d.deck_number,'cabin_type_id':str(c.cabin_type_id),'cabin_type_name':ct.name,'cabin_number':c.cabin_number,'max_occupancy':c.max_occupancy,'is_active':c.is_active} for c,d,ct in rows]


@router.post('/ships/{ship_id}/decks')
async def deck(ship_id:str,data:DeckCreate,admin=Depends(require_admin),session=Depends(get_session)): x=Deck(ship_id=ship_id,**data.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','deck',x.id,data.model_dump()); await session.commit(); return {'id':str(x.id)}


@router.post('/ships/{ship_id}/cabins')
async def cabins(ship_id:str,data:list[CabinCreate],admin=Depends(require_admin),session=Depends(get_session)):
    created=[]
    for item in data:
        x=Cabin(ship_id=ship_id,**item.model_dump()); session.add(x); await session.flush(); audit(session,admin,'create','cabin',x.id,item.model_dump()); created.append(x.id)
    await session.commit(); return {'created':len(created)}


@router.delete('/ships/{id}')
async def delete_ship(id: str, admin=Depends(require_admin), session=Depends(get_session)):
    ship = await session.get(Ship, id)
    if not ship or ship.deleted_at is not None:
        raise AppError('NOT_FOUND', 'Ship not found.', 404)
    confirmed = await session.scalar(select(func.count()).select_from(Booking).join(Sailing, Sailing.id == Booking.sailing_id).join(Cruise, Cruise.id == Sailing.cruise_id).where(Cruise.ship_id == ship.id, Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested])))
    if confirmed:
        raise AppError('VALIDATION_ERROR', 'A ship with confirmed bookings cannot be deleted.', 409)
    ship.deleted_at = datetime.now(timezone.utc); ship.is_active = False
    audit(session, admin, 'soft_delete', 'ship', ship.id)
    await session.commit()
    return {'message': 'Ship deleted.'}


@router.patch('/ships/{id}')
async def patch_ship(id: str, data: ShipCreate, admin=Depends(require_admin), session=Depends(get_session)):
    ship = await session.get(Ship, id)
    if not ship or ship.deleted_at is not None: raise AppError('NOT_FOUND', 'Ship not found.', 404)
    for k, v in data.model_dump().items(): setattr(ship, k, v)
    audit(session, admin, 'update', 'ship', ship.id, data.model_dump()); await session.commit()
    return {'message': 'Updated.'}




@router.patch('/ships/{ship_id}/decks/{deck_id}')
async def patch_deck(ship_id: str, deck_id: str, data: DeckUpdate, admin=Depends(require_admin), session=Depends(get_session)):
    deck = await session.scalar(select(Deck).where(Deck.id == deck_id, Deck.ship_id == ship_id))
    if not deck:
        raise AppError('NOT_FOUND', 'Deck not found.', 404)
    values = data.model_dump(exclude_none=True)
    if 'deck_number' in values:
        duplicate = await session.scalar(
            select(Deck).where(
                Deck.ship_id == ship_id,
                Deck.deck_number == values['deck_number'],
                Deck.id != deck.id,
            )
        )
        if duplicate:
            raise AppError('VALIDATION_ERROR', 'That deck number already exists on this ship.', 409)
    for key, value in values.items():
        setattr(deck, key, value)
    audit(session, admin, 'update', 'deck', deck.id, values)
    await session.commit()
    return {'message': 'Deck updated.'}


@router.delete('/ships/{ship_id}/decks/{deck_id}')
async def delete_deck(ship_id: str, deck_id: str, admin=Depends(require_admin), session=Depends(get_session)):
    deck = await session.scalar(select(Deck).where(Deck.id == deck_id, Deck.ship_id == ship_id))
    if not deck:
        raise AppError('NOT_FOUND', 'Deck not found.', 404)
    cabin_count = await session.scalar(select(func.count()).select_from(Cabin).where(Cabin.deck_id == deck.id, Cabin.is_active.is_(True)))
    if cabin_count:
        raise AppError('VALIDATION_ERROR', 'Remove or deactivate the cabins on this deck before deleting it.', 409)
    await session.delete(deck)
    audit(session, admin, 'delete', 'deck', deck.id)
    await session.commit()
    return {'message': 'Deck deleted.'}


@router.patch('/ships/{ship_id}/cabins/{cabin_id}')
async def patch_cabin(ship_id: str, cabin_id: str, data: CabinUpdate, admin=Depends(require_admin), session=Depends(get_session)):
    cabin = await session.scalar(select(Cabin).where(Cabin.id == cabin_id, Cabin.ship_id == ship_id))
    if not cabin:
        raise AppError('NOT_FOUND', 'Cabin not found.', 404)

    confirmed = await session.scalar(
        select(func.count())
        .select_from(BookingCabin)
        .join(Booking, Booking.id == BookingCabin.booking_id)
        .where(
            BookingCabin.cabin_id == cabin.id,
            Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested]),
        )
    )
    if confirmed:
        raise AppError('VALIDATION_ERROR', 'A cabin with confirmed bookings cannot be changed.', 409)

    values = data.model_dump(exclude_none=True)
    if 'deck_id' in values:
        deck = await session.scalar(select(Deck).where(Deck.id == values['deck_id'], Deck.ship_id == ship_id))
        if not deck:
            raise AppError('NOT_FOUND', 'Target deck not found on this ship.', 404)
    if 'cabin_type_id' in values:
        if not await session.scalar(select(CabinType).where(CabinType.id == values['cabin_type_id'])):
            raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    if 'cabin_number' in values:
        duplicate = await session.scalar(
            select(Cabin).where(
                Cabin.ship_id == ship_id,
                Cabin.cabin_number == values['cabin_number'],
                Cabin.id != cabin.id,
            )
        )
        if duplicate:
            raise AppError('VALIDATION_ERROR', 'That cabin number already exists on this ship.', 409)
    for key, value in values.items():
        setattr(cabin, key, value)
    audit(session, admin, 'update', 'cabin', cabin.id, values)
    await session.commit()
    return {'message': 'Cabin updated.'}


@router.delete('/ships/{ship_id}/cabins/{cabin_id}')
async def delete_cabin(ship_id: str, cabin_id: str, admin=Depends(require_admin), session=Depends(get_session)):
    cabin = await session.scalar(select(Cabin).where(Cabin.id == cabin_id, Cabin.ship_id == ship_id))
    if not cabin:
        raise AppError('NOT_FOUND', 'Cabin not found.', 404)

    active_booking = await session.scalar(
        select(func.count())
        .select_from(BookingCabin)
        .join(Booking, Booking.id == BookingCabin.booking_id)
        .where(
            BookingCabin.cabin_id == cabin.id,
            Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested]),
        )
    )
    held = await session.scalar(
        select(func.count()).select_from(CabinInventory).where(
            CabinInventory.cabin_id == cabin.id,
            CabinInventory.status == InventoryStatus.held,
        )
    )
    if active_booking or held:
        raise AppError('VALIDATION_ERROR', 'This cabin has an active booking or hold and cannot be deleted.', 409)

    cabin.is_active = False
    audit(session, admin, 'soft_delete', 'cabin', cabin.id)
    await session.commit()
    return {'message': 'Cabin deactivated.'}
