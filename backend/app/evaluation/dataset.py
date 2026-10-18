import json
from dataclasses import dataclass
from pathlib import Path

# backend/eval, found relative to this file so it works locally and in Docker.
EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"


@dataclass(frozen=True)
class EvalDocument:
    name: str
    text: str


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    evidence: list[str]
    answerable: bool


def load_corpus(directory: Path = EVAL_DIR / "corpus") -> list[EvalDocument]:
    return [
        EvalDocument(name=path.stem, text=path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.txt"))
    ]


def load_questions(path: Path = EVAL_DIR / "questions.json") -> list[EvalQuestion]:
    raw = json.loads(path.read_text(encoding="utf-8"))["questions"]
    return [
        EvalQuestion(
            id=item["id"],
            question=item["question"],
            evidence=list(item.get("evidence", [])),
            answerable=bool(item["answerable"]),
        )
        for item in raw
    ]


def load_thresholds(path: Path = EVAL_DIR / "thresholds.json") -> dict[str, float]:
    return {name: float(value) for name, value in json.loads(path.read_text(encoding="utf-8")).items()}
