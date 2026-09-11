from pydantic import Field

from aidm.core.entities import Frozen, Slug

REVEAL = "Something hidden here becomes known to the player."
MOVE_ITEM = "An item moves to a new holder."
KILL = "An npc here dies."
UNLOCK_WAY = "A locked way out of this place opens."
MOVE = "Call this to carry the player through an unlocked way out of this place."


class Reveal(Frozen):
    entity_id: Slug = Field(description="Exact id of something hidden here: an npc or an item.")


class MoveItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item here or carried.")
    to: Slug = Field(description="Exact id of the player, an npc here, or this place.")


class Kill(Frozen):
    entity_id: Slug = Field(description="Exact id of an npc here.")


class Move(Frozen):
    to_id: Slug = Field(description="Exact id of the place to move to.")
    with_ids: tuple[Slug, ...] = Field(
        default=(),
        description="Exact ids of living npcs here who follow once. Party members come anyway.",
    )


class UnlockWay(Frozen):
    to_id: Slug = Field(description="Exact id of the locked way's destination.")
