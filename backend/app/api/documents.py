import hashlib
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.collections import get_owned_collection
from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.schemas.document import ChunkRead, DocumentRead
from app.services import storage
from app.services.queue import enqueue_ingestion
from app.services.validation import UploadValidationError, clean_filename, validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


def get_owned_document(db: DbSession, document_id: uuid.UUID, user: CurrentUser) -> Document:
    """Same isolation rule as collections: the owner filter is inside the query."""
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == user.id)
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


def _try_enqueue(document_id: uuid.UUID) -> None:
    """If Redis is down the upload still succeeds; the worker re-queues on startup."""
    try:
        enqueue_ingestion(document_id)
    except Exception:
        logger.warning("Could not enqueue document %s", document_id, exc_info=True)


@router.post(
    "/collections/{collection_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    collection_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> Document:
    # Ownership first, so a stranger learns nothing and we read no body for them.
    get_owned_collection(db, collection_id, user)

    # Read at most limit+1 bytes: enough to know whether it's too big.
    max_bytes = settings.max_upload_bytes
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File too large (max {settings.max_upload_mb} MB)",
        )

    try:
        extension, content_type = validate_upload(file.filename, data)
    except UploadValidationError as exc:
        raise HTTPException(exc.status_code, str(exc))

    digest = hashlib.sha256(data).hexdigest()
    already_there = db.scalar(
        select(Document.id).where(
            Document.collection_id == collection_id, Document.sha256 == digest
        )
    )
    if already_there:
        raise HTTPException(status.HTTP_409_CONFLICT, "This file is already in the collection")

    document_id = uuid.uuid4()
    storage_path = storage.save_file(user.id, document_id, extension, data)
    document = Document(
        id=document_id,
        owner_id=user.id,
        collection_id=collection_id,
        filename=clean_filename(file.filename),
        content_type=content_type,  # decided by us, not the client
        size_bytes=len(data),
        sha256=digest,
        storage_path=storage_path,
        status=DocumentStatus.QUEUED,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError:
        # Two identical uploads at the same instant: the unique constraint wins.
        db.rollback()
        storage.delete_file(storage_path)
        raise HTTPException(status.HTTP_409_CONFLICT, "This file is already in the collection")
    except Exception:
        db.rollback()
        storage.delete_file(storage_path)  # don't leave an orphan file behind
        raise
    db.refresh(document)

    _try_enqueue(document.id)  # only after the row is safely committed
    return document


@router.get("/collections/{collection_id}/documents", response_model=list[DocumentRead])
def list_documents(collection_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[Document]:
    get_owned_collection(db, collection_id, user)
    stmt = (
        select(Document)
        .where(Document.collection_id == collection_id, Document.owner_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Document:
    return get_owned_document(db, document_id, user)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRead])
def list_chunks(
    document_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Chunk]:
    document = get_owned_document(db, document_id, user)
    stmt = (
        select(Chunk)
        .where(Chunk.document_id == document.id, Chunk.owner_id == user.id)
        .order_by(Chunk.chunk_index)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/documents/{document_id}/retry",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_document(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Document:
    document = get_owned_document(db, document_id, user)
    if document.status != DocumentStatus.FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed documents can be retried")
    document.status = DocumentStatus.QUEUED
    document.attempts = 0
    document.error_message = None
    db.commit()
    db.refresh(document)
    _try_enqueue(document.id)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    document = get_owned_document(db, document_id, user)
    path = document.storage_path
    db.delete(document)  # the database cascade removes its chunks
    db.commit()
    storage.delete_file(path)  # remove the file only after the row is gone
