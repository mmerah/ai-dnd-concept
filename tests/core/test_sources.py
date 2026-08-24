from pathlib import Path

import pytest

from aidm.content.io import whole_text

FIXTURES = Path(__file__).parent / "fixtures" / "source"
MAX_CHARS = 120_000


def test_a_markdown_document_reads_to_text_without_its_furniture() -> None:
    text = whole_text(FIXTURES / "drowned-road.md", MAX_CHARS)

    assert "p. 3" not in text
    assert ">" not in text
    assert "chapel lamp is still a mile off" in text


def test_a_pdf_reads_to_text() -> None:
    text = whole_text(FIXTURES / "drowned-road.pdf", MAX_CHARS)

    assert "chapel" in text.lower()
    assert "Bell House" in text


def test_whole_text_refuses_a_document_too_large_to_hand_to_a_model_whole(tmp_path: Path) -> None:
    text = "a short adventure about a bell and a tide"
    small = tmp_path / "small.md"
    small.write_text(text, encoding="utf-8")
    assert whole_text(small, MAX_CHARS) == text

    big = tmp_path / "big.md"
    big.write_text("a" * (MAX_CHARS + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="too large"):
        _ = whole_text(big, MAX_CHARS)
