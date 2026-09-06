from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen
from aidm.core.play import PendingOption
from aidm.core.tools import Attempt
from aidm.engines.rooms.tools import SharedChange
from aidm.engines.tunnelgoons.world import ABILITIES, Ability, Boost

ACTOR = "null for the player; else the exact id of a hired party member here who acts."


class ChangeWorld(Frozen):
    change: SharedChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class ActionRoll(Attempt):
    ability: Ability = Field(description="Which ability the action calls on.")
    items: tuple[CheckedEntityId, ...] = Field(
        default=(), description="Exact ids of items the actor carries that plainly help; +1 each."
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
            "the actor on a miss."
        ),
    )
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.difficulty is None) == (self.against is None):
            raise ValueError("give a difficulty, or an npc to roll against, not both/neither")
        return self


class LevelUp(Frozen):
    ability: Ability | None = Field(
        default=None, description="Which ability to raise by 1; null asks the player."
    )
    boost: Boost | None = Field(
        default=None, description="Health or Inventory to raise by 1; null asks the player."
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
