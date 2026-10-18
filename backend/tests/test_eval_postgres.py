import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PG_TESTS") != "1",
    reason="needs a migrated PostgreSQL; run with RUN_PG_TESTS=1",
)

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.evaluation.runner import run_evaluation  # noqa: E402
from app.models import Chunk, User  # noqa: E402


def test_full_evaluation_runs_and_leaves_nothing_behind():
    engine = create_engine(settings.sqlalchemy_database_url)
    with Session(engine) as db:
        before_chunks = db.scalar(select(func.count()).select_from(Chunk))

        report = run_evaluation(db)

        assert set(report.retrieval) == {"vector", "keyword", "hybrid"}
        for metrics in report.retrieval.values():
            assert 0 <= metrics.hit_at_1 <= metrics.hit_at_3 <= metrics.hit_at_5 <= 1
            assert 0 <= metrics.mrr <= 1
        assert report.dataset.questions == report.dataset.answerable + report.dataset.unanswerable
        assert report.pipeline.ask_count == report.dataset.questions
        assert len(report.questions) == report.dataset.questions
        assert report.dataset.chunks > report.dataset.documents

        # The throwaway user, its documents and its chunks are all gone.
        leftover = db.scalar(
            select(func.count()).select_from(User).where(User.email.like("eval-%@evidenceai.invalid"))
        )
        assert leftover == 0
        assert db.scalar(select(func.count()).select_from(Chunk)) == before_chunks
    engine.dispose()
