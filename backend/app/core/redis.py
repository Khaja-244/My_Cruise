"""Optional Redis helpers. Business correctness never depends on Redis."""
from app.core.config import settings

_client = None

async def get_redis():
    global _client
    if not settings.REDIS_URL:
        return None
    if _client is None:
        from redis.asyncio import Redis
        _client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await _client.ping()
        return _client
    except Exception:
        return None

async def close_redis():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
