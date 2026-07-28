"""The Director's structured output: what should happen this turn and mechanics to resolve it."""

from pydantic import Field

from ...utils.models import Frozen
from .base import PLAYER_ID, EntityId
from .consequences import CanonRef, Consequence, all_canon_refs


class Direction(Frozen):
    """Director output. The Narrator treats `intent` as what was attempted, not what happened."""

    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: list[Consequence] = Field(default_factory=list)

    def canon_refs(self) -> list[CanonRef]:
        """Every canon id these mechanics touch, with its kind — recursive over nested branches."""
        return all_canon_refs(self.mechanics)

    def check(self) -> str | None:
        """An action's contract, for the one fact that is the turn's own."""
        # The player is an actor in canon, so naming them as speaker passes every kind check.
        if self.speaker_id == PLAYER_ID:
            return "speaker_id must be an actor the player addresses, never the player"
        return None
