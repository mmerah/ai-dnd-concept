from pydantic import Field

from aidm.core.entities import Frozen, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import AnyGame, Commission
from aidm.engines.base import Person, World
from aidm.engines.engine import Written

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
ALREADY_SHEETED = "{name} already carries a sheet"
SIGNS_ON = "{who} signs on — {summary}"
HIRE_UNWRITTEN = Fact(
    told=True,
    trace="the hire could not be written",
    card="The hire could not be written; nobody signed on.",
)


class Hire(Frozen):
    target_id: Slug = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )


def require_hireable[M: Person](world: World[M], entity_id: Slug) -> M:
    member = world.require_member_here(entity_id)
    if member.hired:
        raise Refusal(ALREADY_SHEETED.format(name=member.name))
    return member


def hire_target[M: Person](world: World[M], commission: Commission) -> M:
    if commission.target is None:
        raise Refusal(NO_HIRE_TARGET)
    return require_hireable(world, commission.target)


def file_hire(draft: AnyGame, target_id: Slug, terms: str) -> list[Fact]:
    member = require_hireable(draft.world, target_id)
    draft.commission = Commission(operation=HIRE, detail=terms, target=member.id)
    return [Fact(trace=HIRE_PENDING.format(name=member.name, terms=terms))]


def signed_on[M: Person](world: World[M], member: M, summary: str) -> Written:
    facts = world.join(member) if member.id not in world.party else []
    facts.append(
        member.fact(
            SIGNS_ON.format(who=member.mention, summary=summary),
            card=SIGNS_ON.format(who=member.name, summary=summary),
        )
    )
    return Written(tuple(facts), SIGNED_ON.format(name=member.name))
