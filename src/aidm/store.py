from dataclasses import dataclass
from pathlib import Path

from .domain.models import CharacterSheet, GameState, ScenarioDef, Turn

ENCODING = "utf-8"


def read_scenario(path: Path) -> ScenarioDef:
    return ScenarioDef.model_validate_json(_text(path))


def read_sheet(path: Path) -> CharacterSheet:
    return CharacterSheet.model_validate_json(_text(path))


@dataclass(frozen=True, slots=True)
class FileSaves:
    directory: Path

    def load(self, slug: str) -> GameState | None:
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
