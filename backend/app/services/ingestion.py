import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services import storage
from app.services.chunking import chunk_pages
from app.services.embeddings import get_embedder
from app.services.extraction import ExtractionError, extract_pages

logger = logging.getLogger(__name__)


class ProcessResult(NamedTuple):
    outcome: str  # "skipped" | "ready" | "failed" | "retry"
    attempts: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def claim_document(db: Session, document_id: uuid.UUID) -> Document | None:
    """Atomically move queued -> processing.

    Only one caller can win: a second worker (or a duplicate queue message)
    finds the status already changed and gets None.
    """
    result = db.execute(
        update(Document)
        .where(Document.id == document_id, Document.status == DocumentStatus.QUEUED)
        .values(
            status=DocumentStatus.PROCESSING,
            attempts=Document.attempts + 1,
            processing_started_at=_now(),
            error_message=None,
        )
    )
    db.commit()
    if result.rowcount == 0:
        return None
    return db.get(Document, document_id, populate_existing=True)


def _set_status(db: Session, document_id: uuid.UUID, **values) -> None:
    db.execute(update(Document).where(Document.id == document_id).values(**values))
    db.commit()


def process_document(db: Session, document_id: uuid.UUID) -> ProcessResult:
    document = claim_document(db, document_id)
    if document is None:
        return ProcessResult("skipped")

    # Copy what we need now; the object's state can't be trusted after a rollback.
    doc_id, owner_id = document.id, document.owner_id
    attempts, path = document.attempts, document.storage_path

    try:
        data = storage.read_file(path)
        extracted = extract_pages(data, Path(path).suffix.lower())
        chunks = chunk_pages(extracted.pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ExtractionError("No text could be extracted")

        # NEW: embed BEFORE opening the write transaction, so slow model work
        # never holds database locks. A failure here is treated as temporary.
        embedder = get_embedder()
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedder returned the wrong number of vectors")

        # One transaction: either every chunk is saved AND the document is
        # marked ready, or nothing changes. Never "ready" without embeddings.
        db.execute(delete(Chunk).where(Chunk.document_id == doc_id))  # safe re-runs
        db.add_all(
            [
                Chunk(
                    document_id=doc_id,
                    owner_id=owner_id,
                    chunk_index=chunk.index,
                    content=chunk.text,
                    page_number=chunk.page_number,
                    char_count=len(chunk.text),
                    embedding=vector,  # NEW
                )
                for chunk, vector in zip(chunks, vectors)
            ]
        )
        db.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(
                status=DocumentStatus.READY,
                page_count=extracted.page_count,
                chunk_count=len(chunks),
                embedding_model=embedder.model_name,  # NEW
                error_message=None,
                processed_at=_now(),
            )
        )
        db.commit()
        return ProcessResult("ready", attempts)

    except ExtractionError as exc:
        # Permanent: the file itself is the problem. Don't retry.
        db.rollback()
        _set_status(db, doc_id, status=DocumentStatus.FAILED, error_message=str(exc))
        return ProcessResult("failed", attempts)

    except Exception as exc:
        # Possibly temporary (disk, database, model). Retry a few times, then give up.
        db.rollback()
        logger.exception("Ingestion error for document %s", doc_id)
        if attempts >= settings.max_ingest_attempts:
            _set_status(
                db,
                doc_id,
                status=DocumentStatus.FAILED,
                error_message=f"Processing failed after {attempts} attempts ({type(exc).__name__})",
            )
            return ProcessResult("failed", attempts)
        _set_status(
            db,
            doc_id,
            status=DocumentStatus.QUEUED,
            error_message=f"Temporary error ({type(exc).__name__}); retrying",
        )
        return ProcessResult("retry", attempts)


def recover_stuck_documents(
    db: Session,
    stale_minutes: int,
    include_queued: bool = False,
    stale_queued_minutes: int | None = None,
) -> list[uuid.UUID]:
    """Find documents a crashed worker (or a lost queue message) left behind.

    Returns IDs to put back on the queue.

    - 'processing' for longer than stale_minutes: the worker died mid-job.
      Re-queue it, unless it has used all its attempts (a file that keeps
      killing the worker), in which case mark it failed.
    - include_queued=True (worker startup) also returns every 'queued' document.
    - stale_queued_minutes (periodic pass) returns 'queued' documents older than
      that which no worker has ever claimed (attempts == 0): their queue message
      was lost, for example while Redis was down. Duplicates are harmless because
      claim_document lets only one worker through.
    """
    cutoff = _now() - timedelta(minutes=stale_minutes)
    rows = db.execute(
        select(Document.id, Document.attempts).where(
            Document.status == DocumentStatus.PROCESSING,
            Document.processing_started_at < cutoff,
        )
    ).all()
    requeue = [row.id for row in rows if row.attempts < settings.max_ingest_attempts]
    give_up = [row.id for row in rows if row.attempts >= settings.max_ingest_attempts]

    if requeue:
        db.execute(
            update(Document)
            .where(Document.id.in_(requeue))
            .values(
                status=DocumentStatus.QUEUED,
                error_message="Recovered after interrupted processing",
            )
        )
    if give_up:
        db.execute(
            update(Document)
            .where(Document.id.in_(give_up))
            .values(
                status=DocumentStatus.FAILED,
                error_message="Processing was interrupted repeatedly",
            )
        )
    if requeue or give_up:
        db.commit()

    ids = list(requeue)
    if include_queued:
        queued = db.scalars(
            select(Document.id).where(Document.status == DocumentStatus.QUEUED)
        ).all()
        ids = list(dict.fromkeys([*ids, *queued]))  # de-duplicate, keep order
    elif stale_queued_minutes is not None:
        queued_cutoff = _now() - timedelta(minutes=stale_queued_minutes)
        lost = db.scalars(
            select(Document.id).where(
                Document.status == DocumentStatus.QUEUED,
                Document.attempts == 0,
                Document.created_at < queued_cutoff,
            )
        ).all()
        ids = list(dict.fromkeys([*ids, *lost]))
    return ids
