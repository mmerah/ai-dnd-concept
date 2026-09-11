from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Mutable, Slug
from aidm.engines.base import Person

NEXT_SCENE = (
    "Call this with nothing set when the scene reaches a stopping point. Set `pursuit` instead "
    "once the player has left this place. Set `complication` instead to bring a new situation "
    "down on this place."
)
ENTER = "A cast member comes into the scene."
LEAVE = "A cast member goes out of the scene."


class Enter(Frozen):
    entity_id: Slug = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    entity_id: Slug = Field(description="Exact id of someone here.")


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


class SceneDraft[C: Person](Mutable):
    """The next scene the player walks into."""

    place: Slug = Field(description="Slug naming the place. Reuse it when the player returns here.")
    title: str = Field(description="The scene's title, read by the player.")
    focus: str = Field(
        default="",
        description="What this scene is about, in one line the player reads. Empty when the "
        "situation says it all.",
    )
    situation: str = Field(
        min_length=1,
        description="What the player sees and knows on arrival. Hold nothing hidden here.",
    )
    present: tuple[str, ...] = Field(
        default=(), description="Ids of who and what is in the scene now."
    )
    hidden: tuple[str, ...] = Field(default=(), description="Ids of what is hidden here.")
    cast: dict[Slug, C] = Field(
        default_factory=dict,
        description="New people and things, each filed under its own id.",
    )
    arc: str = Field(
        default="",
        description="The setup beyond this scene: pressures, motives, secrets, what can come. "
        "The player never reads it.",
    )


class NextDraft[C: Person](SceneDraft[C]):
    recap: str = Field(
        min_length=1,
        description="One paragraph on the scene the player leaves: what they did, cost, "
        "learned and missed.",
    )
