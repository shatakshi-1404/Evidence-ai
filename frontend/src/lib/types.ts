export type Health = {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
};

export type User = { id: string; email: string; full_name: string; created_at: string };

export type Collection = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export type DocumentItem = {
  id: string;
  collection_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  attempts: number;
  page_count: number | null;
  chunk_count: number;
  created_at: string;
  processed_at: string | null;
};

export type Chunk = {
  id: string;
  chunk_index: number;
  page_number: number | null;
  content: string;
  char_count: number;
};

export type Passage = {
  marker: number | null;
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  chunk_index: number;
  content: string;
  score: number;
  similarity: number | null;
  keyword_score: number | null;
  matched_by: string[];
};

export type SearchResponse = {
  query: string;
  results: Passage[];
  timings: Record<string, number>;
};

export type Citation = {
  marker: number;
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  snippet: string;
};

export type AskResponse = {
  question: string;
  answer: string;
  sufficient_evidence: boolean;
  reason: string | null;
  citations: Citation[];
  sources: Passage[];
  removed_markers: number[];
  timings: Record<string, number>;
  history_id: string | null;
};

export type HistoryItem = {
  id: string;
  question: string;
  collection_id: string | null;
  sufficient_evidence: boolean;
  created_at: string;
};

export type HistoryDetail = HistoryItem & { response: AskResponse };

export type RetrievalMetrics = {
  hit_at_1: number;
  hit_at_3: number;
  hit_at_5: number;
  mrr: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
};

export type ThresholdPoint = {
  threshold: number;
  answerable_pass_rate: number;
  unanswerable_refusal_rate: number;
  balanced_accuracy: number;
};

export type PipelineMetrics = {
  ask_count: number;
  answered_rate: number;
  refusal_rate: number;
  cited_evidence_rate: number;
  invented_citation_rate: number;
  avg_support: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  llm_errors: number;
};

export type QuestionResult = {
  id: string;
  question: string;
  answerable: boolean;
  vector_rank: number | null;
  keyword_rank: number | null;
  hybrid_rank: number | null;
  best_similarity: number | null;
  answered: boolean;
  cited_evidence: boolean | null;
};

export type EvalReport = {
  generated_at: string;
  embedding_model: string;
  llm_provider: string;
  k: number;
  dataset: { documents: number; chunks: number; questions: number; answerable: number; unanswerable: number };
  retrieval: Record<string, RetrievalMetrics>;
  threshold: { points: ThresholdPoint[]; recommended: number; current: number };
  pipeline: PipelineMetrics;
  questions: QuestionResult[];
};
