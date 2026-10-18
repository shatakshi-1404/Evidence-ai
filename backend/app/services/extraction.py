import io
import re
from dataclasses import dataclass

from pypdf import PdfReader


class ExtractionError(Exception):
    """The file itself can't be processed. Retrying will not help."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int | None  # None for plain-text files
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    pages: list[ExtractedPage]
    page_count: int


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t\f\v]+", " ", text)   # collapse runs of spaces/tabs
    text = re.sub(r" ?\n ?", "\n", text)       # trim spaces around line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)     # at most one blank line
    return text.strip()


def _extract_pdf(data: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("This PDF is password-protected")
        total = len(reader.pages)
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                pages.append(ExtractedPage(number, text))
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("Could not read this PDF; it may be corrupted") from exc

    if not pages:
        raise ExtractionError(
            "No extractable text found (scanned PDFs need OCR, which isn't supported yet)"
        )
    return ExtractionResult(pages=pages, page_count=total)


def _extract_text(data: bytes) -> ExtractionResult:
    text = normalize_text(data.decode("utf-8-sig", errors="replace"))
    if not text:
        raise ExtractionError("The file contains no text")
    return ExtractionResult(pages=[ExtractedPage(None, text)], page_count=1)


def extract_pages(data: bytes, extension: str) -> ExtractionResult:
    if extension == ".pdf":
        return _extract_pdf(data)
    return _extract_text(data)
