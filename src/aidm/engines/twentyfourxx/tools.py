from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen, Refusal
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


class ChangeHindrances(Frozen):
    """Record hindrances the player picks up, sheds, or both at once."""

    verb: Literal["change_hindrances"]
    gained: tuple[str, ...] = Field(
        default=(), description="Hindrances the player now carries, that they did not before."
    )
    lost: tuple[str, ...] = Field(
        default=(), description="Hindrances the player no longer carries."
    )

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise Refusal("change_hindrances needs a gained or a lost hindrance")
        return self


class GainItem(Frozen):
    """Add an item to the player's kit, spending credits when it costs any."""

    verb: Literal["gain_item"]
    name: str = Field(min_length=1, description="The item's name.")
    bulky: bool = Field(default=False, description="True when the item takes real space to carry.")
    breaks: int = Field(
        default=1, ge=1, description="How many times the item can break before it is ruined."
    )
    cost: int = Field(
        default=0,
        ge=0,
        description="Credits spent for the item; `cost` 0 only for a thing found or given.",
    )


class DropItem(Frozen):
    """Take an item out of the player's kit for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")


class RepairItem(Frozen):
    """Fix a broken item, spending credits when the repair costs any."""

    verb: Literal["repair_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the player carries.")
    cost: int = Field(default=0, ge=0, description="Credits spent on the repair.")


class Spend(Frozen):
    """Pay credits for anything that is not an item or a repair: bribes, care, passage."""

    verb: Literal["spend"]
    amount: int = Field(gt=0, description="Credits spent.")
    why: str = Field(min_length=1, description="What the credits pay for, in a few words.")


type WorldChange = (
    Reveal | Enter | Leave | Kill | ChangeHindrances | GainItem | DropItem | RepairItem | Spend
)


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Attempt(Frozen):
    what: str = Field(min_length=1, description="The action, in a few words; it heads the card.")
    skill: str = Field(default="", description="Which skill to roll; empty rolls the plain d6.")
    helped: str = Field(default="", description="Why circumstances help, when they do.")
    hindered: str = Field(default="", description="Why the player is hindered, when they are.")
    risking_death: bool = Field(
        default=False,
        description="True when a disaster kills the player and a setback maims them; say it "
        "before the roll.",
    )


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Defend(Frozen):
    item_id: CheckedEntityId = Field(
        description="Exact id of the item the player breaks to defend."
    )
    hindrance: str = Field(
        min_length=1, description="What the harm the player takes becomes, as a hindrance."
    )


class AfterJob(Frozen):
    skill: str = Field(
        min_length=1, description="The skill the job called on, named by the player, to raise."
    )


def outcome(face: int) -> str:
    if face <= 2:
        return "disaster"
    if face <= 4:
        return "setback"
    return "success"
