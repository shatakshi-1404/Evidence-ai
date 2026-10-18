from datetime import datetime

from pydantic import BaseModel


class RetrievalMetrics(BaseModel):
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    latency_p50_ms: float
    latency_p95_ms: float


class ThresholdPointRead(BaseModel):
    threshold: float
    answerable_pass_rate: float
    unanswerable_refusal_rate: float
    balanced_accuracy: float


class ThresholdAnalysis(BaseModel):
    points: list[ThresholdPointRead]
    recommended: float
    current: float


class PipelineMetrics(BaseModel):
    ask_count: int
    answered_rate: float          # answerable questions that got an answer
    refusal_rate: float           # unanswerable questions correctly refused
    cited_evidence_rate: float    # answerable questions where a cited passage holds the evidence
    invented_citation_rate: float # answers where the model cited a source that didn't exist
    avg_support: float            # lexical overlap of answers with their cited passages (heuristic)
    latency_p50_ms: float
    latency_p95_ms: float
    llm_errors: int


class QuestionResult(BaseModel):
    id: str
    question: str
    answerable: bool
    vector_rank: int | None
    keyword_rank: int | None
    hybrid_rank: int | None
    best_similarity: float | None
    answered: bool
    cited_evidence: bool | None


class DatasetInfo(BaseModel):
    documents: int
    chunks: int
    questions: int
    answerable: int
    unanswerable: int


class EvalReport(BaseModel):
    generated_at: datetime
    embedding_model: str
    llm_provider: str
    k: int
    dataset: DatasetInfo
    retrieval: dict[str, RetrievalMetrics]
    threshold: ThresholdAnalysis
    pipeline: PipelineMetrics
    questions: list[QuestionResult]
