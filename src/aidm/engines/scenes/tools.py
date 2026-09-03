from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen

NEXT_SCENE = (
    "Say this scene's question is settled. The player is then asked what they want to pursue, "
    "and their own words build the next scene. Do not answer for them."
)


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class Kill(Frozen):
    """Record that someone here has died."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


class JoinParty(Frozen):
    """A character here starts travelling with the player."""

    verb: Literal["join_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    """A companion stops travelling with the player."""

    verb: Literal["leave_party"]
    entity_id: CheckedEntityId = Field(description="Exact id of the companion leaving.")


class NextScene(Frozen):
    job_done: bool = Field(
        default=False,
        description="A campaign only: settling this scene also finishes the job the player "
        "walked out on.",
    )
    pursuit: str = Field(
        default="",
        description="Set when the player has left this place for good with its question open: "
        "where they are going, in their own words. Empty when the question settled here.",
    )


type SharedChange = Reveal | Enter | Leave | Kill
