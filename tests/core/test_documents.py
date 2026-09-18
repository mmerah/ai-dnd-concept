import re
from pathlib import Path

import pytest

from aidm.core.entities import Refusal
from aidm.core.source import SOURCE_MAX_BYTES, whole_text

FIXTURES = Path(__file__).parent / "fixtures" / "source"


def test_a_markdown_document_reads_to_text_without_its_furniture() -> None:
    text = whole_text(FIXTURES / "drowned-road.md")

    assert "p. 3" not in text
    assert ">" not in text
    assert "chapel lamp is still a mile off" in text


def test_a_caps_heading_paragraph_is_dropped_but_prose_ending_in_a_colon_survives(
    tmp_path: Path,
) -> None:
    document = tmp_path / "heading.md"
    document.write_text(
        "WHAT THE PLAYER HAS READ:\n\n"
        "The chapel lamp is still a mile off, and the road runs low and wet before it:\n\n"
        "The bell house stands at the bend, its door hanging loose on one hinge.",
        encoding="utf-8",
    )

    text = whole_text(document)

    assert "WHAT THE PLAYER HAS READ" not in text
    assert "road runs low and wet before it:" in text


def test_a_pdf_reads_to_text() -> None:
    text = whole_text(FIXTURES / "drowned-road.pdf")

    assert "chapel" in text.lower()
    assert "Bell House" in text


def test_whole_text_refuses_a_document_too_large_to_hand_to_a_model_whole(tmp_path: Path) -> None:
    text = "a short adventure about a bell and a tide"
    small = tmp_path / "small.md"
    small.write_text(text, encoding="utf-8")
    assert whole_text(small) == text

    big = tmp_path / "big.md"
    big.write_text("a" * (SOURCE_MAX_BYTES + 1), encoding="utf-8")
    with pytest.raises(Refusal, match="too large"):
        _ = whole_text(big)


def test_whole_text_refuses_a_markdown_document_that_is_not_utf8(tmp_path: Path) -> None:
    broken = tmp_path / "broken.md"
    broken.write_bytes(b"caf\xe9")
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken)


def test_whole_text_refuses_a_pdf_that_is_not_readable(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 broken")
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken)


def test_whole_text_refuses_a_pdf_whose_catalog_has_no_pages(tmp_path: Path) -> None:
    """A trailer whose catalog has no /Pages makes pypdf raise a bare AttributeError."""
    broken = tmp_path / "no_pages.pdf"
    broken.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n45\n%%EOF\n"
    )
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken)


def test_whole_text_refuses_a_pdf_whose_font_has_no_descendant_fonts(tmp_path: Path) -> None:
    """A composite font with no /DescendantFonts makes pypdf raise a bare KeyError."""
    broken = tmp_path / "no_descendants.pdf"
    broken.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /Subtype /Type0 /BaseFont /Identity-H >>\nendobj\n"
        b"5 0 obj\n<< /Length 34 >>\nstream\nBT /F1 11 Tf 72 720 Td (Hi) Tj ET\nendstream\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n45\n%%EOF\n"
    )
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken)


def test_whole_text_refuses_a_document_it_cannot_open_naming_it(tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable.md"
    unreadable.mkdir()
    with pytest.raises(Refusal, match=re.escape("unreadable.md cannot be read")):
        _ = whole_text(unreadable)
