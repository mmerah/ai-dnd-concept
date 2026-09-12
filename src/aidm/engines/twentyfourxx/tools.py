from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.engines.base import Attempt
from aidm.engines.hiring import ACTOR

CHANGE_HINDRANCES = "The actor picks up hindrances, sheds them, or both at once."
GAIN_ITEM = "The actor gains an item and pays for it."
REPAIR_ITEM = "The actor mends a broken item."
SPEND = "The actor pays credits for something that is not an item or a repair."
TAKE_LEAD = "A hired member takes the lead after the player dies."
SHIP_UPGRADE = "The player upgrades one ship function."
DEFEND = "A carried item or a ship function breaks so a hit becomes a hindrance."
ROLL = (
    "Call this when the outcome of an action matters. The engine picks the dice, "
    "rolls them, and reads the result."
)
TEST_LUCK = (
    "Call this to ask about the world's bad luck when nobody acts. The engine "
    "rolls one d6 and reads it."
)
JOB = (
    "Call this to look for work with `find`, to record agreed work with `take`, "
    "and to close the job with `finish`. With `find` the engine rolls the SRD's "
    "d6. With `finish` it raises one skill for each operator and pays each of "
    "them d6 credits."
)


class ChangeHindrances(Frozen):
    gained: tuple[str, ...] = Field(default=(), description="Hindrances the actor now carries.")
    lost: tuple[str, ...] = Field(default=(), description="Hindrances the actor no longer carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("change_hindrances needs a gained or a lost hindrance")
        return self


class GainItem(Frozen):
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
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class RepairItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries, or a ship function.")
    cost: int = Field(default=0, ge=0, description="Credits spent on the repair.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class Spend(Frozen):
    amount: int = Field(gt=0, description="Credits spent.")
    why: str = Field(min_length=1, description="What the credits pay for, in a few words.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class TakeLead(Frozen):
    entity_id: Slug = Field(description="Exact id of the living hired member who takes the lead.")


class ShipUpgrade(Frozen):
    function_id: Slug = Field(description="Exact id of a ship function. The player pays ₡10.")


class Defend(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries, or a ship function.")
    hindrance: str = Field(
        default="",
        description="What the harm becomes, as a hindrance. Empty for an item that breaks "
        "harmlessly.",
    )
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class Helper(Frozen):
    """A hired member who rolls their own die, and what helping costs them."""

    actor_id: Slug = Field(description="Exact id of the hired member who helps.")
    hindered: str = Field(default="", description="Why the helper is hindered. Empty when none is.")
    risk: str = Field(
        default="",
        description="The harm the helper faces if this goes badly. Empty when helping puts "
        "them in no danger.",
    )
    defend_with: Slug | None = Field(
        default=None,
        description="Exact id of the helper's item or a ship function that breaks to spare "
        "them. Null when nothing shields them.",
    )

    @model_validator(mode="after")
    def _defend_needs_risk(self) -> Self:
        if self.defend_with is not None and not self.risk:
            raise ValueError("defend_with needs the risk it shields against")
        return self


class Roll(Attempt):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
    skill: str = Field(default="", description="Which skill to roll. Empty rolls the plain d6.")
    helped: str = Field(default="", description="Why circumstances help. Empty when none do.")
    helped_by: Helper | None = Field(
        default=None,
        description="The hired member who rolls their own die. Null when none helps.",
    )
    hindered: str = Field(default="", description="Why the actor is hindered. Empty when none is.")
    risk: str = Field(
        default="",
        description="The harm the actor faces if this goes badly, named before the roll. "
        "Empty when they are in no danger.",
    )
    defend_with: Slug | None = Field(
        default=None,
        description="Exact id of the actor's item or a ship function that breaks to spare "
        "them. Null when nothing shields them.",
    )

    @model_validator(mode="after")
    def _defend_needs_risk(self) -> Self:
        if self.defend_with is not None and not self.risk:
            raise ValueError("defend_with needs the risk it shields against")
        return self


class TestLuck(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Raise(Frozen):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
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
