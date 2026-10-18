import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, DbSession
from app.models.ask_history import AskHistory
from app.schemas.history import HistoryDetail, HistoryItem

router = APIRouter(prefix="/history", tags=["history"])


def get_owned_history(db: DbSession, history_id: uuid.UUID, user: CurrentUser) -> AskHistory:
    """Same isolation rule as everywhere: the owner filter is inside the query."""
    item = db.scalar(
        select(AskHistory).where(AskHistory.id == history_id, AskHistory.owner_id == user.id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History entry not found")
    return item


@router.get("", response_model=list[HistoryItem])
def list_history(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AskHistory]:
    stmt = (
        select(AskHistory)
        .where(AskHistory.owner_id == user.id)
        .options(defer(AskHistory.response))  # the list doesn't need the big JSON
        .order_by(AskHistory.created_at.desc(), AskHistory.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())


@router.get("/{history_id}", response_model=HistoryDetail)
def get_history(history_id: uuid.UUID, db: DbSession, user: CurrentUser) -> AskHistory:
    return get_owned_history(db, history_id, user)


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(history_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    item = get_owned_history(db, history_id, user)
    db.delete(item)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(db: DbSession, user: CurrentUser) -> None:
    """Deletes only the caller's own entries."""
    db.execute(delete(AskHistory).where(AskHistory.owner_id == user.id))
    db.commit()
