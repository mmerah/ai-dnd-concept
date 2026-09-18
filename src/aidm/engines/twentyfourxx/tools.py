from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.engines.tools import ACTOR, Attempt

DEFEND_WITH = (
    "Exact id of an item of the {who}, or of a ship function. That item or that function "
    "breaks and protects the {who}. Null when nothing protects the {who}."
)
DEADLY = (
    "True when `risk` is death. A disaster then kills the {who}. The {who} does not get "
    "`risk` as a hindrance. A setback then maims the {who}."
)
HINDRANCE = (
    "What the hit leaves behind after the gear takes it, as a hindrance. Empty when the "
    "gear breaks with no harm."
)


class ChangeHindrances(Frozen):
    gained: tuple[str, ...] = Field(default=(), description="Hindrances the actor now carries.")
    lost: tuple[str, ...] = Field(default=(), description="Hindrances the actor no longer carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)

    @model_validator(mode="after")
    def _some_change(self) -> Self:
        if not self.gained and not self.lost:
            raise ValueError("give a gained hindrance or a lost hindrance")
        return self


class GainItem(Frozen):
    name: str = Field(min_length=1, description="The item's name.")
    bulky: bool = Field(default=False, description="True when the item takes much space to carry.")
    breaks: int = Field(
        default=1, ge=1, description="How many times the item breaks before it is destroyed."
    )
    cost: int = Field(
        default=0,
        ge=0,
        description="Credits paid. Use 0 for a thing found or given.",
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
    actor_id: Slug = Field(description="Exact id of the living hired member who takes the lead.")


class ShipUpgrade(Frozen):
    function_id: Slug = Field(description="Exact id of a ship function. The player pays ₡10.")


class Defend(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries, or a ship function.")
    hindrance: str = Field(
        default="",
        description="What the harm becomes, as a hindrance. Empty for an item that breaks "
        "with no harm.",
    )
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class DropItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class AskWorld(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world when no character acts."
    )


class Staked(Frozen):
    risk: str = Field(
        default="",
        description="What the actor takes in full on a disaster. Name it before the roll. "
        "Empty when the actor is in no danger.",
    )
    deadly: bool = Field(default=False, description=DEADLY.format(who="actor"))
    defend_with_id: Slug | None = Field(default=None, description=DEFEND_WITH.format(who="actor"))
    hindrance: str = Field(default="", description=HINDRANCE)

    @model_validator(mode="after")
    def _defend_fields(self) -> Self:
        check_risk(
            self.risk,
            deadly=self.deadly,
            defend_with_id=self.defend_with_id,
            hindrance=self.hindrance,
        )
        return self


class Helper(Staked):
    actor_id: Slug = Field(description="Exact id of the hired member who helps.")
    hindered: str = Field(
        default="", description="Why the helper is hindered. Empty when nothing hinders them."
    )
    risk: str = Field(
        default="",
        description="What the helper takes in full on a disaster. Name it before the roll. "
        "Empty when the help puts the helper in no danger.",
    )
    deadly: bool = Field(default=False, description=DEADLY.format(who="helper"))
    defend_with_id: Slug | None = Field(default=None, description=DEFEND_WITH.format(who="helper"))


class Roll(Staked, Attempt):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
    skill: str = Field(default="", description="The skill to roll. Empty rolls the plain d6.")
    helped: str = Field(
        default="", description="Why the conditions help. Empty when nothing helps."
    )
    helped_by: Helper | None = Field(
        default=None,
        description="The hired member who helps, adding one d6. Null when nobody helps.",
    )
    hindered: str = Field(
        default="", description="Why the actor is hindered. Empty when nothing hinders them."
    )


class Raise(Frozen):
    actor_id: Slug | None = Field(default=None, description=ACTOR)
    skill: str = Field(
        min_length=1,
        description="The skill that the job used for this operator. A skill that is not on "
        "their sheet is added at d8.",
    )


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
        description="Who wants the work, what the work is, and what the work pays. Required "
        "with `take`.",
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


def check_risk(risk: str, *, deadly: bool, defend_with_id: Slug | None, hindrance: str) -> None:
    if deadly and not risk:
        raise ValueError("deadly needs the risk that it names")
    if defend_with_id is not None and not risk:
        raise ValueError("defend_with_id needs the risk that it protects against")
    if hindrance and defend_with_id is None:
        raise ValueError("hindrance needs the defend_with_id that causes it")
