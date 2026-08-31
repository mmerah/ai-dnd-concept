import re
from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader

MIN_PASSAGE = 24
_BLANK_LINE = re.compile(r"\n\s*\n")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


def given_text(premise: str, document: Path | None, max_chars: int) -> str:
    """Both, when the player gave both: a premise beside a document says what to take from it."""
    if document is None:
        return f"PREMISE:\n{premise}"
    whole = f"SOURCE DOCUMENT:\n{whole_text(document, max_chars)}"
    return f"PREMISE:\n{premise}\n\n{whole}" if premise else whole


def whole_text(path: Path, max_chars: int) -> str:
    pages = (
        _pdf_pages(path) if path.suffix.lower() == ".pdf" else (path.read_text(encoding="utf-8"),)
    )
    text = "\n\n".join(passage for page in pages for passage in _passages(page))
    if not text:
        raise ValueError(f"{path.name} holds no readable text")
    if len(text) > max_chars:
        raise ValueError(
            f"{path.name} is {len(text)} characters, too large to hand to a model whole"
        )
    return text


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Layout mode interleaves columns and mangles letter-spaced display text.
    return tuple(page.extract_text() for page in PdfReader(path).pages)


def _passages(body: str) -> Iterator[str]:
    for block in _BLANK_LINE.split(body.strip()):
        text = " ".join(_LINE_BREAK_HYPHEN.sub(r"\1-\2", _unquoted(block)).split())
        # A page number or a running header is not a passage.
        if len(text) >= MIN_PASSAGE:
            yield text


def _unquoted(block: str) -> str:
    """A Markdown quote marker is punctuation around a line, not part of its text."""
    return "\n".join(line.strip().removeprefix(">").strip() for line in block.splitlines())
