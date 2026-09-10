from typing import Annotated, Literal, Self

from pydantic import Discriminator, Field, model_validator

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.core.tools import Attempt
from aidm.engines import base
from aidm.engines.base import JoinParty, LeaveParty
from aidm.engines.hiring import ACTOR
from aidm.engines.scenes.tools import Enter, Kill, Leave, Reveal


class ChangeHindrances(Frozen):
    """The actor picks up hindrances, sheds them, or both at once."""

    verb: Literal["change_hindrances"]
    gained: tuple[str, ...] = Field(default=(), description="Hindrances the actor now carries.")
    lost: tuple[str, ...] = Field(default=(), description="Hindrances the actor no longer carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("change_hindrances needs a gained or a lost hindrance")
        return self


class GainItem(Frozen):
    """The actor gains an item and pays for it."""

    verb: Literal["gain_item"]
    name: str = Field(min_length=1, description="The item's name.")
    bulky: bool = Field(default=False, description="True when the item takes real space to carry.")
    breaks: int = Field(
        default=1, ge=1, description="How many times the item can break before it is ruined."
    )
    cost: int = Field(
        default=0,
        ge=0,
        description="Credits paid. 0 for a thing found or given.",
    )
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class DropItem(Frozen):
    """The actor loses an item for good."""

    verb: Literal["drop_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item the actor carries.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class RepairItem(Frozen):
    """The actor mends a broken item."""

    verb: Literal["repair_item"]
    item_id: CheckedEntityId = Field(
        description="Exact id of an item the actor carries, or a ship function."
    )
    cost: int = Field(default=0, ge=0, description="Credits spent on the repair.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class Spend(Frozen):
    """The actor pays credits for something that is not an item or a repair."""

    verb: Literal["spend"]
    amount: int = Field(gt=0, description="Credits spent.")
    why: str = Field(min_length=1, description="What the credits pay for, in a few words.")
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)


class TakeLead(Frozen):
    """A hired member takes the lead after the player dies."""

    verb: Literal["take_lead"]
    entity_id: CheckedEntityId = Field(
        description="Exact id of the living hired member who takes the lead."
    )


class ShipUpgrade(Frozen):
    """The player upgrades one ship function."""

    verb: Literal["ship_upgrade"]
    function_id: CheckedEntityId = Field(
        description="Exact id of a ship function. The player pays ₡10."
    )


class Defend(Frozen):
    """A carried item or a ship function breaks so a hit becomes a hindrance."""

    verb: Literal["defend"]
    item_id: CheckedEntityId = Field(
        description="Exact id of an item the actor carries, or a ship function."
    )
    hindrance: str = Field(
        default="",
        description="What the harm becomes, as a hindrance. Empty for an item that breaks "
        "harmlessly.",
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


ChangeWorld = base.ChangeWorld[Annotated[WorldChange, Discriminator("verb")]]


class Roll(Attempt):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: str = Field(default="", description="Which skill to roll. Empty rolls the plain d6.")
    helped: str = Field(default="", description="Why circumstances help. Empty when none do.")
    helped_by: CheckedEntityId | None = Field(
        default=None,
        description="Exact id of a hired member who rolls their own die. Null when none helps.",
    )
    hindered: str = Field(default="", description="Why the actor is hindered. Empty when none is.")
    risking_death: bool = Field(
        default=False,
        description="True when the actor risks death on this roll.",
    )


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Raise(Frozen):
    actor_id: CheckedEntityId | None = Field(default=None, description=ACTOR)
    skill: str = Field(min_length=1, description="The skill the job called on for them.")


class Job(Frozen):
    verb: Literal["find", "take", "finish"] = Field(
        description="`find` looks for work. `take` records agreed work. `finish` closes the job."
    )
    where: str = Field(
        default="",
        description="Where the player looks for work, in a few words. Required with `find`.",
    )
    terms: str = Field(
        default="",
        description="Who wants what done, what that looks like, and what it pays. Required with "
        "`take`.",
    )
    raises: tuple[Raise, ...] = Field(
        default=(),
        description="One per operator: the player and every living hired member. Required with "
        "`finish`.",
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
