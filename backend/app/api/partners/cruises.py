import secrets

import uuid

from datetime import datetime, timezone, time, timedelta

from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Header

from sqlalchemy import select, delete, func

from app.core.database import get_session

from app.core.deps import get_current_user, require_admin

from app.core.exceptions import AppError

from app.core.partner_auth import require_partner_api_key, generate_partner_api_key

from app.core.security import hash_password, validate_password_strength

from app.models import *

from app.schemas.partner import *

from app.services.email_service import send_email

from app.services.booking_service import hold_booking
from app.services.partner_validation import validate_cruise_bookability
from app.services.email_service import send_email, wrap_email


router = APIRouter(prefix='/partners', tags=['Partner Management'])

from app.api.partners.helpers import partner_for_user, owned_cruise

@router.post('/cruises')
async def create_cruise(data: PartnerCruiseCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session)
    values = data.model_dump(exclude={'ship_id', 'ship_name', 'operator_name', 'start_sailing_date', 'return_date'})
    try:
        ship = await session.get(Ship, uuid.UUID(data.ship_id)) if data.ship_id else None
        if ship:
            if ship.deleted_at is not None or not ship.is_active:
                raise AppError('NOT_FOUND', 'Ship not found.', 404)
            if ship.partner_id != p.id:
                raise AppError('FORBIDDEN', 'You can only use a ship owned by your partner account.', 403)
        else:
            if not data.ship_name: raise AppError('VALIDATION_ERROR', 'ship_name is required when ship_id is omitted.', 422)
            ship = Ship(name=data.ship_name, operator_name=data.operator_name or p.business_name, deck_count=1, owner_type='partner', partner_id=p.id)
            session.add(ship); await session.flush()
        for field in ('embark_port_id', 'disembark_port_id'):
            values[field] = uuid.UUID(values[field])
        values['ship_id'] = ship.id
    except ValueError as exc:
        raise AppError('VALIDATION_ERROR', 'One or more identifiers are invalid.', 422) from exc
    if (data.start_sailing_date is None) != (data.return_date is None):
        raise AppError('VALIDATION_ERROR', 'Start sailing date and return date must be provided together.', 422)
    if data.start_sailing_date and data.return_date < data.start_sailing_date:
        raise AppError('VALIDATION_ERROR', 'Return date cannot be before start sailing date.', 422)

    x = Cruise(**values, partner_id=p.id, created_by=user.id, owner_type='partner', approval_status=ApprovalStatus.pending, status=CruiseStatus.draft)
    session.add(x); await session.flush()

    # The mail requires start/return dates to be real cruise data, not just UI fields.
    # Create the initial sailing immediately when those dates are supplied. Inventory
    # rows are generated later as the partner adds physical cabins.
    if data.start_sailing_date and data.return_date:
        closes = datetime.combine(data.start_sailing_date - timedelta(days=1), time(23, 59), tzinfo=timezone.utc)
        session.add(Sailing(
            cruise_id=x.id,
            departure_date=data.start_sailing_date,
            return_date=data.return_date,
            booking_closes_at=closes,
            port_fee_per_guest_cents=0,
            status=SailingStatus.scheduled,
        ))
    await session.commit()
    return {'id': str(x.id), 'approval_status': 'pending', 'initial_sailing_created': bool(data.start_sailing_date)}


@router.get('/cruises/pending', dependencies=[Depends(require_admin)])
async def pending_cruises_early(session=Depends(get_session), admin=Depends(require_admin)):
    rows=(await session.scalars(select(Cruise).where(Cruise.partner_id.is_not(None),Cruise.approval_status.in_([ApprovalStatus.pending,ApprovalStatus.rejected]),Cruise.deleted_at.is_(None)).order_by(Cruise.created_at))).all()
    return [{'id':str(x.id),'partner_id':str(x.partner_id),'name':x.name,'slug':x.slug,'base_price_cents':x.base_price_cents,'approval_status':x.approval_status.value,'status':x.status.value,'commission_type':x.commission_type.value if x.commission_type else None,'commission_value':float(x.commission_value) if x.commission_value is not None else None} for x in rows]


