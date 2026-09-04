from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines.breathless.world import Die, Skill
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


class DropItem(Frozen):
    """Take an item out of the player's backpack for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")


type WorldChange = Reveal | Enter | Leave | Kill | DropItem


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Check(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
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
        default=False, description="True when a fail would plainly hurt the player."
    )

    @model_validator(mode="after")
    def _one_thing(self) -> Self:
        if sum((self.skill is not None, self.item_id is not None, self.stunt)) != 1:
            raise ValueError("roll one thing: a skill, an item, or a stunt")
        return self


class ChangeStress(Frozen):
    amount: int = Field(
        description="How much stress changes: positive for a complication's cost, negative to "
        "clear it."
    )
    why: str = Field(min_length=1, description="What causes the change, in a few words.")


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


def outcome(face: int) -> str:
    if face <= 2:
        return "fail"
    if face <= 4:
        return "success-but"
    return "success"
