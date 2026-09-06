from typing import Literal

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines.base import JoinParty, LeaveParty

NEXT_SCENE = (
    "Call this with nothing set when the scene reaches a stopping point. Set `pursuit` instead "
    "once the player has left this place. Set `complication` instead to bring a new situation "
    "down on this place."
)


class Reveal(Frozen):
    """A hidden entity here becomes known to the player."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


class Enter(Frozen):
    """A cast member comes into the scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """A cast member goes out of the scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class Kill(Frozen):
    """Someone here dies."""

    verb: Literal["kill"]
    entity_id: CheckedEntityId = Field(description="Exact id of who here died.")


class NextScene(Frozen):
    pursuit: str = Field(
        default="",
        description="Where the player is going, in their own words. Empty to offer the way on.",
    )
    complication: str = Field(
        default="",
        description="What arrives or turns here, and why. Empty otherwise.",
    )


type SharedChange = Reveal | Enter | Leave | Kill | JoinParty | LeaveParty