@router.get('/cruises/{cruise_id}')
async def get_owned_cruise(cruise_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    decks = (await session.scalars(select(Deck).where(Deck.ship_id == c.ship_id).order_by(Deck.deck_number))).all()
    types = (await session.scalars(select(CabinType).where(CabinType.cruise_id == c.id).order_by(CabinType.name))).all()
    images = (await session.scalars(select(CruiseImage).where(CruiseImage.cruise_id == c.id).order_by(CruiseImage.sort_order))).all()
    sailings = (await session.scalars(select(Sailing).where(Sailing.cruise_id == c.id).order_by(Sailing.departure_date))).all()
    cabins = (await session.execute(
        select(Cabin, Deck, CabinType)
        .join(Deck, Deck.id == Cabin.deck_id)
        .join(CabinType, CabinType.id == Cabin.cabin_type_id)
        .where(Cabin.ship_id == c.ship_id, CabinType.cruise_id == c.id, Cabin.is_active.is_(True))
        .order_by(Deck.deck_number, Cabin.cabin_number)
    )).all()
    amenity_rows = (await session.execute(
        select(CabinTypeAmenity.cabin_type_id, Amenity)
        .join(Amenity, Amenity.id == CabinTypeAmenity.amenity_id)
        .where(CabinTypeAmenity.cabin_type_id.in_([t.id for t in types]))
    )).all() if types else []
    amenities_by_type = {}
    for type_id, amenity in amenity_rows:
        amenities_by_type.setdefault(type_id, []).append({'id': str(amenity.id), 'name': amenity.name, 'icon_key': amenity.icon_key, 'category': amenity.category})
    return {'id': str(c.id), 'name': c.name, 'slug': c.slug, 'description': c.description, 'ship_id': str(c.ship_id), 'approval_status': c.approval_status.value, 'status': c.status.value,
            'decks': [{'id': str(d.id), 'deck_number': d.deck_number, 'name': d.name} for d in decks],
            'cabin_types': [{'id': str(t.id), 'name': t.name, 'description': t.description, 'max_occupancy': t.max_occupancy, 'base_price_cents': t.base_price_cents, 'price_per_extra_guest_cents': t.price_per_extra_guest_cents, 'amenities': amenities_by_type.get(t.id, [])} for t in types],
            'cabins': [{'id': str(cab.id), 'deck_id': str(cab.deck_id), 'deck_name': deck.name, 'cabin_type_id': str(cab.cabin_type_id), 'cabin_type_name': ct.name, 'cabin_number': cab.cabin_number, 'max_occupancy': cab.max_occupancy} for cab, deck, ct in cabins],
            'images': [{'id': str(i.id), 'url': i.url, 'alt_text': i.alt_text, 'is_cover': i.is_cover, 'sort_order': i.sort_order} for i in images],
            'sailings': [{'id': str(s.id), 'departure_date': s.departure_date, 'return_date': s.return_date, 'booking_closes_at': s.booking_closes_at, 'status': s.status.value} for s in sailings]}


@router.patch('/cruises/{cruise_id}')
async def update_cruise(cruise_id: str, data: PartnerCruiseUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    values = data.model_dump(exclude_none=True)
    start_date = values.pop('start_sailing_date', None)
    return_date = values.pop('return_date', None)
    try:
        if 'embark_port_id' in values: values['embark_port_id'] = uuid.UUID(values['embark_port_id'])
        if 'disembark_port_id' in values: values['disembark_port_id'] = uuid.UUID(values['disembark_port_id'])
    except ValueError as exc: raise AppError('VALIDATION_ERROR', 'Invalid port identifier.', 422) from exc
    if (start_date is None) != (return_date is None):
        raise AppError('VALIDATION_ERROR', 'Start sailing date and return date must be provided together.', 422)
    if start_date and return_date < start_date:
        raise AppError('VALIDATION_ERROR', 'Return date cannot be before start sailing date.', 422)
    for k,v in values.items(): setattr(c,k,v)
    if start_date and return_date:
        sailing = await session.scalar(select(Sailing).where(Sailing.cruise_id == c.id).order_by(Sailing.departure_date).limit(1))
        if sailing:
            locked = await session.scalar(select(func.count()).select_from(CabinInventory).where(CabinInventory.sailing_id == sailing.id, CabinInventory.status.in_([InventoryStatus.held, InventoryStatus.booked])))
            if locked:
                raise AppError('CABIN_UNAVAILABLE', 'The first sailing has held/booked inventory and its dates cannot be changed.', 409)
            sailing.departure_date = start_date
            sailing.return_date = return_date
            sailing.booking_closes_at = datetime.combine(start_date - timedelta(days=1), time(23,59), tzinfo=timezone.utc)
        else:
            closes = datetime.combine(start_date - timedelta(days=1), time(23,59), tzinfo=timezone.utc)
            session.add(Sailing(cruise_id=c.id, departure_date=start_date, return_date=return_date, booking_closes_at=closes, port_fee_per_guest_cents=0, status=SailingStatus.scheduled))
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Cruise updated and resubmitted for approval.', 'approval_status': c.approval_status.value}


@router.delete('/cruises/{cruise_id}')
async def delete_owned(cruise_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session)
    c = await owned_cruise(cruise_id, p, session)
    confirmed = await session.scalar(
        select(func.count()).select_from(Booking)
        .join(Sailing, Sailing.id == Booking.sailing_id)
        .where(
            Sailing.cruise_id == c.id,
            Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested]),
        )
    )
    if confirmed:
        raise AppError('VALIDATION_ERROR', 'A cruise with confirmed bookings cannot be deleted.', 409)
    c.deleted_at = datetime.now(timezone.utc)
    c.status = CruiseStatus.archived
    await session.commit()
    return {'message': 'Cruise removed.'}


