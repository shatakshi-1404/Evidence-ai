from dataclasses import dataclass

from app.services.extraction import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    page_number: int | None


def _best_break(window: str, min_pos: int) -> int | None:
    """Pick the most natural place to cut, but not before min_pos."""
    i = window.rfind("\n\n")
    if i >= min_pos:
        return i
    sentence_end = max(window.rfind(marker) for marker in (". ", "? ", "! ", ".\n"))
    if sentence_end >= min_pos:
        return sentence_end + 1  # keep the punctuation with the sentence
    for marker in ("\n", " "):
        i = window.rfind(marker)
        if i >= min_pos:
            return i
    return None


def split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            cut = _best_break(text[start:end], min_pos=chunk_size // 2)
            if cut is not None:
                end = start + cut

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break

        next_start = end - overlap
        if next_start <= start:
            next_start = end  # no room for overlap; always move forward
        else:
            # Begin the next chunk at a word start, not mid-word.
            while next_start < end and not text[next_start - 1].isspace():
                next_start += 1
        start = next_start
    return chunks


def chunk_pages(
    pages: list[ExtractedPage], chunk_size: int = 1000, overlap: int = 200
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        for piece in split_text(page.text, chunk_size, overlap):
            chunks.append(TextChunk(index=len(chunks), text=piece, page_number=page.page_number))
    return chunks
