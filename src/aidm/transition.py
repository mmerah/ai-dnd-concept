from dataclasses import dataclass

from .facts import Fact
from .world import GameState


@dataclass(frozen=True, slots=True)
class Transition:
    state: GameState
    facts: tuple[Fact, ...]
