from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from random import Random

from ..content.records.character import ProgressionChoice
from ..domain.models.base import Role
from ..domain.models.events import Event
from ..domain.models.progression import MAX_LEVEL, Decisions
from ..domain.models.state import CharacterSheet, GameState, ScenarioDef
from ..domain.models.turn import Turn
from ..domain.reducer import apply
from ..engine import campaign, progression
from ..engine.ruleset import Ruleset
from ..pipeline import TurnOptions, run_turn
from .ports import SaveRepository, TraceSink


@dataclass
class GameApplication:
    slug: str
    scenario: ScenarioDef
    sheet: CharacterSheet
    ruleset: Ruleset
    saves: SaveRepository
    traces: TraceSink
    options: TurnOptions
    rng: Random = field(default_factory=Random)  # shared so seeded games replay across level-ups
    turns: list[Turn] = field(default_factory=list)
    state: GameState = field(init=False)

    def __post_init__(self) -> None:
        saved = self.saves.load(self.slug)
        stamps = self.ruleset.stamps
        self.state = self._begun() if saved is None else campaign.resumable(saved, stamps)

    async def submit(self, prompt: str, on_step: Callable[[Role], None] | None = None) -> Turn:
        """Commit only after the full turn succeeds."""
        turn = await run_turn(
            self.state,
            prompt,
            on_step,
            ruleset=self.ruleset,
            options=self.options,
            rng=self.rng,
        )
        self.state = turn.state
        self.turns.append(turn)
        self.saves.save(self.slug, self.state)
        self.traces.append(self.slug, turn)
        return turn

    def pending_choices(self) -> list[ProgressionChoice]:
        current = self.state.player.progression
        if current is None or current.level >= MAX_LEVEL:
            return []
        return progression.pending(current.origin, current.level + 1, self.ruleset)

    def advance(self, decisions: Decisions) -> None:
        self._record(progression.advance(self.state.player, decisions, self.ruleset, self.rng))

    def restart(self) -> None:
        """Discard the trace with the save to avoid mixing games."""
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state, self.turns = self._begun(), []
        self.saves.save(self.slug, self.state)

    def _begun(self) -> GameState:
        return campaign.begin(self.scenario, self.sheet, self.ruleset)

    def _record(self, events: Sequence[Event]) -> None:
        self.state = apply(self.state, events)
        self.saves.save(self.slug, self.state)
