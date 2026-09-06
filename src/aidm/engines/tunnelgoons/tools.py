from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen
from aidm.core.play import PendingOption
from aidm.core.tools import Attempt
from aidm.engines.base import ACTOR
from aidm.engines.rooms.tools import SharedChange
from aidm.engines.tunnelgoons.world import ABILITIES, Ability, Boost


class Rest(Frozen):
    """The player and the party spend a night here and heal to full Health."""

    verb: Literal["rest"]


class ChangeWorld(Frozen):
    change: SharedChange | Rest = Field(
        discriminator="verb",
        description="The change to apply. `verb` picks which one.",
    )


class ActionRoll(Attempt):
    ability: Ability = Field(description="Which ability the action calls on.")
    items: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of items the actor carries that plainly help."
    )
    difficulty: int | None = Field(
        default=None,
        ge=1,
        description=("Difficulty Score: 8 easy, 10 moderate, 12 hard. Null when `against` is set."),
    )
    against: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of an npc here the actor acts on, in a fight or in talk. Its "
        "Health is the Difficulty Score.",
    )
    dangerous: bool = Field(
        default=False,
        description="True when a miss would hurt. Talk is not dangerous unless the story says so.",
    )
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.difficulty is None) == (self.against is None):
            raise ValueError("give a difficulty, or an npc to roll against, not both/neither")
        return self


class LevelUp(Frozen):
    ability: Ability | None = Field(
        default=None, description="Which ability to raise by 1. Null asks the player."
    )
    boost: Boost | None = Field(
        default=None, description="Health or Inventory to raise by 1. Null asks the player."
    )
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


def level_options(actor_id: EntityId | None) -> tuple[PendingOption, ...]:
    return tuple(
        PendingOption(
            id=f"{ability}-{boost}",
            label=f"{ability.capitalize()} +1, {boost.capitalize()} +1",
            name="level_up",
            args={"ability": ability, "boost": boost, "actor_id": actor_id},
        )
        for ability in ABILITIES
        for boost in ("health", "inventory")
    )
