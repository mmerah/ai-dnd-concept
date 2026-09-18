from pydantic import Field

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact

ACTOR = "Exact id of a hired party member here who acts. Null for the player."
HIRE: Slug = "hire"
SIGNED_ON = "{name} has signed on with the player. Tell it in a line or two. Settle nothing else."
HIRED = "The player has hired {name}, {brief}, on these terms: {terms}. "
UNWRITTEN_CAST = (
    "The cast carries no dice until the player hires them in play. An npc is a name, a brief, "
    "and whether the player has met them. A threat is a brief that the player's own roll meets, "
    "never a stat block. "
)
HIRE_PENDING = (
    "the worldsmith writes {name}'s sheet once this turn ends: {terms}. Nothing more lands this "
    "turn; stop and exit"
)
NO_HIRE_TARGET = "a hire request names no target"
SIGNS_ON = "{who} signs on — {summary}"
HIRE_UNWRITTEN = Fact(
    told=True,
    trace="the hire could not be written",
    card="The hire could not be written; nobody signed on.",
)


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


class Hire(Frozen):
    target_id: Slug = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )
