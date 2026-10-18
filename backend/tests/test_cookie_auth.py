import pytest

from app.core.config import settings
from tests.utils import login, register


def test_login_sets_an_httponly_lax_cookie(client):
    register(client)
    cookie = login(client).headers["set-cookie"].lower()
    assert settings.cookie_name in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "; secure" not in cookie  # development runs over plain http


def test_cookie_is_marked_secure_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    register(client)
    assert "; secure" in login(client).headers["set-cookie"].lower()


def test_cookie_authenticates_without_any_header(client):
    register(client)
    assert login(client).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_logout_clears_the_session(client):
    register(client)
    login(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_a_garbage_cookie_is_rejected(client):
    client.cookies.set(settings.cookie_name, "not-a-token")
    assert client.get("/api/auth/me").status_code == 401


def test_cookie_requests_from_other_origins_cannot_change_data(client):
    register(client)
    login(client)

    blocked = client.post("/api/collections", json={"name": "x"}, headers={"Origin": "https://evil.example"})
    assert blocked.status_code == 403

    allowed = client.post("/api/collections", json={"name": "x"}, headers={"Origin": "http://localhost:5173"})
    assert allowed.status_code == 201
    assert client.post("/api/collections", json={"name": "y"}).status_code == 201  # no Origin header

    # Reading is never blocked by this check.
    assert client.get("/api/collections", headers={"Origin": "https://evil.example"}).status_code == 200
