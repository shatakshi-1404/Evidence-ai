# EvidenceAI: Search less. Know more.

A document-intelligence workspace. Upload PDFs and text, ask questions, and get
answers grounded in cited passages, or an honest "not enough evidence". The
retrieval quality is **measured**, not assumed.

![Ask page with the evidence panel](docs/screenshot-ask.png)
![Evaluation page](docs/screenshot-evaluation.png)

## What makes it different

- **Citations can't be invented.** The model cites passages by number; the server
  checks every number against the passages it actually retrieved, strips any that
  don't match, and rejects answers with no valid citation.
- **It refuses instead of guessing.** A similarity gate skips the model entirely
  when nothing relevant was found, and the model is told to decline when sources
  are insufficient.
- **Hybrid retrieval, with evidence.** PostgreSQL full-text search and pgvector
  similarity are fused with Reciprocal Rank Fusion. The benchmark compares all three
  approaches.
- **Per-user isolation, tested.** Every query filters by owner. A test matrix
  probes every endpoint as a second user.

## Measured quality

Benchmark: 27 questions (22 answerable, 5 not) over 5 documents, run with
`BAAI/bge-small-en-v1.5`. Reproduce with `python -m app.evaluation.run`.

| Method | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---|---|---|---|
| Meaning only (vectors) | _fill in_ | _fill in_ | _fill in_ | _fill in_ |
| Keywords only (full-text) | _fill in_ | _fill in_ | _fill in_ | _fill in_ |
| **Hybrid (RRF)** | _fill in_ | _fill in_ | _fill in_ | _fill in_ |

Correct refusals on unanswerable questions: _fill in_ %. Ask latency p50 / p95: _fill in_ ms.
`MIN_SIMILARITY` was chosen from the benchmark's threshold sweep, not guessed.

## Architecture

