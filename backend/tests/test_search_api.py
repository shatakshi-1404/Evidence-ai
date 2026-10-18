import pytest

from app.api.search import get_llm, get_retriever
from app.main import app
from app.services.llm import LLMError
from tests.fakes import FakeLLM, FakeRetriever, make_candidate
from tests.utils import auth_headers, create_collection


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


def test_search_and_ask_require_authentication(client):
    assert client.post("/api/search", json={"query": "x"}).status_code == 401
    assert client.post("/api/ask", json={"question": "x"}).status_code == 401


def test_input_validation(client, retriever, llm):
    headers = auth_headers(client)
    assert client.post("/api/search", json={"query": "  "}, headers=headers).status_code == 422
    assert client.post("/api/search", json={"query": "x", "limit": 0}, headers=headers).status_code == 422
    assert client.post("/api/search", json={"query": "x", "limit": 21}, headers=headers).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 1001}, headers=headers).status_code == 422


def test_search_returns_passages_and_scopes_to_the_caller(client, retriever):
    headers = auth_headers(client)
    me = client.get("/api/auth/me", headers=headers).json()["id"]

    response = client.post("/api/search", json={"query": "refunds", "limit": 2}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["filename"] == "policy.pdf"
    assert "retrieval_ms" in body["timings"]
    assert str(retriever.calls[0]["owner_id"]) == me
    assert retriever.calls[0]["top_k"] == 2


def test_each_user_searches_only_as_themselves(client, retriever):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    client.post("/api/search", json={"query": "x"}, headers=alice)
    client.post("/api/search", json={"query": "x"}, headers=bob)
    assert retriever.calls[0]["owner_id"] != retriever.calls[1]["owner_id"]


def test_search_in_someone_elses_collection_is_a_404_and_runs_no_search(client, retriever):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    cid = create_collection(client, alice)

    for path, body in (
        ("/api/search", {"query": "x", "collection_id": cid}),
        ("/api/ask", {"question": "x", "collection_id": cid}),
    ):
        assert client.post(path, json=body, headers=bob).status_code == 404
    assert retriever.calls == []


def test_search_scoped_to_own_collection_passes_the_id_through(client, retriever):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    client.post("/api/search", json={"query": "x", "collection_id": cid}, headers=headers)
    assert str(retriever.calls[0]["collection_id"]) == cid


def test_ask_returns_a_grounded_answer_whose_citations_are_retrieved_passages(client, retriever, llm):
    headers = auth_headers(client)
    response = client.post("/api/ask", json={"question": "How long do refunds take?"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["sufficient_evidence"] is True
    assert body["answer"] == "Refunds take five days [1]."
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["marker"] == 1
    assert citation["chunk_id"] == str(retriever.candidates[0].chunk_id)
    assert citation["filename"] == "policy.pdf"
    assert [s["marker"] for s in body["sources"]] == [1, 2]


def test_ask_never_returns_an_invented_citation(client, retriever, llm):
    headers = auth_headers(client)
    llm.reply = "Refunds take five days [1]. Free shipping [9]."
    body = client.post("/api/ask", json={"question": "q"}, headers=headers).json()

    assert body["answer"] == "Refunds take five days [1]. Free shipping."
    assert [c["marker"] for c in body["citations"]] == [1]
    assert body["removed_markers"] == [9]


def test_ask_rejects_an_answer_with_only_invented_sources(client, retriever, llm):
    headers = auth_headers(client)
    llm.reply = "Something made up [9]."
    body = client.post("/api/ask", json={"question": "q"}, headers=headers).json()

    assert body["sufficient_evidence"] is False
    assert body["reason"] == "uncited_answer"
    assert body["citations"] == []


def test_ask_with_weak_evidence_skips_the_model(client, retriever, llm):
    headers = auth_headers(client)
    retriever.candidates = [make_candidate(1, similarity=0.05)]
    body = client.post("/api/ask", json={"question": "unrelated"}, headers=headers).json()

    assert body["sufficient_evidence"] is False
    assert body["reason"] == "no_relevant_passages"
    assert llm.calls == []
    assert len(body["sources"]) == 1  # the closest passages are still shown


def test_ask_turns_model_outages_into_a_502(client, retriever, llm):
    headers = auth_headers(client)
    llm.error = LLMError("down")
    response = client.post("/api/ask", json={"question": "q"}, headers=headers)
    assert response.status_code == 502
