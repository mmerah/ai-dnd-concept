from pydantic import Field

from aidm.core.entities import Frozen, Slug

MOVE_ITEM = "An item moves to a new holder."
UNLOCK_WAY = "A locked way out of this place opens."
MOVE = "Call this to carry the player through an unlocked way out of this place."


class MoveItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item here or carried.")
    to: Slug = Field(description="Exact id of the player, an npc here, or this place.")


class Move(Frozen):
    to_id: Slug = Field(description="Exact id of the place to move to.")
    with_ids: tuple[Slug, ...] = Field(
        default=(),
        description="Exact ids of living npcs here who follow once. Party members come anyway.",
    )


class UnlockWay(Frozen):
    to_id: Slug = Field(description="Exact id of the locked way's destination.")
