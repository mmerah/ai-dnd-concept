from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.core.tools import Attempt
from aidm.engines.base import JoinParty, LeaveParty
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal

ACTOR = "null for the player; else the exact id of a hired crew member here who acts."


class ChangeHindrances(Frozen):
    """Record hindrances the player picks up, sheds, or both at once."""

    verb: Literal["change_hindrances"]
    gained: tuple[str, ...] = Field(
        default=(), description="Hindrances the actor now carries, that they did not before."
    )
    lost: tuple[str, ...] = Field(default=(), description="Hindrances the actor no longer carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("change_hindrances needs a gained or a lost hindrance")
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
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class DropItem(Frozen):
    """Take an item out of the player's kit for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the actor carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class RepairItem(Frozen):
    """Fix a broken item, spending credits when the repair costs any."""

    verb: Literal["repair_item"]
    item_id: CheckedEntityId = Field(
        description="Exact id of an item the actor carries, or a ship function."
    )
    cost: int = Field(default=0, ge=0, description="Credits spent on the repair.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class Spend(Frozen):
    """Pay credits for anything that is not an item or a repair: bribes, care, passage."""

    verb: Literal["spend"]
    amount: int = Field(gt=0, description="Credits spent.")
    why: str = Field(min_length=1, description="What the credits pay for, in a few words.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class TakeLead(Frozen):
    """The hired member who leads once the player is dead; answers the succession decision."""

    verb: Literal["take_lead"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of the living hired member who takes the lead."
    )


class ShipUpgrade(Frozen):
    """Upgrade one ship function; ₡10 from the player, as the SRD prices it."""

    verb: Literal["ship_upgrade"]
    function_id: CheckedEntityId = Field(
        description="Exact id of a ship function; ₡10 from the player."
    )


type WorldChange = (
    Reveal
    | Enter
    | Leave
    | Kill
    | JoinParty
    | LeaveParty
    | ChangeHindrances
    | GainItem
    | DropItem
    | RepairItem
    | Spend
    | TakeLead
    | ShipUpgrade
)


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


class Roll(Attempt):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: str = Field(default="", description="Which skill to roll; empty rolls the plain d6.")
    helped: str = Field(default="", description="Why circumstances help, when they do.")
    helped_by: CheckedEntityId | None = Field(
        default=None,
        description="A hired crew member who helps: they roll their own die for the skill and "
        "the highest counts; `helped` stays the d6 of circumstance.",
    )
    hindered: str = Field(default="", description="Why the actor is hindered, when they are.")
    risking_death: bool = Field(
        default=False,
        description="True when a disaster kills the actor and a setback maims them; say it "
        "before the roll.",
    )


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Defend(Frozen):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    item_id: CheckedEntityId = Field(
        description="Exact id of an item the actor carries, or a ship function."
    )
    hindrance: str = Field(
        min_length=1, description="What the harm the actor takes becomes, as a hindrance."
    )


class TakeJob(Frozen):
    terms: str = Field(
        min_length=1,
        description="Who wants what done, what done looks like, what it pays, as agreed.",
    )


class FindJob(Frozen):
    where: str = Field(
        min_length=1,
        description="Where, or through whom, the player looks for work, in a few words; it "
        "heads the card.",
    )


class Raise(Frozen):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: str = Field(min_length=1, description="The skill the job called on for them, to raise.")


class FinishJob(Frozen):
    raises: tuple[Raise, ...] = Field(
        min_length=1,
        description="One per operator: the player and every living hired member, each with the "
        "skill the job called on for them.",
    )


def outcome(face: int) -> str:
    if face <= 2:
        return "disaster"
    if face <= 4:
        return "setback"
    return "success"
