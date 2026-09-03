import json
import logging
import shutil
from collections.abc import Iterator, Mapping
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


def read_scenarios(
    directory: Path, models: Mapping[EngineId, type[AnyScenario]]
) -> Iterator[tuple[Slug, AnyScenario]]:
    for path in sorted(p for p in directory.iterdir() if (p / WORLD_FILE).is_file()):
        try:
            scenario = read_scenario(directory, path.name, models)
        except Refusal as unreadable:
            # Skip incomplete scenarios so the home screen remains usable.
            LOGGER.warning("skipping scenario %r: %s", path.name, unreadable)
            continue
        yield content_id(path.name), scenario


def read_characters(
    directory: Path, models: Mapping[EngineId, type[AnyCharacter]]
) -> Iterator[tuple[Slug, EngineId, AnyCharacter]]:
    """One entry per character and engine written, so a shared id never names one engine's rules."""
    for path in sorted(directory.iterdir()):
        for engine, model in models.items():
            if not (path / f"{engine}.json").is_file():
                continue
            try:
                yield (
                    content_id(path.name),
                    engine,
                    read_character(directory, path.name, engine, model),
                )
            except Refusal as unreadable:
                LOGGER.warning("skipping character %r: %s", path.name, unreadable)


def read_scenario(
    directory: Path, name: Slug, models: Mapping[EngineId, type[AnyScenario]]
) -> AnyScenario:
    path = directory / content_id(name) / WORLD_FILE
    value = decode(_read_text(path))
    engine = parse(EngineHeader, value).engine
    model = models.get(engine)
    if model is None:
        raise Refusal(f"the scenario needs the unavailable {engine!r} engine")
    return parse(model, value)


def read_character(
    directory: Path, name: Slug, engine: EngineId, model: type[AnyCharacter]
) -> AnyCharacter:
    character = _read(directory / content_id(name) / f"{engine}.json", model)
    if character.engine != engine:
        raise Refusal(f"the character plays {character.engine!r}, not {engine!r}")
    if character.id != content_id(name):
        raise Refusal(f"character {character.id!r} is filed under {content_id(name)!r}")
    return character


def write_character(directory: Path, character: AnyCharacter) -> None:
    folder = directory / content_id(character.id)
    path = folder / f"{character.engine}.json"
    if path.exists():
        raise Refusal(f"character {character.id!r} already exists")
    # One folder is one person played by several engines, so any sibling settles who that is.
    sibling = next(folder.glob("*.json"), None)
    if sibling is not None and (held := _read(sibling, CharacterHeader)).name != character.name:
        raise Refusal(f"character {character.id!r} is {held.name!r}, not {character.name!r}")
    write_text(path, character.model_dump_json(indent=2))


def write_scenario(
    directory: Path,
    name: Slug,
    scenario: AnyScenario,
    source: Path | None = None,
) -> None:
    folder = directory / content_id(name)
    if folder.exists():
        raise Refusal(f"scenario {name!r} already exists")
    write_text(folder / WORLD_FILE, scenario.model_dump_json(indent=2))
    if source is not None:
        shutil.copyfile(source, folder / f"{SOURCE_STEM}{source.suffix}")


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise Refusal(f"{path.parent.name!r} has no {path.name}")
    try:
        return path.read_text(encoding=ENCODING)
    except UnicodeDecodeError as broken:
        raise Refusal(f"{path.name} is not {ENCODING}: {broken}") from broken


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    return parse(model, decode(_read_text(path)))


def _unique_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    require_unique("keys in a JSON object", (key for key, _ in pairs))
    return dict(pairs)


def _safe_path(directory: Path, stem: str, suffix: str) -> Path:
    if fullmatch(_SAVE_SLUG_PATTERN, stem) is None:
        raise ValueError(f"invalid storage slug {stem!r}")
    return directory / f"{stem}{suffix}"
