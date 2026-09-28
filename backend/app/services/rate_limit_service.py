from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.core.database import SessionLocal
from app.models import RateLimitCounter
from app.core.exceptions import AppError

async def check_rate_limit(session, key: str, limit: int, window_seconds: int) -> None:
    """Persist the counter in its own transaction so rejected requests still count."""
    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    window_start = datetime.fromtimestamp(epoch - (epoch % window_seconds), tz=timezone.utc)
    async with SessionLocal() as limiter:
        await limiter.execute(
            insert(RateLimitCounter)
            .values(key=key, window_start=window_start, count=0)
            .on_conflict_do_nothing(index_elements=[RateLimitCounter.key])
        )
        row = await limiter.scalar(select(RateLimitCounter).where(RateLimitCounter.key == key).with_for_update())
        if row.window_start < window_start:
            row.window_start, row.count = window_start, 0
        if row.count >= limit:
            retry_after = max(1, int((window_start + timedelta(seconds=window_seconds) - now).total_seconds()))
            await limiter.commit()
            raise AppError('RATE_LIMITED', f'Too many requests. Retry after {retry_after} seconds.', 429, {'retry_after': retry_after})
        row.count += 1
        await limiter.commit()
