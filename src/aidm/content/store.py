import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch
from shutil import rmtree

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from aidm.state.base import SAVE_VERSION, EngineId, Slug, content_id
from aidm.state.turn import TraceEntry
from aidm.state.world import GameState, ScenarioMeta

from .authored import (
    Binding,
    Character,
    CharacterOverlay,
    CharacterProfile,
    CreatedCharacter,
    Scenario,
    ScenarioOverlay,
    ScenarioWorld,
    check_hooks,
)
from .sources import CanonSource, PremiseSource

ENCODING = "utf-8"
WORLD_FILE = "world.json"
PROFILE_FILE = "base.json"
SOURCE_STEM = "source"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
_SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9_-]*"

type Playable[T] = Iterator[tuple[Slug, T, tuple[EngineId, ...]]]


def read_scenarios(directory: Path, engines: Sequence[EngineId]) -> Playable[ScenarioWorld]:
    return _playable(directory, WORLD_FILE, ScenarioWorld, engines)


def read_characters(directory: Path, engines: Sequence[EngineId]) -> Playable[CharacterProfile]:
    return _playable(directory, PROFILE_FILE, CharacterProfile, engines)


def load_scenario(directory: Path, name: Slug, binding: Binding) -> Scenario:
    folder = directory / content_id(name)
    scenario = Scenario(
        id=name,
        engine=binding.engine,
        world=_read(folder / WORLD_FILE, ScenarioWorld),
        overlay=_read(folder / f"{binding.engine}.json", ScenarioOverlay),
    )
    check_hooks(scenario.world, binding)
    binding.check_overlay(scenario.overlay.entities.values())
    return scenario


def source_file(directory: Path, name: Slug) -> Path | None:
    folder = directory / content_id(name)
    paths = (folder / f"{SOURCE_STEM}{suffix}" for suffix in SOURCE_SUFFIXES)
    return next((path for path in paths if path.is_file()), None)


def read_source(directory: Path, name: Slug, premise: str) -> CanonSource:
    path = source_file(directory, name)
    text = premise if path is None else path.read_text(encoding=ENCODING)
    return PremiseSource(text=text)


def require_source(directory: Path, name: Slug) -> Path:
    path = source_file(directory, name)
    if path is None:
        raise ValueError(
            f"scenario {name!r} expands from a document but ships no {SOURCE_STEM} file"
        )
    return path


def load_character(directory: Path, name: Slug, binding: Binding) -> Character:
    folder = directory / content_id(name)
    character = Character(
        id=name,
        engine=binding.engine,
        profile=_read(folder / PROFILE_FILE, CharacterProfile),
        overlay=_read(folder / f"{binding.engine}.json", CharacterOverlay),
    )
    binding.check_overlay((character.overlay.character, *character.overlay.entities.values()))
    return character


def write_character(
    directory: Path, name: Slug, engine: EngineId, created: CreatedCharacter
) -> None:
    folder = directory / content_id(name)
    if folder.exists():
        raise ValueError(f"character {name!r} already exists")
    _write(folder / PROFILE_FILE, created.profile.model_dump_json(indent=2))
    _write(folder / f"{engine}.json", created.overlay.model_dump_json(indent=2))


def write_scenario(
    directory: Path,
    name: Slug,
    scenario: ScenarioWorld,
    overlays: Mapping[EngineId, ScenarioOverlay],
    source: str | Path | None = None,
) -> None:
    folder = directory / content_id(name)
    if folder.exists():
        raise ValueError(f"scenario {name!r} already exists")
    _write(folder / WORLD_FILE, scenario.model_dump_json(indent=2))
    for engine, overlay in overlays.items():
        _write(folder / f"{engine}.json", overlay.model_dump_json(indent=2))
    if isinstance(source, Path):
        _copy(folder / f"{SOURCE_STEM}{source.suffix}", source)
    elif source is not None:
        _write(folder / f"{SOURCE_STEM}{SOURCE_SUFFIXES[0]}", source)


def _playable[T: BaseModel](
    directory: Path, canon: str, model: type[T], engines: Sequence[EngineId]
) -> Playable[T]:
    """A directory holding no canon file is not content; one with no overlay plays under no rules.

    Skipping both keeps a scratch directory or a half-written scenario out of the launcher instead
    of failing the home screen, which is the only way into the app.
    """
    for path in sorted(directory.iterdir()):
        if not (path / canon).is_file():
            continue
        written = tuple(engine for engine in engines if (path / f"{engine}.json").is_file())
        if written:
            yield content_id(path.name), _read(path / canon, model), written


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    if not path.is_file():
        raise ValueError(f"{path.parent.name!r} has no {path.name}")
    return model.model_validate_json(path.read_text(encoding=ENCODING))


def engine_text(path: Path) -> str:
    """In content so `engines.loader` and `engines.advancement` share it without a cycle."""
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


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


@dataclass(frozen=True, slots=True)
class FileStore:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if fullmatch(_SAVE_SLUG_PATTERN, path.stem) is not None
        )

    def shell(self, slug: str) -> SaveShell | None:
        path = self._save_path(slug)
        if not path.exists():
            return None
        shell = SaveShell.model_validate_json(path.read_text(encoding=ENCODING))
        _require_save_version(shell.save_version, "save")
        return shell

    def load(self, slug: str) -> GameState | None:
        """The shell probes the stored version first, so drift fails readably."""
        if self.shell(slug) is None:
            return None
        body = self._save_path(slug).read_text(encoding=ENCODING)
        return GameState.model_validate_json(body)

    def save(self, slug: str, state: GameState) -> None:
        _write(self._save_path(slug), state.model_dump_json(indent=2))

    def append_trace(self, slug: str, entry: TraceEntry) -> None:
        path = self._trace_path(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=ENCODING) as file:
            file.write(TRACE_ADAPTER.dump_json(entry).decode(ENCODING) + "\n")

    def load_trace(self, slug: str) -> tuple[TraceEntry, ...]:
        path = self._trace_path(slug)
        if not path.exists():
            return ()
        entries: list[TraceEntry] = []
        for line in path.read_text(encoding=ENCODING).splitlines():
            if not line:
                continue
            _require_save_version(_line_version(line), "trace")
            entries.append(TRACE_ADAPTER.validate_json(line))
        return tuple(entries)

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        self._save_path(slug).unlink(missing_ok=True)
        self._trace_path(slug).unlink(missing_ok=True)
        rmtree(self.media_dir(slug), ignore_errors=True)

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")

    def _trace_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".trace.jsonl")


def _line_version(line: str) -> int:
    """A line written before `save_version` existed reports as 0, not as a validation error."""
    parsed: JsonValue = json.loads(line)
    version = parsed.get("save_version", 0) if isinstance(parsed, dict) else 0
    return version if isinstance(version, int) else 0


def _copy(path: Path, original: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(original.read_bytes())


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding=ENCODING)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    if fullmatch(_SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return directory / f"{stem}{suffix}"
