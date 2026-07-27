"""Primitives the other model modules build on: the frozen base, copy helper, and vocabularies."""

from typing import Literal, NewType, get_args

from pydantic import BaseModel, ConfigDict

# Spelled in full because that is how they are rendered to a role.
Ability = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
Kind = Literal["actor", "location", "item"]
Role = Literal["director", "narrator", "maintainer", "creator"]

ABILITIES: tuple[Ability, ...] = get_args(Ability)

# Branded so a location or item name can never be passed where an entity id is expected.
EntityId = NewType("EntityId", str)

# The player is an actor entity like any other, under one reserved id so events, inventories and
# positions name them the same way they name anyone. No scenario entity may claim it (state.py).
PLAYER_ID = EntityId("player")

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 8


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def updated[T: Frozen](obj: T, **changes: object) -> T:
    """Copy with changes, revalidated — `model_copy(update=)` would skip `extra="forbid"`."""
    return type(obj).model_validate(obj.model_dump() | changes)
