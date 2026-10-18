import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SearchRequest(BaseModel):
    query: Query
    collection_id: uuid.UUID | None = None
    limit: int = Field(default=6, ge=1, le=20)


class PassageRead(BaseModel):
    marker: int | None = None  # the [n] used in answers (only set by /ask)
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float
    similarity: float | None
    keyword_score: float | None
    matched_by: list[str]


class SearchResponse(BaseModel):
    query: str
    results: list[PassageRead]
    timings: dict[str, int]


class AskRequest(BaseModel):
    question: Question
    collection_id: uuid.UUID | None = None


class CitationRead(BaseModel):
    marker: int
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    snippet: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sufficient_evidence: bool
    reason: str | None
    citations: list[CitationRead]
    sources: list[PassageRead]
    removed_markers: list[int]  # invented citations we stripped (for transparency)
    timings: dict[str, int]
    history_id: uuid.UUID | None = None  # the saved history entry for this answer
