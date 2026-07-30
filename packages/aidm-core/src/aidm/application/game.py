from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from pydantic import BaseModel

from ..agents.context import DirectorScene
from ..agents.stages import SharedStages, Stage
from ..domain.base import Role
from ..domain.definitions import (
    CharacterDefinition,
    ScenarioDefinition,
    validate_definition_engines,
)
from ..domain.events import Event
from ..domain.reducer import apply
from ..domain.state import (
    GameState,
    attach_initial_rules,
    world_from_definitions,
)
from ..domain.turn import Turn
from ..engine_api.contracts import AdvancementEngine, AdvancementStatus, RulesEngine
from ..pipeline import TurnOptions, run_turn
from .compatibility import save_mismatches, stamp_mismatches
from .ports import SaveRepository, TraceSink


@dataclass
class GameApplication:
    slug: str
    scenario: ScenarioDefinition
    character: CharacterDefinition
    engine: RulesEngine
    director: Stage[DirectorScene, BaseModel]
    stages: SharedStages
    saves: SaveRepository
    traces: TraceSink
    options: TurnOptions
    rng: Random = field(default_factory=Random)
    turns: list[Turn] = field(default_factory=list)
    state: GameState = field(init=False)

    def __post_init__(self) -> None:
        validate_definition_engines(self.scenario, self.character, self.engine.stamp)
        saved = self.saves.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(saved)
        self.turns = list(self.traces.load(self.slug))

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
        self.turns.append(turn)
        self.saves.save(self.slug, self.state)
        self.traces.append(self.slug, turn)
        return turn

    def advancement_available(self) -> bool:
        advancement = self.engine.advancement
        return advancement is not None and advancement.available(self.state)

    def advancement_status(self) -> AdvancementStatus:
        return self._advancement().status(self.state)

    def advancement_preview(self) -> BaseModel:
        advancement = self._advancement()
        if not advancement.available(self.state):
            raise ValueError("no advancement is available")
        return advancement.preview(self.state)

    def advancement_plan(self, decisions: BaseModel) -> BaseModel:
        advancement = self._advancement()
        if not advancement.available(self.state):
            raise ValueError("no advancement is available")
        return advancement.plan(self.state, decisions)

    def advance(self, decisions: BaseModel) -> tuple[Event, ...]:
        advancement = self._advancement()
        if not advancement.available(self.state):
            raise ValueError("no advancement is available")
        events = advancement.advance(self.state, decisions, self.rng)
        self.state = apply(self.state, events, self.engine.rules)
        self.saves.save(self.slug, self.state)
        return tuple(events)

    def restart(self) -> None:
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state = self._begun()
        self.turns = []

    def _begun(self) -> GameState:
        world = world_from_definitions(self.scenario, self.character)
        initialized = self.engine.lifecycle.initialise(
            world,
            self.scenario,
            self.character,
        )
        state = GameState(
            engine=self.engine.stamp,
            scenario=self.scenario.meta,
            world=attach_initial_rules(
                world,
                initialized.entity_rules,
                self.engine.stamp,
            ),
            rules=initialized.game_rules,
        )
        self.engine.rules.validate_state(state)
        return state

    def _resumable(self, state: GameState) -> GameState:
        problems = (
            *save_mismatches(state, self.scenario, self.character),
            *stamp_mismatches(state, self.engine.stamp),
        )
        if problems:
            raise ValueError("; ".join(problems))
        self.engine.rules.validate_state(state)
        return state

    def _advancement(self) -> AdvancementEngine:
        advancement = self.engine.advancement
        if advancement is None:
            raise ValueError(f"engine {self.engine.stamp.id!r} has no advancement")
        return advancement
