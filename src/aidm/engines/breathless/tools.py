from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.core.tools import Attempt
from aidm.engines.base import ACTOR, JoinParty, LeaveParty
from aidm.engines.breathless.world import Die, Skill
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


class DropItem(Frozen):
    """Take an item out of the actor's backpack for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the actor carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


type WorldChange = Reveal | Enter | Leave | Kill | JoinParty | LeaveParty | DropItem


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


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
        description="True to attempt an extraordinary stunt at d12 instead of a skill or item.",
    )
    dangerous: bool = Field(
        default=False, description="True when a fail would plainly hurt the actor."
    )
    helped_by: CheckedEntityId | None = Field(
        default=None,
        description="A hired survivor here who helps: they also make the check on their own die "
        "of the same skill and share its risks; the highest die counts. Only on a skill check.",
    )

    @model_validator(mode="after")
    def _one_thing(self) -> Self:
        if sum((self.skill is not None, self.item_id is not None, self.stunt)) != 1:
            raise ValueError("roll one thing: a skill, an item, or a stunt")
        if self.helped_by is not None and self.skill is None:
            raise ValueError("help joins a skill check: an item or a stunt is one person's")
        return self


class ChangeStress(Frozen):
    amount: int = Field(
        description="How much stress changes: positive for a complication's cost, negative to "
        "clear it."
    )
    why: str = Field(min_length=1, description="What causes the change, in a few words.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class LootCheck(Frozen):
    item: str = Field(
        min_length=1,
        description="What is found if the roll finds anything; the die sets how good it is.",
    )
    granted: Die | None = Field(
        default=None, description="Leave null; the engine fills it when the player answers."
    )
    choice: str | None = Field(
        default=None, description="Leave null; the engine fills it when the player answers."
    )

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if (self.granted is None) != (self.choice is None):
            raise ValueError("granted and choice arrive together, or not at all")
        return self


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
