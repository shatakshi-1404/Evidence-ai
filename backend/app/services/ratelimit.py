import logging

import redis

from app.services.queue import get_redis

logger = logging.getLogger(__name__)


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> int | None:
    """Fixed-window counter in Redis. Returns None if allowed, else seconds to wait.

    If Redis is down we allow the request (fail open): rate limiting is a safety
    net, and an outage shouldn't lock every user out of the app.
    """
    if limit <= 0:
        return None
    try:
        client = get_redis()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)
        ttl = client.ttl(key)
        if ttl < 0:  # a crash between INCR and EXPIRE would leave a key that never resets
            client.expire(key, window_seconds)
            ttl = window_seconds
    except redis.RedisError:
        logger.warning("Rate limiter unavailable; allowing the request", exc_info=True)
        return None
    return max(ttl, 1) if count > limit else None
