import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from pypdf import PdfReader

from aidm.state.entities import EngineId, Mutable, Slug, content_id
from aidm.state.model import Game, ScenarioMeta, WorldState, check_player_playable
from aidm.state.play import Exchange, PendingDecision

from .model import (
    Character,
    CharacterOverlay,
    CharacterProfile,
    CreatedCharacter,
    Scenario,
)

ENCODING = "utf-8"
WORLD_FILE = "world.json"
PROFILE_FILE = "base.json"
SOURCE_STEM = "source"
SOURCE_SUFFIXES = (".md", ".txt", ".pdf")
_SAVE_SLUG_PATTERN = r"[a-z0-9][a-z0-9_-]*"

LOGGER = logging.getLogger(__name__)


def read_scenarios(
    directory: Path, engines: Sequence[EngineId]
) -> Iterator[tuple[Slug, Scenario, tuple[EngineId, ...]]]:
    for path in _content_dirs(directory, WORLD_FILE):
        try:
            scenario = _read(path / WORLD_FILE, Scenario)
        except ValueError as unreadable:
            # Skip incomplete scenarios so the home screen remains usable.
            LOGGER.warning("skipping scenario %r: %s", path.name, unreadable)
            continue
        # Installed order, so a scenario naming an engine twice cannot offer it twice.
        playable = tuple(engine for engine in engines if engine in scenario.engines)
        if not playable:
            LOGGER.warning("skipping scenario %r: it names no installed engine", path.name)
            continue
        yield content_id(path.name), scenario, playable


def read_characters(
    directory: Path, engines: Sequence[EngineId]
) -> Iterator[tuple[Slug, CharacterProfile, tuple[EngineId, ...]]]:
    for path in _content_dirs(directory, PROFILE_FILE):
        written = tuple(engine for engine in engines if (path / f"{engine}.json").is_file())
        if written:
            yield content_id(path.name), _read(path / PROFILE_FILE, CharacterProfile), written


def _content_dirs(directory: Path, canon: str) -> Iterator[Path]:
    return (path for path in sorted(directory.iterdir()) if (path / canon).is_file())


def load_scenario(directory: Path, name: Slug) -> Scenario:
    folder = directory / content_id(name)
    return _read(folder / WORLD_FILE, Scenario)


def source_file(directory: Path, name: Slug) -> Path | None:
    folder = directory / content_id(name)
    paths = (folder / f"{SOURCE_STEM}{suffix}" for suffix in SOURCE_SUFFIXES)
    return next((path for path in paths if path.is_file()), None)


def load_character(
    directory: Path,
    name: Slug,
    engine: EngineId,
    check_overlay: Callable[[dict[str, JsonValue]], None],
) -> Character:
    folder = directory / content_id(name)
    character = Character(
        id=name,
        profile=_read(folder / PROFILE_FILE, CharacterProfile),
        overlay=_read(folder / f"{engine}.json", CharacterOverlay),
    )
    check_overlay(character.overlay.character)
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


def _read[T: BaseModel](path: Path, model: type[T]) -> T:
    if not path.is_file():
        raise ValueError(f"{path.parent.name!r} has no {path.name}")
    return model.model_validate_json(path.read_text(encoding=ENCODING))


def engine_text(path: Path) -> str:
    """In content so `engines.engine` and `engines.advancement` share it without a cycle."""
    if not path.is_file():
        raise ValueError(f"engine file {str(path)!r} is missing")
    return path.read_text(encoding=ENCODING)


class SavedGame(BaseModel):
    # Revalidated on the way out too: a runtime `Game` validates nothing itself.
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")

    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState
    mechanics: JsonValue
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)
    pending: PendingDecision | None

    @model_validator(mode="after")
    def _the_player_is_playable(self) -> Self:
        check_player_playable(self.world)
        return self

    @classmethod
    def of(cls, state: Game) -> Self:
        return cls(
            scenario_id=state.scenario_id,
            character_id=state.character_id,
            scenario=state.scenario,
            engine=state.engine,
            world=state.world,
            mechanics=state.mechanics.model_dump(mode="json"),
            history=state.history,
            turn=state.turn,
            pending=state.pending,
        )

    def game(self, mechanics: Mutable) -> Game:
        return Game(
            scenario_id=self.scenario_id,
            character_id=self.character_id,
            scenario=self.scenario,
            engine=self.engine,
            world=self.world,
            mechanics=mechanics,
            history=self.history,
            turn=self.turn,
            pending=self.pending,
        )


@dataclass(frozen=True, slots=True)
class FileStore:
    directory: Path

    def slugs(self) -> tuple[str, ...]:
        return tuple(
            path.stem
            for path in sorted(self.directory.glob("*.json"))
            if fullmatch(_SAVE_SLUG_PATTERN, path.stem) is not None
        )

    def load(self, slug: str) -> SavedGame | None:
        path = self._save_path(slug)
        if not path.exists():
            return None
        return SavedGame.model_validate_json(path.read_text(encoding=ENCODING))

    def save(self, slug: str, saved: SavedGame) -> None:
        _write(self._save_path(slug), saved.model_dump_json(indent=2))

    def write_journal(self, slug: str, body: str) -> Path:
        path = self._journal_path(slug)
        _write(path, body)
        return path

    def media_dir(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".media")

    def discard(self, slug: str) -> None:
        self._save_path(slug).unlink(missing_ok=True)
        self._journal_path(slug).unlink(missing_ok=True)

    def _save_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".json")

    def _journal_path(self, slug: str) -> Path:
        return _safe_path(self.directory, slug, ".journal.md")


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


MIN_PASSAGE = 24
_BLANK_LINE = re.compile(r"\n\s*\n")
_LINE_BREAK_HYPHEN = re.compile(r"(\w)-\s+(\w)")


def whole_text(path: Path, max_chars: int) -> str:
    pages = (
        _pdf_pages(path) if path.suffix.lower() == ".pdf" else (path.read_text(encoding="utf-8"),)
    )
    text = "\n\n".join(passage for page in pages for passage in _passages(page))
    if not text:
        raise ValueError(f"{path.name} holds no readable text")
    if len(text) > max_chars:
        raise ValueError(
            f"{path.name} is {len(text)} characters, too large to hand to a model whole"
        )
    return text


def _pdf_pages(path: Path) -> tuple[str, ...]:
    # Layout mode interleaves columns and mangles letter-spaced display text.
    return tuple(page.extract_text() for page in PdfReader(path).pages)


def _passages(body: str) -> Iterator[str]:
    for block in _BLANK_LINE.split(body.strip()):
        text = " ".join(_LINE_BREAK_HYPHEN.sub(r"\1-\2", _unquoted(block)).split())
        # A page number or a running header is not a passage.
        if len(text) >= MIN_PASSAGE:
            yield text


def _unquoted(block: str) -> str:
    """A Markdown quote marker is punctuation around a line, not part of its text."""
    return "\n".join(line.strip().removeprefix(">").strip() for line in block.splitlines())
