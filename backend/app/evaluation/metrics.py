import math
import re
from dataclasses import dataclass

from app.services.retrieval import Candidate

_CITATION = re.compile(r"\[\d{1,3}(?:\s*,\s*\d{1,3})*\]")
_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "this", "that", "with", "from", "you", "your",
    "can", "will", "not", "has", "have", "had", "its", "but", "any", "all", "our", "may",
}


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def has_evidence(content: str, evidence: list[str]) -> bool:
    """True if any evidence phrase appears in the passage (ignoring case and spacing)."""
    haystack = normalize(content)
    return any(normalize(phrase) in haystack for phrase in evidence if phrase.strip())


def first_hit_rank(contents: list[str], evidence: list[str]) -> int | None:
    """1-based position of the first passage containing the evidence, or None."""
    for rank, content in enumerate(contents, start=1):
        if has_evidence(content, evidence):
            return rank
    return None


def hit_rate(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    return sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks)


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    if not ranks:
        return 0.0
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value that at least pct% of values do not exceed."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[index]


def best_similarity(candidates: list[Candidate]) -> float | None:
    """What the answer gate looks at: the best cosine similarity among retrieved passages."""
    values = [c.similarity for c in candidates if c.similarity is not None]
    return max(values) if values else None


@dataclass(frozen=True)
class ThresholdPoint:
    threshold: float
    answerable_pass_rate: float
    unanswerable_refusal_rate: float
    balanced_accuracy: float


def sweep_thresholds(
    answerable_best: list[float | None], unanswerable_best: list[float | None]
) -> list[ThresholdPoint]:
    """For each candidate MIN_SIMILARITY, how often would the gate do the right thing?

    - An answerable question should PASS the gate (best similarity >= threshold).
    - An unanswerable question should be REFUSED (best similarity < threshold).
    """
    points = []
    for step in range(0, 96, 5):
        threshold = step / 100
        passed = sum(1 for best in answerable_best if best is not None and best >= threshold)
        refused = sum(1 for best in unanswerable_best if best is None or best < threshold)
        pass_rate = passed / len(answerable_best) if answerable_best else 0.0
        refusal_rate = refused / len(unanswerable_best) if unanswerable_best else 0.0
        points.append(
            ThresholdPoint(threshold, pass_rate, refusal_rate, (pass_rate + refusal_rate) / 2)
        )
    return points


def recommend_threshold(points: list[ThresholdPoint]) -> float:
    """Best balanced accuracy. Ties favor refusing wrong questions, then the lower threshold."""
    best = max(
        points,
        key=lambda p: (p.balanced_accuracy, p.unanswerable_refusal_rate, -p.threshold),
    )
    return best.threshold


def content_words(text: str) -> set[str]:
    tokens = re.findall(r"[^\W_]+", text.lower())
    return {token for token in tokens if len(token) > 2 and token not in _STOPWORDS}


def support_score(answer: str, passages: list[str]) -> float:
    """Share of the answer's content words that appear in its cited passages.

    A cheap heuristic for 'is this answer grounded in what it cites?'. It can
    flag an answer that says things its sources don't, but it is not proof of
    correctness; treat it as a smoke alarm, not a verdict.
    """
    words = content_words(_CITATION.sub(" ", answer))
    if not words or not passages:
        return 0.0
    source: set[str] = set()
    for passage in passages:
        source |= content_words(passage)
    return len(words & source) / len(words)
