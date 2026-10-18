import logging
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _resolve(relative_path: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    full = (root / relative_path).resolve()
    # Defence in depth: refuse anything that resolves outside the upload folder.
    if root != full and root not in full.parents:
        raise ValueError("Path escapes the upload directory")
    return full


def save_file(owner_id: uuid.UUID, document_id: uuid.UUID, extension: str, data: bytes) -> str:
    """Save under <owner>/<document-id><ext>. Returns the path relative to UPLOAD_DIR."""
    relative = Path(str(owner_id)) / f"{document_id}{extension}"
    full = _resolve(relative.as_posix())
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return relative.as_posix()


def read_file(relative_path: str) -> bytes:
    return _resolve(relative_path).read_bytes()


def delete_file(relative_path: str) -> None:
    """Best effort: a leftover file is harmless, a crash while cleaning up is not."""
    try:
        _resolve(relative_path).unlink(missing_ok=True)
    except (OSError, ValueError):
        logger.warning("Could not delete stored file %s", relative_path, exc_info=True)
