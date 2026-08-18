import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pypdf import PdfReader

type ExpansionPolicy = Literal["closed", "grounded", "generative"]

CONTEXT_BUDGET = 2000
RECORD_CHARS = 600
MIN_RECORD = 24
SEARCH_RESULTS = 6
_BLANK_LINE = re.compile(r"\n\s*\n")
_WORD = re.compile(r"[a-z0-9']{3,}")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


@dataclass(frozen=True, slots=True)
class SourceRecord:
    id: str
    text: str


class CanonSource(Protocol):
    """What may exist beyond the state already materialized."""

    def context(self) -> str: ...

    def search(self, query: str) -> tuple[SourceRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class PremiseSource:
    """A scenario's own words: its `source.md` when it ships one, else the premise it was authored
    from."""

    text: str

    def context(self) -> str:
        return self.text

    def search(self, query: str) -> tuple[SourceRecord, ...]:
        """A premise is already whole in the prompt, so there is nothing left to look up."""
        del query
        return ()


@dataclass(frozen=True, slots=True)
class RecordSource:
    records: tuple[SourceRecord, ...]

    def context(self) -> str:
        """The document's opening, bounded: the rest is reached with `search`."""
        shown: list[SourceRecord] = []
        spent = 0
        for record in self.records:
            if spent + len(record.text) > CONTEXT_BUDGET:
                break
            shown.append(record)
            spent += len(record.text)
        return render(shown)

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


def render(records: Sequence[SourceRecord]) -> str:
    return "\n\n".join(f"[{record.id}] {record.text}" for record in records)


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
