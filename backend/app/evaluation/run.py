"""Run the evaluation benchmark.

    python -m app.evaluation.run                 # run, save report, print summary
    python -m app.evaluation.run --check         # also fail (exit 1) if below eval/thresholds.json
    python -m app.evaluation.run --output x.json # save the report somewhere else
"""
import argparse
import os
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.evaluation.dataset import load_thresholds
from app.evaluation.runner import check_thresholds, run_evaluation
from app.schemas.evaluation import EvalReport


def print_summary(report: EvalReport) -> None:
    d = report.dataset
    print(f"\nEvaluation: {d.questions} questions ({d.answerable} answerable, {d.unanswerable} not) "
          f"over {d.documents} documents / {d.chunks} passages")
    print(f"Embedding model: {report.embedding_model}    LLM provider: {report.llm_provider}\n")
    print(f"{'Method':<10}{'Hit@1':>8}{'Hit@3':>8}{'Hit@5':>8}{'MRR':>8}{'p50 ms':>10}{'p95 ms':>10}")
    for mode, r in report.retrieval.items():
        print(f"{mode:<10}{r.hit_at_1:>8.2f}{r.hit_at_3:>8.2f}{r.hit_at_5:>8.2f}"
              f"{r.mrr:>8.2f}{r.latency_p50_ms:>10.1f}{r.latency_p95_ms:>10.1f}")
    p = report.pipeline
    print(f"\nAnswered (answerable):      {p.answered_rate:.0%}")
    print(f"Refused (unanswerable):     {p.refusal_rate:.0%}")
    print(f"Cited the right passage:    {p.cited_evidence_rate:.0%}")
    print(f"Invented citations:         {p.invented_citation_rate:.0%} of answers (all stripped before display)")
    print(f"Answer support (heuristic): {p.avg_support:.2f}")
    print(f"Ask latency p50 / p95:      {p.latency_p50_ms:.0f} / {p.latency_p95_ms:.0f} ms")
    t = report.threshold
    print(f"\nRecommended MIN_SIMILARITY: {t.recommended:.2f}  (currently {t.current:.2f})\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if below the minimum quality bar")
    parser.add_argument("--output", default=settings.eval_report_path, help="where to save the JSON report")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        report = run_evaluation(db)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, output)  # the API never sees a half-written file
    print_summary(report)
    print(f"Report saved to {output}")

    if args.check:
        failures = check_thresholds(report, load_thresholds())
        if failures:
            print("\nQuality check FAILED:")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print("Quality check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
