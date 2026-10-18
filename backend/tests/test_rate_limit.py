import redis

from app.core.config import settings
from tests.utils import auth_headers, login, register


def ask(client, headers):
    return client.post("/api/ask", json={"question": "q"}, headers=headers)


def test_ask_is_limited_per_user_and_separately_from_search(client, retriever, llm, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_ask_per_minute", 2)
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")

    assert ask(client, alice).status_code == 200
    assert ask(client, alice).status_code == 200
    blocked = ask(client, alice)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1

    assert ask(client, bob).status_code == 200  # Bob has his own budget
    assert client.post("/api/search", json={"query": "q"}, headers=alice).status_code == 200


def test_a_limit_of_zero_disables_limiting(client, retriever, llm, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_ask_per_minute", 0)
    headers = auth_headers(client)
    assert all(ask(client, headers).status_code == 200 for _ in range(5))


def test_login_attempts_are_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 3)
    register(client)  # uses one of the three
    statuses = [login(client, password="wrong-password-1").status_code for _ in range(3)]
    assert statuses == [401, 401, 429]


def test_unauthenticated_requests_get_401_not_429(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_ask_per_minute", 1)
    assert client.post("/api/ask", json={"question": "q"}).status_code == 401
    assert client.post("/api/ask", json={"question": "q"}).status_code == 401


def test_rate_limiter_fails_open_when_redis_is_down(client, retriever, llm, monkeypatch):
    class BrokenRedis:
        def incr(self, key):
            raise redis.ConnectionError("redis is down")

    monkeypatch.setattr("app.services.ratelimit.get_redis", lambda: BrokenRedis())
    monkeypatch.setattr(settings, "rate_limit_ask_per_minute", 1)
    headers = auth_headers(client)
    assert ask(client, headers).status_code == 200
    assert ask(client, headers).status_code == 200
