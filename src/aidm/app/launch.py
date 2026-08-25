from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from textwrap import shorten
from typing import Protocol

from pydantic import ValidationError

from aidm.config import Settings
from aidm.content.io import FileStore, SavedGame, read_characters, read_scenarios
from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.state.entities import PLAYER_ID, EngineId, Entity, Frozen, Slug
from aidm.state.model import Game

ENGINES: tuple[type[Engine], ...] = (Loner3eEngine, TwentyfourxxEngine)


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in ENGINES)


def engine_class(engine_id: EngineId) -> type[Engine]:
    found = next((engine for engine in ENGINES if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def build_engine(engine_id: EngineId, extra_packs: Path | None = None) -> Engine:
    return engine_class(engine_id)(extra_packs)


def begin_game(engine: Engine, scenario_id: Slug, scenario: Scenario, character: Character) -> Game:
    """One opening state, so the app, the evals, and the tests all start a game the same way."""
    # Loaded content outlives the mutable game state, which restart() rebuilds from it.
    world = scenario.world.model_copy(deep=True)
    player = Entity(
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        parent_id=scenario.starting_location_id,
        traits=list(character.profile.traits),
    )
    for entity in (*(item.model_copy(deep=True) for item in character.profile.items), player):
        if world.find(entity.id) is not None:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        world.entities.append(entity)
    state = Game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        world=world,
        mechanics=engine.opening_mechanics(world, character.rules),
    )
    engine.validate(state)
    # The world was composed here by hand, so the commit is the only thing that validates it.
    return state.committed()


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


class CatalogEntry(Frozen):
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
    scenarios: tuple[CatalogEntry, ...]
    characters: tuple[CatalogEntry, ...]
    saves: tuple[SaveOption, ...]
    unreadable: tuple[UnreadableSave, ...] = ()

    def badge(self, engine: EngineId) -> tuple[str, str]:
        found = _one(self.engines, engine)
        if found is None:
            raise ValueError(f"unknown engine {engine!r}")
        return found.badge

    def scenario(self, scenario_id: Slug) -> CatalogEntry:
        found = _one(self.scenarios, scenario_id)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CatalogEntry, ...]:
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

    def compatible_characters(self) -> tuple[CatalogEntry, ...]:
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


def load_catalog(settings: Settings) -> LauncherCatalog:
    engine_options = tuple(EngineOption(id=engine.id, badge=engine.badge) for engine in ENGINES)
    engine_ids = tuple(option.id for option in engine_options)
    scenarios = tuple(
        CatalogEntry(
            id=name, title=scenario.meta.title, subtitle=scenario.meta.premise, engines=playable
        )
        for name, scenario, playable in read_scenarios(settings.scenarios_dir, engine_ids)
    )
    characters = tuple(
        CatalogEntry(id=name, title=profile.name, subtitle=profile.brief, engines=engines)
        for name, profile, engines in read_characters(settings.characters_dir, engine_ids)
    )
    files = FileStore(settings.saves_dir)
    saves: list[SaveOption] = []
    unreadable: list[UnreadableSave] = []
    for slug in files.slugs():
        try:
            saved = files.load(slug)
            if saved is None:
                continue
            # An installed engine's mechanics must still parse, or /game would crash on resume.
            if saved.engine in engine_ids:
                engine_class(saved.engine).mechanics_type.model_validate(saved.mechanics)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=_short_reason(error)))
            continue
        saves.append(_save_option(slug, saved, scenarios, characters))
    return LauncherCatalog(
        engines=engine_options,
        scenarios=scenarios,
        characters=characters,
        saves=tuple(saves),
        unreadable=tuple(unreadable),
    )


def _save_option(
    slug: str,
    saved: SavedGame,
    scenarios: Sequence[CatalogEntry],
    characters: Sequence[CatalogEntry],
) -> SaveOption:
    character = _one(characters, saved.character_id)
    return SaveOption(
        slug=slug,
        scenario_id=saved.scenario_id,
        character_id=saved.character_id,
        engine=saved.engine,
        scenario_title=saved.scenario.title,
        character_title=saved.character_id if character is None else character.title,
        turn=saved.turn,
        problem=_save_refusal(saved, scenarios, characters),
    )


def _save_refusal(
    saved: SavedGame,
    scenarios: Sequence[CatalogEntry],
    characters: Sequence[CatalogEntry],
) -> str | None:
    """A save names its own origin, so the only question left is whether that origin still plays."""
    for purpose, wanted, offered in (
        ("scenario", saved.scenario_id, scenarios),
        ("character", saved.character_id, characters),
    ):
        found = _one(offered, wanted)
        if found is None:
            return f"{purpose} {wanted!r} is gone"
        if saved.engine not in found.engines:
            return f"{purpose} {wanted!r} no longer offers the {saved.engine!r} engine"
    return None


SHORT_REASON_WIDTH = 200


def _short_reason(error: Exception) -> str:
    """A rejected save shows a one-line reason; a full validation traceback is unreadable."""
    return shorten(str(error), width=SHORT_REASON_WIDTH, placeholder=" ...")
