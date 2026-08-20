from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from textwrap import shorten
from typing import Protocol

from pydantic import ValidationError

from aidm.app.registry import ENGINES, engine_class
from aidm.config import Settings
from aidm.content.store import FileStore, SaveShell, read_characters, read_scenarios
from aidm.state.base import EngineId, Frozen, Slug


def as_engine_id(value: str) -> EngineId:
    """Narrow a routed string, so an unknown engine cannot reach a filename downstream."""
    return engine_class(EngineId(value)).id


class _Identified(Protocol):
    @property
    def id(self) -> str: ...


def _one[T: _Identified](options: Iterable[T], wanted: str) -> T | None:
    return next((option for option in options if option.id == wanted), None)


class EngineOption(Frozen):
    id: EngineId
    badge: tuple[str, str]


class ContentOption(Frozen):
    id: Slug
    title: str
    subtitle: str
    engines: tuple[EngineId, ...]


class SaveOption(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug
    engine: EngineId
    scenario_title: str
    character_title: str
    turn: int
    problem: str | None = None

    @property
    def resumable(self) -> bool:
        return self.problem is None


class UnreadableSave(Frozen):
    slug: str
    problem: str


class LauncherCatalog(Frozen):
    engines: tuple[EngineOption, ...]
    scenarios: tuple[ContentOption, ...]
    characters: tuple[ContentOption, ...]
    saves: tuple[SaveOption, ...]
    unreadable: tuple[UnreadableSave, ...] = ()

    def badge(self, engine: EngineId) -> tuple[str, str]:
        found = _one(self.engines, engine)
        if found is None:
            raise ValueError(f"unknown engine {engine!r}")
        return found.badge

    def scenario(self, scenario_id: Slug) -> ContentOption:
        found = _one(self.scenarios, scenario_id)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[ContentOption, ...]:
        """A character is playable under any engine it ships an overlay for."""
        return tuple(option for option in self.characters if engine in option.engines)

    def save(self, slug: str) -> SaveOption:
        found = next((option for option in self.saves if option.slug == slug), None)
        if found is None:
            raise ValueError(f"unknown save {slug!r}")
        return found


class LaunchTarget(Frozen):
    slug: str
    scenario_id: Slug
    character_id: Slug
    engine: EngineId

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_id}/{self.character_id}/{self.engine}"

    def __str__(self) -> str:
        return f"{self.scenario_id}/{self.character_id} under {self.engine}"


@dataclass(slots=True)
class LauncherController:
    catalog: LauncherCatalog
    selected_scenario: Slug | None = None
    selected_engine: EngineId | None = None
    selected_character: Slug | None = None

    def __post_init__(self) -> None:
        if self.selected_scenario is None and self.catalog.scenarios:
            self.selected_scenario = self.catalog.scenarios[0].id
        self._select_engine()

    def choose_scenario(self, scenario_id: Slug) -> None:
        self.catalog.scenario(scenario_id)
        self.selected_scenario = scenario_id
        self._select_engine()

    def choose_engine(self, engine: EngineId) -> None:
        if engine not in self.available_engines():
            raise ValueError(
                f"scenario {self.selected_scenario!r} has no {engine!r} rules written for it"
            )
        self.selected_engine = engine
        self._select_character()

    def choose_character(self, character_id: Slug) -> None:
        if character_id not in {option.id for option in self.compatible_characters()}:
            raise ValueError(
                f"character {character_id!r} has no {self.selected_engine!r} rules written for it"
            )
        self.selected_character = character_id

    def available_engines(self) -> tuple[EngineId, ...]:
        if self.selected_scenario is None:
            return ()
        return self.catalog.scenario(self.selected_scenario).engines

    def compatible_characters(self) -> tuple[ContentOption, ...]:
        if self.selected_engine is None:
            return ()
        return self.catalog.characters_for(self.selected_engine)

    def new_game(self) -> LaunchTarget:
        scenario, engine, character = (
            self.selected_scenario,
            self.selected_engine,
            self.selected_character,
        )
        if scenario is None or engine is None or character is None:
            raise ValueError("choose a scenario, its rules, and a character written for them")
        return LaunchTarget(
            slug=f"{scenario}--{character}--{engine}",
            scenario_id=scenario,
            character_id=character,
            engine=engine,
        )

    def resume(self, slug: str) -> LaunchTarget:
        saved = self.catalog.save(slug)
        if saved.problem is not None:
            raise ValueError(saved.problem)
        return LaunchTarget(
            slug=saved.slug,
            scenario_id=saved.scenario_id,
            character_id=saved.character_id,
            engine=saved.engine,
        )

    def _select_engine(self) -> None:
        engines = self.available_engines()
        if self.selected_engine not in engines:
            self.selected_engine = engines[0] if engines else None
        self._select_character()

    def _select_character(self) -> None:
        compatible = self.compatible_characters()
        if self.selected_character not in {option.id for option in compatible}:
            self.selected_character = compatible[0].id if compatible else None


def load_catalog(config: Settings) -> LauncherCatalog:
    engine_options = tuple(EngineOption(id=engine.id, badge=engine.badge) for engine in ENGINES)
    engine_ids = tuple(option.id for option in engine_options)
    scenarios = tuple(
        ContentOption(
            id=name, title=scenario.meta.title, subtitle=scenario.meta.premise, engines=engine_ids
        )
        for name, scenario in read_scenarios(config.scenarios_dir)
    )
    characters = tuple(
        ContentOption(id=name, title=profile.name, subtitle=profile.brief, engines=engines)
        for name, profile, engines in read_characters(config.characters_dir, engine_ids)
    )
    files = FileStore(config.saves_dir)
    saves: list[SaveOption] = []
    unreadable: list[UnreadableSave] = []
    for slug in files.slugs():
        try:
            shell = files.shell(slug)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=_brief(error)))
            continue
        if shell is None:
            continue
        saves.append(_save_option(slug, shell, scenarios, characters))
    return LauncherCatalog(
        engines=engine_options,
        scenarios=scenarios,
        characters=characters,
        saves=tuple(saves),
        unreadable=tuple(unreadable),
    )


def _save_option(
    slug: str,
    shell: SaveShell,
    scenarios: Sequence[ContentOption],
    characters: Sequence[ContentOption],
) -> SaveOption:
    character = _one(characters, shell.character_id)
    return SaveOption(
        slug=slug,
        scenario_id=shell.scenario_id,
        character_id=shell.character_id,
        engine=shell.engine,
        scenario_title=shell.scenario.title,
        character_title=shell.character_id if character is None else character.title,
        turn=shell.turn,
        problem=_unplayable_reason(shell, scenarios, characters),
    )


def _unplayable_reason(
    shell: SaveShell,
    scenarios: Sequence[ContentOption],
    characters: Sequence[ContentOption],
) -> str | None:
    """A save names its own origin, so the only question left is whether that origin still plays."""
    for purpose, wanted, offered in (
        ("scenario", shell.scenario_id, scenarios),
        ("character", shell.character_id, characters),
    ):
        found = _one(offered, wanted)
        if found is None:
            return f"{purpose} {wanted!r} is gone"
        if shell.engine not in found.engines:
            return f"{purpose} {wanted!r} no longer offers the {shell.engine!r} engine"
    return None


def _brief(error: Exception) -> str:
    """A rejected save shows a one-line reason; a full validation traceback is unreadable."""
    return shorten(str(error), width=200, placeholder=" ...")
