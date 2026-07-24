"""The single open game. Single-player by design, so one session per process is enough — but a
value with a constructor, not built at import, so the scenario picker has somewhere to put its
result."""

from dataclasses import dataclass, field
from functools import cache
from typing import Self

from .. import store
from ..domain.models import GameState, Role, Turn

SLUG = "poc"
SCENARIO = "whispering_vault"


@dataclass
class Session:
    slug: str
    scenario: str
    state: GameState
    turns: list[Turn] = field(default_factory=list)  # this process only; the save holds history
    busy: bool = False
    step: Role | None = None

    @classmethod
    def load(cls, slug: str, scenario: str) -> Self:
        return cls(slug=slug, scenario=scenario, state=store.load(slug) or store.new_game(scenario))

    def commit(self, turn: Turn) -> None:
        """The one place a turn becomes durable."""
        self.state = turn.state
        self.turns.append(turn)
        store.save(self.slug, self.state)
        store.append_trace(self.slug, turn)

    def restart(self) -> None:
        store.reset(self.slug)
        self.state, self.turns = store.new_game(self.scenario), []
        store.save(self.slug, self.state)


@cache
def current_session() -> Session:
    """Process-level, not per-client: `@ui.page` bodies run once per connection, so building a
    session there would reset the trace panel on every browser reload."""
    return Session.load(SLUG, SCENARIO)
