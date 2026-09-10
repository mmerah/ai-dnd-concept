from abc import abstractmethod
from random import Random
from typing import Any, ClassVar, Self

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Mutable, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.model import Check, Game, Generation, WorldsmithAnswer
from aidm.engines.base import Person
from aidm.engines.scenes.world import SceneWorld
from aidm.engines.seam import Engine

HIRE: Slug = "hire"
ACTOR = "Exact id of a hired party member here who acts. Null for the player."
SIGNED_ON = "{name} has signed on with the player. Tell it in a line or two. Settle nothing else."
HIRE_TOOL = (
    "Call this when the player hires someone here to work. Someone already travelling with the "
    "player can be hired too. The worldsmith writes their sheet once the turn ends. Nothing "
    "more lands this turn."
)
HIRE_UNWRITTEN = Fact(
    told=True,
    trace="the hire could not be written",
    card="The hire could not be written; nobody signed on.",
)


class ItemSheet[I: BaseModel](Mutable):
    items: dict[EntityId, I] = Field(default_factory=dict)

    def require(self, item_id: EntityId, owner: str) -> I:
        item = self.items.get(item_id)
        if item is None:
            raise Refusal(f"{item_id!r} is not among {owner}'s items")
        return item

    def drop(self, item_id: EntityId, owner: str) -> I:
        item = self.require(item_id, owner)
        del self.items[item_id]
        return item


class Sheeted[S: BaseModel](Person):
    sheet: S | None = Field(default=None, description="Leave empty.")

    def dice(self) -> S:
        if self.sheet is None:
            raise Refusal(f"{self.name} carries no dice")
        return self.sheet

    def unwritten(self) -> str:
        parts = (super().unwritten(), "a sheet" if self.sheet is not None else "")
        return ", ".join(part for part in parts if part)


class SheetedWorld[C: Sheeted[Any], P: Sheeted[Any]](SceneWorld[C, P]):
    member_noun: ClassVar[str]

    @model_validator(mode="after")
    def _player_carries_a_sheet(self) -> Self:
        if self.player.sheet is None:
            raise ValueError("the player carries no sheet")
        return self

    def require_actor(self, actor_id: EntityId | None) -> C | P:
        if actor_id is None or actor_id == self.player.id:
            return self.player
        entity = self.require(actor_id)
        if entity.alive and entity.sheet is not None and entity.id in self.party:
            return entity
        raise Refusal(f"{entity.name} is not the player or a hired {self.member_noun}")

    def require_hireable(self, entity_id: EntityId) -> C | P:
        member = self.require_here(entity_id, alive=True)
        if member.sheet is not None:
            raise Refusal(f"{member.name} already carries a sheet")
        return member


class Hire(Frozen):
    entity_id: CheckedEntityId = Field(description="Exact id of who here signs on.")
    terms: str = Field(
        min_length=1,
        description="What they are hired for, and on what terms, as agreed.",
    )


class Hiring[P: Person, M: Person, G: Game[Any], A: BaseModel](Engine[P, G]):
    """Bringing in someone whose sheet the worldsmith authors. List it first in the bases."""

    hire_answer: type[A]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if HIRE not in cls.operations:
            cls.operations = (*cls.operations, HIRE)

    def hire(self, draft: G, args: Hire, _rng: Random) -> list[Fact]:
        member = self.hireable(draft, args.entity_id)
        draft.generation = Generation(operation=HIRE, brief=args.terms, target=member.id)
        trace = (
            f"the worldsmith writes {member.name}'s sheet once this turn ends: {args.terms}. "
            "Nothing more lands this turn; stop and exit"
        )
        return [Fact(trace=trace)]

    def unwritten(self, request: Generation) -> Fact:
        return HIRE_UNWRITTEN if request.operation == HIRE else super().unwritten(request)

    def validate(self, state: G) -> None:
        super().validate(state)
        generation = state.generation
        if generation is not None and generation.operation == HIRE:
            self.hireable(state, _hire_target(generation))

    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        if request.operation != HIRE:
            return await super().advance(draft, request, worldsmith)
        member = self.hireable(draft, _hire_target(request))
        answer = await worldsmith(
            self.hire_prompt(draft, member, request.brief), self.hire_answer, self.hire_bar(draft)
        )
        summary = self.install_sheet(draft, member, answer)
        world = self.world(draft)
        facts = world.join(member) if member.id not in world.party else []
        trace = f"{member.mention} signs on — {summary}"
        facts.append(member.fact(trace, card=f"{member.name} signs on — {summary}"))
        return tuple(facts), SIGNED_ON.format(name=member.name)

    def hire_bar(self, draft: G) -> Check[A]:
        return lambda _answer: None

    @abstractmethod
    def hireable(self, draft: G, entity_id: EntityId) -> M: ...
    @abstractmethod
    def hire_prompt(self, draft: G, member: M, terms: str) -> str: ...
    @abstractmethod
    def install_sheet(self, draft: G, member: M, answer: A) -> str:
        """Write the sheet onto the member; the summary the sign-on is told in."""


def _hire_target(request: Generation) -> EntityId:
    if request.target is None:
        raise Refusal("a hire names who signs on")
    return request.target
