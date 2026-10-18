import hashlib
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation import metrics as m
from app.evaluation.dataset import EvalDocument, EvalQuestion, load_corpus, load_questions
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.schemas.evaluation import (
    DatasetInfo,
    EvalReport,
    PipelineMetrics,
    QuestionResult,
    RetrievalMetrics,
    ThresholdAnalysis,
    ThresholdPointRead,
)
from app.services import storage
from app.services.embeddings import Embedder, get_embedder
from app.services.ingestion import process_document
from app.services.llm import LLMError, LLMProvider, get_llm_provider
from app.services.rag import answer_question
from app.services.retrieval import HybridRetriever

K = 5
MODES = ("vector", "keyword", "hybrid")


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _ingest(
    db: Session,
    owner_id: uuid.UUID,
    collection_id: uuid.UUID,
    corpus: list[EvalDocument],
    stored_paths: list[str],
) -> int:
    """Run the real ingestion pipeline (extract, chunk, embed) on each corpus file."""
    total_chunks = 0
    for item in corpus:
        data = item.text.encode("utf-8")
        document_id = uuid.uuid4()
        path = storage.save_file(owner_id, document_id, ".txt", data)
        stored_paths.append(path)
        db.add(
            Document(
                id=document_id,
                owner_id=owner_id,
                collection_id=collection_id,
                filename=f"{item.name}.txt",
                content_type="text/plain",
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                storage_path=path,
                status=DocumentStatus.QUEUED,
            )
        )
        db.commit()
        result = process_document(db, document_id)
        if result.outcome != "ready":
            failed = db.get(Document, document_id, populate_existing=True)
            reason = failed.error_message if failed else result.outcome
            raise RuntimeError(f"Could not ingest {item.name}: {reason}")
        total_chunks += db.scalar(select(Document.chunk_count).where(Document.id == document_id)) or 0
    return total_chunks


def _evaluate(
    db: Session,
    owner_id: uuid.UUID,
    collection_id: uuid.UUID,
    questions: list[EvalQuestion],
    embedder: Embedder,
    llm: LLMProvider,
    document_count: int,
    chunk_count: int,
) -> EvalReport:
    retriever = HybridRetriever(db, embedder)
    ranks: dict[str, list[int | None]] = {mode: [] for mode in MODES}
    latencies: dict[str, list[float]] = {mode: [] for mode in MODES}
    answerable_best: list[float | None] = []
    unanswerable_best: list[float | None] = []
    results: list[QuestionResult] = []

    ask_latencies: list[float] = []
    supports: list[float] = []
    answerable_total = unanswerable_total = 0
    answered_ok = refused_ok = cited_hits = invented = llm_errors = 0

    for question in questions:
        mode_ranks: dict[str, int | None] = {}
        best: float | None = None

        for mode in MODES:
            started = time.perf_counter()
            top_k = max(K, settings.retrieval_top_k) if mode == "hybrid" else K
            candidates = retriever.retrieve(
                owner_id=owner_id,
                query=question.question,
                collection_id=collection_id,
                top_k=top_k,
                mode=mode,
            )
            latencies[mode].append((time.perf_counter() - started) * 1000)
            if mode == "hybrid":
                best = m.best_similarity(candidates)  # what the gate sees
            if question.answerable:
                rank = m.first_hit_rank([c.content for c in candidates[:K]], question.evidence)
                ranks[mode].append(rank)
                mode_ranks[mode] = rank

        (answerable_best if question.answerable else unanswerable_best).append(best)

        # Full question-answering path, exactly as the API runs it.
        answered = False
        cited_evidence: bool | None = None
        try:
            outcome = answer_question(
                question=question.question,
                owner_id=owner_id,
                collection_id=collection_id,
                retriever=retriever,
                llm=llm,
            )
            ask_latencies.append(float(outcome.timings["total_ms"]))
            answered = outcome.sufficient_evidence
            if outcome.removed_markers:
                invented += 1
            if question.answerable and answered:
                cited_texts = [outcome.sources[marker - 1].content for marker in outcome.cited_markers]
                cited_evidence = any(m.has_evidence(text, question.evidence) for text in cited_texts)
                supports.append(m.support_score(outcome.answer, cited_texts))
        except LLMError:
            llm_errors += 1

        if question.answerable:
            answerable_total += 1
            answered_ok += int(answered)
            cited_hits += int(cited_evidence is True)
        else:
            unanswerable_total += 1
            refused_ok += int(not answered)

        results.append(
            QuestionResult(
                id=question.id,
                question=question.question,
                answerable=question.answerable,
                vector_rank=mode_ranks.get("vector"),
                keyword_rank=mode_ranks.get("keyword"),
                hybrid_rank=mode_ranks.get("hybrid"),
                best_similarity=None if best is None else round(best, 4),
                answered=answered,
                cited_evidence=cited_evidence,
            )
        )

    retrieval = {
        mode: RetrievalMetrics(
            hit_at_1=m.hit_rate(ranks[mode], 1),
            hit_at_3=m.hit_rate(ranks[mode], 3),
            hit_at_5=m.hit_rate(ranks[mode], 5),
            mrr=m.mean_reciprocal_rank(ranks[mode]),
            latency_p50_ms=round(m.percentile(latencies[mode], 50), 1),
            latency_p95_ms=round(m.percentile(latencies[mode], 95), 1),
        )
        for mode in MODES
    }

    points = m.sweep_thresholds(answerable_best, unanswerable_best)
    threshold = ThresholdAnalysis(
        points=[
            ThresholdPointRead(
                threshold=p.threshold,
                answerable_pass_rate=p.answerable_pass_rate,
                unanswerable_refusal_rate=p.unanswerable_refusal_rate,
                balanced_accuracy=p.balanced_accuracy,
            )
            for p in points
        ],
        recommended=m.recommend_threshold(points),
        current=settings.min_similarity,
    )

    pipeline = PipelineMetrics(
        ask_count=len(questions),
        answered_rate=_rate(answered_ok, answerable_total),
        refusal_rate=_rate(refused_ok, unanswerable_total),
        cited_evidence_rate=_rate(cited_hits, answerable_total),
        invented_citation_rate=_rate(invented, len(questions)),
        avg_support=sum(supports) / len(supports) if supports else 0.0,
        latency_p50_ms=round(m.percentile(ask_latencies, 50), 1),
        latency_p95_ms=round(m.percentile(ask_latencies, 95), 1),
        llm_errors=llm_errors,
    )

    return EvalReport(
        generated_at=datetime.now(timezone.utc),
        embedding_model=embedder.model_name,
        llm_provider=llm.name,
        k=K,
        dataset=DatasetInfo(
            documents=document_count,
            chunks=chunk_count,
            questions=len(questions),
            answerable=answerable_total,
            unanswerable=unanswerable_total,
        ),
        retrieval=retrieval,
        threshold=threshold,
        pipeline=pipeline,
        questions=results,
    )


