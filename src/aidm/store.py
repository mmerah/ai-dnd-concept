from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from .domain.base import TRACE_VERSION
from .domain.definitions import CharacterDefinition, ScenarioDefinition
from .domain.state import GameState
from .domain.turn import Turn

ENCODING = "utf-8"
_SLUG_PATTERN = r"[a-z0-9][a-z0-9_-]*"


def read_scenario(path: Path) -> ScenarioDefinition:
    return ScenarioDefinition.model_validate_json(path.read_text(encoding=ENCODING))


def read_character(path: Path) -> CharacterDefinition:
    return CharacterDefinition.model_validate_json(path.read_text(encoding=ENCODING))


def read_named_scenario(directory: Path, name: str) -> ScenarioDefinition:
    return read_scenario(_safe_path(directory, name, ".json"))


def read_named_character(directory: Path, name: str) -> CharacterDefinition:
    return read_character(_safe_path(directory, name, ".json"))


def read_scenarios(directory: Path) -> dict[str, ScenarioDefinition]:
    return {_safe_stem(path.stem): read_scenario(path) for path in sorted(directory.glob("*.json"))}


def read_characters(directory: Path) -> dict[str, CharacterDefinition]:
    return {
        _safe_stem(path.stem): read_character(path) for path in sorted(directory.glob("*.json"))
    }


def read_turns(path: Path) -> tuple[Turn, ...]:
    if not path.exists():
        return ()
    turns = tuple(
        Turn.model_validate_json(line)
        for line in path.read_text(encoding=ENCODING).splitlines()
        if line
    )
    wrong = [turn.trace_version for turn in turns if turn.trace_version != TRACE_VERSION]
    if wrong:
        raise ValueError(f"trace version is {wrong[0]}, this build needs {TRACE_VERSION}")
    return turns


@dataclass(frozen=True, slots=True)
class FileSaves:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if fullmatch(_SLUG_PATTERN, path.stem) is not None
        )

    def load(self, slug: str) -> GameState | None:
        path = self._path(slug)
        if not path.exists():
            return None
        return GameState.model_validate_json(path.read_text(encoding=ENCODING))

    def save(self, slug: str, state: GameState) -> None:
        _write(self._path(slug), state.model_dump_json(indent=2))

    def discard(self, slug: str) -> None:
        self._path(slug).unlink(missing_ok=True)

    def _path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


@dataclass(frozen=True, slots=True)
class FileTraces:
    directory: Path

    def append(self, slug: str, turn: Turn) -> None:
        path = self._path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=ENCODING) as file:
            file.write(turn.model_dump_json() + "\n")

    def load(self, slug: str) -> tuple[Turn, ...]:
        return read_turns(self._path(slug))

    def discard(self, slug: str) -> None:
        self._path(slug).unlink(missing_ok=True)

    def _path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".trace.jsonl")


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding=ENCODING)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    return directory / f"{_safe_stem(stem)}{suffix}"


def _safe_stem(stem: str) -> str:
    if fullmatch(_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return stem
