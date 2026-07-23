"""The single open game. Single-player by design, so one module-level session is enough."""

from dataclasses import dataclass, field

from .. import store
from ..domain.models import GameState, Role
from ..domain.turn import Turn

SLUG = "poc"
SCENARIO = "whispering_vault"


@dataclass
class Session:
    state: GameState
    turns: list[Turn] = field(default_factory=list)  # this process only; the save holds history
    busy: bool = False
    step: Role | None = None


session = Session(state=store.load(SLUG) or store.new_game(SCENARIO))
