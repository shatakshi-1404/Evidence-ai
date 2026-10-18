import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers tables on Base)
from app.api.search import get_llm, get_retriever
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from tests.fakes import FakeLLM, FakeRetriever, make_candidate


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Every test writes uploads to its own temporary folder."""
    path = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(path))
    return path


@pytest.fixture(autouse=True)
def enqueued(monkeypatch):
    """Replace the Redis queue with a list that records enqueued document IDs."""
    calls: list = []
    monkeypatch.setattr(
        "app.api.documents.enqueue_ingestion",
        lambda document_id, **kwargs: calls.append(document_id),
    )
    return calls


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # SQLite ignores ON DELETE CASCADE unless told otherwise; PostgreSQL doesn't.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    """A test client wired to a fresh, empty database for every test."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db(session_factory):
    """A session for tests that call the ingestion code or inspect rows directly."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def hash_embeddings(monkeypatch):
    """Tests never load a real model; they use the deterministic hash embedder."""
    monkeypatch.setattr(settings, "embedding_provider", "hash")


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """The rate limiter talks to an in-memory Redis, fresh for every test."""
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr("app.services.ratelimit.get_redis", lambda: client)
    return client


@pytest.fixture()
def retriever(client):
    fake = FakeRetriever([make_candidate(1, similarity=0.8), make_candidate(2, similarity=0.7)])
    app.dependency_overrides[get_retriever] = lambda: fake
    return fake


@pytest.fixture()
def llm(client):
    fake = FakeLLM("Refunds take five days [1].")
    app.dependency_overrides[get_llm] = lambda: fake
    return fake
