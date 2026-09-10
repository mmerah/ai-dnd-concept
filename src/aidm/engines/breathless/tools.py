from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines import base
from aidm.engines.base import Attempt, JoinParty, LeaveParty
from aidm.engines.breathless.world import Die, Skill
from aidm.engines.hiring import ACTOR
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


class DropItem(Frozen):
    """The actor loses an item for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the actor carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class ChangeStress(Frozen):
    """The actor's stress goes up or down."""

    verb: Literal["change_stress"]
    amount: int = Field(
        description="How much stress changes. Positive costs stress, negative clears it."
    )
    why: str = Field(min_length=1, description="What causes the change, in a few words.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class UseMedKit(Frozen):
    """The actor spends their med kit."""

    verb: Literal["use_med_kit"]
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


type WorldChange = (
    Reveal | Enter | Leave | Kill | JoinParty | LeaveParty | DropItem | ChangeStress | UseMedKit
)


ChangeWorld = base.ChangeWorld[Annotated[WorldChange, Discriminator("verb")]]


class Check(Attempt):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: Skill | None = Field(
        default=None, description="Which of the six skills the action calls on."
    )
    item_id: CheckedEntityId | None = Field(
        default=None, description="Exact id of a carried item used instead of a skill."
    )
    stunt: bool = Field(
        default=False,
        description="True for an extraordinary stunt at d12.",
    )
    dangerous: bool = Field(
        default=False, description="True when a fail would plainly hurt the actor."
    )
    helped_by: CheckedEntityId | None = Field(
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
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


def outcome(face: int) -> str:
    if face <= 2:
        return "fail"
    if face <= 4:
        return "success-but"
    return "success"
