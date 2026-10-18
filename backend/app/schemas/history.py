import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.search import AskResponse


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    collection_id: uuid.UUID | None
    sufficient_evidence: bool
    created_at: datetime


class HistoryDetail(HistoryItem):
    response: AskResponse
