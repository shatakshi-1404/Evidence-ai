import uuid

from app.core.security import create_access_token
from tests.utils import login, register, auth_headers


def test_register_creates_user_without_exposing_password(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email_rejected_case_insensitively(client):
    assert register(client, email="alice@example.com").status_code == 201
    assert register(client, email="ALICE@Example.com").status_code == 409


def test_register_rejects_short_password(client):
    assert register(client, password="short").status_code == 422


def test_register_rejects_invalid_email(client):
    assert register(client, email="not-an-email").status_code == 422


def test_login_returns_bearer_token(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_email_is_case_insensitive(client):
    register(client)
    assert login(client, email="ALICE@example.com").status_code == 200


def test_login_wrong_password(client):
    register(client)
    assert login(client, password="wrong-password-123").status_code == 401


def test_login_unknown_email(client):
    assert login(client, email="nobody@example.com").status_code == 401


def test_me_returns_current_user(client):
    headers = auth_headers(client)
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 401


def test_me_rejects_expired_token(client):
    user_id = register(client).json()["id"]
    expired = create_access_token(user_id, expires_minutes=-1)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_me_rejects_token_for_nonexistent_user(client):
    token = create_access_token(str(uuid.uuid4()))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
