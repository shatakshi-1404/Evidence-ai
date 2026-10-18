import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.collections import get_owned_collection
from app.api.deps import CurrentUser, DbSession
from app.api.limits import user_rate_limit
from app.models.ask_history import AskHistory
from app.schemas.search import (
    AskRequest,
    AskResponse,
    CitationRead,
    PassageRead,
    SearchRequest,
    SearchResponse,
)
from app.services.embeddings import get_embedder
from app.services.llm import LLMError, LLMProvider, get_llm_provider
from app.services.rag import answer_question
from app.services.retrieval import Candidate, HybridRetriever, Retriever

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


# Dependencies, so tests can swap in fakes without touching PostgreSQL or a model.
def get_retriever(db: DbSession) -> Retriever:
    return HybridRetriever(db, get_embedder())


def get_llm() -> LLMProvider:
    return get_llm_provider()


def _passage(candidate: Candidate, marker: int | None = None) -> PassageRead:
    return PassageRead(
        marker=marker,
        chunk_id=candidate.chunk_id,
        document_id=candidate.document_id,
        filename=candidate.filename,
        page_number=candidate.page_number,
        chunk_index=candidate.chunk_index,
        content=candidate.content,
        score=round(candidate.score, 6),
        similarity=None if candidate.similarity is None else round(candidate.similarity, 4),
        keyword_score=None if candidate.keyword_score is None else round(candidate.keyword_score, 4),
        matched_by=list(candidate.matched_by),
    )


def _snippet(content: str, limit: int = 300) -> str:
    content = " ".join(content.split())
    return content if len(content) <= limit else content[:limit].rsplit(" ", 1)[0] + "…"


@router.post(
    "/search",
    response_model=SearchResponse,
    dependencies=[Depends(user_rate_limit("search", "rate_limit_search_per_minute"))],
)
def search(
    payload: SearchRequest,
    db: DbSession,
    user: CurrentUser,
    retriever: Annotated[Retriever, Depends(get_retriever)],
) -> SearchResponse:
    # Ownership check first: someone else's collection is simply a 404.
    if payload.collection_id is not None:
        get_owned_collection(db, payload.collection_id, user)

    started = time.perf_counter()
    candidates = retriever.retrieve(
        owner_id=user.id,
        query=payload.query,
        collection_id=payload.collection_id,
        top_k=payload.limit,
    )
    elapsed = round((time.perf_counter() - started) * 1000)
    return SearchResponse(
        query=payload.query,
        results=[_passage(c) for c in candidates],
        timings={"retrieval_ms": elapsed},
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[Depends(user_rate_limit("ask", "rate_limit_ask_per_minute"))],
)
def ask(
    payload: AskRequest,
    db: DbSession,
    user: CurrentUser,
    retriever: Annotated[Retriever, Depends(get_retriever)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
) -> AskResponse:
    if payload.collection_id is not None:
        get_owned_collection(db, payload.collection_id, user)

    try:
        result = answer_question(
            question=payload.question,
            owner_id=user.id,
            collection_id=payload.collection_id,
            retriever=retriever,
            llm=llm,
        )
    except LLMError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The language model is unavailable. Passage search still works at /api/search.",
        )

    # Citations are built from the retrieved passages themselves, never from model text.
    citations = [
        CitationRead(
            marker=marker,
            chunk_id=result.sources[marker - 1].chunk_id,
            document_id=result.sources[marker - 1].document_id,
            filename=result.sources[marker - 1].filename,
            page_number=result.sources[marker - 1].page_number,
            snippet=_snippet(result.sources[marker - 1].content),
        )
        for marker in result.cited_markers
    ]
    history_id = uuid.uuid4()
    response = AskResponse(
        question=payload.question,
        answer=result.answer,
        sufficient_evidence=result.sufficient_evidence,
        reason=result.reason,
        citations=citations,
        sources=[_passage(c, marker=i) for i, c in enumerate(result.sources, start=1)],
        removed_markers=result.removed_markers,
        timings=result.timings,
        history_id=history_id,
    )

    # Saving history must never break an answer the user is waiting for.
    try:
        db.add(
            AskHistory(
                id=history_id,
                owner_id=user.id,
                collection_id=payload.collection_id,
                question=payload.question,
                sufficient_evidence=response.sufficient_evidence,
                response=response.model_dump(mode="json"),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not save ask history", exc_info=True)
        response.history_id = None
    return response


def ask(
    payload: AskRequest,
    db: DbSession,
    user: CurrentUser,
    retriever: Annotated[Retriever, Depends(get_retriever)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
) -> AskResponse:
    if payload.collection_id is not None:
        get_owned_collection(db, payload.collection_id, user)

    try:
        result = answer_question(
            question=payload.question,
            owner_id=user.id,
            collection_id=payload.collection_id,
            retriever=retriever,
            llm=llm,
        )
    except LLMError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The language model is unavailable. Passage search still works at /api/search.",
        )

    # Citations are built from the retrieved passages themselves, never from model text.
    citations = [
        CitationRead(
            marker=marker,
            chunk_id=result.sources[marker - 1].chunk_id,
            document_id=result.sources[marker - 1].document_id,
            filename=result.sources[marker - 1].filename,
            page_number=result.sources[marker - 1].page_number,
            snippet=_snippet(result.sources[marker - 1].content),
        )
        for marker in result.cited_markers
    ]
    return AskResponse(
        question=payload.question,
        answer=result.answer,
        sufficient_evidence=result.sufficient_evidence,
        reason=result.reason,
        citations=citations,
        sources=[_passage(c, marker=i) for i, c in enumerate(result.sources, start=1)],
        removed_markers=result.removed_markers,
        timings=result.timings,
    )
