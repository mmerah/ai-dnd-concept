from pydantic import Field

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact

REVEAL = "A hidden entity here becomes known to the player."
KILL = "Someone here dies."
JOIN_PARTY = "A character here starts travelling with the player."
LEAVE_PARTY = "A party member stops travelling with the player."
ACTOR = "Exact id of a hired party member here who acts. Null for the player."
DROP_ITEM = "The actor loses an item for good."
HIRE: Slug = "hire"
SIGNED_ON = "{name} has signed on with the player. Tell it in a line or two. Settle nothing else."
HIRED = "The player has hired {name}, {brief}, on these terms: {terms}. "
UNWRITTEN_CAST = (
    "The cast carries no dice until the player hires them in play. An npc is a name, a brief, "
    "and whether the player has met them. A threat is a brief that the player's own roll meets, "
    "never a stat block. "
)
HIRE_TOOL = (
    "Call this when the player hires someone here to work. Someone already travelling with the "
    "player can be hired too. The worldsmith writes their sheet once the turn ends. Nothing "
    "more lands this turn. A sheet is for someone hired to work, never for one who only comes "
    "along."
)
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
    entity_id: Slug = Field(description="Exact id of something hidden here.")


class Kill(Frozen):
    entity_id: Slug = Field(description="Exact id of who here died.")


class JoinParty(Frozen):
    entity_id: Slug = Field(description="Exact id of who is joining.")


class LeaveParty(Frozen):
    entity_id: Slug = Field(description="Exact id of the party member leaving.")


class DropItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class AskWorld(Frozen):
    question: str = Field(
        min_length=1, description="A closed question about the world where nobody is acting."
    )


class Hire(Frozen):
    entity_id: Slug = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )
