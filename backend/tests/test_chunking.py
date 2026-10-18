import pytest

from app.services.chunking import chunk_pages, split_text
from app.services.extraction import ExtractedPage


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i:04d}" for i in range(n))


def test_empty_text_gives_no_chunks():
    assert split_text("   \n  ", 100, 20) == []


def test_short_text_is_a_single_chunk():
    assert split_text("hello world", 100, 20) == ["hello world"]


def test_chunks_respect_size_limit_and_cover_every_word():
    text = words(300)
    chunks = split_text(text, 100, 20)
    assert len(chunks) > 3
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert {w for chunk in chunks for w in chunk.split()} == set(text.split())


def test_consecutive_chunks_overlap():
    chunks = split_text(words(300), 100, 30)
    for previous, following in zip(chunks, chunks[1:]):
        assert following.split()[0] in previous.split()


def test_prefers_paragraph_boundary():
    text = "a" * 60 + "\n\n" + "b" * 80
    chunks = split_text(text, 100, 20)
    assert chunks[0] == "a" * 60
    assert chunks[1] == "b" * 80


def test_text_without_any_break_points_is_hard_cut_and_terminates():
    text = "a" * 5000
    chunks = split_text(text, 1000, 200)
    assert len(chunks) == 5
    assert "".join(chunks) == text


def test_chunk_pages_keeps_page_numbers_and_never_mixes_pages():
    pages = [
        ExtractedPage(1, words(80, "p1w")),
        ExtractedPage(2, words(80, "p2w")),
    ]
    chunks = chunk_pages(pages, 100, 20)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    for chunk in chunks:
        expected_prefix = f"p{chunk.page_number}w"
        assert all(word.startswith(expected_prefix) for word in chunk.text.split())


@pytest.mark.parametrize("size, overlap", [(0, 0), (100, 100), (100, -1), (100, 150)])
def test_invalid_settings_raise(size, overlap):
    with pytest.raises(ValueError):
        split_text("some text", size, overlap)
