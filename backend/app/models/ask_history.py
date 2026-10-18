import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AskHistory(Base):
    """A saved snapshot of one question and the full answer shown to the user.

    It is a snapshot: if a document is deleted later, the old answer still
    shows what it said at the time.
    """

    __tablename__ = "ask_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # If the collection is deleted, keep the history entry and just forget the link.
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"), default=None
    )
    question: Mapped[str] = mapped_column(Text)
    sufficient_evidence: Mapped[bool] = mapped_column(Boolean)
    # JSONB on PostgreSQL, plain JSON on SQLite (used by the fast tests).
    response: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
