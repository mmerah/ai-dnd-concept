from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Slug
from aidm.engines.core import Person
from aidm.engines.hub import MIN_JOB, Board

MIN_SITUATION = 80  # what the worldsmith owes a scene; an authored `Scene` is held to less
MIN_RECAP = 60


class SceneDraft[C: Person](Frozen):
    """Ids arrive as free text so a wrong one can match a cast name before it is refused."""

    place: Slug
    title: str
    question: str = Field(min_length=10)
    situation: str = Field(
        min_length=MIN_SITUATION,
        description="What the player sees and knows on arrival: where they are, why they are "
        "here, what is in front of them. Read to the player, so it holds nothing hidden.",
    )
    present: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()
    cast: dict[EntityId, C] = Field(
        default_factory=dict,
        description="New people and things, filed under their own id. An id already in THE "
        "WHOLE CAST re-files that person: their `brief` is rewritten and nothing else; their "
        "name and their sheet stay as the rules hold them.",
    )


class NextDraft[C: Person](SceneDraft[C]):
    """A scene written in play, away from a return."""

    recap: str = Field(
        min_length=MIN_RECAP,
        description="One paragraph on the scene the player is leaving: what they did, what it "
        "cost, what they learned, what they missed. Read by the game master and by you, never "
        "by the player.",
    )


class JobDraft[C: Person](NextDraft[C]):
    """The scene that leaves the hub: its recap is the hub visit."""

    job: str = Field(min_length=MIN_JOB)


class HubDraft[C: Person](SceneDraft[C]):
    """The campaign's opening: the hub and its board."""

    offers: Board


class ReturnDraft[C: Person](HubDraft[C]):
    """The return home: the debrief is the paragraph; the verdict is the master's."""

    debrief: str = Field(min_length=1)
