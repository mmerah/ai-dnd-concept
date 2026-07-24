"""The Director's structured output: what should happen this turn and mechanics to resolve it."""

from pydantic import Field

from .base import Ability, EntityId, Frozen
from .consequences import CanonRef, Consequence


class Check(Frozen):
    ability: Ability
    dc: int


class Mechanics(Frozen):
    """The turn's typed mechanics: an optional check and the consequences on each branch."""

    check: Check | None = None
    unconditional: list[Consequence] = Field(default_factory=list)  # always applied
    on_success: list[Consequence] = Field(default_factory=list)  # applied iff the check passes
    on_failure: list[Consequence] = Field(default_factory=list)  # applied iff the check fails

    def canon_refs(self) -> list[CanonRef]:
        """Every canon id these mechanics touch, with the kind it must be."""
        groups = (*self.unconditional, *self.on_success, *self.on_failure)
        return [ref for c in groups for ref in c.canon_refs()]


class Direction(Frozen):
    """Director output. The Narrator treats `intent` as what was attempted, not what happened."""

    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: Mechanics = Field(default_factory=Mechanics)
