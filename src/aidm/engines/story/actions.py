from typing import Literal

from pydantic import Field

from aidm.state.base import EntityId, Frozen, Slug
from aidm.state.plan import TurnPlanBase


class Risk(Frozen):
    """The one thing this engine resolves: an uncertain attempt, settled by 2d6 against a 7."""

    act: Literal["risk"] = "risk"
    actor_id: EntityId = Field(
        description="Exact id of the actor taking the risk: the player, or an actor here."
    )
    approach: Literal["bold", "subtle", "clever", "empathetic"] = Field(
        description="How they go about it; that approach's number on their sheet is the bonus."
    )
    difficulty: Literal["risky", "demanding", "extreme"] = Field(
        description="How hard it is: risky costs nothing, demanding -1, extreme -2."
    )
    helping_tag_id: Slug | None = Field(
        default=None,
        description="Exact id of the one tag that directly helps — an edge, a bond, or a gear "
        "benefit on an item that actor carries. Null when none does.",
    )
    hindering_tag_id: Slug | None = Field(
        default=None,
        description="Exact id of the one tag on that actor's sheet that directly hinders — a "
        "burden or a condition. Null when none does.",
    )
    stakes: str = Field(
        min_length=1, description="What is attempted, in a few words; it names the roll."
    )


class TurnPlan(TurnPlanBase):
    action: Risk | None = Field(
        default=None,
        description="The one risk this turn resolves, or null when nothing is uncertain enough "
        "to roll for.",
    )
