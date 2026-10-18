import time
import uuid
from functools import lru_cache

import redis

from app.core.config import settings

QUEUE_KEY = "evidenceai:ingest:queue"
DELAYED_KEY = "evidenceai:ingest:delayed"


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=3,  # fail fast if Redis is down
        socket_timeout=10,         # must exceed the blocking pop timeout
    )


def enqueue_ingestion(
    document_id: uuid.UUID,
    delay_seconds: float = 0,
    client: redis.Redis | None = None,
) -> None:
    client = client or get_redis()
    if delay_seconds > 0:
        client.zadd(DELAYED_KEY, {str(document_id): time.time() + delay_seconds})
    else:
        client.lpush(QUEUE_KEY, str(document_id))


def promote_due(client: redis.Redis) -> int:
    """Move retries whose wait is over onto the main queue."""
    moved = 0
    for item in client.zrangebyscore(DELAYED_KEY, 0, time.time()):
        # zrem returns 1 only for the worker that removes it, so there are no duplicates.
        if client.zrem(DELAYED_KEY, item):
            client.lpush(QUEUE_KEY, item)
            moved += 1
    return moved


def dequeue(client: redis.Redis, timeout: int = 2) -> uuid.UUID | None:
    """Wait up to `timeout` seconds for a job. Returns None if there isn't one."""
    item = client.brpop(QUEUE_KEY, timeout=timeout)
    if not item:
        return None
    _, value = item
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