@router.post('/cruises/{cruise_id}/decks')
async def add_deck(cruise_id: str, data: PartnerDeckCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    d=Deck(ship_id=c.ship_id,deck_number=data.deck_number,name=data.name); session.add(d); c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'id':str(d.id)}


@router.post('/cruises/{cruise_id}/cabin-types')
async def add_cabin_type(cruise_id: str, data: PartnerCabinTypeCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    x=CabinType(cruise_id=c.id,name=data.name,description=data.description,max_occupancy=data.max_occupancy,base_price_cents=data.base_price_cents,price_per_extra_guest_cents=data.price_per_extra_guest_cents); session.add(x); await session.flush()
    for aid in data.amenity_ids:
        try: session.add(CabinTypeAmenity(cabin_type_id=x.id,amenity_id=uuid.UUID(aid)))
        except ValueError: raise AppError('VALIDATION_ERROR','Invalid amenity identifier.',422)
    c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'id':str(x.id)}


@router.post('/cruises/{cruise_id}/cabins')
async def add_cabin(cruise_id: str, data: PartnerCabinCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    deck=await session.scalar(select(Deck).where(Deck.id==uuid.UUID(data.deck_id),Deck.ship_id==c.ship_id))
    ct=await session.scalar(select(CabinType).where(CabinType.id==uuid.UUID(data.cabin_type_id),CabinType.cruise_id==c.id))
    if not deck or not ct: raise AppError('NOT_FOUND','Deck or cabin type does not belong to this cruise.',404)
    x=Cabin(ship_id=c.ship_id,deck_id=deck.id,cabin_type_id=ct.id,cabin_number=data.cabin_number,max_occupancy=data.max_occupancy); session.add(x); await session.flush()
    active_sailings=(await session.scalars(select(Sailing).where(Sailing.cruise_id==c.id,Sailing.status.in_([SailingStatus.scheduled,SailingStatus.open])))).all()
    for sailing in active_sailings:
        exists=await session.scalar(select(CabinInventory.id).where(CabinInventory.sailing_id==sailing.id,CabinInventory.cabin_id==x.id))
        if not exists:
            session.add(CabinInventory(sailing_id=sailing.id,cabin_id=x.id,price_cents=ct.base_price_cents,status=InventoryStatus.available))
    c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'id':str(x.id),'inventory_rows_created':len(active_sailings)}



