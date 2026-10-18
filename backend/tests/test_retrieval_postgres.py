import os
import uuid

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="needs a migrated PostgreSQL; run with RUN_PG_TESTS=1",
)

from app.core.config import settings  # noqa: E402
from app.models import Chunk, Collection, Document, User  # noqa: E402
from app.models.document import DocumentStatus  # noqa: E402
from app.services.embeddings import HashEmbedder  # noqa: E402
from app.services.retrieval import HybridRetriever  # noqa: E402

TEXTS = {
    "refund": "Refunds are issued within five business days of receiving the returned item.",
    "shipping": "Standard shipping takes three to seven days and is free above fifty dollars.",
    "cells": "Mitochondria produce most of the chemical energy needed to power the cell.",
}
BOB_TEXT = "Bob's confidential refund strategy memo."


@pytest.fixture()
def session():
    engine = create_engine(settings.sqlalchemy_database_url)
    with Session(engine) as s:
        yield s  # closing the session without commit discards everything we added
    engine.dispose()


def seed(session, email, texts):
    embedder = HashEmbedder()
    user = User(email=email, hashed_password="x", full_name=email)
    session.add(user)
    session.flush()
    collection = Collection(owner_id=user.id, name="c")
    session.add(collection)
    session.flush()
    document = Document(
        owner_id=user.id,
        collection_id=collection.id,
        filename=f"{email}.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        storage_path="x",
        status=DocumentStatus.READY,
        embedding_model=embedder.model_name,
        chunk_count=len(texts),
    )
    session.add(document)
    session.flush()
    contents = list(texts.values())
    for index, (content, vector) in enumerate(zip(contents, embedder.embed_documents(contents))):
        session.add(
            Chunk(
                document_id=document.id,
                owner_id=user.id,
                chunk_index=index,
                content=content,
                char_count=len(content),
                embedding=vector,
            )
        )
    session.flush()
    return user, collection


def test_hybrid_search_finds_the_relevant_passage(session):
    user, _ = seed(session, f"{uuid.uuid4().hex}@example.com", TEXTS)
    results = HybridRetriever(session, HashEmbedder()).retrieve(
        owner_id=user.id, query="how long do refunds take", top_k=3
    )
    assert results[0].content == TEXTS["refund"]
    assert set(results[0].matched_by) == {"vector", "keyword"}
    assert results[0].similarity is not None and results[0].keyword_score is not None


def test_users_never_see_each_others_passages(session):
    alice, _ = seed(session, f"{uuid.uuid4().hex}@example.com", TEXTS)
    bob, _ = seed(session, f"{uuid.uuid4().hex}@example.com", {"memo": BOB_TEXT})
    retriever = HybridRetriever(session, HashEmbedder())

    alice_results = retriever.retrieve(owner_id=alice.id, query="refund", top_k=10)
    bob_results = retriever.retrieve(owner_id=bob.id, query="refund", top_k=10)

    assert alice_results and {r.content for r in alice_results} <= set(TEXTS.values())
    assert bob_results and {r.content for r in bob_results} == {BOB_TEXT}


def test_collection_filter_limits_results(session):
    user, first = seed(session, f"{uuid.uuid4().hex}@example.com", TEXTS)
    _, second = seed(session, f"{uuid.uuid4().hex}@example.com", {"memo": BOB_TEXT})
    retriever = HybridRetriever(session, HashEmbedder())

    scoped = retriever.retrieve(
        owner_id=user.id, query="refund", collection_id=first.id, top_k=10
    )
    assert scoped
    # Someone else's collection id yields nothing for this user.
    assert retriever.retrieve(
        owner_id=user.id, query="refund", collection_id=second.id, top_k=10
    ) == []


def test_documents_that_are_not_ready_are_invisible(session):
    user, _ = seed(session, f"{uuid.uuid4().hex}@example.com", TEXTS)
    session.execute(
        update(Document).where(Document.owner_id == user.id).values(status=DocumentStatus.QUEUED)
    )
    session.flush()
    assert HybridRetriever(session, HashEmbedder()).retrieve(
        owner_id=user.id, query="refund", top_k=5
    ) == []


def test_punctuation_only_and_quoted_queries_do_not_crash(session):
    user, _ = seed(session, f"{uuid.uuid4().hex}@example.com", TEXTS)
    retriever = HybridRetriever(session, HashEmbedder())
    for query in ("?!", "what's the 'refund' policy; DROP TABLE chunks;--", "a & b | c:*"):
        assert isinstance(retriever.retrieve(owner_id=user.id, query=query, top_k=3), list)
