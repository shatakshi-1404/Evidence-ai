from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "EvidenceAI"
    assert "timestamp" in body


def test_unknown_route_returns_404():
    assert client.get("/api/does-not-exist").status_code == 404
