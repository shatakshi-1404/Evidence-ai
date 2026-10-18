import re
from pathlib import PurePosixPath

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


class UploadValidationError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def clean_filename(filename: str | None) -> str:
    """A safe display name: no directories, no control characters.

    This is only for showing to users. Files are stored under a generated ID,
    so a name like '../../etc/passwd' can never influence where a file lands.
    """
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if name in {"", ".", ".."}:
        return "document"
    if len(name) > 255:
        # Cut the name, not the extension: the extension decides the file type.
        suffix = PurePosixPath(name).suffix[:20]
        name = name[: 255 - len(suffix)] + suffix
    return name


def get_extension(filename: str | None) -> str:
    return PurePosixPath(clean_filename(filename)).suffix.lower()


def validate_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    """Return (extension, content_type) or raise UploadValidationError."""
    extension = get_extension(filename)
    if extension not in ALLOWED_TYPES:
        raise UploadValidationError(
            f"Unsupported file type '{extension or 'none'}'. Allowed: .pdf, .txt, .md",
            status_code=415,
        )
    if not data:
        raise UploadValidationError("The file is empty")

    if extension == ".pdf":
        # Every real PDF starts with this marker. Deeper problems are caught
        # by the worker, which marks the document failed with a clear reason.
        if not data.startswith(b"%PDF-"):
            raise UploadValidationError("This file is not a valid PDF")
    else:
        if b"\x00" in data:
            raise UploadValidationError("This does not look like a text file")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UploadValidationError("Text files must be UTF-8 encoded")

    return extension, ALLOWED_TYPES[extension]
