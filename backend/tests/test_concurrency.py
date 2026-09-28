"""Cross-channel PostgreSQL inventory locking integration test."""
import os
import pytest

pytestmark=pytest.mark.asyncio

@pytest.mark.skipif(not all(os.getenv(x) for x in ('BASE_URL','TRAVELER_TOKEN','PARTNER_API_KEY','SAILING_ID','CABIN_ID')), reason='Set API concurrency environment variables to run.')
async def test_same_cabin_has_single_cross_channel_winner():
    from concurrency_runner import main
    await main()
