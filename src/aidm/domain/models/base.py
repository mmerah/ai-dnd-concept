"""Primitives the other model modules build on: the frozen base, copy helper, and vocabularies."""

from typing import Literal, NewType, get_args

from pydantic import BaseModel, ConfigDict

Ability = Literal["strength", "dexterity", "intellect", "wisdom"]
Kind = Literal["npc", "location", "item"]
Role = Literal["director", "narrator", "maintainer", "creator"]

# Branded so a location or item name can never be passed where an entity id is expected.
EntityId = NewType("EntityId", str)

# The player is a Character, not a world entity, but positions and inventories reference actors by
# id — so the player gets one reserved id. No scenario entity may claim it (validated in state.py).
PLAYER_ID = EntityId("player")

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 6


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with changes, revalidated — `model_copy(update=)` would skip `extra="forbid"`."""
    return type(obj).model_validate(obj.model_dump() | changes)
