from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from pydantic import BaseModel, ConfigDict, TypeAdapter

from .base import SAVE_VERSION, EngineId, Slug, content_id
from .content import (
    Character,
    CharacterOverlay,
    CharacterProfile,
    Scenario,
    ScenarioOverlay,
    ScenarioWorld,
)
from .registry import engine_ids
from .turn import TraceEntry
from .world import EngineRules, GameState, ScenarioMeta

ENCODING = "utf-8"
WORLD_FILE = "world.json"
PROFILE_FILE = "base.json"
_SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9_-]*"

type Playable[T] = Iterator[tuple[Slug, T, tuple[EngineId, ...]]]


def read_scenarios(directory: Path) -> Playable[ScenarioWorld]:
    return _playable(directory, WORLD_FILE, ScenarioWorld)


def read_characters(directory: Path) -> Playable[CharacterProfile]:
    return _playable(directory, PROFILE_FILE, CharacterProfile)


def load_scenario(directory: Path, name: Slug, engine: EngineId) -> Scenario:
    folder = directory / content_id(name)
    return Scenario(
        id=name,
        engine=engine,
        world=_read(folder / WORLD_FILE, ScenarioWorld),
        overlay=_read(folder / f"{engine}.json", ScenarioOverlay),
    )


def load_character(directory: Path, name: Slug, engine: EngineId) -> Character:
    folder = directory / content_id(name)
    return Character(
        id=name,
        engine=engine,
        profile=_read(folder / PROFILE_FILE, CharacterProfile),
        overlay=_read(folder / f"{engine}.json", CharacterOverlay),
    )


def _playable[T: BaseModel](directory: Path, canon: str, model: type[T]) -> Playable[T]:
    """A directory holding no canon file is not content; one with no overlay plays under no rules.

    Skipping both keeps a scratch directory or a half-written scenario out of the launcher instead
    of failing the home screen, which is the only way into the app.
    """
    for path in sorted(directory.iterdir()):
        if not (path / canon).is_file():
            continue
        engines = tuple(engine for engine in engine_ids() if (path / f"{engine}.json").is_file())
        if engines:
            yield content_id(path.name), _read(path / canon, model), engines


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    if not path.is_file():
        raise ValueError(f"{path.parent.name!r} has no {path.name}")
    return model.model_validate_json(path.read_text(encoding=ENCODING))


class _StoredVersion(BaseModel):
    """Probes the stored version before the rest is validated, so drift fails readably.

    A file written before `save_version` existed reports as version 0 rather than as a
    validation error naming this private model.
    """

    save_version: int = 0


def _require_save_version(stored: int, what: str) -> None:
    if stored != SAVE_VERSION:
        raise ValueError(f"{what} is version {stored}, this build needs {SAVE_VERSION}")


class SaveShell(BaseModel):
    model_config = ConfigDict(extra="ignore")

    save_version: int = 0
    engine: EngineId
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    turn: int


TRACE_ADAPTER: TypeAdapter[TraceEntry] = TypeAdapter(TraceEntry)


def read_trace(path: Path) -> tuple[TraceEntry, ...]:
    if not path.exists():
        return ()
    entries: list[TraceEntry] = []
    for line in path.read_text(encoding=ENCODING).splitlines():
        if not line:
            continue
        _require_save_version(_StoredVersion.model_validate_json(line).save_version, "trace")
        entries.append(TRACE_ADAPTER.validate_json(line))
    return tuple(entries)


@dataclass(frozen=True, slots=True)
class FileSaves:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if fullmatch(_SAVE_SLUG_PATTERN, path.stem) is not None
        )

    def shell(self, slug: str) -> SaveShell | None:
        path = self._path(slug)
        if not path.exists():
            return None
        shell = SaveShell.model_validate_json(path.read_text(encoding=ENCODING))
        _require_save_version(shell.save_version, "save")
        return shell

    def load(
        self, slug: str, state_type: type[GameState[EngineRules]]
    ) -> GameState[EngineRules] | None:
        path = self._path(slug)
        if not path.exists():
            return None
        body = path.read_text(encoding=ENCODING)
        _require_save_version(_StoredVersion.model_validate_json(body).save_version, "save")
        return state_type.model_validate_json(body)

    def save(self, slug: str, state: GameState[EngineRules]) -> None:
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
    if fullmatch(_SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return stem
