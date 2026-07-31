from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from pydantic import BaseModel, TypeAdapter

from .domain.base import SAVE_VERSION
from .domain.definitions import CharacterDefinition, ScenarioDefinition
from .domain.state import GameState
from .domain.turn import TraceEntry

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


class _StoredVersion(BaseModel):
    """Probes the stored version before the rest is validated, so drift fails readably.

    A file written before `save_version` existed reports as version 0 rather than as a
    validation error naming this private model.
    """

    save_version: int = 0


class _TracedVersion(BaseModel):
    state: _StoredVersion = _StoredVersion()


def _require_save_version(stored: int, what: str) -> None:
    if stored != SAVE_VERSION:
        raise ValueError(f"{what} is version {stored}, this build needs {SAVE_VERSION}")


TRACE_ADAPTER: TypeAdapter[TraceEntry] = TypeAdapter(TraceEntry)


def read_trace(path: Path) -> tuple[TraceEntry, ...]:
    if not path.exists():
        return ()
    entries: list[TraceEntry] = []
    for line in path.read_text(encoding=ENCODING).splitlines():
        if not line:
            continue
        _require_save_version(_TracedVersion.model_validate_json(line).state.save_version, "trace")
        entries.append(TRACE_ADAPTER.validate_json(line))
    return tuple(entries)


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
        body = path.read_text(encoding=ENCODING)
        _require_save_version(_StoredVersion.model_validate_json(body).save_version, "save")
        return GameState.model_validate_json(body)

    def save(self, slug: str, state: GameState) -> None:
        _write(self._path(slug), state.model_dump_json(indent=2))

    def discard(self, slug: str) -> None:
        self._path(slug).unlink(missing_ok=True)

    def _path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


@dataclass(frozen=True, slots=True)
class FileTraces:
    directory: Path

    def append(self, slug: str, entry: TraceEntry) -> None:
        path = self._path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=ENCODING) as file:
            file.write(TRACE_ADAPTER.dump_json(entry).decode(ENCODING) + "\n")

    def load(self, slug: str) -> tuple[TraceEntry, ...]:
        return read_trace(self._path(slug))

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
