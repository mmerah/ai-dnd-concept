from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen, Refusal
from aidm.core.play import PendingOption
from aidm.engines.tunnelgoons.world import ABILITIES, Ability, Boost

LEVEL_OPTIONS: tuple[PendingOption, ...] = tuple(
    PendingOption(
        id=f"{ability}-{boost}",
        label=f"{ability.capitalize()} +1, {boost.capitalize()} +1",
        name="level_up",
        args={"ability": ability, "boost": boost},
    )
    for ability in ABILITIES
    for boost in ("health", "inventory")
)


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


type WorldChange = Reveal | MoveItem | Kill


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Move(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the place to move to.")
    with_ids: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of living NPCs here who come along."
    )


class UnlockWay(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the locked way's destination.")


class ActionRoll(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
    ability: Ability = Field(description="Which ability the action calls on.")
    items: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of items the player carries that plainly help; +1 each."
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Difficulty Score; the SRD's guidelines: 8 easy, 10 moderate, 12 hard. Null when "
            "`against` names an NPC."
        ),
    )
    against: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of an npc here; its Health is the Difficulty Score.",
    )
    dangerous: bool = Field(
        default=False,
        description=(
            "A fight, a trap, a fall: the margin becomes damage, to the NPC on a hit or to "
            "the player on a miss."
        ),
    )

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.difficulty is None) == (self.against is None):
            raise Refusal("give a difficulty, or an npc to roll against, not both/neither")
        return self


class LevelUp(Frozen):
    ability: Ability | None = Field(
        default=None, description="Which ability to raise by 1; null asks the player."
    )
    boost: Boost | None = Field(
        default=None, description="Health or Inventory to raise by 1; null asks the player."
    )
