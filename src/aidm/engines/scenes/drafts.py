from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Slug
from aidm.engines.base import Person


class SceneDraft[C: Person](Frozen):
    """The next scene the player walks into."""

    place: Slug = Field(description="Slug naming the place. Reuse it when the player returns here.")
    title: str = Field(description="The scene's title, read by the player.")
    focus: str = Field(
        default="",
        description="What this scene is about, in one line the player reads. Can be empty.",
    )
    situation: str = Field(
        min_length=1,
        description="What the player sees and knows on arrival. Hold nothing hidden here.",
    )
    present: tuple[str, ...] = Field(
        default=(), description="Ids of who and what is in the scene now."
    )
    hidden: tuple[str, ...] = Field(default=(), description="Ids of what is hidden here.")
    cast: dict[EntityId, C] = Field(
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
