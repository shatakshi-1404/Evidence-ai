from datetime import datetime, timezone

import pytest

from app.evaluation.metrics import (
    best_similarity,
    first_hit_rank,
    has_evidence,
    hit_rate,
    mean_reciprocal_rank,
    percentile,
    recommend_threshold,
    support_score,
    sweep_thresholds,
)
from app.evaluation.runner import check_thresholds
from app.schemas.evaluation import (
    DatasetInfo,
    EvalReport,
    PipelineMetrics,
    RetrievalMetrics,
    ThresholdAnalysis,
)
from tests.fakes import make_candidate


def test_evidence_matching_ignores_case_and_spacing():
    assert has_evidence("The Quick   brown\nfox", ["quick brown"])
    assert not has_evidence("The quick fox", ["quick brown"])
    assert not has_evidence("anything", [])
    assert not has_evidence("anything", ["   "])


def test_first_hit_rank():
    contents = ["alpha", "the answer is here", "gamma"]
    assert first_hit_rank(contents, ["answer is here"]) == 2
    assert first_hit_rank(contents, ["missing"]) is None


def test_hit_rate_and_mrr():
    ranks = [1, 3, None, 6]
    assert hit_rate(ranks, 1) == pytest.approx(0.25)
    assert hit_rate(ranks, 3) == pytest.approx(0.5)
    assert hit_rate(ranks, 5) == pytest.approx(0.5)
    assert mean_reciprocal_rank(ranks) == pytest.approx(0.375)
    assert hit_rate([], 3) == 0.0 and mean_reciprocal_rank([]) == 0.0


def test_percentile_uses_nearest_rank():
    values = [float(n) for n in range(1, 11)]
    assert percentile(values, 50) == 5.0
    assert percentile(values, 95) == 10.0
    assert percentile([], 50) == 0.0


def test_best_similarity_ignores_keyword_only_hits():
    candidates = [make_candidate(1, similarity=0.4), make_candidate(2, similarity=None), make_candidate(3, similarity=0.7)]
    assert best_similarity(candidates) == 0.7
    assert best_similarity([make_candidate(1, similarity=None)]) is None


def test_threshold_sweep_and_recommendation():
    points = sweep_thresholds(answerable_best=[0.8, 0.6, None], unanswerable_best=[0.3, 0.55])
    at_half = next(p for p in points if p.threshold == 0.5)
    assert at_half.answerable_pass_rate == pytest.approx(2 / 3)
    assert at_half.unanswerable_refusal_rate == pytest.approx(0.5)
    assert recommend_threshold(points) == 0.6


def test_support_score_rewards_overlap_and_ignores_citation_markers():
    passage = "Refunds are issued within seven business days."
    assert support_score("Refunds are issued within seven business days [1].", [passage]) == 1.0
    assert support_score("Dragons breathe volcanic fire [1].", [passage]) == 0.0
    assert support_score("", [passage]) == 0.0
    assert support_score("Refunds", []) == 0.0


def make_report(hit5=0.9, mrr=0.8, answered=0.9, refusal=0.8, cited=0.8) -> EvalReport:
    retrieval = RetrievalMetrics(
        hit_at_1=0.5, hit_at_3=0.7, hit_at_5=hit5, mrr=mrr, latency_p50_ms=1, latency_p95_ms=2
    )
    return EvalReport(
        generated_at=datetime.now(timezone.utc),
        embedding_model="x",
        llm_provider="extractive",
        k=5,
        dataset=DatasetInfo(documents=1, chunks=1, questions=1, answerable=1, unanswerable=0),
        retrieval={"vector": retrieval, "keyword": retrieval, "hybrid": retrieval},
        threshold=ThresholdAnalysis(points=[], recommended=0.5, current=0.5),
        pipeline=PipelineMetrics(
            ask_count=1, answered_rate=answered, refusal_rate=refusal, cited_evidence_rate=cited,
            invented_citation_rate=0, avg_support=1, latency_p50_ms=1, latency_p95_ms=2, llm_errors=0,
        ),
        questions=[],
    )


def test_quality_gate_passes_and_fails():
    bar = {"hybrid_hit_at_5": 0.8, "hybrid_mrr": 0.6, "refusal_rate": 0.4}
    assert check_thresholds(make_report(), bar) == []

    failures = check_thresholds(make_report(hit5=0.5, refusal=0.1), bar)
    assert len(failures) == 2
    assert any("hybrid_hit_at_5" in f for f in failures)
    assert any("refusal_rate" in f for f in failures)

    assert check_thresholds(make_report(), {"nonsense": 1.0})  # unknown names are reported
