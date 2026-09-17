from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact

NEXT_SCENE = (
    "Call this with nothing set when the scene reaches a stopping point. Set `pursuit` instead "
    "once the player has left this place. Set `complication` instead to bring a new situation "
    "down on this place."
)
ENTER = "A cast member comes into the scene."
LEAVE = "A cast member goes out of the scene."
MOVING_ON = (
    "The player takes the way on this scene offered. PLAYER ACTION is where they mean to go. "
    "Play their leaving if nothing stops them. Then call `next_scene` with `pursuit` in their "
    "own words. The crossing is written after this turn."
)

WAY_OFFERED = Fact(
    trace=(
        "this scene offers a way on. Ask the player what they want to pursue next — in the "
        "fiction, naming what the scene left open, never as a list of choices. They may also "
        "stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)

SCENE_LEFT = Fact(
    trace=(
        "the player has left this place; close the scene on their going and describe nothing "
        "of where they arrive: the crossing is written next"
    ),
    told=True,
)


class Enter(Frozen):
    target_id: Slug = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    target_id: Slug = Field(description="Exact id of someone here.")


class NextScene(Frozen):
    pursuit: str = Field(
        default="",
        description="Where the player is going, in their own words. Empty to offer the way on.",
    )
    complication: str = Field(
        default="",
        description="What arrives or turns here, and why. Empty otherwise.",
    )

    @model_validator(mode="after")
    def _one_or_none(self) -> Self:
        if self.pursuit and self.complication:
            raise ValueError("a pursuit or a complication, not both")
        return self
