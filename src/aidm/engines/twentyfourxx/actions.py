from typing import Literal

from pydantic import Field

from aidm.state.base import EntityId, Frozen
from aidm.state.plan import Branched

from .mechanics import TwentyfourxxEffect


class Attempt(Frozen):
    """One risky attempt, answered by the highest die of a pool."""

    act: Literal["attempt"] = "attempt"
    actor_id: EntityId = Field(
        description="Exact id of the actor attempting this: the player, or an actor here."
    )
    goal: str = Field(
        min_length=1,
        description="What the actor is trying to do and what they risk by trying, in one line.",
    )
    skill: str = Field(
        default="",
        description="The skill on the actor's sheet this calls on, copied exactly as it is "
        "written there. Empty when none of theirs applies: they roll the bare d6.",
    )
    helped: str = Field(
        default="",
        description="One tag in the scene that makes this easier — a trait on the actor, on "
        "what they carry, on where they stand, or on who stands there with them — copied "
        "exactly. Empty when nothing helps; you cannot invent one.",
    )
    hindered: str = Field(
        default="",
        description="One tag in the scene that makes this harder, copied the same way. Empty "
        "when nothing hinders.",
    )
    luck_test: str = Field(
        default="",
        description="What bad luck might arrive alongside this — running out of ammo, running "
        "into guards. The engine rolls whether it does. Empty for no test.",
    )


class TurnPlan(Branched[TwentyfourxxEffect]):
    action: Attempt | None = Field(
        default=None,
        description="The one attempt this turn resolves, or null when nothing the player does "
        "is risky enough to roll.",
    )
