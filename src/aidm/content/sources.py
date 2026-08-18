import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pypdf import PdfReader

type ExpansionPolicy = Literal["closed", "cited", "invented", "cited_or_invented"]

RECORD_CHARS = 600
MIN_RECORD = 24
SEARCH_RESULTS = 6
# A searched source answers in at most SEARCH_RESULTS records; a whole one answers with the book.
# ~30k tokens, which admits a 76-page adventure and refuses what would swallow the context.
WHOLE_CHARS = 120_000
_BLANK_LINE = re.compile(r"\n\s*\n")
_WORD = re.compile(r"[a-z0-9']{3,}")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


@dataclass(frozen=True, slots=True)
class SourceRecord:
    id: str
    text: str


class CanonSource(Protocol):
    """What may exist beyond the state already materialized."""

    def passages(self, query: str) -> str:
        """The text this source offers for those words, or `""` when it offers nothing."""
        ...


@dataclass(frozen=True, slots=True)
class WholeSource:
    text: str

    def passages(self, query: str) -> str:
        """Whole text, so every need is answered with all of it."""
        del query
        return self.text


@dataclass(frozen=True, slots=True)
class RecordSource:
    records: tuple[SourceRecord, ...]

    def passages(self, query: str) -> str:
        return render(self.search(query))

    def search(self, query: str) -> tuple[SourceRecord, ...]:
        """Every record holding a word of the query, the most of them first, ties in document
        order."""
        terms = set(_WORD.findall(query.lower()))
        # Distinct terms, not occurrences: counting occurrences lets one common word carried
        # thirteen times by a long passage outrank the record that answers the question.
        scored = [
            (sum(term in record.text.lower() for term in terms), order, record)
            for order, record in enumerate(self.records)
        ]
        found = sorted((row for row in scored if row[0]), key=lambda row: (-row[0], row[1]))
        return tuple(record for _, _, record in found[:SEARCH_RESULTS])


SILENT = (
    "The adventure's text holds no passage on this need. What follows is the adventure's premise: "
    "write canon of your own that is consistent with it."
)


@dataclass(frozen=True, slots=True)
class CitedOrInventedSource:
    """The document where it speaks, the premise where it is silent."""

    document: RecordSource
    premise: str

    def passages(self, query: str) -> str:
        return self.document.passages(query) or f"{SILENT}\n\n{self.premise}"


def render(records: Sequence[SourceRecord]) -> str:
    return "\n\n".join(f"[{record.id}] {record.text}" for record in records)


def whole_text(path: Path) -> str:
    """A document as one text. Ids belong to search results; a reader handed the whole document
    cites nothing, so they would be noise."""
    text = "\n\n".join(record.text for record in ingest(path).records)
    if len(text) > WHOLE_CHARS:
        raise ValueError(
            f"{path.name} is {len(text)} characters, too large to hand to a model whole: author "
            f"it `cited` or `cited_or_invented`, which search the document instead"
        )
    return text


def ingest(path: Path) -> RecordSource:
    """A document to the records it is searched by; extraction is deterministic."""
    pages = (
        _pdf_pages(path) if path.suffix.lower() == ".pdf" else (path.read_text(encoding="utf-8"),)
    )
    records = tuple(
        record for number, page in enumerate(pages, start=1) for record in _records(number, page)
    )
    if not records:
        raise ValueError(f"{path.name} holds no readable text")
    return RecordSource(records=records)


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Not layout mode: it reads a page as one grid, so it weaves side-by-side columns together
    # word by word and turns a letter-spaced display font into gibberish.
    return tuple(page.extract_text() for page in PdfReader(path).pages)


def _records(page: int, body: str) -> Iterator[SourceRecord]:
    index = 0
    for block in _BLANK_LINE.split(body.strip()):
        for text in _capped(_LINE_BREAK_HYPHEN.sub(r"\1-\2", _unquoted(block)).split()):
            index += 1
            # A page number or a running header is not a passage.
            if len(text) < MIN_RECORD:
                continue
            yield SourceRecord(id=f"p{page}-{index}", text=text)


def _capped(words: Sequence[str]) -> Iterator[str]:
    """No one passage swallows a page: a block nothing separates is cut on a word boundary."""
    held: list[str] = []
    spent = 0
    for word in words:
        if held and spent + len(word) > RECORD_CHARS:
            yield " ".join(held)
            held, spent = [], 0
        held.append(word)
        spent += len(word) + 1
    if held:
        yield " ".join(held)


def _unquoted(block: str) -> str:
    """A Markdown quote marker is punctuation around a line, not part of its text."""
    return "\n".join(line.strip().removeprefix(">").strip() for line in block.splitlines())
