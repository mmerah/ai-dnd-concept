import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from pydantic import BaseModel, JsonValue

from aidm.kernel.envelope import CharacterEnvelope, ScenarioEnvelope
from aidm.kernel.protocol import EngineIdentity
from aidm.state.entities import EngineId, Slug, content_id, require_unique
from aidm.state.model import Character, Game, Scenario

ENCODING = "utf-8"
WORLD_FILE = "world.json"
SOURCE_STEM = "source"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
_SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9-]*"

LOGGER = logging.getLogger(__name__)


def scenario_of(envelope: ScenarioEnvelope, engine: EngineIdentity) -> Scenario:
    if envelope.engine != engine.id:
        raise ValueError(f"the scenario plays {envelope.engine!r}, not {engine.id!r}")
    return Scenario.model_validate(envelope.model_dump())


def character_of(envelope: CharacterEnvelope, engine: EngineIdentity) -> Character:
    if envelope.engine != engine.id:
        raise ValueError(f"the character plays {envelope.engine!r}, not {engine.id!r}")
    return Character.model_validate(envelope.model_dump())


def read_scenarios(
    directory: Path, engines: Mapping[EngineId, EngineIdentity]
) -> Iterator[tuple[Slug, Scenario]]:
    for path in _content_dirs(directory, WORLD_FILE):
        try:
            envelope = _read(path / WORLD_FILE, ScenarioEnvelope)
            engine = engines.get(envelope.engine)
            if engine is None:
                LOGGER.warning(
                    "skipping scenario %r: it needs the %r engine", path.name, envelope.engine
                )
                continue
            scenario = scenario_of(envelope, engine)
        except ValueError as unreadable:
            # Skip incomplete scenarios so the home screen remains usable.
            LOGGER.warning("skipping scenario %r: %s", path.name, unreadable)
            continue
        yield content_id(path.name), scenario


def read_characters(
    directory: Path, engines: Mapping[EngineId, EngineIdentity]
) -> Iterator[tuple[Slug, Character, tuple[EngineId, ...]]]:
    """One entry per character: the catalog keys by id, so the first written engine names them."""
    for path in sorted(directory.iterdir()):
        written = tuple(engine for engine in engines if (path / f"{engine}.json").is_file())
        if not written:
            continue
        try:
            envelope = _read(path / f"{written[0]}.json", CharacterEnvelope)
            character = character_of(envelope, engines[written[0]])
        except ValueError as unreadable:
            LOGGER.warning("skipping character %r: %s", path.name, unreadable)
            continue
        yield content_id(path.name), character, written


def _content_dirs(directory: Path, canon: str) -> Iterator[Path]:
    return (path for path in sorted(directory.iterdir()) if (path / canon).is_file())


def scenario_envelope(directory: Path, name: Slug) -> ScenarioEnvelope:
    folder = directory / content_id(name)
    return _read(folder / WORLD_FILE, ScenarioEnvelope)


def load_scenario(directory: Path, name: Slug, engine: EngineIdentity) -> Scenario:
    return scenario_of(scenario_envelope(directory, name), engine)


def source_file(directory: Path, name: Slug) -> Path | None:
    folder = directory / content_id(name)
    paths = (folder / f"{SOURCE_STEM}{suffix}" for suffix in SOURCE_SUFFIXES)
    return next((path for path in paths if path.is_file()), None)


def load_character(directory: Path, name: Slug, engine: EngineIdentity) -> Character:
    folder = directory / content_id(name)
    character = character_of(_read(folder / f"{engine.id}.json", CharacterEnvelope), engine)
    if character.id != content_id(name):
        raise ValueError(f"character {character.id!r} is filed under {content_id(name)!r}")
    return character


def write_character(directory: Path, character: CharacterEnvelope) -> None:
    folder = directory / content_id(character.id)
    path = folder / f"{character.engine}.json"
    if path.exists():
        raise ValueError(f"character {character.id!r} already exists")
    # One folder is one person played by several engines, so any sibling settles who that is.
    sibling = next(folder.glob("*.json"), None)
    if sibling is not None and (held := _read(sibling, CharacterEnvelope)).name != character.name:
        raise ValueError(f"character {character.id!r} is {held.name!r}, not {character.name!r}")
    _write(path, character.model_dump_json(indent=2))


def write_scenario(
    directory: Path,
    name: Slug,
    scenario: Scenario,
    source: str | Path | None = None,
) -> None:
    folder = directory / content_id(name)
    if folder.exists():
        raise ValueError(f"scenario {name!r} already exists")
    _write(folder / WORLD_FILE, scenario.model_dump_json(indent=2))
    if isinstance(source, Path):
        _copy(folder / f"{SOURCE_STEM}{source.suffix}", source)
    elif source is not None:
        _write(folder / f"{SOURCE_STEM}{SOURCE_SUFFIXES[0]}", source)


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"{path.parent.name!r} has no {path.name}")
    return path.read_text(encoding=ENCODING)


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    # `json` keeps the last of two equal keys, so a doubled entity id would vanish without a word.
    return model.model_validate(json.loads(_read_text(path), object_pairs_hook=_unique_keys))


def _unique_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    require_unique("keys in a JSON object", (key for key, _ in pairs))
    return dict(pairs)


def engine_text(path: Path) -> str:
    """In content so `engines.core` and `turn.context` share it without a cycle."""
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


@dataclass(frozen=True, slots=True)
class FileStore:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if fullmatch(_SAVE_SLUG_PATTERN, path.stem) is not None
        )

    def load(self, slug: str) -> str | None:
        path = self._save_path(slug)
        return path.read_text(encoding=ENCODING) if path.exists() else None

    def save(self, slug: str, state: Game) -> None:
        _write(self._save_path(slug), state.model_dump_json(indent=2))

    def stamp(self, slug: str) -> int:
        """A viewer in another process polls this rather than re-parsing the save every tick."""
        path = self._save_path(slug)
        return path.stat().st_mtime_ns if path.exists() else 0

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        self._save_path(slug).unlink(missing_ok=True)

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


def _copy(path: Path, original: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(original.read_bytes())


def _write(path: Path, body: str) -> None:
    """Two processes may read one save; a reader must never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f"{path.name}.writing")
    staged.write_text(body, encoding=ENCODING)
    staged.replace(path)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    if fullmatch(_SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return directory / f"{stem}{suffix}"
