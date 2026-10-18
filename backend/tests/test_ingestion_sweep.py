import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.models.document import Document, DocumentStatus
from app.services.ingestion import recover_stuck_documents
from tests.test_ingestion import fresh
from tests.utils import auth_headers, create_collection, upload


def test_old_unclaimed_queued_documents_are_swept(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    ids = {
        name: uuid.UUID(upload(client, headers, cid, f"{name}.txt", f"body of {name}".encode()).json()["id"])
        for name in ("lost", "fresh", "retrying")
    }

    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.execute(update(Document).where(Document.id.in_([ids["lost"], ids["retrying"]])).values(created_at=old))
    # 'retrying' was already attempted once: it is waiting out a backoff, not lost.
    db.execute(update(Document).where(Document.id == ids["retrying"]).values(attempts=1))
    db.commit()

    swept = recover_stuck_documents(db, stale_minutes=10, stale_queued_minutes=5)

    assert swept == [ids["lost"]]
    assert fresh(db, ids["lost"]).status == DocumentStatus.QUEUED  # re-enqueued, not changed


def test_periodic_pass_without_the_option_sweeps_nothing(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    doc_id = uuid.UUID(upload(client, headers, cid).json()["id"])
    db.execute(
        update(Document)
        .where(Document.id == doc_id)
        .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=30))
    )
    db.commit()

    assert recover_stuck_documents(db, stale_minutes=10) == []
