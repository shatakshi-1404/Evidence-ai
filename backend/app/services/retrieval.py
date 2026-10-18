import re
import uuid
from dataclasses import dataclass, replace
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embeddings import Embedder


@dataclass(frozen=True)
class Candidate:
    """A retrieved passage plus the evidence for why it was retrieved."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    similarity: float | None = None     # cosine similarity (vector search)
    keyword_score: float | None = None  # ts_rank_cd (keyword search)
    score: float = 0.0                  # fused RRF score, used for ordering
    matched_by: tuple[str, ...] = ()    # ("vector",), ("keyword",) or both


class Retriever(Protocol):
    def retrieve(
        self,
        *,
        owner_id: uuid.UUID,
        query: str,
        collection_id: uuid.UUID | None = None,
        top_k: int = 6,
    ) -> list[Candidate]: ...


def rrf_fuse(
    vector_hits: list[Candidate], keyword_hits: list[Candidate], k: int = 60
) -> list[Candidate]:
    """Reciprocal Rank Fusion. Each list contributes 1/(k+rank) per passage."""
    merged: dict[uuid.UUID, Candidate] = {}
    scores: dict[uuid.UUID, float] = {}

    for label, hits in (("vector", vector_hits), ("keyword", keyword_hits)):
        for rank, hit in enumerate(hits, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            existing = merged.get(hit.chunk_id)
            if existing is None:
                merged[hit.chunk_id] = replace(hit, matched_by=(label,))
            else:
                merged[hit.chunk_id] = replace(
                    existing,
                    similarity=existing.similarity if existing.similarity is not None else hit.similarity,
                    keyword_score=(
                        existing.keyword_score
                        if existing.keyword_score is not None
                        else hit.keyword_score
                    ),
                    matched_by=existing.matched_by + (label,),
                )

    fused = [replace(item, score=scores[chunk_id]) for chunk_id, item in merged.items()]
    fused.sort(key=lambda item: (-item.score, str(item.chunk_id)))  # ties: stable order
    return fused


def build_tsquery(value: str, max_terms: int = 32) -> str:
    """Turn free text into 'a | b | c' for PostgreSQL's to_tsquery.

    Natural questions contain filler words, so requiring every word to match
    would find nothing; OR lets any word match and ranking sorts the rest.
    Only letters and digits are kept, so user input can never inject
    tsquery syntax (& | ! : ( ) ').
    """
    terms: list[str] = []
    for token in re.findall(r"[^\W_]+", value.lower()):
        if token not in terms:
            terms.append(token)
    return " | ".join(terms[:max_terms])


def vector_literal(vector: list[float]) -> str:
    """pgvector's text format: [0.1,0.2,...]"""
    return "[" + ",".join(f"{x:.8g}" for x in vector) + "]"


# The isolation rule: every search is restricted to the caller's own,
# fully processed documents.
_OWNER_FILTER = "c.owner_id = :owner_id AND d.owner_id = :owner_id AND d.status = 'ready'"


class HybridRetriever:
    def __init__(self, db: Session, embedder: Embedder):
        self._db = db
        self._embedder = embedder

    def retrieve(
        self,
        *,
        owner_id: uuid.UUID,
        query: str,
        collection_id: uuid.UUID | None = None,
        top_k: int = 6,
        mode: str = "hybrid",
    ) -> list[Candidate]:
        if mode not in ("hybrid", "vector", "keyword"):
            raise ValueError(f"Unknown retrieval mode '{mode}'")
        limit = max(settings.retrieval_candidates, top_k * 3)

        vector_hits: list[Candidate] = []
        keyword_hits: list[Candidate] = []
        if mode in ("hybrid", "vector"):
            query_vector = vector_literal(self._embedder.embed_query(query))
            vector_hits = self._vector_hits(owner_id, query_vector, collection_id, limit)
        if mode in ("hybrid", "keyword"):
            tsquery = build_tsquery(query)
            if tsquery:
                keyword_hits = self._keyword_hits(owner_id, tsquery, collection_id, limit)

        if mode == "vector":
            return vector_hits[:top_k]
        if mode == "keyword":
            return keyword_hits[:top_k]
        return rrf_fuse(vector_hits, keyword_hits, settings.rrf_k)[:top_k]

    def _vector_hits(self, owner_id, query_vector, collection_id, limit) -> list[Candidate]:
        collection_clause = "AND d.collection_id = :collection_id" if collection_id else ""
        sql = f"""
            SELECT c.id AS chunk_id, c.document_id, d.filename, c.page_number,
                   c.chunk_index, c.content,
                   1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {_OWNER_FILTER}
              AND c.embedding IS NOT NULL
              AND d.embedding_model = :model
              {collection_clause}
            ORDER BY c.embedding <=> CAST(:qvec AS vector), c.id
            LIMIT :limit
        """
        params = {
            "owner_id": owner_id,
            "qvec": query_vector,
            "model": self._embedder.model_name,
            "limit": limit,
        }
        if collection_id:
            params["collection_id"] = collection_id
        rows = self._db.execute(text(sql), params).mappings().all()
        return [
            Candidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                filename=row["filename"],
                page_number=row["page_number"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    def _keyword_hits(self, owner_id, tsquery, collection_id, limit) -> list[Candidate]:
        collection_clause = "AND d.collection_id = :collection_id" if collection_id else ""
        sql = f"""
            SELECT c.id AS chunk_id, c.document_id, d.filename, c.page_number,
                   c.chunk_index, c.content,
                   ts_rank_cd(c.search_vector, q.query) AS keyword_score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            CROSS JOIN (SELECT to_tsquery('english', :tsq) AS query) q
            WHERE {_OWNER_FILTER}
              AND c.search_vector @@ q.query
              {collection_clause}
            ORDER BY keyword_score DESC, c.id
            LIMIT :limit
        """
        params = {"owner_id": owner_id, "tsq": tsquery, "limit": limit}
        if collection_id:
            params["collection_id"] = collection_id
        rows = self._db.execute(text(sql), params).mappings().all()
        return [
            Candidate(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                filename=row["filename"],
                page_number=row["page_number"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                keyword_score=float(row["keyword_score"]),
            )
            for row in rows
        ]
