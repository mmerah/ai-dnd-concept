from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, parse, parse_json
from aidm.core.facts import Fact
from aidm.core.io import decode, read_prompt
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    EngineHeader,
    Game,
    Generation,
    PackSelection,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Chapter, DecisionOption, Exchange, Mark, PendingOption, SpokenLine
from aidm.core.prompt import Sections
from aidm.core.tools import MasterTool, master_tool
from aidm.core.views import Companion, Look, NarratorView, PlayerView, Rows
from aidm.engines.base import (
    JOIN_PARTY,
    KILL,
    LEAVE_PARTY,
    PLAYER_ID,
    REVEAL,
    JoinParty,
    Kill,
    LeaveParty,
    Person,
    Reveal,
    World,
    render_worldsmith,
)
from aidm.engines.hiring import HIRE, HIRE_TOOL, HIRE_UNWRITTEN, SIGNED_ON, Hire, Hiring

type AnyEngine = Engine[Any, Any, Any]


@dataclass(frozen=True, slots=True)
class Written:
    """What a worldsmith write leaves: the facts, and what to tell the narrator, if anything."""

    facts: tuple[Fact, ...]
    telling: str | None


@dataclass(frozen=True, slots=True)
class Request[G: Game[Any]]:
    """What a failed write tells the player, and the write itself."""

    unwritten: Fact
    write: Callable[[G, Generation, WorldsmithAnswer], Awaitable[Written]]


