import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    """Deliberately omits storage_path and sha256: internal details we don't expose."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collection_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error_message: str | None
    attempts: int
    page_count: int | None
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    page_number: int | None
    content: str
    char_count: int