def run_evaluation(db: Session) -> EvalReport:
    corpus = load_corpus()
    questions = load_questions()
    embedder = get_embedder()
    llm = get_llm_provider()

    # A throwaway, deactivated user owns the corpus, so no real data is touched
    # and nobody can log in as it.
    user = User(
        email=f"eval-{uuid.uuid4().hex}@evidenceai.invalid",
        hashed_password="!",
        full_name="Evaluation run",
        is_active=False,
    )
    db.add(user)
    db.flush()
    user_id = user.id
    collection = Collection(owner_id=user_id, name="Evaluation corpus")
    db.add(collection)
    db.commit()
    collection_id = collection.id

    stored_paths: list[str] = []
    try:
        chunk_count = _ingest(db, user_id, collection_id, corpus, stored_paths)
        return _evaluate(
            db, user_id, collection_id, questions, embedder, llm, len(corpus), chunk_count
        )
    finally:
        db.rollback()
        db.execute(delete(User).where(User.id == user_id))  # the database cascades to everything else
        db.commit()
        for path in stored_paths:
            storage.delete_file(path)


def check_thresholds(report: EvalReport, thresholds: dict[str, float]) -> list[str]:
    """Compare a report to the minimum quality bar. Returns human-readable failures."""
    hybrid = report.retrieval["hybrid"]
    actual = {
        "hybrid_hit_at_5": hybrid.hit_at_5,
        "hybrid_mrr": hybrid.mrr,
        "answered_rate": report.pipeline.answered_rate,
        "refusal_rate": report.pipeline.refusal_rate,
        "cited_evidence_rate": report.pipeline.cited_evidence_rate,
    }
    failures = []
    for name, minimum in thresholds.items():
        if name not in actual:
            failures.append(f"Unknown threshold '{name}' in thresholds.json")
        elif actual[name] < minimum:
            failures.append(f"{name}: {actual[name]:.2f} is below the required {minimum:.2f}")
    return failures
