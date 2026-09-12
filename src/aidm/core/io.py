import json
import logging
import os
import re
from collections.abc import Callable, Collection, Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import mkstemp

from pydantic import BaseModel, JsonValue

from aidm.core.entities import EngineId, Refusal, Slug, check_unique, content_id, parse, parse_json
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, CharacterHeader, EngineHeader

LOGGER = logging.getLogger(__name__)

ENCODING = "utf-8"
WORLD_FILE = "world.json"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
# Two content ids joined by `--`: a save name is not a `Slug`.
SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9-]*"


@dataclass(frozen=True, slots=True)
class FileStore:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if re.fullmatch(SAVE_SLUG_PATTERN, path.stem) is not None
        )

    def read(self, slug: str) -> str | None:
        path = self._save_path(slug)
        return _read_text(path) if path.is_file() else None

    def write(self, slug: str, state: AnyGame, /) -> None:
        write_text(self._save_path(slug), state.model_dump_json(indent=2))

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        try:
            self._save_path(slug).unlink(missing_ok=True)
        except OSError as broken:
            raise Refusal(f"{slug} cannot be discarded: {broken}") from broken

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")


@dataclass(frozen=True, slots=True)
class Library:
    scenarios: Path
    characters: Path

    def scenario_folder(self, scenario_id: Slug) -> Path:
        return self.scenarios / content_id(scenario_id)

    def character_folder(self, character_id: Slug) -> Path:
        return self.characters / content_id(character_id)

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
        for path in sorted(
            entry for entry in self.scenarios.iterdir() if (entry / WORLD_FILE).is_file()
        ):
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
        """One entry per (character, engine) file, so a shared id never names one engine's rules."""
        if not self.characters.is_dir():
            return
        for path in sorted(entry for entry in self.characters.iterdir() if entry.is_dir()):
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
        self, scenario_id: Slug, models: Mapping[EngineId, type[AnyScenario]]
    ) -> AnyScenario:
        path = self.scenario_folder(scenario_id) / WORLD_FILE
        raw = _read_text(path)
        return parse_json(routed(decode(raw), models), raw)

    def read_character(
        self, character_id: Slug, engine: EngineId, model: type[AnyCharacter]
    ) -> AnyCharacter:
        character = _read(self.character_folder(character_id) / f"{engine}.json", model)
        _check_filed(character.id, character.engine, content_id(character_id), engine)
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

    def write_scenario(self, scenario_id: Slug, scenario: AnyScenario) -> None:
        folder = self.scenario_folder(scenario_id)
        if folder.exists():
            raise Refusal(f"scenario {scenario_id!r} already exists")
        write_text(folder / WORLD_FILE, scenario.model_dump_json(indent=2))


@cache
def read_prompt(path: Path) -> str:
    return path.read_text(encoding=ENCODING)


def publish(path: Path, write: Callable[[Path], object]) -> None:
    """Write beside, then replace: a reader never sees a partial file."""
    staged: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = mkstemp(dir=path.parent, prefix=f".{path.name}.")
        os.close(fd)
        staged = Path(name)
        write(staged)
        staged.replace(path)
    except OSError as broken:
        raise Refusal(f"{path.name} cannot be written: {broken}") from broken
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def write_text(path: Path, body: str) -> None:
    publish(path, lambda staged: staged.write_text(body, encoding=ENCODING))


def decode(raw: str) -> JsonValue:
    """`json` keeps the last of two equal keys, so a doubled id would vanish without a word."""
    try:
        return json.loads(raw, object_pairs_hook=_unique_keys)
    except json.JSONDecodeError as broken:
        raise Refusal(f"not JSON: {broken}") from broken


def routed[T](value: JsonValue, by_engine: Mapping[EngineId, T]) -> T:
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
    except (OSError, UnicodeDecodeError) as broken:
        raise Refusal(f"{path.name} cannot be read: {broken}") from broken


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    raw = _read_text(path)
    decode(raw)
    return parse_json(model, raw)


def _check_filed(character_id: str, plays: EngineId, filed_under: Slug, engine: EngineId) -> None:
    if plays != engine:
        raise Refusal(f"the character plays {plays!r}, not {engine!r}")
    if character_id != filed_under:
        raise Refusal(f"character {character_id!r} is filed under {filed_under!r}")


def _unique_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    check_unique("keys in a JSON object", (key for key, _ in pairs))
    return dict(pairs)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    if re.fullmatch(SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return directory / f"{stem}{suffix}"
