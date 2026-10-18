import uuid

import pytest

from app.services.llm import LLMError
from app.services.rag import INSUFFICIENT_MESSAGE, answer_question
from tests.fakes import FakeLLM, FakeRetriever, make_candidate

OWNER = uuid.uuid4()


def ask(retriever, llm):
    return answer_question(
        question="How long do refunds take?",
        owner_id=OWNER,
        collection_id=None,
        retriever=retriever,
        llm=llm,
        min_similarity=0.5,
    )


def test_grounded_answer_is_returned_with_citations():
    retriever = FakeRetriever([make_candidate(1, similarity=0.8), make_candidate(2, similarity=0.6)])
    result = ask(retriever, FakeLLM("Refunds take five days [1]."))

    assert result.sufficient_evidence
    assert result.answer == "Refunds take five days [1]."
    assert result.cited_markers == [1]
    assert len(result.sources) == 2
    assert retriever.calls[0]["owner_id"] == OWNER
    assert set(result.timings) == {"retrieval_ms", "generation_ms", "total_ms"}


def test_weak_retrieval_never_reaches_the_model():
    llm = FakeLLM("should not be used [1]")
    result = ask(FakeRetriever([make_candidate(1, similarity=0.1)]), llm)

    assert not result.sufficient_evidence
    assert result.reason == "no_relevant_passages"
    assert result.answer == INSUFFICIENT_MESSAGE
    assert llm.calls == []


def test_nothing_retrieved_means_insufficient_evidence():
    llm = FakeLLM("anything [1]")
    result = ask(FakeRetriever([]), llm)
    assert not result.sufficient_evidence and llm.calls == []


def test_keyword_only_matches_do_not_count_as_evidence():
    candidate = make_candidate(1, similarity=None, keyword_score=0.4)
    result = ask(FakeRetriever([candidate]), FakeLLM("x [1]"))
    assert not result.sufficient_evidence


def test_model_can_decline():
    result = ask(FakeRetriever([make_candidate(1)]), FakeLLM("INSUFFICIENT_EVIDENCE"))
    assert not result.sufficient_evidence
    assert result.reason == "model_declined"
    assert result.answer == INSUFFICIENT_MESSAGE


def test_invented_citation_is_stripped_and_reported():
    retriever = FakeRetriever([make_candidate(1), make_candidate(2)])
    result = ask(retriever, FakeLLM("Refunds take five days [1]. Shipping is free [7]."))

    assert result.sufficient_evidence
    assert result.answer == "Refunds take five days [1]. Shipping is free."
    assert result.cited_markers == [1]
    assert result.removed_markers == [7]


def test_answer_citing_only_invented_sources_is_rejected():
    result = ask(FakeRetriever([make_candidate(1)]), FakeLLM("Totally made up [42]."))
    assert not result.sufficient_evidence
    assert result.reason == "uncited_answer"
    assert result.cited_markers == []
    assert result.removed_markers == [42]


def test_uncited_answer_is_rejected():
    result = ask(FakeRetriever([make_candidate(1)]), FakeLLM("Refunds take five days."))
    assert not result.sufficient_evidence
    assert result.reason == "uncited_answer"


def test_marker_numbers_follow_source_order():
    retriever = FakeRetriever([make_candidate(1), make_candidate(2), make_candidate(3)])
    result = ask(retriever, FakeLLM(lambda passages: f"The last source says so [{len(passages)}]."))
    assert result.cited_markers == [3]


def test_llm_errors_propagate():
    with pytest.raises(LLMError):
        ask(FakeRetriever([make_candidate(1)]), FakeLLM(error=LLMError("down")))
