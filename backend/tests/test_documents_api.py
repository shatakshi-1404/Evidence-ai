import uuid
from pathlib import Path

from sqlalchemy import func, select, update

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services.ingestion import process_document
from tests.utils import SAMPLE_TEXT, auth_headers, create_collection, upload


def stored_files() -> list[Path]:
    return [p for p in Path(settings.upload_dir).rglob("*") if p.is_file()]


def test_documents_require_authentication(client):
    assert client.get(f"/api/collections/{uuid.uuid4()}/documents").status_code == 401
    assert client.get(f"/api/documents/{uuid.uuid4()}").status_code == 401


def test_upload_text_document(client, enqueued):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    data = b"Hello evidence world."

    response = upload(client, headers, cid, "notes.txt", data)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["content_type"] == "text/plain"
    assert body["size_bytes"] == len(data)
    assert body["status"] == "queued"
    assert body["chunk_count"] == 0
    assert "storage_path" not in body and "sha256" not in body
    assert enqueued == [uuid.UUID(body["id"])]
    assert len(stored_files()) == 1


def test_client_supplied_content_type_is_ignored(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    response = upload(client, headers, cid, "a.txt", b"hi", content_type="application/x-msdownload")
    assert response.json()["content_type"] == "text/plain"


def test_rejects_unsupported_type(client, enqueued):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    response = upload(client, headers, cid, "malware.exe", b"MZ\x90\x00")
    assert response.status_code == 415
    assert enqueued == [] and stored_files() == []


def test_rejects_empty_file(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    assert upload(client, headers, cid, "empty.txt", b"").status_code == 422


def test_rejects_fake_pdf(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    assert upload(client, headers, cid, "invoice.pdf", b"just some text").status_code == 422


def test_rejects_binary_data_named_txt(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    assert upload(client, headers, cid, "data.txt", b"abc\x00def").status_code == 422


def test_rejects_non_utf8_text(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    assert upload(client, headers, cid, "latin.txt", b"\xff\xfe\xfa").status_code == 422


def test_size_limit_is_enforced_exactly(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    one_mb = 1024 * 1024
    assert upload(client, headers, cid, "ok.txt", b"a" * one_mb).status_code == 201
    assert upload(client, headers, cid, "big.txt", b"b" * (one_mb + 1)).status_code == 413


def test_duplicate_file_rejected_in_same_collection_only(client):
    headers = auth_headers(client)
    first = create_collection(client, headers, "One")
    second = create_collection(client, headers, "Two")
    assert upload(client, headers, first, "a.txt", b"same bytes").status_code == 201
    assert upload(client, headers, first, "copy.txt", b"same bytes").status_code == 409
    assert upload(client, headers, second, "a.txt", b"same bytes").status_code == 201


def test_cannot_upload_to_someone_elses_collection(client, enqueued):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    cid = create_collection(client, alice)

    assert upload(client, bob, cid).status_code == 404
    assert enqueued == [] and stored_files() == []


def test_documents_are_isolated_between_users(client):
    alice = auth_headers(client, email="alice@example.com")
    bob = auth_headers(client, email="bob@example.com", full_name="Bob")
    cid = create_collection(client, alice)
    doc_id = upload(client, alice, cid).json()["id"]

    assert client.get(f"/api/collections/{cid}/documents", headers=bob).status_code == 404
    assert client.get(f"/api/documents/{doc_id}", headers=bob).status_code == 404
    assert client.get(f"/api/documents/{doc_id}/chunks", headers=bob).status_code == 404
    assert client.post(f"/api/documents/{doc_id}/retry", headers=bob).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=bob).status_code == 404

    assert client.get(f"/api/documents/{doc_id}", headers=alice).status_code == 200


def test_filename_path_tricks_are_neutralised(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    response = upload(client, headers, cid, "../../etc/passwd.txt", b"data")

    assert response.status_code == 201
    assert response.json()["filename"] == "passwd.txt"
    root = Path(settings.upload_dir).resolve()
    assert all(root in path.resolve().parents for path in stored_files())


def test_list_documents(client):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    upload(client, headers, cid, "a.txt", b"first")
    upload(client, headers, cid, "b.txt", b"second")
    listed = client.get(f"/api/collections/{cid}/documents", headers=headers).json()
    assert {d["filename"] for d in listed} == {"a.txt", "b.txt"}


def test_delete_document_removes_file_and_chunks(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    doc_id = upload(client, headers, cid, "a.txt", SAMPLE_TEXT.encode()).json()["id"]
    assert process_document(db, uuid.UUID(doc_id)).outcome == "ready"
    assert db.scalar(select(func.count()).select_from(Chunk)) > 0
    assert len(stored_files()) == 1

    assert client.delete(f"/api/documents/{doc_id}", headers=headers).status_code == 204

    assert client.get(f"/api/documents/{doc_id}", headers=headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(Chunk)) == 0
    assert stored_files() == []


def test_deleting_a_collection_deletes_its_documents_and_files(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    upload(client, headers, cid, "a.txt", b"first")
    upload(client, headers, cid, "b.txt", b"second")
    assert len(stored_files()) == 2

    assert client.delete(f"/api/collections/{cid}", headers=headers).status_code == 204

    assert stored_files() == []
    assert db.scalar(select(func.count()).select_from(Document)) == 0


def test_retry_only_works_for_failed_documents(client, db, enqueued):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    doc_id = upload(client, headers, cid).json()["id"]
    assert client.post(f"/api/documents/{doc_id}/retry", headers=headers).status_code == 409

    db.execute(
        update(Document)
        .where(Document.id == uuid.UUID(doc_id))
        .values(status=DocumentStatus.FAILED, attempts=3, error_message="boom")
    )
    db.commit()
    enqueued.clear()

    response = client.post(f"/api/documents/{doc_id}/retry", headers=headers)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["attempts"] == 0
    assert body["error_message"] is None
    assert enqueued == [uuid.UUID(doc_id)]


def test_chunks_endpoint_paginates(client, db):
    headers = auth_headers(client)
    cid = create_collection(client, headers)
    doc_id = upload(client, headers, cid, "a.txt", SAMPLE_TEXT.encode()).json()["id"]

    url = f"/api/documents/{doc_id}/chunks"
    assert client.get(url, headers=headers).json() == []  # not processed yet

    process_document(db, uuid.UUID(doc_id))
    first_two = client.get(url, params={"limit": 2}, headers=headers).json()
    assert [c["chunk_index"] for c in first_two] == [0, 1]
    next_page = client.get(url, params={"limit": 2, "offset": 2}, headers=headers).json()
    assert next_page[0]["chunk_index"] == 2
    assert client.get(url, params={"limit": 0}, headers=headers).status_code == 422
