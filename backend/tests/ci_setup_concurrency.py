"""Prepare a deterministic cross-channel inventory race for CI.

Run after `seeds/seed.py` and before starting the API. The script creates a
fresh traveler token, a fresh partner API key, exposes the first published
platform cruise to that partner, and selects one available cabin.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.partner_auth import generate_partner_api_key
from app.core.security import create_access_token, hash_password
from app.models import (
    ApprovalStatus,
    Cabin,
    CabinInventory,
    Cruise,
    CruiseStatus,
    InventoryStatus,
    PartnerApiKey,
    Partner,
    PartnerCruiseExposure,
    PartnerStatus,
    Sailing,
    SailingStatus,
    User,
    UserRole,
)


async def main() -> None:
    async with SessionLocal() as session:
        traveler = await session.scalar(
            select(User).where(User.email == "ci-traveler@mycruise.test")
        )
        if not traveler:
            traveler = User(
                full_name="CI Traveler",
                email="ci-traveler@mycruise.test",
                password_hash=hash_password("CITraveler1234"),
                role=UserRole.traveler,
                is_email_verified=True,
                must_change_password=False,
            )
            session.add(traveler)
            await session.flush()

        partner = await session.scalar(select(Partner).where(Partner.email == "partner123@mycruise.demo"))
        if not partner or not partner.user_id or partner.status != PartnerStatus.active:
            raise RuntimeError("Seed partner1@example.com is not active/configured.")

        cruise = await session.scalar(
            select(Cruise)
            .where(
                Cruise.approval_status == ApprovalStatus.approved,
                Cruise.status == CruiseStatus.published,
                Cruise.partner_id.is_(None),
            )
            .order_by(Cruise.created_at)
        )
        if not cruise:
            raise RuntimeError("No published platform cruise available for CI race.")

        exposure = await session.scalar(
            select(PartnerCruiseExposure).where(
                PartnerCruiseExposure.partner_id == partner.id,
                PartnerCruiseExposure.cruise_id == cruise.id,
            )
        )
        if not exposure:
            session.add(
                PartnerCruiseExposure(
                    partner_id=partner.id,
                    cruise_id=cruise.id,
                    enabled=True,
                )
            )
        else:
            exposure.enabled = True

        sailing = await session.scalar(
            select(Sailing)
            .where(
                Sailing.cruise_id == cruise.id,
                Sailing.status == SailingStatus.open,
                Sailing.booking_closes_at > datetime.now(timezone.utc),
            )
            .order_by(Sailing.departure_date)
        )
        if not sailing:
            raise RuntimeError("No open sailing available for CI race.")

        inventory = await session.scalar(
            select(CabinInventory)
            .where(
                CabinInventory.sailing_id == sailing.id,
                CabinInventory.status == InventoryStatus.available,
            )
            .order_by(CabinInventory.cabin_id)
        )
        if not inventory:
            raise RuntimeError("No available cabin inventory for CI race.")

        raw_key, digest, prefix = generate_partner_api_key()
        session.add(
            PartnerApiKey(
                partner_id=partner.id,
                key_hash=digest,
                key_prefix=prefix,
                active=True,
                rate_limit_per_minute=120,
            )
        )
        await session.commit()

        token = create_access_token(str(traveler.id), traveler.role.value)
        output = os.getenv("CI_OUTPUT_FILE", "ci-concurrency.env")
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(f"TRAVELER_TOKEN={token}\n")
            handle.write(f"PARTNER_API_KEY={raw_key}\n")
            handle.write(f"SAILING_ID={sailing.id}\n")
            handle.write(f"CABIN_ID={inventory.cabin_id}\n")

        print(f"Prepared cross-channel race: sailing={sailing.id}, cabin={inventory.cabin_id}")
        print(f"Wrote CI variables to {output}")


if __name__ == "__main__":
    asyncio.run(main())
