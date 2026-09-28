from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models import (
    ApprovalStatus,
    Cabin,
    CabinInventory,
    CabinType,
    Cruise,
    CruiseStatus,
    InventoryStatus,
    IntegrationStatus,
    Partner,
    PartnerCruiseExposure,
    PartnerStatus,
    Sailing,
    SailingStatus,
    Ship,
)


async def exposed_sailing(
    sailing_id: str,
    partner: Partner,
    session: AsyncSession,
    website_id=None,
) -> tuple[Sailing, Cruise]:
    """Validate that a sailing is genuinely bookable through a partner API key."""
    if partner.status != PartnerStatus.active or partner.integration_status != IntegrationStatus.connected:
        raise AppError("FORBIDDEN", "Partner integration is inactive.", 403)

    try:
        sailing = await session.get(Sailing, sailing_id)
    except (TypeError, ValueError):
        sailing = None
    if not sailing:
        raise AppError("NOT_FOUND", "Sailing not found.", 404)

    cruise = await session.get(Cruise, sailing.cruise_id)
    if (
        not cruise
        or cruise.deleted_at is not None
        or cruise.approval_status != ApprovalStatus.approved
        or cruise.status != CruiseStatus.published
    ):
        raise AppError("NOT_FOUND", "Cruise is not available.", 404)

    exposure_conditions = [
        PartnerCruiseExposure.partner_id == partner.id,
        PartnerCruiseExposure.cruise_id == cruise.id,
        PartnerCruiseExposure.enabled.is_(True),
    ]
    if website_id is not None:
        exposure_conditions.append(PartnerCruiseExposure.partner_website_id == website_id)
    else:
        # Legacy partner-level exposure remains supported for existing API clients.
        exposure_conditions.append(PartnerCruiseExposure.partner_website_id.is_(None))
    exposure = await session.scalar(select(PartnerCruiseExposure.id).where(*exposure_conditions))
    if not exposure:
        raise AppError("FORBIDDEN", "Cruise is not exposed to this partner.", 403)

    if sailing.status not in (SailingStatus.scheduled, SailingStatus.open):
        raise AppError("SAILING_CLOSED", "This sailing is not available for booking.", 409)

    if not await session.scalar(
        select(CabinInventory.id).where(
            CabinInventory.sailing_id == sailing.id,
            CabinInventory.status == InventoryStatus.available,
        )
    ):
        raise AppError("SOLD_OUT", "This sailing has no available cabins.", 409)

    return sailing, cruise


async def validate_cruise_bookability(
    cruise: Cruise,
    session: AsyncSession,
    *,
    require_commission: bool = False,
) -> list[str]:
    """Return missing setup items instead of approving an unusable cruise."""
    missing: list[str] = []

    if not cruise.ship_id:
        missing.append("ship")
    if not cruise.embark_port_id or not cruise.disembark_port_id:
        missing.append("ports")
    if require_commission and (cruise.commission_type is None or cruise.commission_value is None):
        missing.append("commission")

    deck_exists = await session.scalar(
        select(Cabin.id).join(Ship, Ship.id == Cabin.ship_id, isouter=True).where(Ship.id == cruise.ship_id)
    )
    # Decks are checked directly because a ship can exist without any deck rows.
    from app.models import Deck
    if not await session.scalar(select(Deck.id).where(Deck.ship_id == cruise.ship_id)):
        missing.append("deck")

    if not await session.scalar(select(CabinType.id).where(CabinType.cruise_id == cruise.id)):
        missing.append("cabin_type")

    cabin_exists = await session.scalar(
        select(Cabin.id).join(CabinType, CabinType.id == Cabin.cabin_type_id).where(CabinType.cruise_id == cruise.id, Cabin.is_active.is_(True))
    )
    if not cabin_exists:
        missing.append("physical_cabin")

    sailings = (await session.scalars(select(Sailing).where(Sailing.cruise_id == cruise.id))).all()
    if not sailings:
        missing.append("sailing")
    else:
        inventory_exists = await session.scalar(
            select(CabinInventory.id)
            .join(Sailing, Sailing.id == CabinInventory.sailing_id)
            .where(Sailing.cruise_id == cruise.id)
        )
        if not inventory_exists:
            missing.append("inventory")
        available_exists = await session.scalar(
            select(CabinInventory.id)
            .join(Sailing, Sailing.id == CabinInventory.sailing_id)
            .where(
                Sailing.cruise_id == cruise.id,
                CabinInventory.status == InventoryStatus.available,
            )
        )
        if not available_exists:
            missing.append("available_cabin")

    return missing
