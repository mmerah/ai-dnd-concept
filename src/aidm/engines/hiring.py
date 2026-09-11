from abc import abstractmethod
from random import Random
from typing import Any

from pydantic import BaseModel, Field

from aidm.core.entities import Frozen, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import Check, Game, Generation, WorldsmithAnswer
from aidm.core.tools import MasterTool, master_tool
from aidm.engines.base import Person
from aidm.engines.seam import Engine, Request, Written

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


class Hiring[P: Person, M: Person, G: Game[Any], A: BaseModel](Engine[P, G]):
    """Bringing in someone whose sheet the worldsmith authors."""

    member: type[M]
    hire_answer: type[A]

    def hire(self, draft: G, args: Hire, _rng: Random) -> list[Fact]:
        member = self.hireable(draft, args.entity_id)
        draft.generation = Generation(operation=HIRE, detail=args.terms, target=member.id)
        trace = (
            f"the worldsmith writes {member.name}'s sheet once this turn ends: {args.terms}. "
            "Nothing more lands this turn; stop and exit"
        )
        return [Fact(trace=trace)]

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        return (*super().master_tools(), master_tool("hire", HIRE_TOOL, Hire, self.hire))

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        return {**super().worldsmith_requests(), HIRE: Request(HIRE_UNWRITTEN, self.write_hire)}

    async def write_hire(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        if request.target is None:
            raise Refusal("a hire request names no target")
        member = self.hireable(draft, request.target)
        answer = await worldsmith(
            self.hire_prompt(draft, member, request.detail),
            self.hire_answer,
            self.hire_check(draft),
        )
        summary = self.install_sheet(member, answer)
        world = self.world(draft)
        facts = world.join(member) if member.id not in world.party else []
        trace = f"{member.mention} signs on — {summary}"
        facts.append(member.fact(trace, card=f"{member.name} signs on — {summary}"))
        return tuple(facts), SIGNED_ON.format(name=member.name)

    def hire_check(self, _draft: G) -> Check[A]:
        return lambda _answer: None

    def hireable(self, draft: G, entity_id: Slug) -> M:
        member = self.world(draft).require_hireable(entity_id)
        if not isinstance(member, self.member):
            raise ValueError(f"{member.id!r} is not a {self.member.__name__}")
        return member

    @abstractmethod
    def hire_prompt(self, draft: G, member: M, terms: str) -> str: ...
    @abstractmethod
    def install_sheet(self, member: M, answer: A) -> str:
        """Write the sheet onto the member; the summary the sign-on is told in."""
