from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from random import Random
from textwrap import shorten

from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.base import SAVE_VERSION, AdvancementDecision, EngineId, Slug
from ..core.config import Settings
from ..core.content import Character, Scenario, authored_world
from ..core.facts import Fact
from ..core.registry import AnyEngine, build_engine
from ..core.store import (
    FileSaves,
    FileTraces,
    SaveShell,
    load_character,
    load_scenario,
    read_characters,
    read_scenarios,
)
from ..core.turn import Advance, TraceEntry, Turn
from ..core.world import EngineRules, GameState
from .pipeline import TurnOptions, TurnScript, default_cast, run_turn


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
            shell = files.shell(slug)
        except (ValidationError, ValueError) as error:
            unreadable.append(UnreadableSave(slug=slug, problem=_brief(error)))
            continue
        if shell is None:
            continue
        saves.append(_save_option(slug, shell, scenarios, characters))
    return LauncherCatalog(
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
    character = next((option for option in characters if option.id == shell.character_id), None)
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
        found = next((option for option in offered if option.id == wanted), None)
        if found is None:
            return f"{purpose} {wanted!r} is gone"
        if shell.engine not in found.engines:
            return f"{purpose} {wanted!r} no longer offers the {shell.engine!r} engine"
    return None


def _brief(error: Exception) -> str:
    """A rejected save shows a one-line reason; a full validation traceback is unreadable."""
    return shorten(str(error), width=200, placeholder=" ...")


@dataclass
class GameSession:
    target: LaunchTarget
    scenario: Scenario
    character: Character
    engine: AnyEngine
    script: TurnScript
    saves: FileSaves
    traces: FileTraces
    options: TurnOptions
    rng: Random = field(default_factory=Random)
    entries: list[TraceEntry] = field(default_factory=list)
    busy: bool = False
    step: str | None = None
    state: GameState[EngineRules] = field(init=False)

    def __post_init__(self) -> None:
        if self.engine.id != self.target.engine:
            raise ValueError(f"{self.target} was opened with the {self.engine.id!r} engine")
        shell = self.saves.shell(self.slug)
        if shell is not None and shell.engine != self.engine.id:
            raise ValueError(f"save {self.slug!r} plays {shell.engine!r}, not {self.engine.id!r}")
        saved = None if shell is None else self.saves.load(self.slug, self.engine.state_type)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(saved)
        self.entries = list(self.traces.load(self.slug))

    @property
    def slug(self) -> str:
        return self.target.slug

    @property
    def role_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.script)

    async def submit(
        self,
        prompt: str,
        on_step: Callable[[str], None] | None = None,
    ) -> Turn:
        """Commit only after the full turn succeeds."""
        result = await run_turn(
            self.state,
            prompt,
            engine=self.engine,
            script=self.script,
            options=self.options,
            rng=self.rng,
            on_step=on_step,
        )
        self._commit(result.state, result.turn)
        return result.turn

    def advance(self, decision: AdvancementDecision) -> tuple[Fact, ...]:
        transition = self.engine.advance(decision, self.state, self.rng)
        self.engine.validate_state(transition.state)
        self._commit(transition.state, Advance(facts=transition.facts))
        return transition.facts

    def advancement_available(self) -> bool:
        return self.engine.advancement_available(self.state)

    def restart(self) -> None:
        opening = self._begun()
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state = opening
        self.entries = []

    def _commit(self, state: GameState[EngineRules], entry: TraceEntry) -> None:
        self.saves.save(self.slug, state)
        self.traces.append(self.slug, entry)
        self.state = state
        self.entries.append(entry)

    def _begun(self) -> GameState[EngineRules]:
        authored = authored_world(self.scenario, self.character)
        state = self.engine.state_type(
            save_version=SAVE_VERSION,
            scenario_id=self.scenario.id,
            character_id=self.character.id,
            scenario=self.scenario.meta,
            engine=self.engine.id,
            world=self.engine.initial_world(authored, self.character.overlay.character),
        )
        self.engine.validate_state(state)
        return state

    def _resumable(self, state: GameState[EngineRules]) -> GameState[EngineRules]:
        if (state.scenario_id, state.character_id) != (self.scenario.id, self.character.id):
            raise ValueError(
                f"save is {state.scenario_id!r}/{state.character_id!r}, "
                f"selected is {self.scenario.id!r}/{self.character.id!r}"
            )
        if state.scenario != self.scenario.meta:
            raise ValueError(
                f"save scenario is {state.scenario.title!r}, "
                f"selected scenario is {self.scenario.meta.title!r}"
            )
        self.engine.validate_state(state)
        return state


@dataclass(slots=True)
class Runtime:
    """The composition root: settings, the built engines, and the games currently open."""

    config: Settings
    _engines: dict[EngineId, AnyEngine] = field(default_factory=dict, repr=False)
    _sessions: dict[str, GameSession] = field(default_factory=dict, repr=False)

    def engine(self, engine_id: EngineId) -> AnyEngine:
        """Memoised: building the 5e engine compiles the whole content pack."""
        held = self._engines.get(engine_id)
        if held is None:
            held = build_engine(engine_id, self.config)
            self._engines[engine_id] = held
        return held

    def session(self, target: LaunchTarget) -> GameSession:
        """Memoised: a page render must not rebuild the game and drop the turn in flight."""
        held = self._sessions.get(target.slug)
        if held is not None:
            if held.target != target:
                raise ValueError(f"open session {target.slug!r} plays {held.target}, not {target}")
            return held
        opened = self._open(target)
        self._sessions[target.slug] = opened
        return opened

    def _open(self, target: LaunchTarget) -> GameSession:
        config = self.config
        engine = self.engine(target.engine)
        options = TurnOptions(
            history_window=config.history_window,
            max_growth=config.max_growth,
        )
        return GameSession(
            target=target,
            scenario=load_scenario(config.scenarios_dir, target.scenario_id, target.engine),
            character=load_character(config.characters_dir, target.character_id, target.engine),
            engine=engine,
            script=default_cast(engine, config).script(engine, options),
            saves=FileSaves(config.saves_dir),
            traces=FileTraces(config.saves_dir),
            options=options,
        )
