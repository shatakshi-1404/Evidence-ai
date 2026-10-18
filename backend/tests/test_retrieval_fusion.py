from dataclasses import replace

from app.services.retrieval import build_tsquery, rrf_fuse, vector_literal
from tests.fakes import make_candidate


def test_passage_found_by_both_searches_ranks_first_and_keeps_both_scores():
    a, b, c = make_candidate(1), make_candidate(2), make_candidate(3)
    vector_hits = [replace(b, similarity=0.9), replace(a, similarity=0.4)]
    keyword_hits = [replace(a, similarity=None, keyword_score=0.5), replace(c, similarity=None, keyword_score=0.2)]

    fused = rrf_fuse(vector_hits, keyword_hits, k=60)

    assert [item.chunk_id for item in fused] == [a.chunk_id, b.chunk_id, c.chunk_id]
    assert fused[0].similarity == 0.4
    assert fused[0].keyword_score == 0.5
    assert set(fused[0].matched_by) == {"vector", "keyword"}
    assert fused[1].matched_by == ("vector",)
    assert fused[2].matched_by == ("keyword",)


def test_scores_follow_the_rrf_formula():
    a = make_candidate(1)
    fused = rrf_fuse([a], [replace(a, similarity=None)], k=60)
    assert abs(fused[0].score - (1 / 61 + 1 / 61)) < 1e-12


def test_empty_inputs():
    assert rrf_fuse([], []) == []


def test_ties_are_ordered_deterministically():
    b, c = make_candidate(2), make_candidate(3)
    fused = rrf_fuse([b], [replace(c, similarity=None)])
    assert [item.chunk_id for item in fused] == sorted([b.chunk_id, c.chunk_id], key=str)


def test_tsquery_uses_or_between_words():
    assert build_tsquery("What is the refund policy?") == "what | is | the | refund | policy"


def test_tsquery_cannot_be_injected_with_operators():
    assert build_tsquery("a' & b | c:* ) ( !d") == "a | b | c | d"


def test_tsquery_deduplicates_and_handles_junk():
    assert build_tsquery("refund refund REFUND") == "refund"
    assert build_tsquery("?!?") == ""


def test_tsquery_is_capped():
    long_query = " ".join(f"w{i}" for i in range(100))
    assert len(build_tsquery(long_query).split(" | ")) == 32


def test_vector_literal_format():
    assert vector_literal([0.5, -1.0]) == "[0.5,-1]"
