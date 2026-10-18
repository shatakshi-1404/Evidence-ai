from app.models.chunk import EMBEDDING_DIM
from app.models.document import DocumentStatus
from app.services.embeddings import get_embedder
from app.services.ingestion import process_document
from tests.test_ingestion import chunks_of, fresh, setup_document


def test_ready_documents_have_embedded_chunks(client, db):
    doc_id = setup_document(client)

    assert process_document(db, doc_id).outcome == "ready"

    chunks = chunks_of(db, doc_id)
    assert chunks
    assert all(c.embedding is not None and len(c.embedding) == EMBEDDING_DIM for c in chunks)
    assert fresh(db, doc_id).embedding_model == get_embedder().model_name


def test_embedding_failure_is_retried_and_leaves_no_half_finished_state(client, db, monkeypatch):
    def broken(texts):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(get_embedder(), "embed_documents", broken)
    doc_id = setup_document(client)

    assert process_document(db, doc_id).outcome == "retry"

    assert chunks_of(db, doc_id) == []
    assert fresh(db, doc_id).status == DocumentStatus.QUEUED
