"""Shared helpers for the central cabin inventory."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CabinInventory, InventoryStatus


async def get_locked_inventory(
    session: AsyncSession,
    sailing_id,
    cabin_ids,
):
    """Load and lock the requested inventory rows in a fixed order.

    Direct traveler bookings and partner bookings both call this helper. The
    PostgreSQL row lock is what prevents two channels from claiming the same
    cabin at the same time.
    """
    ordered_cabin_ids = sorted(cabin_ids)

    result = await session.execute(
        select(CabinInventory)
        .where(
            CabinInventory.sailing_id == sailing_id,
            CabinInventory.cabin_id.in_(ordered_cabin_ids),
        )
        .order_by(CabinInventory.cabin_id)
        .with_for_update(nowait=False)
    )
    return result.scalars().all()


async def release_expired_holds(session: AsyncSession):
    """Return expired temporary holds to the available inventory pool."""
    now = datetime.now(timezone.utc)

    await session.execute(
        update(CabinInventory)
        .where(
            CabinInventory.status == InventoryStatus.held,
            CabinInventory.hold_expires_at <= now,
        )
        .values(
            status=InventoryStatus.available,
            held_by_user_id=None,
            hold_expires_at=None,
            booking_id=None,
            version=CabinInventory.version + 1,
        )
    )
