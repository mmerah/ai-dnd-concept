from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines.base import JoinParty, LeaveParty


class Reveal(Frozen):
    """Something hidden here becomes known to the player."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of something hidden here: an npc or an item."
    )


class MoveItem(Frozen):
    """An item moves to a new holder."""

    verb: Literal["move_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item here or carried.")
    to: CheckedEntityId = Field(description="Exact id of the player, an npc here, or this place.")


class Kill(Frozen):
    """An npc here dies."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of an npc here.")


class Move(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the place to move to.")
    with_ids: tuple[CheckedEntityId, ...] = Field(
        default=(),
        description="Exact ids of living npcs here who follow once. Party members come anyway.",
    )


class UnlockWay(Frozen):
    """A locked way out of this place opens."""

    verb: Literal["unlock_way"]
    to_id: CheckedEntityId = Field(description="Exact id of the locked way's destination.")


type SharedChange = Reveal | MoveItem | Kill | JoinParty | LeaveParty | UnlockWay
