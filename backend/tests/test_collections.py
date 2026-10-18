import uuid

from tests.utils import auth_headers


def test_collections_require_authentication(client):
    assert client.get("/api/collections").status_code == 401
    assert client.post("/api/collections", json={"name": "x"}).status_code == 401


def test_create_and_list_collection(client):
    headers = auth_headers(client)
    response = client.post(
        "/api/collections",
        json={"name": "Research", "description": "Papers"},
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Research"

    listed = client.get("/api/collections", headers=headers).json()
    assert [c["id"] for c in listed] == [created["id"]]


def test_name_is_required_and_trimmed(client):
    headers = auth_headers(client)
    blank = client.post("/api/collections", json={"name": "   "}, headers=headers)
    assert blank.status_code == 422

    padded = client.post("/api/collections", json={"name": "  Notes  "}, headers=headers)
    assert padded.json()["name"] == "Notes"


def test_get_own_collection(client):
    headers = auth_headers(client)
    created = client.post("/api/collections", json={"name": "Mine"}, headers=headers).json()
    response = client.get(f"/api/collections/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Mine"


def test_users_cannot_see_each_others_collections(client):
    alice = auth_headers(client, email="alice@example.com", full_name="Alice")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")

    created = client.post(
        "/api/collections", json={"name": "Alice private"}, headers=alice
    ).json()
    cid = created["id"]

    # Bob sees nothing, and can't read or delete Alice's collection.
    assert client.get("/api/collections", headers=bob).json() == []
    assert client.get(f"/api/collections/{cid}", headers=bob).status_code == 404
    assert client.delete(f"/api/collections/{cid}", headers=bob).status_code == 404

    # Alice's collection is untouched.
    assert client.get(f"/api/collections/{cid}", headers=alice).status_code == 200


def test_delete_own_collection(client):
    headers = auth_headers(client)
    created = client.post("/api/collections", json={"name": "Temp"}, headers=headers).json()
    url = f"/api/collections/{created['id']}"
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_unknown_id_returns_404(client):
    headers = auth_headers(client)
    response = client.get(f"/api/collections/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_malformed_id_returns_422(client):
    headers = auth_headers(client)
    assert client.get("/api/collections/not-a-uuid", headers=headers).status_code == 422
