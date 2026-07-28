"""JSON persistence: paths in, values out.

No configuration, no cache and no composition — every path is handed in, so nothing here decides
where a game lives or what a new one is made of. A save is exactly one `GameState`; the trace is
append-only JSONL; a scenario and a character sheet are read-only definitions.

The two adapters implement `application/ports.py`. They are the only classes in this build that
touch the filesystem."""

from dataclasses import dataclass
from pathlib import Path

from .domain.models import CharacterSheet, GameState, ScenarioDef, Turn

ENCODING = "utf-8"  # narration is full of curly quotes; the platform default is not enough


def read_scenario(path: Path) -> ScenarioDef:
    return ScenarioDef.model_validate_json(_text(path))


def read_sheet(path: Path) -> CharacterSheet:
    return CharacterSheet.model_validate_json(_text(path))


@dataclass(frozen=True, slots=True)
class FileSaves:
    """One JSON file per slug, under one directory."""

    directory: Path

    def load(self, slug: str) -> GameState | None:
        """`None` for a slug never saved — how every first game starts. Whether a save that *does*
        exist may still be played is `campaign.resumable`'s question, not this one's."""
        path = self._path(slug)
        if not path.exists():
            return None
        return GameState.model_validate_json(_text(path))

    def save(self, slug: str, state: GameState) -> None:
        _write(self._path(slug), state.model_dump_json(indent=2))

    def discard(self, slug: str) -> None:
        self._path(slug).unlink(missing_ok=True)

    def _path(self, slug: str) -> Path:
        return self.directory / f"{slug}.json"


@dataclass(frozen=True, slots=True)
class FileTraces:
    """One JSONL file per slug: a turn is appended and never rewritten, because the trace is the
    record of what each role was shown. Unversioned — stamp a version before anything reads it
    back."""

    directory: Path

    def append(self, slug: str, turn: Turn) -> None:
        path = self._path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=ENCODING) as file:
            file.write(turn.model_dump_json() + "\n")

    def discard(self, slug: str) -> None:
        self._path(slug).unlink(missing_ok=True)

    def _path(self, slug: str) -> Path:
        return self.directory / f"{slug}.trace.jsonl"


def _text(path: Path) -> str:
    return path.read_text(encoding=ENCODING)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding=ENCODING)
