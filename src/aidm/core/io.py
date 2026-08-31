import json
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from pydantic import BaseModel, JsonValue

from aidm.core.entities import EngineId, Slug, content_id, require_unique
from aidm.core.model import Character, CharacterHeader, EngineHeader, Game, Scenario

ENCODING = "utf-8"
WORLD_FILE = "world.json"
SOURCE_STEM = "source"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
_SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9-]*"

LOGGER = logging.getLogger(__name__)


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

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        self._save_path(slug).unlink(missing_ok=True)

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


def decoded(raw: str) -> JsonValue:
    """`json` keeps the last of two equal keys, so a doubled id would vanish without a word."""
    return json.loads(raw, object_pairs_hook=_unique_keys)


def read_scenarios(directory: Path, engines: Sequence[EngineId]) -> Iterator[tuple[Slug, Scenario]]:
    for path in _content_dirs(directory, WORLD_FILE):
        try:
            value = decoded(_read_text(path / WORLD_FILE))
            if (header := EngineHeader.model_validate(value)).engine not in engines:
                LOGGER.warning(
                    "skipping scenario %r: it needs the %r engine", path.name, header.engine
                )
                continue
            scenario = Scenario.model_validate(value)
        except ValueError as unreadable:
            # Skip incomplete scenarios so the home screen remains usable.
            LOGGER.warning("skipping scenario %r: %s", path.name, unreadable)
            continue
        yield content_id(path.name), scenario


def read_characters(
    directory: Path, engines: Sequence[EngineId]
) -> Iterator[tuple[Slug, EngineId, Character]]:
    """One entry per character and engine written, so a shared id never names one engine's rules."""
    for path in sorted(directory.iterdir()):
        for engine in engines:
            if not (path / f"{engine}.json").is_file():
                continue
            try:
                yield content_id(path.name), engine, load_character(directory, path.name, engine)
            except ValueError as unreadable:
                LOGGER.warning("skipping character %r: %s", path.name, unreadable)


def read_scenario(directory: Path, name: Slug) -> Scenario:
    return _read(directory / content_id(name) / WORLD_FILE, Scenario)


def load_character(directory: Path, name: Slug, engine: EngineId) -> Character:
    character = _read(directory / content_id(name) / f"{engine}.json", Character)
    if character.engine != engine:
        raise ValueError(f"the character plays {character.engine!r}, not {engine!r}")
    if character.id != content_id(name):
        raise ValueError(f"character {character.id!r} is filed under {content_id(name)!r}")
    return character


def write_character(directory: Path, character: Character) -> None:
    folder = directory / content_id(character.id)
    path = folder / f"{character.engine}.json"
    if path.exists():
        raise ValueError(f"character {character.id!r} already exists")
    # One folder is one person played by several engines, so any sibling settles who that is.
    sibling = next(folder.glob("*.json"), None)
    if sibling is not None and (held := _read(sibling, CharacterHeader)).name != character.name:
        raise ValueError(f"character {character.id!r} is {held.name!r}, not {character.name!r}")
    _write(path, character.model_dump_json(indent=2))


def write_scenario(
    directory: Path,
    name: Slug,
    scenario: Scenario,
    source: Path | None = None,
) -> None:
    folder = directory / content_id(name)
    if folder.exists():
        raise ValueError(f"scenario {name!r} already exists")
    _write(folder / WORLD_FILE, scenario.model_dump_json(indent=2))
    if source is not None:
        _copy(folder / f"{SOURCE_STEM}{source.suffix}", source)


def engine_text(path: Path) -> str:
    """In core so `engines.core` and `turn.context` share it without a cycle."""
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


def _content_dirs(directory: Path, canon: str) -> Iterator[Path]:
    return (path for path in sorted(directory.iterdir()) if (path / canon).is_file())


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"{path.parent.name!r} has no {path.name}")
    return path.read_text(encoding=ENCODING)


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    return model.model_validate(decoded(_read_text(path)))


def _unique_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    require_unique("keys in a JSON object", (key for key, _ in pairs))
    return dict(pairs)


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
