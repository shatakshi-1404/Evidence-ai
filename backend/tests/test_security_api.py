from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.config import settings
from app.main import create_app
from app.models.user import User
from tests.utils import auth_headers, create_collection, register, upload


def test_security_headers_and_timing_are_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["server-timing"].startswith("app;dur=")


def test_api_docs_are_not_exposed_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    production_client = TestClient(create_app())
    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404
    assert production_client.get("/api/health").status_code == 200


def test_unsigned_tokens_are_rejected(client):
    user_id = register(client).json()["id"]
    unsigned = jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        None,
        algorithm="none",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"})
    assert response.status_code == 401


def test_tokens_signed_with_another_key_are_rejected(client):
    user_id = register(client).json()["id"]
    forged = jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "a-completely-different-secret-key-0123456789",
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_deactivated_users_lose_access_immediately(client, db):
    headers = auth_headers(client)
    db.execute(update(User).where(User.email == "alice@example.com").values(is_active=False))
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_cross_user_access_matrix(client, retriever, llm):
    """Everything Alice owns is invisible to Bob, on every endpoint that takes an id."""
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")

    cid = create_collection(client, alice)
    doc_id = upload(client, alice, cid).json()["id"]
    history_id = client.post("/api/ask", json={"question": "q"}, headers=alice).json()["history_id"]

    probes = [
        ("GET", f"/api/collections/{cid}", None),
        ("DELETE", f"/api/collections/{cid}", None),
        ("GET", f"/api/collections/{cid}/documents", None),
        ("GET", f"/api/documents/{doc_id}", None),
        ("GET", f"/api/documents/{doc_id}/chunks", None),
        ("POST", f"/api/documents/{doc_id}/retry", None),
        ("DELETE", f"/api/documents/{doc_id}", None),
        ("GET", f"/api/history/{history_id}", None),
        ("DELETE", f"/api/history/{history_id}", None),
        ("POST", "/api/search", {"query": "q", "collection_id": cid}),
        ("POST", "/api/ask", {"question": "q", "collection_id": cid}),
    ]
    for method, path, body in probes:
        response = client.request(method, path, json=body, headers=bob)
        assert response.status_code == 404, f"Bob reached {method} {path} ({response.status_code})"
    assert upload(client, bob, cid).status_code == 404

    # Nothing of Alice's was touched by those attempts.
    assert client.get(f"/api/collections/{cid}", headers=alice).status_code == 200
    assert client.get(f"/api/documents/{doc_id}", headers=alice).status_code == 200
    assert client.get(f"/api/history/{history_id}", headers=alice).status_code == 200
    assert client.get("/api/collections", headers=bob).json() == []
    assert client.get("/api/history", headers=bob).json() == []


def test_upload_abuse_cases(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)

    assert upload(client, headers, cid, "report.pdf.exe", b"MZ").status_code == 415
    assert upload(client, headers, cid, "NOTES.TXT", b"upper-case extension is fine").status_code == 201

    backslashes = upload(client, headers, cid, "..\\..\\windows\\evil.txt", b"windows-style traversal")
    assert backslashes.status_code == 201
    assert backslashes.json()["filename"] == "evil.txt"

    long_name = upload(client, headers, cid, "a" * 400 + ".txt", b"very long filename")
    assert long_name.status_code == 201
    assert len(long_name.json()["filename"]) <= 255
