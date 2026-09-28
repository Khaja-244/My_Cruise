"""Real cross-channel inventory race test.

Requires a running API and an OPEN sailing/cabin.

Environment variables:
    BASE_URL=http://localhost:8000/api
    TRAVELER_TOKEN=<traveler access token>
    PARTNER_API_KEY=<active partner API key>
    SAILING_ID=<same sailing for both calls>
    CABIN_ID=<same cabin for both calls>

The two requests are started together for the same cabin.

Expected result:
    One request -> HTTP 200
    Other request -> HTTP 409

This verifies that the central cabin inventory lock prevents
double-booking across direct traveler and partner channels.
"""

import asyncio
import os
import uuid

import httpx


# ---------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------

BASE = os.getenv(
    "BASE_URL",
    "http://localhost:8000/api",
).rstrip("/")

TRAVELER_TOKEN = os.environ["TRAVELER_TOKEN"]
PARTNER_API_KEY = os.environ["PARTNER_API_KEY"]
SAILING_ID = os.environ["SAILING_ID"]
CABIN_ID = os.environ["CABIN_ID"]

PARTNER_CUSTOMER_NAME = os.getenv(
    "PARTNER_CUSTOMER_NAME",
    "Concurrency Test Customer",
)

PARTNER_CUSTOMER_EMAIL = os.getenv(
    "PARTNER_CUSTOMER_EMAIL",
    "concurrency@example.com",
)


# ---------------------------------------------------------
# Main concurrency test
# ---------------------------------------------------------

async def main():
    async with httpx.AsyncClient(timeout=30) as client:

        # -------------------------------------------------
        # Direct traveler request headers
        # -------------------------------------------------

        traveler_headers = {
            "Authorization": f"Bearer {TRAVELER_TOKEN}",
            "Idempotency-Key": f"concurrency-{uuid.uuid4()}",
        }

        # -------------------------------------------------
        # Partner API request headers
        # -------------------------------------------------

        partner_headers = {
            "X-Partner-API-Key": PARTNER_API_KEY,
            "Idempotency-Key": f"concurrency-partner-{uuid.uuid4()}",
        }

        # -------------------------------------------------
        # Direct traveler booking payload
        # -------------------------------------------------

        direct_payload = {
            "sailing_id": SAILING_ID,
            "cabins": [
                {
                    "cabin_id": CABIN_ID,
                    "occupancy": 1,
                }
            ],
            "guests": [
                {
                    "cabin_id": CABIN_ID,
                    "full_name": "Concurrency Test Customer",
                    "date_of_birth": "1990-01-01",
                    "nationality": "IN",
                    "is_lead_guest": True,
                }
            ],
        }

        # -------------------------------------------------
        # Partner booking payload
        # -------------------------------------------------

        partner_payload = {
            "sailing_id": SAILING_ID,
            "cabins": [
                {
                    "cabin_id": CABIN_ID,
                    "occupancy": 1,
                }
            ],
            "guest_count": 1,
            "customer_name": PARTNER_CUSTOMER_NAME,
            "customer_email": PARTNER_CUSTOMER_EMAIL,
            "guests": [
                {
                    "cabin_id": CABIN_ID,
                    "full_name": PARTNER_CUSTOMER_NAME,
                    "date_of_birth": "1990-01-01",
                    "nationality": "IN",
                    "is_lead_guest": True,
                }
            ],
        }

        # -------------------------------------------------
        # Direct traveler request
        # -------------------------------------------------

        async def direct_booking():
            return await client.post(
                f"{BASE}/bookings/hold",
                headers=traveler_headers,
                json=direct_payload,
            )

        # -------------------------------------------------
        # Partner request
        # -------------------------------------------------

        async def partner_booking():
            return await client.post(
                f"{BASE}/partner-api/bookings",
                headers=partner_headers,
                json=partner_payload,
            )

        # -------------------------------------------------
        # Start both requests at the same time
        # -------------------------------------------------

        direct_response, partner_response = await asyncio.gather(
            direct_booking(),
            partner_booking(),
        )

        # -------------------------------------------------
        # Collect HTTP status codes
        # -------------------------------------------------

        statuses = (
            direct_response.status_code,
            partner_response.status_code,
        )

        # -------------------------------------------------
        # Print complete API responses for CI debugging
        # -------------------------------------------------

        print(
            "traveler hold:",
            direct_response.status_code,
            direct_response.text,
        )

        print(
            "partner hold:",
            partner_response.status_code,
            partner_response.text,
        )

        # -------------------------------------------------
        # Verify concurrency protection
        #
        # Exactly one request must succeed with 200.
        # The other request must fail with 409 because
        # the same cabin cannot be booked twice.
        # -------------------------------------------------

        expected = [200, 409]
        actual = sorted(statuses)

        assert actual == expected, (
            "Expected exactly one success (200) and "
            f"one conflict (409), but got {statuses}. "
            f"Direct response: {direct_response.text}. "
            f"Partner response: {partner_response.text}"
        )

        print(
            "SUCCESS: Cross-channel inventory locking worked. "
            f"Statuses={statuses}"
        )


# ---------------------------------------------------------
# Script entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())