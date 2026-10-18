import pytest

from app.services.extraction import ExtractionError, extract_pages, normalize_text
from tests.utils import make_pdf


def test_normalize_text():
    assert normalize_text("a   b\t\tc") == "a b c"
    assert normalize_text("a  \n  b") == "a\nb"
    assert normalize_text("x\n\n\n\n\ny") == "x\n\ny"


def test_text_file_is_one_unnumbered_page():
    result = extract_pages(b"Hello\r\n\r\n\r\n\r\nWorld", ".txt")
    assert result.page_count == 1
    assert result.pages[0].page_number is None
    assert result.pages[0].text == "Hello\n\nWorld"


def test_utf8_bom_is_stripped():
    assert extract_pages(b"\xef\xbb\xbfTitle", ".md").pages[0].text == "Title"


def test_whitespace_only_text_is_rejected():
    with pytest.raises(ExtractionError):
        extract_pages(b"  \n\n  ", ".txt")


def test_pdf_pages_are_extracted_with_numbers():
    result = extract_pages(make_pdf(["Apples are red", "Oranges are orange"]), ".pdf")
    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Apples" in result.pages[0].text
    assert "Oranges" in result.pages[1].text


def test_unreadable_pdf_raises_extraction_error():
    with pytest.raises(ExtractionError):
        extract_pages(b"%PDF-1.4\nthis is not really a pdf", ".pdf")


def test_pdf_without_text_raises_extraction_error():
    with pytest.raises(ExtractionError, match="extractable text"):
        extract_pages(make_pdf([""]), ".pdf")
