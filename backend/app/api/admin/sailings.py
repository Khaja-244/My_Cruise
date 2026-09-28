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


router = APIRouter(prefix='/admin', tags=['Admin - Sailings'])

from app.api.admin.helpers import audit, fanout_new_cruise

@router.get('/sailings')
async def list_sailings(admin=Depends(require_admin), session=Depends(get_session)):
    """List sailings for the admin inventory screen."""
    rows = (await session.scalars(select(Sailing).order_by(Sailing.departure_date.desc()))).all()
    return [
        {
            'id': str(x.id), 'cruise_id': str(x.cruise_id),
            'departure_date': x.departure_date, 'return_date': x.return_date,
            'status': x.status.value, 'booking_closes_at': x.booking_closes_at,
        }
        for x in rows
    ]


@router.post('/sailings')
async def sailing(data:SailingCreate,admin=Depends(require_admin),session=Depends(get_session)):
    s=Sailing(cruise_id=data.cruise_id,departure_date=data.departure_date,return_date=data.return_date,booking_closes_at=data.booking_closes_at,port_fee_per_guest_cents=data.port_fee_per_guest_cents,status=SailingStatus.scheduled); session.add(s); await session.flush()
    c=await session.get(Cruise,data.cruise_id)
    if not c or c.deleted_at is not None: raise AppError('NOT_FOUND','Cruise not found.',404)
    cabins=(await session.scalars(select(Cabin).where(Cabin.ship_id==c.ship_id,Cabin.is_active==True))).all()
    physical_type_ids={cab.cabin_type_id for cab in cabins}
    physical_types={x.id:x for x in (await session.scalars(select(CabinType).where(CabinType.id.in_(physical_type_ids)))).all()}
    current_types={x.name:x for x in (await session.scalars(select(CabinType).where(CabinType.cruise_id==c.id))).all()}
    for cab in cabins:
        physical=physical_types.get(cab.cabin_type_id)
        target=current_types.get(physical.name) if physical else None
        if not target: await session.rollback(); raise AppError('VALIDATION_ERROR',f'No cabin type named {physical.name if physical else "unknown"} exists on this cruise.',422)
        session.add(CabinInventory(sailing_id=s.id,cabin_id=cab.id,price_cents=target.base_price_cents,status=InventoryStatus.available))
    audit(session,admin,'create','sailing',s.id,{'cruise_id':str(c.id),'inventory_generated':len(cabins)}); await session.commit(); return {'id':str(s.id),'inventory_generated':len(cabins)}


@router.patch('/sailings/{id}')
async def sailing_patch(id:str,data:SailingUpdate,admin=Depends(require_admin),session=Depends(get_session)):
    s=await session.get(Sailing,id)
    if not s: raise AppError('NOT_FOUND','Sailing not found.',404)
    values = data.model_dump(exclude_none=True)
    if 'status' in values:
        try:
            s.status = SailingStatus(values.pop('status'))
        except ValueError as exc:
            raise AppError('VALIDATION_ERROR', 'Invalid sailing status.', 422) from exc
    if 'return_date' in values and values['return_date'] < s.departure_date:
        raise AppError('VALIDATION_ERROR', 'Return date must be on or after departure date.', 422)
    if 'departure_date' in values and values['departure_date'] > s.return_date:
        raise AppError('VALIDATION_ERROR', 'Departure date must be on or before return date.', 422)
    for key, value in values.items():
        setattr(s, key, value)
    audit(session,admin,'update','sailing',s.id,data.model_dump(exclude_none=True)); await session.commit(); return {'message':'Updated.'}


@router.post('/sailings/{id}/cancel')
async def cancel_sailing(id: str, data: dict, admin=Depends(require_admin), session=Depends(get_session)):
    sailing = await session.get(Sailing, id)
    if not sailing: raise AppError('NOT_FOUND', 'Sailing not found.', 404)
    reason = str(data.get('reason', '')).strip()
    if not reason: raise AppError('VALIDATION_ERROR', 'Cancellation reason is required.', 422)
    if sailing.status == SailingStatus.cancelled: return {'message': 'Sailing is already cancelled.', 'affected_bookings': 0}

    sailing.status = SailingStatus.cancelled
    affected = 0
    confirmed = (await session.scalars(select(Booking).where(Booking.sailing_id == sailing.id, Booking.status == BookingStatus.confirmed).with_for_update())).all()
    for booking in confirmed:
        request = CancellationRequest(
            booking_id=booking.id, requested_by=admin.id, reason=reason,
            status=CancellationStatus.approved, reviewed_by=admin.id,
            admin_note='Operator-initiated sailing cancellation.',
            policy_snapshot={'reason': 'operator_cancelled'},
            calculated_refund_cents=booking.total_cents, final_refund_cents=booking.total_cents,
            requested_at=datetime.now(timezone.utc), reviewed_at=datetime.now(timezone.utc),
        )
        session.add(request); await session.flush()
        payment = await session.scalar(select(Payment).where(Payment.booking_id == booking.id).order_by(Payment.created_at.desc()))
        if payment and booking.total_cents > 0:
            session.add(Refund(booking_id=booking.id, cancellation_request_id=request.id, payment_id=payment.id, amount_cents=booking.total_cents, status=RefundStatus.pending))
        booking.status = BookingStatus.cancelled; booking.cancelled_at = datetime.now(timezone.utc)
        inventory = (await session.scalars(select(CabinInventory).join(BookingCabin, BookingCabin.cabin_inventory_id == CabinInventory.id).where(BookingCabin.booking_id == booking.id).with_for_update())).all()
        for row in inventory:
            row.status = InventoryStatus.available; row.booking_id = None; row.held_by_user_id = None; row.hold_expires_at = None; row.version += 1
        if booking.channel == BookingChannel.direct:
            await notify(session, booking.user_id, NotificationType.booking_cancelled, 'Sailing cancelled', f'Your sailing for booking {booking.booking_reference} was cancelled by the operator. A full refund is being processed.', {'booking_reference': booking.booking_reference, 'reason': reason})
        elif booking.customer_email:
            from app.services.email_service import send_email, wrap_email
            background_email = wrap_email(
                'Sailing cancelled',
                f'<p>Your booking <b>{booking.booking_reference}</b> was cancelled by the operator due to an '
                f'operational change to the sailing. A full refund is being processed automatically and no '
                f'action is needed from you.</p>',
                preheader=f'Booking {booking.booking_reference} was cancelled — refund in progress')
            # Send after the transaction commits below; this is intentionally queued here.
            session.info.setdefault('partner_cancellation_emails', []).append((booking.customer_email, f'Sailing cancelled — {booking.booking_reference}', background_email))
        affected += 1

    audit(session, admin, 'cancel', 'sailing', sailing.id, {'reason': reason, 'affected_bookings': affected})
    await session.commit()
    for email, subject, body in session.info.pop('partner_cancellation_emails', []):
        from app.services.email_service import send_email
        await send_email(email, subject, body)
    return {'message': 'Sailing cancelled. Full refunds have been queued.', 'affected_bookings': affected}


