from pydantic import Field

from aidm.core.entities import Frozen, Slug

ACTOR = "Exact id of a hired party member here who acts. Null for the player."


class Attempt(Frozen):
    what: str = Field(
        min_length=1,
        description="The attempt, in a few words the player reads.",
    )


class Reveal(Frozen):
    target_id: Slug = Field(description="Exact id of something hidden here.")


class Kill(Frozen):
    target_id: Slug = Field(description="Exact id of who here died.")


class JoinParty(Frozen):
    target_id: Slug = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    target_id: Slug = Field(description="Exact id of the party member leaving.")
