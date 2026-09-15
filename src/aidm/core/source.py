import re
from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader

from aidm.core.entities import Refusal

MIN_PASSAGE = 24
BLANK_LINE = re.compile(r"\n\s*\n")
LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")
CAPS_HEADING = re.compile(r"[A-Z][A-Z '-]+:")


def given_text(premise: str, document: Path | None, max_chars: int) -> str:
    """Both, when the player gave both: a premise beside a document says what to take from it."""
    if document is None:
        return f"PREMISE:\n{premise}"
    whole = f"SOURCE DOCUMENT:\n{whole_text(document, max_chars)}"
    return f"PREMISE:\n{premise}\n\n{whole}" if premise else whole


def whole_text(path: Path, max_chars: int) -> str:
    try:
        pages = (
            _pdf_pages(path)
            if path.suffix.lower() == ".pdf"
            else (path.read_text(encoding="utf-8"),)
        )
    # pypdf raises whatever it likes on hostile bytes; nothing of ours runs in this block.
    except Exception as broken:
        raise Refusal(f"{path.name} cannot be read: {broken}") from broken
    text = "\n\n".join(passage for page in pages for passage in _passages(page))
    if not text:
        raise Refusal(f"{path.name} holds no readable text")
    size = len(text.encode("utf-8"))
    if size > max_chars:
        raise Refusal(f"{path.name} is {size} bytes, too large to hand to a model whole")
    return text


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Layout mode interleaves columns and mangles letter-spaced display text.
    return tuple(page.extract_text() for page in PdfReader(path).pages)


def _passages(body: str) -> Iterator[str]:
    for block in BLANK_LINE.split(body.strip()):
        text = " ".join(LINE_BREAK_HYPHEN.sub(r"\1-\2", _unquoted(block)).split())
        # A page number or a running header is not a passage.
        if len(text) >= MIN_PASSAGE and not CAPS_HEADING.fullmatch(text):
            yield text


def _unquoted(block: str) -> str:
    return "\n".join(line.strip().removeprefix(">").strip() for line in block.splitlines())
