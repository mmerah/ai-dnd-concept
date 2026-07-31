from typing import Literal

from pydantic import Field, TypeAdapter

from aidm.domain.base import PLAYER_ID, EntityId

from ...utils.models import Frozen
from .consequences import CanonRef, Consequence, all_canon_refs

MECHANICS_ADAPTER: TypeAdapter[list[Consequence]] = TypeAdapter(list[Consequence])


class Dnd5eDirection(Frozen):
    """A proposed attempt, not a resolved outcome."""

    engine: Literal["dnd5e"] = "dnd5e"
    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: list[Consequence] = Field(default_factory=list)

    def canon_refs(self) -> list[CanonRef]:
        return all_canon_refs(self.mechanics)

    def check(self) -> str | None:
        if self.speaker_id == PLAYER_ID:
            return "speaker_id must be an actor the player addresses, never the player"
        return None
