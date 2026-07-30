from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, ValidationError

from ..config import Settings
from ..domain.definitions import CharacterDefinition, ScenarioDefinition
from ..domain.engine import EngineRef, EngineStamp
from ..domain.state import GameState
from ..store import FileSaves, read_characters, read_scenarios
from .compatibility import save_mismatches, stamp_mismatches

type EngineStampLookup = Callable[[EngineRef], EngineStamp]


class LauncherModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ScenarioOption(LauncherModel):
    name: str
    title: str
    premise: str
    engine: EngineRef


class CharacterOption(LauncherModel):
    name: str
    title: str
    brief: str
    engine: EngineRef


class SaveOption(LauncherModel):
    slug: str
    scenario_title: str
    character_title: str
    engine: EngineRef
    turn: int
    scenario_name: str | None
    character_name: str | None
    problem: str | None = None

    @property
    def resumable(self) -> bool:
        return (
            self.problem is None
            and self.scenario_name is not None
            and self.character_name is not None
        )


class UnreadableSave(LauncherModel):
    slug: str
    problem: str


class LauncherCatalog(LauncherModel):
    scenarios: tuple[ScenarioOption, ...]
    characters: tuple[CharacterOption, ...]
    saves: tuple[SaveOption, ...]
    unreadable: tuple[UnreadableSave, ...] = ()

    def scenario(self, name: str) -> ScenarioOption:
        found = next((option for option in self.scenarios if option.name == name), None)
        if found is None:
            raise ValueError(f"unknown scenario {name!r}")
        return found

    def character(self, name: str) -> CharacterOption:
        found = next((option for option in self.characters if option.name == name), None)
        if found is None:
            raise ValueError(f"unknown character {name!r}")
        return found

    def compatible_characters(self, scenario_name: str) -> tuple[CharacterOption, ...]:
        engine = self.scenario(scenario_name).engine
        return tuple(character for character in self.characters if character.engine == engine)

    def save(self, slug: str) -> SaveOption:
        found = next((option for option in self.saves if option.slug == slug), None)
        if found is None:
            raise ValueError(f"unknown save {slug!r}")
        return found


class LaunchTarget(LauncherModel):
    slug: str
    scenario_name: str
    character_name: str

    @property
    def path(self) -> str:
        return f"/game/{self.slug}/{self.scenario_name}/{self.character_name}"


@dataclass(slots=True)
class LauncherController:
    catalog: LauncherCatalog
    selected_scenario: str | None = None
    selected_character: str | None = None

    def __post_init__(self) -> None:
        if self.selected_scenario is None and self.catalog.scenarios:
            self.selected_scenario = self.catalog.scenarios[0].name
        self._select_first_compatible_character()

    def choose_scenario(self, name: str) -> None:
        self.catalog.scenario(name)
        self.selected_scenario = name
        compatible = self.compatible_characters()
        if self.selected_character not in {character.name for character in compatible}:
            self.selected_character = compatible[0].name if compatible else None

    def choose_character(self, name: str) -> None:
        if name not in {character.name for character in self.compatible_characters()}:
            raise ValueError(
                f"character {name!r} is not compatible with scenario {self.selected_scenario!r}"
            )
        self.selected_character = name

    def compatible_characters(self) -> tuple[CharacterOption, ...]:
        if self.selected_scenario is None:
            return ()
        return self.catalog.compatible_characters(self.selected_scenario)

    def new_game(self) -> LaunchTarget:
        if self.selected_scenario is None or self.selected_character is None:
            raise ValueError("choose a scenario and compatible character")
        return LaunchTarget(
            slug=f"{self.selected_scenario}--{self.selected_character}",
            scenario_name=self.selected_scenario,
            character_name=self.selected_character,
        )

    def resume(self, slug: str) -> LaunchTarget:
        saved = self.catalog.save(slug)
        if saved.problem is not None or saved.scenario_name is None or saved.character_name is None:
            raise ValueError(saved.problem or f"save {slug!r} cannot be resumed")
        return LaunchTarget(
            slug=saved.slug,
            scenario_name=saved.scenario_name,
            character_name=saved.character_name,
        )

    def _select_first_compatible_character(self) -> None:
        compatible = self.compatible_characters()
        self.selected_character = compatible[0].name if compatible else None


def load_catalog(config: Settings, installed_stamp: EngineStampLookup) -> LauncherCatalog:
    scenarios = read_scenarios(config.scenarios_dir)
    characters = read_characters(config.characters_dir)
    scenario_options = tuple(
        ScenarioOption(
            name=name,
            title=definition.meta.title,
            premise=definition.meta.premise,
            engine=definition.engine,
        )
        for name, definition in scenarios.items()
    )
    character_options = tuple(
        CharacterOption(
            name=name,
            title=definition.name,
            brief=definition.brief,
            engine=definition.engine,
        )
        for name, definition in characters.items()
    )
    files = FileSaves(config.saves_dir)
    saves: list[SaveOption] = []
    unreadable: list[UnreadableSave] = []
    for slug in files.slugs():
        try:
            state = files.load(slug)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=str(error)))
            continue
        if state is None:
            continue
        saves.append(
            _save_option(
                slug,
                state,
                scenarios,
                characters,
                installed_stamp,
            )
        )
    return LauncherCatalog(
        scenarios=scenario_options,
        characters=character_options,
        saves=tuple(saves),
        unreadable=tuple(unreadable),
    )


def _save_option(
    slug: str,
    state: GameState,
    scenarios: Mapping[str, ScenarioDefinition],
    characters: Mapping[str, CharacterDefinition],
    installed_stamp: EngineStampLookup,
) -> SaveOption:
    engine = EngineRef(
        id=state.engine.id,
        rules_version=state.engine.rules_version,
    )
    scenario_names = [
        name
        for name, definition in scenarios.items()
        if definition.engine == engine and definition.meta == state.scenario
    ]
    character_names = [
        name
        for name, definition in characters.items()
        if definition.engine == engine
        and definition.name == state.player.name
        and definition.brief == state.player.brief
    ]
    problems: list[str] = []
    if len(scenario_names) != 1:
        problems.append(f"matched {len(scenario_names)} scenarios")
    if len(character_names) != 1:
        problems.append(f"matched {len(character_names)} characters")
    if len(scenario_names) == 1 and len(character_names) == 1:
        problems.extend(
            save_mismatches(
                state,
                scenarios[scenario_names[0]],
                characters[character_names[0]],
            )
        )
        try:
            stamp = installed_stamp(scenarios[scenario_names[0]].engine)
        except ValueError as error:
            problems.append(str(error))
        else:
            problems.extend(stamp_mismatches(state, stamp))
    return SaveOption(
        slug=slug,
        scenario_title=state.scenario.title,
        character_title=state.player.name,
        engine=engine,
        turn=state.turn,
        scenario_name=scenario_names[0] if len(scenario_names) == 1 else None,
        character_name=character_names[0] if len(character_names) == 1 else None,
        problem="; ".join(problems) or None,
    )
