from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug

MOVE_ITEM = "An item moves to a new holder."
UNLOCK_WAY = "A locked way out of this place opens."
MOVE = "Call this to carry the player through an unlocked way out of this place."
MEANWHILE = (
    "Time has passed where the player is not. Move a dweller, move a loose item, and shut a "
    "way they know — any combination, in one call, while ELSEWHERE is shown."
)
NOTHING_OFFSCREEN = "no time has passed offscreen; call this only while ELSEWHERE is shown"
MOVES_OFFSCREEN = "something moves where the player cannot see"
MOVED_CARD = "Elsewhere, something moves."


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


class Meanwhile(Frozen):
    dweller_id: Slug | None = Field(
        default=None, description="Exact id of a dweller elsewhere who walks to a new place."
    )
    dweller_to: Slug | None = Field(
        default=None, description="Exact id of the place the dweller walks to."
    )
    item_id: Slug | None = Field(
        default=None, description="Exact id of a loose item elsewhere that moves to a new place."
    )
    item_to: Slug | None = Field(
        default=None, description="Exact id of the place the item moves to."
    )
    shut_from: Slug | None = Field(
        default=None, description="Exact id of one end of the way that shuts."
    )
    shut_to: Slug | None = Field(
        default=None, description="Exact id of the other end of the way that shuts."
    )

    @model_validator(mode="after")
    def _paired(self) -> Self:
        pairs = (
            (self.dweller_id, self.dweller_to),
            (self.item_id, self.item_to),
            (self.shut_from, self.shut_to),
        )
        for first, second in pairs:
            if (first is None) != (second is None):
                raise ValueError("each of the three pairs takes both ends or neither")
        if all(first is None for first, _ in pairs):
            raise ValueError("give a dweller, an item or a way to shut")
        return self
