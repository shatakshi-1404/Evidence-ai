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


def ask(client, headers, question="How long do refunds take?", **extra):
    response = client.post("/api/ask", json={"question": question, **extra}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_history_requires_authentication(client):
    assert client.get("/api/history").status_code == 401
    assert client.delete("/api/history").status_code == 401


def test_every_answer_is_saved_and_can_be_reopened(client, retriever, llm):
    headers = auth_headers(client)
    answer = ask(client, headers)
    assert answer["history_id"]

    items = client.get("/api/history", headers=headers).json()
    assert [item["id"] for item in items] == [answer["history_id"]]
    assert items[0]["question"] == "How long do refunds take?"
    assert items[0]["sufficient_evidence"] is True
    assert "response" not in items[0]

    detail = client.get(f"/api/history/{answer['history_id']}", headers=headers).json()
    assert detail["response"]["answer"] == answer["answer"]
    assert detail["response"]["citations"] == answer["citations"]
    assert detail["response"]["sources"] == answer["sources"]


def test_answers_without_enough_evidence_are_saved_too(client, retriever, llm):
    headers = auth_headers(client)
    retriever.candidates = [make_candidate(1, similarity=0.05)]
    answer = ask(client, headers, "unrelated question")

    items = client.get("/api/history", headers=headers).json()
    assert items[0]["id"] == answer["history_id"]
    assert items[0]["sufficient_evidence"] is False


def test_failed_asks_are_not_saved(client, retriever, llm):
    headers = auth_headers(client)
    llm.error = LLMError("down")
    assert client.post("/api/ask", json={"question": "q"}, headers=headers).status_code == 502
    assert client.get("/api/history", headers=headers).json() == []


def test_history_is_private_to_each_user(client, retriever, llm):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    entry = ask(client, alice)["history_id"]

    assert client.get("/api/history", headers=bob).json() == []
    assert client.get(f"/api/history/{entry}", headers=bob).status_code == 404
    assert client.delete(f"/api/history/{entry}", headers=bob).status_code == 404
    assert client.get(f"/api/history/{entry}", headers=alice).status_code == 200


def test_delete_one_entry(client, retriever, llm):
    headers = auth_headers(client)
    first = ask(client, headers, "first")["history_id"]
    second = ask(client, headers, "second")["history_id"]

    assert client.delete(f"/api/history/{first}", headers=headers).status_code == 204

    remaining = [item["id"] for item in client.get("/api/history", headers=headers).json()]
    assert remaining == [second]


def test_clearing_history_only_clears_the_callers_entries(client, retriever, llm):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    ask(client, alice)
    ask(client, bob)

    assert client.delete("/api/history", headers=alice).status_code == 204

    assert client.get("/api/history", headers=alice).json() == []
    assert len(client.get("/api/history", headers=bob).json()) == 1


def test_history_survives_deleting_its_collection(client, retriever, llm):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    ask(client, headers, collection_id=cid)
    assert client.get("/api/history", headers=headers).json()[0]["collection_id"] == cid

    assert client.delete(f"/api/collections/{cid}", headers=headers).status_code == 204

    items = client.get("/api/history", headers=headers).json()
    assert len(items) == 1 and items[0]["collection_id"] is None


def test_pagination_limits_are_validated(client):
    headers = auth_headers(client)
    assert client.get("/api/history", params={"limit": 0}, headers=headers).status_code == 422
    assert client.get("/api/history", params={"limit": 101}, headers=headers).status_code == 422
