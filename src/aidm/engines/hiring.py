from abc import abstractmethod
from random import Random
from typing import Any

from pydantic import BaseModel, Field

from aidm.core.entities import Frozen, Mutable, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import Game, Generation, Objection, WorldsmithAnswer
from aidm.core.tools import MasterTool, master_tool
from aidm.engines.base import Person
from aidm.engines.seam import Engine

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


class ItemSheet[I: BaseModel](Mutable):
    items: dict[Slug, I] = Field(default_factory=dict)

    def require(self, item_id: Slug, owner: str) -> I:
        item = self.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {owner}'s items")
        return item

    def drop(self, item_id: Slug, owner: str) -> I:
        item = self.require(item_id, owner)
        del self.items[item_id]
        return item


class Hire(Frozen):
    entity_id: Slug = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )


class DropItem(Frozen):
    item_id: Slug = Field(description="Exact id of an item the actor carries.")
    actor_id: Slug | None = Field(default=None, description=ACTOR)


class Hiring[P: Person, M: Person, G: Game[Any], A: BaseModel](Engine[P, G]):
    """Bringing in someone whose sheet the worldsmith authors. List it first in the bases."""

    hire_answer: type[A]

    def hire(self, draft: G, args: Hire, _rng: Random) -> list[Fact]:
        member = self.hireable(draft, args.entity_id)
        draft.generation = Generation(operation=HIRE, brief=args.terms, target=member.id)
        trace = (
            f"the worldsmith writes {member.name}'s sheet once this turn ends: {args.terms}. "
            "Nothing more lands this turn; stop and exit"
        )
        return [Fact(trace=trace)]

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (*super().master_tools(), master_tool("hire", HIRE_TOOL, Hire, self.hire))

    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        if request.operation != HIRE:
            return await super().advance(draft, request, worldsmith)
        member = self.hireable(draft, request.require_target())
        answer = await worldsmith(
            self.hire_prompt(draft, member, request.brief), self.hire_answer, self.hire_bar(draft)
        )
        summary = self.install_sheet(member, answer)
        world = self.world(draft)
        facts = world.join(member) if member.id not in world.party else []
        trace = f"{member.mention} signs on — {summary}"
        facts.append(member.fact(trace, card=f"{member.name} signs on — {summary}"))
        return tuple(facts), SIGNED_ON.format(name=member.name)

    def hire_bar(self, _draft: G) -> Objection[A]:
        return lambda _answer: None

    @abstractmethod
    def hireable(self, draft: G, entity_id: Slug) -> M: ...
    @abstractmethod
    def hire_prompt(self, draft: G, member: M, terms: str) -> str: ...
    @abstractmethod
    def install_sheet(self, member: M, answer: A) -> str:
        """Write the sheet onto the member; the summary the sign-on is told in."""
