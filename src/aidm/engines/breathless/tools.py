from typing import Self

from pydantic import Field, field_validator, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.engines.base import Attempt
from aidm.engines.breathless.world import Die, Skill
from aidm.engines.hiring import ACTOR

CHANGE_STRESS = "The actor's stress goes up or down."
USE_MED_KIT = "The actor spends their med kit."
ROLL = (
    "Call this for an action with a real cost. Roll one thing: a skill, a carried "
    "item, or a stunt. The engine rolls, reads the result, and wears the die down."
)
CATCH_BREATH = (
    "Call this after a lull in the danger. The engine resets the actor's skills, "
    "loot die and stunt, and brings a new complication."
)
LOOT_CHECK = (
    "Call this to scavenge for an item. The engine rolls the loot die and asks the "
    "player what to do with a find."
)
TEST_LUCK = (
    "Call this to ask about the world when nobody acts. The engine rolls the die "
    "you pick and reads it."
)


class ChangeStress(Frozen):
    amount: int = Field(
        description="How much stress changes. Positive costs stress, negative clears it."
    )
    why: str = Field(min_length=1, description="What causes the change, in a few words.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)

    @field_validator("amount")
    @classmethod
    def _non_zero(cls, amount: int) -> int:
        if amount == 0:
            raise ValueError("a non-zero amount")
        return amount


class UseMedKit(Frozen):
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class Roll(Attempt):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
    skill: Skill | None = Field(
        default=None, description="Which of the six skills the action calls on."
    )
    item_id: Slug | None = Field(
        default=None, description="Exact id of a carried item used instead of a skill."
    )
    stunt: bool = Field(
        default=False,
        description="True for an extraordinary stunt at d12.",
    )
    dangerous: bool = Field(
        default=False, description="True when a fail would plainly hurt the actor."
    )
    helped_by: Slug | None = Field(
        default=None,
        description="Exact id of a hired member who checks the same skill. Only with `skill`.",
    )

    @model_validator(mode="after")
    def _one_thing(self) -> Self:
        if sum((self.skill is not None, self.item_id is not None, self.stunt)) != 1:
            raise ValueError("roll one thing: a skill, an item, or a stunt")
        if self.helped_by is not None and self.skill is None:
            raise ValueError("help joins a skill check: an item or a stunt is one person's")
        return self


class LootCheck(Frozen):
    item: str = Field(
        min_length=1,
        description="What is found if the roll finds anything.",
    )


class TakeLoot(Frozen):
    """Not a tool: `granted` is rolled, so only the options the roll wrote may carry one."""

    item: str = Field(min_length=1)
    granted: Die
    choice: str = Field(min_length=1)


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )
    die: Die = Field(description="Which die to roll, picked by the odds.")


class Actor(Frozen):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
