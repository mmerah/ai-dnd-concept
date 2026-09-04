from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Slug
from aidm.engines.base import Person
from aidm.engines.hub import MIN_JOB, MIN_RECAP, MIN_SUMMARY, Board

MIN_SITUATION = 80  # what the worldsmith owes a scene; an authored `Scene` is held to less
MIN_ARC = 60
RECAP = Field(
    min_length=MIN_RECAP,
    description="One paragraph on the scene the player is leaving: what they did, what it "
    "cost, what they learned, what they missed. Read by the game master and by you, never "
    "by the player.",
)


class SceneDraft[C: Person](Frozen):
    """Ids arrive as free text so a wrong one can match a cast name before it is refused."""

    place: Slug = Field(description="Where the scene is, read by the player.")
    title: str = Field(description="The scene's title, read by the player.")
    question: str = Field(min_length=10, description="What this scene settles, read by the player.")
    situation: str = Field(
        min_length=MIN_SITUATION,
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
        description="A few lines on what lies beyond this scene, for the game master and for "
        "you, never the player: who waits farther in, what the job hides, how it can end.",
    )


class NextDraft[C: Person](SceneDraft[C]):
    """A scene written in play, away from a return."""

    recap: str = RECAP
    arc: str = Field(
        min_length=MIN_ARC,
        description="A few lines on what lies beyond this scene, for the game master and for "
        "you, never the player: who waits farther in, what the job hides, how it can end. "
        "Rewritten every scene so it follows what happened.",
    )


class JobDraft[C: Person](NextDraft[C]):
    """The scene that leaves the hub: its recap is the hub visit."""

    job: str = Field(
        min_length=MIN_JOB,
        description="Who wants what done, what done looks like, what it pays; read by the "
        "player through the scene row and the card.",
    )


class HubDraft[C: Person](SceneDraft[C]):
    """The campaign's opening: the hub and its board."""

    offers: Board = Field(description="The board of offers, read by the player.")
    arc: str = Field(
        default="",
        description="A few lines on what lies beyond this scene, for the game master and for "
        "you, never the player: who waits farther in, what the job hides, how it can end. A "
        "campaign's hub leaves it empty.",
    )


class ReturnDraft[C: Person](HubDraft[C]):
    """The return home: the debrief is the paragraph; the verdict is the master's.

    One answer, two readers: debrief, situation and question are the player's; summary, recap
    and arc are not. Leaks in play make this two spawns.
    """

    debrief: str = Field(
        min_length=1,
        description="One paragraph on the job just left, in the second person and the "
        "present tense; read by the player.",
    )
    summary: str = Field(
        min_length=MIN_SUMMARY,
        description="One paragraph on the job, in the third person, for the game master and "
        "for you, never the player: what was done, what was left undone, who was met and "
        "how it stands with them, what is owed, what was learned and what is still hidden.",
    )
    recap: str = RECAP


class CastDraft[C: Person](Frozen):
    """One commissioned entry; `arc` bends only where it must."""

    cast: dict[EntityId, C] = Field(
        min_length=1,
        max_length=1,
        description="One entry under its own id. A new id is a new person, thing or rumour, "
        "unmet; an id already in THE WHOLE CAST re-files that entry's brief and nothing else.",
    )
    arc: str = Field(
        default="",
        description="Rewritten only where it must bend to hold the new entry; empty keeps it.",
    )
