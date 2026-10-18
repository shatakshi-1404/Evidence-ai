import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus:
    QUEUED = "queued"          # waiting for a worker
    PROCESSING = "processing"  # a worker is extracting and chunking
    READY = "ready"            # chunks saved, searchable
    FAILED = "failed"          # see error_message


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # The same file (same bytes) can't be added twice to one collection.
        UniqueConstraint("collection_id", "sha256", name="uq_documents_collection_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))  # display only, never used as a path
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(512))  # relative to UPLOAD_DIR

    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.QUEUED, server_default="queued", index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    embedding_model: Mapped[str | None] = mapped_column(String(100), default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
