from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Slug
from aidm.engines.base import Person


class SceneDraft[C: Person](Frozen):
    """Ids arrive as free text so a wrong one can match a cast name before it is refused."""

    place: Slug = Field(description="Where the scene is, read by the player.")
    title: str = Field(description="The scene's title, read by the player.")
    focus: str = Field(
        default="",
        description="What this scene is about, in one line the player reads, when one thing is; "
        "empty when the situation says it all.",
    )
    situation: str = Field(
        min_length=1,
        description="What the player sees and knows on arrival: where they are, why they are "
        "here, what is in front of them. Read to the player, so it holds nothing hidden.",
    )
    present: tuple[str, ...] = Field(
        default=(),
        description="Ids present in the scene now, read by the game master and by you, "
        "never the player.",
    )
    hidden: tuple[str, ...] = Field(
        default=(),
        description="Ids hidden here, read by the game master and by you, never the player.",
    )
    cast: dict[EntityId, C] = Field(
        default_factory=dict,
        description="New people and things, filed under their own id. An id already in THE "
        "WHOLE CAST re-files that person: their `brief` is rewritten and nothing else; their "
        "name and their sheet stay as the rules hold them. A `brief` reaches the narrator once "
        "the player has met its entry, so what they must not learn goes in `arc`.",
    )
    arc: str = Field(
        default="",
        description="The setup beyond this scene, for the game master and for you, never the "
        "player: pressures, motives, secrets, what may come. Revise it only when what happened "
        "warrants it; empty keeps it as it stands.",
    )


class NextDraft[C: Person](SceneDraft[C]):
    """A scene written in play."""

    recap: str = Field(
        min_length=1,
        description="One paragraph on the scene the player is leaving: what they did, what it "
        "cost, what they learned, what they missed. Read by the game master and by you, never "
        "by the player.",
    )
