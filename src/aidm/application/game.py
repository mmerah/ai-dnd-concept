from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from ..agents.stages import DirectorStage, SharedStages
from ..domain.base import SAVE_VERSION, Role
from ..domain.definitions import Character, Scenario
from ..domain.state import GameState, authored_world
from ..domain.transition import Fact
from ..domain.turn import Advance, TraceEntry, Turn
from ..engines import AdvancementDecision, Engine, resolve_advancement
from ..pipeline import TurnOptions, run_turn
from .ports import SaveRepository, TraceSink


@dataclass
class GameApplication:
    slug: str
    scenario: Scenario
    character: Character
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

    def advance(self, decision: AdvancementDecision) -> tuple[Fact, ...]:
        transition = resolve_advancement(self.engine, decision, self.state, self.rng)
        self.engine.rules.validate_state(transition.state)
        self.state = transition.state
        entry = Advance(facts=transition.facts, state=self.state)
        self.entries.append(entry)
        self.saves.save(self.slug, self.state)
        self.traces.append(self.slug, entry)
        return transition.facts

    def advancement_available(self) -> bool:
        return self.engine.advancement.available(self.state)

    def restart(self) -> None:
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state = self._begun()
        self.entries = []

    def _begun(self) -> GameState:
        authored = authored_world(self.scenario, self.character)
        state = GameState(
            save_version=SAVE_VERSION,
            scenario_id=self.scenario.id,
            character_id=self.character.id,
            scenario=self.scenario.meta,
            world=authored.world,
            engine=self.engine.lifecycle.initialise(authored, self.character.overlay.character),
        )
        self.engine.rules.validate_state(state)
        return state

    def _resumable(self, state: GameState) -> GameState:
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
        self.engine.rules.validate_state(state)
        return state
