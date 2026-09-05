from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen

NEXT_SCENE = (
    "Offer the player the way on: this scene has reached a useful stopping point. They are "
    "then asked what they want to pursue, and their own words build the next scene; they may "
    "also stay. Do not answer for them. Set `pursuit` instead once the player has left this "
    "place. Or set `complication` to bring a new situation down on this place, only when "
    "`change_world` (an arrival, a reveal, a death) cannot make it from what is here."
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
    pursuit: str = Field(
        default="",
        description="Set when the player has left this place for good: where they are going, "
        "in their own words. Empty to offer the way on from here.",
    )
    complication: str = Field(
        default="",
        description="Set to change the situation here without the player leaving: what arrives "
        "or turns, and why, for the worldsmith. Written now, the turn ends; the player answers "
        "it next turn. Empty otherwise.",
    )


type SharedChange = Reveal | Enter | Leave | Kill | JoinParty | LeaveParty
