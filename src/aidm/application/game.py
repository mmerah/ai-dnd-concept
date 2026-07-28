"""One open game, and the three things that can be done to it: submit a turn, take a level, restart.

No NiceGUI, no filesystem, no globals — every collaborator is a field, so the core runs from a
script and a test can hand it an in-memory repository. What a front end adds on top is presentation
only: which role is working, whether a turn is in flight, how a choice is rendered.

This is also the only place a turn becomes durable, which is what keeps a half-applied turn
unrepresentable: `run_turn` either returns a whole one or raises, leaving the state untouched."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from random import Random

from ..content import Library
from ..content.records import ProgressionChoice
from ..domain.models import (
    MAX_LEVEL,
    CharacterSheet,
    Decisions,
    Event,
    GameState,
    Role,
    ScenarioDef,
    Turn,
)
from ..domain.reducer import apply
from ..engine import campaign, progression
from ..engine.ruleset import Ruleset
from ..pipeline import TurnOptions, run_turn
from .ports import SaveRepository, TraceSink


@dataclass
class GameApplication:
    """Mutable, because a turn advances it; nothing it depends on is.

    `library` is here alongside `ruleset` because the role prompts still render records — see
    `agents/views.py`. Every rule reads `ruleset`."""

    slug: str
    scenario: ScenarioDef
    sheet: CharacterSheet
    library: Library
    ruleset: Ruleset
    saves: SaveRepository
    traces: TraceSink
    options: TurnOptions
    # One stream for every roll this game makes, turns and level-ups alike, so a seeded game replays
    # identically.
    rng: Random = field(default_factory=Random)
    turns: list[Turn] = field(default_factory=list)  # this process only; the save holds the history
    state: GameState = field(init=False)

    def __post_init__(self) -> None:
        """The save is read here because there is no application without a state: one that had to be
        opened after construction could be used before it was."""
        saved = self.saves.load(self.slug)
        stamps = self.library.stamps
        self.state = self._begun() if saved is None else campaign.resumable(saved, stamps)

    async def submit(self, prompt: str, on_step: Callable[[Role], None] | None = None) -> Turn:
        """One whole turn, committed. Raises on any role failure, leaving the game untouched."""
        turn = await run_turn(
            self.state,
            prompt,
            on_step,
            library=self.library,
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
        """What reaching the next level asks the player to decide — nothing at all when there is no
        next level to reach, which is a character with no class or one already at the last."""
        current = self.state.player.progression
        if current is None or current.level >= MAX_LEVEL:
            return []
        return progression.pending(current.origin, current.level + 1, self.ruleset)

    def advance(self, decisions: Decisions) -> None:
        """A level, taken. No role runs, so there is nothing to trace — but the state still becomes
        durable through the one place that does that."""
        self._record(progression.advance(self.state.player, decisions, self.ruleset, self.rng))

    def restart(self) -> None:
        """The save and the trace go together: a new game keeping the old trace would open with
        someone else's history in the panel."""
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state, self.turns = self._begun(), []
        self.saves.save(self.slug, self.state)

    def _begun(self) -> GameState:
        return campaign.begin(self.scenario, self.sheet, self.ruleset, self.library.stamps)

    def _record(self, events: Sequence[Event]) -> None:
        self.state = apply(self.state, events)
        self.saves.save(self.slug, self.state)
