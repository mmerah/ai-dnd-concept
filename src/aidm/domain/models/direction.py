"""The Director's structured output: what should happen this turn and mechanics to resolve it."""

from pydantic import Field

from .base import EntityId, Frozen
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
