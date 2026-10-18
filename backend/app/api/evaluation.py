from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.schemas.evaluation import EvalReport

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/latest", response_model=EvalReport)
def latest_report(user: CurrentUser) -> EvalReport:
    """The most recent benchmark report. It describes the synthetic corpus, not anyone's documents."""
    path = Path(settings.eval_report_path)
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No evaluation report yet. Run: python -m app.evaluation.run",
        )
    try:
        return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "The evaluation report is unreadable")