class Engine[P: Person, M: Person, G: Game[Any]](ABC):
    # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    art_style: str
    look: Look
    directory: Path  # rules.md; a scene engine's packs/
    family_dir: Path
    game: type[G]
    member: type[M]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    instructions: str
    tools: dict[str, MasterTool[G]]
    requests: dict[Slug, Request[G]]

    def __init__(self) -> None:
        self.instructions = (
            f"{read_prompt(self.directory / 'rules.md')}\n"
            f"{read_prompt(self.family_dir / 'rules.md')}"
        )
        tools = self.master_tools()
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError(f"the {self.id!r} engine names a tool twice: {names}")
        self.tools = {tool.name: tool for tool in tools}
        self.requests = self.worldsmith_requests()

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        """Each layer adds its own after `super()`'s: the seam, then the family, then the engine."""
        shared = (
            master_tool("reveal", REVEAL, Reveal, self.reveal),
            master_tool("kill", KILL, Kill, self.kill),
            master_tool("join_party", JOIN_PARTY, JoinParty, self.join_party),
            master_tool("leave_party", LEAVE_PARTY, LeaveParty, self.leave_party),
        )
        if self.hiring() is None:
            return shared
        return (*shared, master_tool("hire", HIRE_TOOL, Hire, self.hire))

    def reveal(self, draft: G, args: Reveal, _rng: Random) -> list[Fact]:
        return self.world_of(draft).reveal_hidden(args.entity_id)

    def kill(self, draft: G, args: Kill, _rng: Random) -> list[Fact]:
        return self.world_of(draft).kill(args.entity_id)

    def join_party(self, draft: G, args: JoinParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).join_party(args.entity_id)

    def leave_party(self, draft: G, args: LeaveParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).leave_party(args.entity_id)

    def hiring(self) -> Hiring[G, M] | None:
        """The write of a hired member's sheet; `None` when this engine hires nobody."""
        return None

    def hire(self, draft: G, args: Hire, _rng: Random) -> list[Fact]:
        member = self.world_of(draft).require_hireable(args.entity_id)
        draft.generation = Generation(operation=HIRE, detail=args.terms, target=member.id)
        trace = (
            f"the worldsmith writes {member.name}'s sheet once this turn ends: {args.terms}. "
            "Nothing more lands this turn; stop and exit"
        )
        return [Fact(trace=trace)]

    async def write_hire(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        hiring = self.hiring()
        if hiring is None:
            raise ValueError(f"the {self.id!r} engine hires nobody")
        if request.target is None:
            raise Refusal("a hire request names no target")
        member = self.world_of(draft).require_hireable(request.target)
        summary = await hiring(draft, member, request.detail, worldsmith)
        world = self.world_of(draft)
        facts = world.join(member) if member.id not in world.party else []
        trace = f"{member.mention} signs on — {summary}"
        facts.append(member.fact(trace, card=f"{member.name} signs on — {summary}"))
        return Written(tuple(facts), SIGNED_ON.format(name=member.name))

    async def advance(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        """Write and install on `draft`; the facts, and what to tell the narrator, if anything."""
        return await self.requests[request.operation].write(draft, request, worldsmith)

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def preview_character(self, character: AnyCharacter) -> Rows:
        return self.player_of(character).rows()

    def companions(self, state: G) -> tuple[Companion, ...]:
        return tuple(
            Companion(
                id=member.id,
                label=member.name,
                detail=member.brief,
                sheet=member.rows(),
                chattiness=member.chattiness,
            )
            for member in self.world_of(state).members()
        )

    def restore(self, raw: str) -> G:
        if (header := parse(EngineHeader, decode(raw))).engine != self.id:
            raise Refusal(f"the save plays {header.engine!r}, not {self.id!r}")
        state = parse_json(self.game, raw)
        self.validate(state)
        return state

    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = self.tools.get(chosen.name)
        if found is None:
            raise Refusal(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)

    def render_request(
        self, draft: G, *, intent: str, guidance: str, answer: type[BaseModel]
    ) -> str:
        world = self.world_of(draft)
        return render_worldsmith(
            role=read_prompt(self.family_dir / "worldsmith.md"),
            source=world.source,
            scope=draft.scenario.scope,
            family=self.family_sections(draft),
            intent=intent,
            guidance=guidance,
            answer=answer,
        )

    def render_opening(
        self, source: str, scope: str, *, intent: str, guidance: str, answer: type[BaseModel]
    ) -> str:
        return render_worldsmith(
            role=read_prompt(self.family_dir / "worldsmith.md"),
            source=source,
            scope=scope,
            family=self.family_sections(None),
            intent=intent,
            guidance=guidance,
            answer=answer,
        )

    def build_scenario(
        self,
        meta: ScenarioMeta,
        packs: PackSelection | None,
        draft: BaseModel,
        source: str,
        premise: str,
    ) -> AnyScenario:
        """No check here: `begin` is the one check an opening meets, and `check` always runs it."""
        return self.scenario(
            meta=meta.with_premise(premise),
            engine=self.id,
            packs=packs,
            source=source,
            payload=draft,
        )

    def close(
        self,
        draft: G,
        lines: tuple[SpokenLine, ...],
        facts: tuple[Fact, ...],
        *,
        words: str = "",
        mark: Mark = "",
        proposal: str = "",
    ) -> G:
        exchange = Exchange(
            words=words,
            mark=mark,
            lines=lines,
            facts=facts,
            decision="" if draft.pending is None else draft.pending.prompt,
            proposal=proposal,
        )
        draft.log[-1].exchanges.append(exchange)
        return self.land(draft)

    def open_chapter(self, draft: G) -> None:
        """The title and focus the narrator sees are the ones the history keeps."""
        if draft.log and not draft.log[-1].exchanges:
            draft.log.pop()
        view = self.narrator_view(draft)
        draft.log.append(Chapter(title=view.title, focus=view.focus))

    def land(self, draft: G) -> G:
        self.validate(draft)
        return draft.commit()

    def begin(self, scenario_id: Slug, scenario: AnyScenario, character: AnyCharacter) -> G:
        if scenario.engine != self.id:
            raise Refusal(
                f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
                f"which the {self.id!r} engine does not play"
            )
        if character.engine != self.id:
            raise Refusal(
                f"{character.id!r} is written for the {character.engine!r} rules, "
                f"which the {self.id!r} engine does not play"
            )
        state = parse(
            self.game,
            {
                "scenario_id": scenario_id,
                "character_id": character.id,
                "scenario": scenario.meta,
                "engine": self.id,
                "packs": scenario.packs,
                "payload": self.new_game(scenario, character),
            },
        )
        self.open_chapter(state)
        return self.land(state)

    def player_of(self, character: AnyCharacter) -> P:
        if character.payload.id != PLAYER_ID or not character.payload.known:
            raise Refusal("a character sheet is the player's: id 'player', known")
        return deepcopy(character.payload)

    def over(self, state: G) -> str | None:
        return "You died." if not self.world_of(state).player.alive else None

    def validate(self, state: G) -> None:
        """Refuse a state this engine cannot play; a family adds its check after `super()`."""
        if not state.log:
            raise Refusal(f"a {self.id!r} game has no chapter open")
        request = state.generation
        if request is not None and request.operation not in self.requests:
            raise Refusal(f"the {self.id!r} engine writes no {request.operation!r}")

    @abstractmethod
    def creation_steps(self, picks: Picks, /) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def create_character(self, name: str, brief: str, picks: Picks, /) -> AnyCharacter: ...
    @abstractmethod
    def world_of(self, state: G) -> World[M, P]: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> World[M, P]: ...
    @abstractmethod
    def master_sections(self, state: G) -> Sections: ...
    @abstractmethod
    def family_sections(self, draft: G | None) -> Sections: ...

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        """Each layer adds its own after `super()`'s: the seam's `hire`, then the family."""
        if self.hiring() is None:
            return {}
        return {HIRE: Request(HIRE_UNWRITTEN, self.write_hire)}

    @abstractmethod
    def narrator_view(self, state: G) -> NarratorView: ...
    @abstractmethod
    def player_view(self, state: G) -> PlayerView: ...
    @abstractmethod
    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: PackSelection | None,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario: ...
    @abstractmethod
    def act(self, draft: G, action: Slug, words: str, /) -> None:
        """The page's action against the state now: refuse it stale, else request or note."""


async def compose[M: BaseModel](
    worldsmith: WorldsmithAnswer,
    prompt: str,
    model: type[M],
    build: Callable[[M], AnyScenario],
    check: Callable[[AnyScenario], None],
) -> AnyScenario:
    return build(await worldsmith(prompt, model, lambda answer: check(build(answer))))
