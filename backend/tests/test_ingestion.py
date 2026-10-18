import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services import storage
from app.services.ingestion import process_document, recover_stuck_documents
from tests.utils import SAMPLE_TEXT, auth_headers, create_collection, make_pdf, upload


def setup_document(client, filename="notes.txt", data=SAMPLE_TEXT.encode()) -> uuid.UUID:
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    response = upload(client, headers, cid, filename, data)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def fresh(db, document_id: uuid.UUID) -> Document:
    return db.get(Document, document_id, populate_existing=True)


def chunks_of(db, document_id: uuid.UUID) -> list[Chunk]:
    return list(
        db.scalars(
            select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
        ).all()
    )


def test_text_document_becomes_ready_with_chunks(client, db):
    doc_id = setup_document(client)

    result = process_document(db, doc_id)

    assert result.outcome == "ready"
    doc = fresh(db, doc_id)
    assert doc.status == DocumentStatus.READY
    assert doc.attempts == 1
    assert doc.processed_at is not None
    assert doc.chunk_count > 1

    chunks = chunks_of(db, doc_id)
    assert len(chunks) == doc.chunk_count
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.owner_id == doc.owner_id for c in chunks)
    assert all(len(c.content) <= settings.chunk_size for c in chunks)


def test_pdf_chunks_carry_page_numbers(client, db):
    data = make_pdf(["First page about apples", "Second page about oranges"])
    doc_id = setup_document(client, "fruit.pdf", data)

    assert process_document(db, doc_id).outcome == "ready"

    assert fresh(db, doc_id).page_count == 2
    chunks = chunks_of(db, doc_id)
    assert [c.page_number for c in chunks] == [1, 2]
    assert "apples" in chunks[0].content
    assert "oranges" in chunks[1].content


def test_processing_is_idempotent(client, db):
    doc_id = setup_document(client)
    process_document(db, doc_id)
    first_count = len(chunks_of(db, doc_id))

    # A duplicate queue message for a finished document does nothing.
    assert process_document(db, doc_id).outcome == "skipped"

    # Reprocessing replaces the chunks instead of duplicating them.
    db.execute(update(Document).where(Document.id == doc_id).values(status=DocumentStatus.QUEUED))
    db.commit()
    assert process_document(db, doc_id).outcome == "ready"
    assert len(chunks_of(db, doc_id)) == first_count


def test_unknown_document_is_skipped(db):
    assert process_document(db, uuid.uuid4()).outcome == "skipped"


def test_corrupt_pdf_fails_immediately_without_retry(client, db):
    doc_id = setup_document(client, "bad.pdf", b"%PDF-1.4\nthis is not really a pdf")

    result = process_document(db, doc_id)

    assert result.outcome == "failed"
    doc = fresh(db, doc_id)
    assert doc.status == DocumentStatus.FAILED
    assert doc.attempts == 1
    assert "PDF" in doc.error_message
    assert chunks_of(db, doc_id) == []


def test_pdf_without_text_fails_with_clear_message(client, db):
    doc_id = setup_document(client, "scan.pdf", make_pdf([""]))

    assert process_document(db, doc_id).outcome == "failed"
    assert "extractable text" in fresh(db, doc_id).error_message


def test_temporary_errors_are_retried_then_give_up(client, db, monkeypatch):
    def broken_disk(path):
        raise OSError("disk unavailable")

    monkeypatch.setattr(storage, "read_file", broken_disk)
    doc_id = setup_document(client)

    for attempt in range(1, settings.max_ingest_attempts):
        result = process_document(db, doc_id)
        assert (result.outcome, result.attempts) == ("retry", attempt)
        assert fresh(db, doc_id).status == DocumentStatus.QUEUED

    final = process_document(db, doc_id)
    assert (final.outcome, final.attempts) == ("failed", settings.max_ingest_attempts)
    assert fresh(db, doc_id).status == DocumentStatus.FAILED


def test_recovery_of_documents_left_behind_by_a_crashed_worker(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    ids = {}
    for name in ("stale", "fresh", "queued", "poison"):
        response = upload(client, headers, cid, f"{name}.txt", f"content of {name}".encode())
        ids[name] = uuid.UUID(response.json()["id"])

    now = datetime.now(timezone.utc)

    def mark_processing(name: str, minutes_ago: int, attempts: int) -> None:
        db.execute(
            update(Document)
            .where(Document.id == ids[name])
            .values(
                status=DocumentStatus.PROCESSING,
                processing_started_at=now - timedelta(minutes=minutes_ago),
                attempts=attempts,
            )
        )

    mark_processing("stale", minutes_ago=30, attempts=1)
    mark_processing("fresh", minutes_ago=1, attempts=1)
    mark_processing("poison", minutes_ago=30, attempts=settings.max_ingest_attempts)
    db.commit()

    recovered = recover_stuck_documents(db, stale_minutes=10)

    assert recovered == [ids["stale"]]
    assert fresh(db, ids["stale"]).status == DocumentStatus.QUEUED
    assert fresh(db, ids["fresh"]).status == DocumentStatus.PROCESSING  # still working
    assert fresh(db, ids["poison"]).status == DocumentStatus.FAILED     # gave up

    at_startup = recover_stuck_documents(db, stale_minutes=10, include_queued=True)
    assert set(at_startup) == {ids["stale"], ids["queued"]}
