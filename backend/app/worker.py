"""Background worker. Run with:  python -m app.worker"""
import logging
import signal
import time

import redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.embeddings import get_embedder
from app.services.ingestion import process_document, recover_stuck_documents
from app.services.queue import dequeue, enqueue_ingestion, get_redis, promote_due

logger = logging.getLogger("evidenceai.worker")

RECOVERY_INTERVAL_SECONDS = 60
_running = True


def _request_stop(signum, frame) -> None:
    global _running
    logger.info("Shutdown requested; finishing the current job first")
    _running = False


def backoff_seconds(attempts: int) -> float:
    """5s, 10s, 20s, ... capped at 5 minutes."""
    return min(settings.retry_base_seconds * 2 ** max(attempts - 1, 0), 300)


def _recover(client: redis.Redis, include_queued: bool) -> None:
    with SessionLocal() as db:
        ids = recover_stuck_documents(
            db,
            settings.stale_processing_minutes,
            include_queued=include_queued,
            # The periodic pass also rescues documents whose queue message was lost.
            stale_queued_minutes=None if include_queued else settings.queued_sweep_minutes,
        )
    for document_id in ids:
        enqueue_ingestion(document_id, client=client)
    if ids:
        logger.info("Re-enqueued %d document(s)", len(ids))


def _startup_recovery(client: redis.Redis) -> None:
    # The database may still be running migrations when we boot, so retry.
    for attempt in range(1, 31):
        try:
            _recover(client, include_queued=True)
            return
        except Exception as exc:
            logger.warning("Startup recovery failed (%s); retry %d/30", exc, attempt)
            time.sleep(2)
    raise RuntimeError("Database or Redis never became available")


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    client = get_redis()
    _startup_recovery(client)
    try:
        logger.info("Loading embedding model (first run downloads ~130 MB)...")
        get_embedder().embed_query("warm up")
    except Exception:
        logger.exception("Embedding warm-up failed; will retry when the first job arrives")
    logger.info("Worker started")

    last_recovery = time.monotonic()
    while _running:
        try:
            promote_due(client)
            document_id = dequeue(client, timeout=2)

            if document_id is not None:
                with SessionLocal() as db:
                    result = process_document(db, document_id)
                logger.info("Document %s -> %s", document_id, result.outcome)
                if result.outcome == "retry":
                    enqueue_ingestion(
                        document_id,
                        delay_seconds=backoff_seconds(result.attempts),
                        client=client,
                    )

            if time.monotonic() - last_recovery > RECOVERY_INTERVAL_SECONDS:
                _recover(client, include_queued=False)
                last_recovery = time.monotonic()

        except redis.RedisError:
            logger.exception("Redis error; backing off")
            time.sleep(2)
        except Exception:
            logger.exception("Unexpected worker error")
            time.sleep(1)

    logger.info("Worker stopped")


if __name__ == "__main__":
    run()