@router.patch('/cruises/{cruise_id}/decks/{deck_id}')
async def update_deck(cruise_id: str, deck_id: str, data: PartnerDeckUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    deck = await session.scalar(select(Deck).where(Deck.id == deck_id, Deck.ship_id == c.ship_id))
    if not deck: raise AppError('NOT_FOUND', 'Deck not found.', 404)
    values = data.model_dump(exclude_none=True)
    if 'deck_number' in values:
        duplicate = await session.scalar(select(Deck).where(Deck.ship_id == c.ship_id, Deck.deck_number == values['deck_number'], Deck.id != deck.id))
        if duplicate: raise AppError('VALIDATION_ERROR', 'That deck number already exists.', 409)
    for k, v in values.items(): setattr(deck, k, v)
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Deck updated and cruise resubmitted for approval.'}

@router.delete('/cruises/{cruise_id}/decks/{deck_id}')
async def delete_deck(cruise_id: str, deck_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    deck = await session.scalar(select(Deck).where(Deck.id == deck_id, Deck.ship_id == c.ship_id))
    if not deck: raise AppError('NOT_FOUND', 'Deck not found.', 404)
    cabins = await session.scalar(select(func.count()).select_from(Cabin).where(Cabin.deck_id == deck.id, Cabin.is_active.is_(True)))
    if cabins: raise AppError('VALIDATION_ERROR', 'Remove or deactivate cabins on this deck before deleting it.', 409)
    await session.delete(deck); c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Deck deleted.'}

@router.patch('/cruises/{cruise_id}/cabin-types/{cabin_type_id}')
async def update_cabin_type(cruise_id: str, cabin_type_id: str, data: PartnerCabinTypeUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    ct = await session.scalar(select(CabinType).where(CabinType.id == cabin_type_id, CabinType.cruise_id == c.id))
    if not ct: raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    linked = await session.scalar(select(func.count()).select_from(CabinInventory).join(Cabin, Cabin.id == CabinInventory.cabin_id).where(Cabin.cabin_type_id == ct.id, CabinInventory.status.in_([InventoryStatus.held, InventoryStatus.booked])))
    if linked: raise AppError('CABIN_UNAVAILABLE', 'A cabin type with held/booked inventory cannot be changed.', 409)
    values = data.model_dump(exclude_none=True, exclude={'amenity_ids'})
    for k, v in values.items(): setattr(ct, k, v)
    if data.amenity_ids is not None:
        ids=[]
        for aid in data.amenity_ids:
            try: ids.append(uuid.UUID(aid))
            except ValueError as exc: raise AppError('VALIDATION_ERROR', 'Invalid amenity identifier.', 422) from exc
        if ids:
            valid=(await session.scalars(select(Amenity.id).where(Amenity.id.in_(ids)))).all()
            if len(valid) != len(set(ids)): raise AppError('NOT_FOUND', 'One or more amenities do not exist.', 404)
        await session.execute(delete(CabinTypeAmenity).where(CabinTypeAmenity.cabin_type_id == ct.id))
        for aid in ids: session.add(CabinTypeAmenity(cabin_type_id=ct.id, amenity_id=aid))
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Cabin type updated and cruise resubmitted for approval.'}

@router.delete('/cruises/{cruise_id}/cabin-types/{cabin_type_id}')
async def delete_cabin_type(cruise_id: str, cabin_type_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    ct = await session.scalar(select(CabinType).where(CabinType.id == cabin_type_id, CabinType.cruise_id == c.id))
    if not ct: raise AppError('NOT_FOUND', 'Cabin type not found.', 404)
    cabin_count = await session.scalar(select(func.count()).select_from(Cabin).where(Cabin.cabin_type_id == ct.id, Cabin.is_active.is_(True)))
    if cabin_count: raise AppError('VALIDATION_ERROR', 'Remove or deactivate physical cabins using this cabin type first.', 409)
    await session.execute(delete(CabinTypeAmenity).where(CabinTypeAmenity.cabin_type_id == ct.id))
    await session.delete(ct); c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Cabin type deleted.'}

@router.patch('/cruises/{cruise_id}/cabins/{cabin_id}')
async def update_cabin(cruise_id: str, cabin_id: str, data: PartnerCabinUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    cabin = await session.scalar(select(Cabin).where(Cabin.id == cabin_id, Cabin.ship_id == c.ship_id))
    if not cabin: raise AppError('NOT_FOUND', 'Cabin not found.', 404)
    locked = await session.scalar(select(func.count()).select_from(CabinInventory).where(CabinInventory.cabin_id == cabin.id, CabinInventory.status.in_([InventoryStatus.held, InventoryStatus.booked])))
    if locked: raise AppError('CABIN_UNAVAILABLE', 'A cabin with held/booked inventory cannot be changed.', 409)
    values = data.model_dump(exclude_none=True)
    if 'deck_id' in values:
        deck = await session.scalar(select(Deck).where(Deck.id == values['deck_id'], Deck.ship_id == c.ship_id))
        if not deck: raise AppError('NOT_FOUND', 'Target deck not found.', 404)
    if 'cabin_type_id' in values:
        ct = await session.scalar(select(CabinType).where(CabinType.id == values['cabin_type_id'], CabinType.cruise_id == c.id))
        if not ct: raise AppError('NOT_FOUND', 'Target cabin type not found.', 404)
    if 'cabin_number' in values:
        duplicate = await session.scalar(select(Cabin).where(Cabin.ship_id == c.ship_id, Cabin.cabin_number == values['cabin_number'], Cabin.id != cabin.id))
        if duplicate: raise AppError('VALIDATION_ERROR', 'That cabin number already exists.', 409)
    for k, v in values.items(): setattr(cabin, k, v)
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Cabin updated and cruise resubmitted for approval.'}

@router.delete('/cruises/{cruise_id}/cabins/{cabin_id}')
async def delete_cabin(cruise_id: str, cabin_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    cabin = await session.scalar(select(Cabin).where(Cabin.id == cabin_id, Cabin.ship_id == c.ship_id))
    if not cabin: raise AppError('NOT_FOUND', 'Cabin not found.', 404)
    locked = await session.scalar(select(func.count()).select_from(CabinInventory).where(CabinInventory.cabin_id == cabin.id, CabinInventory.status.in_([InventoryStatus.held, InventoryStatus.booked])))
    if locked: raise AppError('CABIN_UNAVAILABLE', 'A cabin with held/booked inventory cannot be deleted.', 409)
    cabin.is_active = False
    await session.execute(delete(CabinInventory).where(CabinInventory.cabin_id == cabin.id))
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Cabin removed.'}

@router.post('/cruises/{cruise_id}/images')
async def add_image(cruise_id: str, data: PartnerImageCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    x=CruiseImage(cruise_id=c.id,**data.model_dump()); session.add(x); c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'id':str(x.id)}


@router.post('/cruises/{cruise_id}/images/presign')
async def presign_partner_image(cruise_id: str, data: dict, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    content_type=str(data.get('content_type','image/jpeg')).lower()
    if content_type not in {'image/jpeg','image/png','image/webp'}: raise AppError('VALIDATION_ERROR','Only JPEG, PNG and WebP images are supported.',422)
    from app.services.storage_service import presign_put
    key=f'cruises/{c.id}/{secrets.token_hex(16)}'; url=presign_put(key,content_type=content_type)
    if not url: raise AppError('INTERNAL_ERROR','Object storage is not configured.',503)
    return {'upload_url':url,'key':key,'content_type':content_type}



@router.patch('/cruises/{cruise_id}/images/{image_id}')
async def update_image(cruise_id: str, image_id: str, data: PartnerImageUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    image = await session.scalar(select(CruiseImage).where(CruiseImage.id == image_id, CruiseImage.cruise_id == c.id))
    if not image: raise AppError('NOT_FOUND', 'Cruise image not found.', 404)
    values = data.model_dump(exclude_none=True)
    make_cover = values.get('is_cover') is True
    for k, v in values.items(): setattr(image, k, v)
    if make_cover:
        await session.execute(__import__('sqlalchemy').update(CruiseImage).where(CruiseImage.cruise_id == c.id, CruiseImage.id != image.id).values(is_cover=False))
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Image updated and cruise resubmitted for approval.'}

@router.delete('/cruises/{cruise_id}/images/{image_id}')
async def delete_image(cruise_id: str, image_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    image = await session.scalar(select(CruiseImage).where(CruiseImage.id == image_id, CruiseImage.cruise_id == c.id))
    if not image: raise AppError('NOT_FOUND', 'Cruise image not found.', 404)
    was_cover = image.is_cover
    await session.delete(image)
    await session.flush()
    if was_cover:
        replacement = await session.scalar(select(CruiseImage).where(CruiseImage.cruise_id == c.id).order_by(CruiseImage.sort_order, CruiseImage.id))
        if replacement: replacement.is_cover = True
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Image deleted.'}

@router.put('/cruises/{cruise_id}/itinerary')
async def replace_itinerary(cruise_id: str, data: list[PartnerItineraryItem], user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    await session.execute(delete(CruiseItinerary).where(CruiseItinerary.cruise_id==c.id))
    for item in data:
        vals=item.model_dump(); vals['cruise_id']=c.id; vals['port_id']=uuid.UUID(vals['port_id']) if vals['port_id'] else None
        for k in ('arrival_time','departure_time'):
            vals[k]=time.fromisoformat(vals[k]) if vals[k] else None
        session.add(CruiseItinerary(**vals))
    c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'message':'Itinerary saved and submitted for approval.'}


@router.post('/cruises/{cruise_id}/sailings')
async def add_sailing(cruise_id: str, data: PartnerSailingCreate, user=Depends(get_current_user), session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    if data.return_date < data.departure_date: raise AppError('VALIDATION_ERROR','Return date cannot be before departure.',422)
    try: closes=datetime.fromisoformat(data.booking_closes_at.replace('Z','+00:00'))
    except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid booking_closes_at datetime.',422) from exc
    s=Sailing(cruise_id=c.id,departure_date=data.departure_date,return_date=data.return_date,booking_closes_at=closes,port_fee_per_guest_cents=data.port_fee_per_guest_cents,status=SailingStatus.scheduled); session.add(s); await session.flush()
    cabins=(await session.scalars(select(Cabin).where(Cabin.ship_id==c.ship_id,Cabin.is_active.is_(True),Cabin.cabin_type_id.in_(select(CabinType.id).where(CabinType.cruise_id==c.id))))).all()
    cruise_types={x.id:x for x in (await session.scalars(select(CabinType).where(CabinType.cruise_id==c.id))).all()}
    for cab in cabins:
        target=cruise_types.get(cab.cabin_type_id)
        if not target:
            await session.rollback()
            raise AppError('VALIDATION_ERROR',f'Cabin {cab.cabin_number} uses a cabin type outside this cruise.',422)
        session.add(CabinInventory(sailing_id=s.id,cabin_id=cab.id,price_cents=target.base_price_cents,status=InventoryStatus.available))
    c.approval_status=ApprovalStatus.pending; c.status=CruiseStatus.draft; await session.commit(); return {'id':str(s.id),'inventory_generated':len(cabins)}



@router.patch('/cruises/{cruise_id}/sailings/{sailing_id}')
async def update_sailing(cruise_id: str, sailing_id: str, data: PartnerSailingUpdate, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    sailing = await session.scalar(select(Sailing).where(Sailing.id == sailing_id, Sailing.cruise_id == c.id))
    if not sailing: raise AppError('NOT_FOUND', 'Sailing not found.', 404)
    locked = await session.scalar(select(func.count()).select_from(CabinInventory).where(CabinInventory.sailing_id == sailing.id, CabinInventory.status.in_([InventoryStatus.held, InventoryStatus.booked])))
    if locked: raise AppError('CABIN_UNAVAILABLE', 'A sailing with held/booked inventory cannot be changed.', 409)
    values = data.model_dump(exclude_none=True)
    departure = values.get('departure_date', sailing.departure_date)
    ret = values.get('return_date', sailing.return_date)
    if ret < departure: raise AppError('VALIDATION_ERROR', 'Return date cannot be before departure.', 422)
    if 'booking_closes_at' in values:
        try: values['booking_closes_at'] = datetime.fromisoformat(values['booking_closes_at'].replace('Z','+00:00'))
        except ValueError as exc: raise AppError('VALIDATION_ERROR', 'Invalid booking_closes_at datetime.', 422) from exc
    for k, v in values.items(): setattr(sailing, k, v)
    c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Sailing updated and cruise resubmitted for approval.'}

@router.delete('/cruises/{cruise_id}/sailings/{sailing_id}')
async def delete_sailing(cruise_id: str, sailing_id: str, user=Depends(get_current_user), session=Depends(get_session)):
    p = await partner_for_user(user, session); c = await owned_cruise(cruise_id, p, session)
    sailing = await session.scalar(select(Sailing).where(Sailing.id == sailing_id, Sailing.cruise_id == c.id))
    if not sailing: raise AppError('NOT_FOUND', 'Sailing not found.', 404)
    active_bookings = await session.scalar(select(func.count()).select_from(Booking).where(Booking.sailing_id == sailing.id, Booking.status.in_([BookingStatus.confirmed, BookingStatus.cancellation_requested, BookingStatus.pending_payment])))
    if active_bookings: raise AppError('VALIDATION_ERROR', 'A sailing with active bookings or holds cannot be deleted.', 409)
    await session.execute(delete(CabinInventory).where(CabinInventory.sailing_id == sailing.id))
    await session.delete(sailing); c.approval_status = ApprovalStatus.pending; c.status = CruiseStatus.draft
    await session.commit(); return {'message': 'Sailing deleted.'}

@router.get('/cruises/{cruise_id}/amenities')
async def list_cruise_amenities(cruise_id:str,user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session); c=await owned_cruise(cruise_id,p,session)
    rows=(await session.execute(select(Amenity).join(CabinTypeAmenity,CabinTypeAmenity.amenity_id==Amenity.id).join(CabinType,CabinType.id==CabinTypeAmenity.cabin_type_id).where(CabinType.cruise_id==c.id).order_by(Amenity.name))).scalars().unique().all()
    return [{'id':str(x.id),'name':x.name,'icon_key':x.icon_key,'category':x.category} for x in rows]


@router.post('/cruises/{cruise_id}/review')
async def review_cruise(cruise_id:str,data:ReviewApplication,admin=Depends(require_admin),session=Depends(get_session)):
    c=await session.get(Cruise,cruise_id)
    if not c or not c.partner_id: raise AppError('NOT_FOUND','Partner cruise not found.',404)
    if data.approved:
        missing=await validate_cruise_bookability(c,session,require_commission=True)
        if missing:
            raise AppError('VALIDATION_ERROR',f'Cruise is not ready for approval. Missing: {", ".join(missing)}.',422,{'missing':missing})
    c.approval_status=ApprovalStatus.approved if data.approved else ApprovalStatus.rejected
    c.status=CruiseStatus.published if data.approved else CruiseStatus.draft
    await session.commit()

    # Notify the partner after the decision. This is a partner-account event,
    # so it is delivered by email to the registered partner address.
    partner = await session.get(Partner, c.partner_id)
    if partner and partner.email:
        decision = 'approved' if data.approved else 'rejected'
        reason_html = f'<p style="color:#66788c"><b>Admin note:</b> {data.reason}</p>' if data.reason else ''
        body = (
            f'<p>Your cruise <b>{c.name}</b> has been <b>{decision}</b> by the my_cruise admin team.</p>'
            f'{reason_html}'
            + ('<p>The cruise is now available on the partner websites where it is enabled.</p>' if data.approved else
               '<p>You can update the cruise and resubmit it for review.</p>')
        )
        await send_email(
            partner.email,
            f'Cruise {decision} — {c.name}',
            wrap_email(f'Cruise {decision.title()}', body, preheader=f'{c.name} was {decision}'),
        )
    return {'message':'Cruise reviewed.','approval_status':c.approval_status.value,'reason':data.reason}


@router.get('/sailings/{sailing_id}/inventory')
async def partner_inventory(sailing_id:str,user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session)
    try: sid=uuid.UUID(sailing_id)
    except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid sailing identifier.',422) from exc
    sailing=await session.get(Sailing,sid)
    if not sailing: raise AppError('NOT_FOUND','Sailing not found.',404)
    cruise=await owned_cruise(str(sailing.cruise_id),p,session)
    rows=(await session.execute(select(CabinInventory,Cabin).join(Cabin,Cabin.id==CabinInventory.cabin_id).where(CabinInventory.sailing_id==sailing.id).order_by(Cabin.cabin_number))).all()
    return [{'cabin_id':str(inv.cabin_id),'cabin_number':cab.cabin_number,'status':inv.status.value,'price_cents':inv.price_cents,'version':inv.version} for inv,cab in rows]


@router.patch('/sailings/{sailing_id}/inventory/{cabin_id}')
async def partner_inventory_edit(sailing_id:str,cabin_id:str,data:dict,user=Depends(get_current_user),session=Depends(get_session)):
    p=await partner_for_user(user,session)
    try: sid=uuid.UUID(sailing_id); cid=uuid.UUID(cabin_id)
    except ValueError as exc: raise AppError('VALIDATION_ERROR','Invalid sailing or cabin identifier.',422) from exc
    sailing=await session.get(Sailing,sid)
    if not sailing: raise AppError('NOT_FOUND','Sailing not found.',404)
    await owned_cruise(str(sailing.cruise_id),p,session)
    inv=await session.scalar(select(CabinInventory).where(CabinInventory.sailing_id==sid,CabinInventory.cabin_id==cid).with_for_update())
    if not inv: raise AppError('NOT_FOUND','Inventory row not found.',404)
    if inv.status in (InventoryStatus.booked,InventoryStatus.held): raise AppError('CABIN_UNAVAILABLE','Booked/held cabins cannot be changed.',409)
    if 'price_cents' in data:
        try: price=int(data['price_cents'])
        except (TypeError,ValueError): raise AppError('VALIDATION_ERROR','price_cents must be an integer.',422)
        if price<0: raise AppError('VALIDATION_ERROR','price_cents cannot be negative.',422)
        inv.price_cents=price
    if 'status' in data:
        if data['status'] not in ('available','blocked'): raise AppError('VALIDATION_ERROR','Status must be available or blocked.',422)
        inv.status=InventoryStatus(data['status'])
    inv.version += 1; await session.commit(); return {'message':'Inventory updated.','status':inv.status.value,'price_cents':inv.price_cents,'version':inv.version}

