from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from aidm.core.entities import Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.model import Check, Game, WorldsmithAnswer
from aidm.engines.base import Person

HIRE: Slug = "hire"
ACTOR = "Exact id of a hired party member here who acts. Null for the player."
SIGNED_ON = "{name} has signed on with the player. Tell it in a line or two. Settle nothing else."
HIRE_TOOL = (
    "Call this when the player hires someone here to work. Someone already travelling with the "
    "player can be hired too. The worldsmith writes their sheet once the turn ends. Nothing "
    "more lands this turn. A sheet is for someone hired to work, never for one who only comes "
    "along."
)
DROP_ITEM = "The actor loses an item for good."
HIRE_UNWRITTEN = Fact(
    told=True,
    trace="the hire could not be written",
    card="The hire could not be written; nobody signed on.",
)


class Hire(Frozen):
    entity_id: Slug = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )


class DropItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


# The worldsmith's write of one member's sheet: the summary the sign-on is told in.
type Hiring[G: Game[Any], M: Person] = Callable[[G, M, str, WorldsmithAnswer], Awaitable[str]]


def _no_check[A: BaseModel](_draft: object) -> Check[A]:
    """A write whose only bar is its own schema."""

    def unchecked(_answer: A) -> None: ...

    return unchecked


def hiring[G: Game[Any], M: Person, A: BaseModel](
    answer: type[A],
    prompt: Callable[[G, M, str], str],
    install: Callable[[M, A], str],
    check: Callable[[G], Check[A]] = _no_check,
) -> Hiring[G, M]:
    async def write(draft: G, member: M, terms: str, worldsmith: WorldsmithAnswer) -> str:
        answered = await worldsmith(prompt(draft, member, terms), answer, check(draft))
        return install(member, answered)

    return write
