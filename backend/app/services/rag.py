import re
import time
import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.services.llm import LLMProvider
from app.services.retrieval import Candidate, Retriever

INSUFFICIENT_TOKEN = "INSUFFICIENT_EVIDENCE"
INSUFFICIENT_MESSAGE = "The documents don't contain enough evidence to answer this question."

# [1] or [1, 2]. One to three digits, so a year like [2024] is left alone.
_MARKER = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")


@dataclass(frozen=True)
class ValidatedAnswer:
    text: str
    cited: list[int]      # valid markers actually used, in order of first use
    removed: list[int]    # markers that pointed at no retrieved passage
    insufficient: bool
    reason: str | None


def validate_citations(text: str, source_count: int) -> ValidatedAnswer:
    """The model may only cite passages we retrieved. Everything else is removed.

    - The model declining => insufficient evidence.
    - Markers outside 1..source_count are invented: stripped and reported.
    - After stripping, an answer with no citation at all can't be verified,
      so it is rejected rather than shown as if it were grounded.
    """
    if INSUFFICIENT_TOKEN in text:
        return ValidatedAnswer("", [], [], True, "model_declined")

    cited: list[int] = []
    removed: list[int] = []

    def _replace(match: re.Match) -> str:
        numbers = [int(part) for part in match.group(1).split(",")]
        valid = [n for n in numbers if 1 <= n <= source_count]
        removed.extend(n for n in numbers if not 1 <= n <= source_count)
        for n in valid:
            if n not in cited:
                cited.append(n)
        return f"[{', '.join(str(n) for n in valid)}]" if valid else ""

    cleaned = _MARKER.sub(_replace, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,;:!?])", r"\1", cleaned).strip()

    if not cited:
        return ValidatedAnswer("", [], removed, True, "uncited_answer")
    return ValidatedAnswer(cleaned, cited, removed, False, None)


@dataclass(frozen=True)
class AskResult:
    answer: str
    sufficient_evidence: bool
    reason: str | None
    sources: list[Candidate]     # everything retrieved; source N has marker N
    cited_markers: list[int]
    removed_markers: list[int]
    timings: dict[str, int]


def answer_question(
    *,
    question: str,
    owner_id: uuid.UUID,
    collection_id: uuid.UUID | None,
    retriever: Retriever,
    llm: LLMProvider,
    top_k: int | None = None,
    min_similarity: float | None = None,
) -> AskResult:
    started = time.perf_counter()
    threshold = settings.min_similarity if min_similarity is None else min_similarity

    sources = retriever.retrieve(
        owner_id=owner_id,
        query=question,
        collection_id=collection_id,
        top_k=top_k or settings.retrieval_top_k,
    )
    retrieved = time.perf_counter()

    def finish(
        answer: str, ok: bool, reason: str | None, cited: list[int], removed: list[int], generated: float
    ) -> AskResult:
        return AskResult(
            answer=answer,
            sufficient_evidence=ok,
            reason=reason,
            sources=sources,
            cited_markers=cited,
            removed_markers=removed,
            timings={
                "retrieval_ms": round((retrieved - started) * 1000),
                "generation_ms": round((generated - retrieved) * 1000),
                "total_ms": round((generated - started) * 1000),
            },
        )

    # Gate 1: don't even call the model if nothing retrieved looks relevant.
    # Only passages with a similarity score count; keyword-only matches don't.
    best = max((s.similarity for s in sources if s.similarity is not None), default=None)
    if not sources or best is None or best < threshold:
        return finish(INSUFFICIENT_MESSAGE, False, "no_relevant_passages", [], [], retrieved)

    # LLMError (if any) propagates; the API turns it into a clean 502.
    raw = llm.answer(question, sources)
    generated = time.perf_counter()

    # Gate 2: the model's answer must cite only passages we actually retrieved.
    validated = validate_citations(raw, len(sources))
    if validated.insufficient:
        return finish(
            INSUFFICIENT_MESSAGE, False, validated.reason, [], validated.removed, generated
        )
    return finish(validated.text, True, None, validated.cited, validated.removed, generated)
