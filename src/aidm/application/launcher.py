from collections.abc import Sequence
from dataclasses import dataclass
from textwrap import shorten

from pydantic import BaseModel, ConfigDict, ValidationError

from ..config import Settings
from ..domain.base import EngineId, Slug
from ..domain.state import GameState
from ..store import FileSaves, read_characters, read_scenarios


class LauncherModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ContentOption(LauncherModel):
    id: Slug
    title: str
    engines: tuple[EngineId, ...]


class ScenarioOption(ContentOption):
    premise: str


class CharacterOption(ContentOption):
    brief: str


class SaveOption(LauncherModel):
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


class UnreadableSave(LauncherModel):
    slug: str
    problem: str


class LauncherCatalog(LauncherModel):
    scenarios: tuple[ScenarioOption, ...]
    characters: tuple[CharacterOption, ...]
    saves: tuple[SaveOption, ...]
    unreadable: tuple[UnreadableSave, ...] = ()

    def scenario(self, scenario_id: Slug) -> ScenarioOption:
        found = next((option for option in self.scenarios if option.id == scenario_id), None)
        if found is None:
            raise ValueError(f"unknown scenario {scenario_id!r}")
        return found

    def characters_for(self, engine: EngineId) -> tuple[CharacterOption, ...]:
        """A character is playable under any engine it ships an overlay for."""
        return tuple(option for option in self.characters if engine in option.engines)

    def save(self, slug: str) -> SaveOption:
        found = next((option for option in self.saves if option.slug == slug), None)
        if found is None:
            raise ValueError(f"unknown save {slug!r}")
        return found


class LaunchTarget(LauncherModel):
    slug: str
    scenario_id: Slug
    character_id: Slug
    engine: EngineId

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_id}/{self.character_id}/{self.engine}"


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
                f"character {character_id!r} has no {self.selected_engine!r} sheet written for it"
            )
        self.selected_character = character_id

    def available_engines(self) -> tuple[EngineId, ...]:
        if self.selected_scenario is None:
            return ()
        return self.catalog.scenario(self.selected_scenario).engines

    def compatible_characters(self) -> tuple[CharacterOption, ...]:
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
    scenarios = tuple(
        ScenarioOption(id=name, title=world.meta.title, premise=world.meta.premise, engines=engines)
        for name, world, engines in read_scenarios(config.scenarios_dir)
    )
    characters = tuple(
        CharacterOption(id=name, title=profile.name, brief=profile.brief, engines=engines)
        for name, profile, engines in read_characters(config.characters_dir)
    )
    files = FileSaves(config.saves_dir)
    saves: list[SaveOption] = []
    unreadable: list[UnreadableSave] = []
    for slug in files.slugs():
        try:
            state = files.load(slug)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=_brief(error)))
            continue
        if state is None:
            continue
        saves.append(_save_option(slug, state, scenarios, characters))
    return LauncherCatalog(
        scenarios=scenarios,
        characters=characters,
        saves=tuple(saves),
        unreadable=tuple(unreadable),
    )


def _save_option(
    slug: str,
    state: GameState,
    scenarios: Sequence[ContentOption],
    characters: Sequence[ContentOption],
) -> SaveOption:
    return SaveOption(
        slug=slug,
        scenario_id=state.scenario_id,
        character_id=state.character_id,
        engine=state.engine_id,
        scenario_title=state.scenario.title,
        character_title=state.player.name,
        turn=state.turn,
        problem=_unplayable_reason(state, scenarios, characters),
    )


def _unplayable_reason(
    state: GameState,
    scenarios: Sequence[ContentOption],
    characters: Sequence[ContentOption],
) -> str | None:
    """A save names its own origin, so the only question left is whether that origin still plays."""
    for purpose, wanted, offered in (
        ("scenario", state.scenario_id, scenarios),
        ("character", state.character_id, characters),
    ):
        found = next((option for option in offered if option.id == wanted), None)
        if found is None:
            return f"{purpose} {wanted!r} is gone"
        if state.engine_id not in found.engines:
            return f"{purpose} {wanted!r} no longer offers the {state.engine_id!r} engine"
    return None


def _brief(error: Exception) -> str:
    """A rejected save shows a one-line reason; a full validation traceback is unreadable."""
    return shorten(str(error), width=200, placeholder=" ...")
