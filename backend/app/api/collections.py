import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.collection import Collection
from app.models.document import Document
from app.schemas.collection import CollectionCreate, CollectionRead
from app.services import storage

router = APIRouter(prefix="/collections", tags=["collections"])


def get_owned_collection(
    db: DbSession, collection_id: uuid.UUID, user: CurrentUser
) -> Collection:
    """The isolation rule lives here: the owner filter is part of the query itself.

    Someone else's collection is indistinguishable from one that doesn't exist.
    We return 404 rather than 403 so we don't even confirm that the ID is real.
    """
    collection = db.scalar(
        select(Collection).where(
            Collection.id == collection_id, Collection.owner_id == user.id
        )
    )
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collection not found")
    return collection


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CollectionCreate, db: DbSession, user: CurrentUser
) -> Collection:
    collection = Collection(
        owner_id=user.id, name=payload.name, description=payload.description
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


@router.get("", response_model=list[CollectionRead])
def list_collections(db: DbSession, user: CurrentUser) -> list[Collection]:
    stmt = (
        select(Collection)
        .where(Collection.owner_id == user.id)
        .order_by(Collection.created_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.get("/{collection_id}", response_model=CollectionRead)
def get_collection(
    collection_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Collection:
    return get_owned_collection(db, collection_id, user)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    collection = get_owned_collection(db, collection_id, user)
    # Remember the file paths first; after the delete the rows are gone.
    paths = list(
        db.scalars(
            select(Document.storage_path).where(Document.collection_id == collection.id)
        ).all()
    )
    db.delete(collection)  # cascades to documents and chunks in the database
    db.commit()
    for path in paths:
        storage.delete_file(path)
