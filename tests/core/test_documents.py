import re
from pathlib import Path

import pytest

from aidm.core.entities import Refusal
from aidm.core.source import whole_text

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
    with pytest.raises(Refusal, match="too large"):
        _ = whole_text(big, MAX_CHARS)


def test_whole_text_refuses_a_markdown_document_that_is_not_utf8(tmp_path: Path) -> None:
    broken = tmp_path / "broken.md"
    broken.write_bytes(b"caf\xe9")
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken, MAX_CHARS)


def test_whole_text_refuses_a_pdf_that_is_not_readable(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 broken")
    with pytest.raises(Refusal, match="cannot be read"):
        _ = whole_text(broken, MAX_CHARS)


def test_whole_text_refuses_a_document_it_cannot_open_naming_it(tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable.md"
    unreadable.mkdir()
    with pytest.raises(Refusal, match=re.escape("unreadable.md cannot be read")):
        _ = whole_text(unreadable, MAX_CHARS)
