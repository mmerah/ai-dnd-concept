from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from pydantic import BaseModel

from ..agents.stages import DirectorStage, SharedStages
from ..domain.advancement import AdvancementStatus
from ..domain.base import SAVE_VERSION, Role
from ..domain.definitions import (
    CharacterDefinition,
    ScenarioDefinition,
    validate_definition_engines,
)
from ..domain.state import GameState, world_from_definitions
from ..domain.transition import Fact
from ..domain.turn import Advance, TraceEntry, Turn
from ..engines import Advancement, Engine
from ..pipeline import TurnOptions, run_turn
from .ports import SaveRepository, TraceSink


@dataclass
class GameApplication:
    slug: str
    scenario: ScenarioDefinition
    character: CharacterDefinition
    engine: Engine
    director: DirectorStage
    stages: SharedStages
    saves: SaveRepository
    traces: TraceSink
    options: TurnOptions
    rng: Random = field(default_factory=Random)
    entries: list[TraceEntry] = field(default_factory=list)
    state: GameState = field(init=False)

    def __post_init__(self) -> None:
        validate_definition_engines(self.scenario, self.character, self.engine.id)
        saved = self.saves.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(saved)
        self.entries = list(self.traces.load(self.slug))

    async def submit(
        self,
        prompt: str,
        on_step: Callable[[Role], None] | None = None,
    ) -> Turn:
        """Commit only after the full turn succeeds."""
        turn = await run_turn(
            self.state,
            prompt,
            engine=self.engine,
            director=self.director,
            stages=self.stages,
            options=self.options,
            rng=self.rng,
            on_step=on_step,
        )
        self.state = turn.state
        self.entries.append(turn)
        self.saves.save(self.slug, self.state)
        self.traces.append(self.slug, turn)
        return turn

    def advancement_available(self) -> bool:
        return self.engine.advancement.available(self.state)

    def advancement_status(self) -> AdvancementStatus:
        return self.engine.advancement.status(self.state)

    def advancement_preview(self) -> BaseModel:
        return self._advancement().preview(self.state)

    def advancement_plan(self, decisions: BaseModel) -> BaseModel:
        return self._advancement().plan(self.state, decisions)

    def advance(self, decisions: BaseModel) -> tuple[Fact, ...]:
        transition = self._advancement().advance(self.state, decisions, self.rng)
        self.engine.rules.validate_state(transition.state)
        self.state = transition.state
        entry = Advance(facts=transition.facts, state=self.state)
        self.entries.append(entry)
        self.saves.save(self.slug, self.state)
        self.traces.append(self.slug, entry)
        return transition.facts

    def restart(self) -> None:
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state = self._begun()
        self.entries = []

    def _begun(self) -> GameState:
        authored = world_from_definitions(self.scenario, self.character)
        state = GameState(
            save_version=SAVE_VERSION,
            scenario=self.scenario.meta,
            world=authored.world,
            engine=self.engine.lifecycle.initialise(authored, self.character.engine_data),
        )
        self.engine.rules.validate_state(state)
        return state

    def _resumable(self, state: GameState) -> GameState:
        if state.scenario != self.scenario.meta:
            raise ValueError(
                f"save scenario is {state.scenario.title!r}, "
                f"selected scenario is {self.scenario.meta.title!r}"
            )
        if (state.player.name, state.player.brief) != (self.character.name, self.character.brief):
            raise ValueError(
                f"save player is {state.player.name!r}, "
                f"selected character is {self.character.name!r}"
            )
        self.engine.rules.validate_state(state)
        return state

    def _advancement(self) -> Advancement:
        if not self.advancement_available():
            raise ValueError("no advancement is available")
        return self.engine.advancement
