from abc import ABC, abstractmethod
from random import Random

from aidm.state.base import Frozen
from aidm.state.plan import Resolution
from aidm.state.world import GameState

from .loader import Engine


class Action(Frozen, ABC):
    """One thing a beat puts to the dice, and how it settles itself."""

    @abstractmethod
    def resolve(self, engine: Engine, draft: GameState, rng: Random) -> Resolution:
        """Rolls and mutates the draft; the engine is here for what an action reads off content."""
