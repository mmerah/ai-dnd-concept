from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen


class Reveal(Frozen):
    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of something hidden here: an npc or an item."
    )


class MoveItem(Frozen):
    verb: Literal["move_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item here or carried.")
    to: CheckedEntityId = Field(description="Exact id of the player, an npc here, or this place.")


class Kill(Frozen):
    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of an npc here.")


class Move(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the place to move to.")
    with_ids: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of living NPCs here who come along."
    )


class UnlockWay(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the locked way's destination.")


type SharedChange = Reveal | MoveItem | Kill
