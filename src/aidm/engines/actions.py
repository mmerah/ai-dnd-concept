from abc import ABC, abstractmethod
from random import Random
from typing import ClassVar

from aidm.state.base import Frozen, Slug
from aidm.state.plan import Resolution
from aidm.state.world import GameState

from .loader import Engine


class Action(Frozen, ABC):
    """One thing a plan puts to the dice: what it can settle on, and how it settles itself."""

    outcomes: ClassVar[frozenset[Slug]]

    @abstractmethod
    def resolve(self, engine: Engine, draft: GameState, rng: Random) -> Resolution:
        """Rolls and mutates the draft; the engine is here for what an action reads off content."""
