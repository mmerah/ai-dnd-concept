import re
from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader

MIN_PASSAGE = 24
# The ceiling on a document handed to an author whole: ~30k tokens, which admits a 76-page
# adventure and refuses what would swallow the context.
WHOLE_CHARS = 120_000
_BLANK_LINE = re.compile(r"\n\s*\n")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


def whole_text(path: Path) -> str:
    pages = (
        _pdf_pages(path) if path.suffix.lower() == ".pdf" else (path.read_text(encoding="utf-8"),)
    )
    text = "\n\n".join(passage for page in pages for passage in _passages(page))
    if not text:
        raise ValueError(f"{path.name} holds no readable text")
    if len(text) > WHOLE_CHARS:
        raise ValueError(
            f"{path.name} is {len(text)} characters, too large to hand to a model whole"
        )
    return text


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Not layout mode: it reads a page as one grid, so it weaves side-by-side columns together
    # word by word and turns a letter-spaced display font into gibberish.
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
