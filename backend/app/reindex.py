"""Re-embed documents.  Run:  python -m app.reindex          (only those missing/outdated)
                              python -m app.reindex --all    (everything)

Documents are unsearchable while they're queued again, so run this when convenient."""
import argparse

from sqlalchemy import or_, select, update

from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.embeddings import get_embedder
from app.services.queue import enqueue_ingestion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="re-embed every ready document")
    args = parser.parse_args()

    model_name = get_embedder().model_name
    with SessionLocal() as db:
        stmt = select(Document.id).where(Document.status == DocumentStatus.READY)
        if not args.all:
            stmt = stmt.where(
                or_(Document.embedding_model.is_(None), Document.embedding_model != model_name)
            )
        ids = list(db.scalars(stmt).all())
        if ids:
            db.execute(
                update(Document)
                .where(Document.id.in_(ids))
                .values(status=DocumentStatus.QUEUED, attempts=0, error_message=None)
            )
            db.commit()

    for document_id in ids:
        enqueue_ingestion(document_id)
    print(f"Re-queued {len(ids)} document(s) for embedding with {model_name}")


if __name__ == "__main__":
    main()
