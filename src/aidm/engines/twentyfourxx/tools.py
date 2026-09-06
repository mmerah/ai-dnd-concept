from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.core.tools import Attempt
from aidm.engines.base import ACTOR, JoinParty, LeaveParty
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


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


class Defend(Frozen):
    """Break a carried item or a ship function so a hit becomes a hindrance; word the harm."""

    verb: Literal["defend"]
    item_id: CheckedEntityId = Field(
        description="Exact id of an item the actor carries, or a ship function."
    )
    hindrance: str = Field(
        default="",
        description="What the harm becomes, as a hindrance. Empty only when the ship's hull "
        "armor takes the hit; it breaks harmlessly.",
    )
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


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
    | Defend
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


class Raise(Frozen):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: str = Field(min_length=1, description="The skill the job called on for them, to raise.")


class Job(Frozen):
    verb: Literal["find", "take", "finish"] = Field(
        description="`find` rolls the SRD's d6 for work; `take` records the job's terms as "
        "agreed; `finish` closes it: raises and pay."
    )
    where: str = Field(
        default="",
        description="Where, or through whom, the player looks for work, in a few words; it "
        "heads the card. With `find`.",
    )
    terms: str = Field(
        default="",
        description="Who wants what done, what done looks like, what it pays, as agreed. "
        "With `take`.",
    )
    raises: tuple[Raise, ...] = Field(
        default=(),
        description="One per operator: the player and every living hired member, each with the "
        "skill the job called on for them. With `finish`.",
    )

    @model_validator(mode="after")
    def _fields_for_verb(self) -> Self:
        wanted = {"find": "where", "take": "terms", "finish": "raises"}[self.verb]
        given = {"where": self.where, "terms": self.terms, "raises": self.raises}
        if not given.pop(wanted) or any(given.values()):
            raise ValueError(f"{self.verb} takes {wanted} only")
        return self


def outcome(face: int) -> str:
    if face <= 2:
        return "disaster"
    if face <= 4:
        return "setback"
    return "success"
