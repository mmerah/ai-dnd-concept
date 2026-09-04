import json
import logging
import shutil
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch

from pydantic import BaseModel, JsonValue

from aidm.core.entities import EngineId, Refusal, Slug, content_id, parse, require_unique
from aidm.core.model import (
    AnyCharacter,
    AnyGame,
    AnyScenario,
    CharacterHeader,
    EngineHeader,
)

ENCODING = "utf-8"
WORLD_FILE = "world.json"
SOURCE_STEM = "source"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
# Two content ids joined by `--`: a save name is not a `Slug`.
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
        return _read_text(path) if path.is_file() else None

    def save(self, slug: str, state: AnyGame) -> None:
        write_text(self._save_path(slug), state.model_dump_json(indent=2))

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        self._save_path(slug).unlink(missing_ok=True)

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


@dataclass(frozen=True, slots=True)
class Library:
    """The two content directories; `FileStore` is the third, the saves."""

    scenarios: Path
    characters: Path

    def scenario_folder(self, name: Slug) -> Path:
        return self.scenarios / content_id(name)

    def character_folder(self, name: Slug) -> Path:
        return self.characters / content_id(name)

    def scenario_ids(self) -> tuple[str, ...]:
        """Every entry, slug or not: a new slug must not collide with a stray folder."""
        if not self.scenarios.is_dir():
            return ()
        return tuple(entry.name for entry in self.scenarios.iterdir())

    def read_scenarios(
        self, models: Mapping[EngineId, type[AnyScenario]]
    ) -> Iterator[tuple[Slug, AnyScenario]]:
        if not self.scenarios.is_dir():
            return
        for path in sorted(p for p in self.scenarios.iterdir() if (p / WORLD_FILE).is_file()):
            try:
                scenario = self.read_scenario(path.name, models)
            except Refusal as unreadable:
                # Skip incomplete scenarios so the home screen remains usable.
                LOGGER.warning("skipping scenario %r: %s", path.name, unreadable)
                continue
            yield content_id(path.name), scenario

    def read_characters(
        self, engines: Collection[EngineId]
    ) -> Iterator[tuple[Slug, EngineId, CharacterHeader]]:
        """One entry per character and engine written, so a shared id never names one
        engine's rules."""
        if not self.characters.is_dir():
            return
        for path in sorted(p for p in self.characters.iterdir() if p.is_dir()):
            for engine in engines:
                file = path / f"{engine}.json"
                if not file.is_file():
                    continue
                try:
                    name = content_id(path.name)
                    header = _read(file, CharacterHeader)
                    _check_filed(header.id, header.engine, name, engine)
                except Refusal as unreadable:
                    LOGGER.warning("skipping character %r: %s", path.name, unreadable)
                    continue
                yield name, engine, header

    def read_scenario(
        self, name: Slug, models: Mapping[EngineId, type[AnyScenario]]
    ) -> AnyScenario:
        path = self.scenario_folder(name) / WORLD_FILE
        value = decode(_read_text(path))
        model = routed(value, models)
        return parse(model, value)

    def read_character(
        self, name: Slug, engine: EngineId, model: type[AnyCharacter]
    ) -> AnyCharacter:
        character = _read(self.character_folder(name) / f"{engine}.json", model)
        _check_filed(character.id, character.engine, content_id(name), engine)
        return character

    def write_character(self, character: AnyCharacter) -> None:
        folder = self.character_folder(character.id)
        path = folder / f"{character.engine}.json"
        if path.exists():
            raise Refusal(f"character {character.id!r} already exists")
        # One folder is one person played by several engines, so any sibling settles who that is.
        sibling = next(folder.glob("*.json"), None)
        if sibling is not None:
            filed, named = _read(sibling, CharacterHeader).payload.name, character.payload.name
            if filed != named:
                raise Refusal(f"character {character.id!r} is {filed!r}, not {named!r}")
        write_text(path, character.model_dump_json(indent=2))

    def write_scenario(
        self,
        name: Slug,
        scenario: AnyScenario,
        source: Path | None = None,
    ) -> None:
        folder = self.scenario_folder(name)
        if folder.exists():
            raise Refusal(f"scenario {name!r} already exists")
        write_text(folder / WORLD_FILE, scenario.model_dump_json(indent=2))
        if source is not None:
            shutil.copyfile(source, folder / f"{SOURCE_STEM}{source.suffix}")


def write_text(path: Path, body: str) -> None:
    """Two processes may read one save; a reader must never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f"{path.name}.writing")
    staged.write_text(body, encoding=ENCODING)
    staged.replace(path)


def decode(raw: str) -> JsonValue:
    """`json` keeps the last of two equal keys, so a doubled id would vanish without a word."""
    try:
        return json.loads(raw, object_pairs_hook=_unique_keys)
    except json.JSONDecodeError as broken:
        raise Refusal(f"not JSON: {broken}") from broken


def routed[T](value: JsonValue, by_engine: Mapping[EngineId, T]) -> T:
    """What the caller keeps under the engine a document's header names."""
    engine = parse(EngineHeader, value).engine
    found = by_engine.get(engine)
    if found is None:
        raise Refusal(f"the {engine!r} engine is not installed")
    return found


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise Refusal(f"{path.parent.name!r} has no {path.name}")
    try:
        return path.read_text(encoding=ENCODING)
    except UnicodeDecodeError as broken:
        raise Refusal(f"{path.name} is not {ENCODING}: {broken}") from broken


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    return parse(model, decode(_read_text(path)))


def _check_filed(character_id: str, plays: EngineId, name: Slug, engine: EngineId) -> None:
    if plays != engine:
        raise Refusal(f"the character plays {plays!r}, not {engine!r}")
    if character_id != name:
        raise Refusal(f"character {character_id!r} is filed under {name!r}")


def _unique_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    require_unique("keys in a JSON object", (key for key, _ in pairs))
    return dict(pairs)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    if fullmatch(_SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return directory / f"{stem}{suffix}"
