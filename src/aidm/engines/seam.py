from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks, check_picks
from aidm.core.entities import EngineId, Refusal, Slug, parse, parse_json, slug
from aidm.core.facts import Fact
from aidm.core.io import decode, read_cached_text, read_model
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
from aidm.core.prompt import Sections, sections
from aidm.core.tools import MasterTool, master_tool, schema_text
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
)
from aidm.engines.hiring import HIRE, HIRE_TOOL, HIRE_UNWRITTEN, SIGNED_ON, Hire

SOURCELESS = "(none — write from what is below)"

type AnyEngine = Engine[Any, Any, Any]


@dataclass(frozen=True, slots=True)
class Written:
    facts: tuple[Fact, ...]
    telling: str | None


@dataclass(frozen=True, slots=True)
class Request[G: Game[Any]]:
    unwritten: Fact
    write: Callable[[G, Generation, WorldsmithAnswer], Awaitable[Written]]


class Engine[P: Person, M: Person, G: Game[Any]](ABC):
    # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    art_style: str
    meanwhile_turns: int = 6
    hires: bool = False
    directory: Path  # rules.md; a scene engine's packs/
    family_dir: Path
    opening_sections: Sections
    game: type[G]
    member: type[M]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    # Derived by __init__ from the above.
    instructions: str
    look: Look
    tools: dict[str, MasterTool[G]]
    requests: dict[Slug, Request[G]]

    def __init__(self) -> None:
        self.instructions = (
            f"{read_cached_text(self.directory / 'rules.md')}\n"
            f"{read_cached_text(self.family_dir / 'rules.md')}"
        )
        self.look = read_model(self.directory / "look.json", Look)
        tools = self.master_tools()
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError(f"the {self.id!r} engine names a tool twice: {names}")
        if self.meanwhile_turns < 2:
            raise ValueError(f"the {self.id!r} engine ticks every {self.meanwhile_turns} turns")
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
        if not self.hires:
            return shared
        return (*shared, master_tool("hire", HIRE_TOOL, Hire, self.hire))

    def worldsmith_requests(self) -> dict[Slug, Request[G]]:
        if not self.hires:
            return {}
        return {HIRE: Request(HIRE_UNWRITTEN, self.write_hire)}

    def reveal(self, draft: G, args: Reveal, _rng: Random) -> list[Fact]:
        return self.world_of(draft).reveal_hidden(args.entity_id)

    def kill(self, draft: G, args: Kill, _rng: Random) -> list[Fact]:
        return self.world_of(draft).kill(args.entity_id)

    def join_party(self, draft: G, args: JoinParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).join_party(args.entity_id)

    def leave_party(self, draft: G, args: LeaveParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).leave_party(args.entity_id)

    async def write_sheet(
        self, _draft: G, _member: M, _terms: str, _worldsmith: WorldsmithAnswer, /
    ) -> str:
        raise ValueError(f"the {self.id!r} engine hires nobody")

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
        if request.target is None:
            raise Refusal("a hire request names no target")
        member = self.world_of(draft).require_hireable(request.target)
        summary = await self.write_sheet(draft, member, request.detail, worldsmith)
        world = self.world_of(draft)
        facts = world.join(member) if member.id not in world.party else []
        trace = f"{member.mention} signs on — {summary}"
        facts.append(member.fact(trace, card=f"{member.name} signs on — {summary}"))
        return Written(tuple(facts), SIGNED_ON.format(name=member.name))

    async def advance(self, draft: G, request: Generation, worldsmith: WorldsmithAnswer) -> Written:
        return await self.requests[request.operation].write(draft, request, worldsmith)

    def supplement_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def select_packs(self, _supplements: Sequence[Slug]) -> PackSelection | None:
        return None

    def admit(self, _packs: PackSelection | None, _character: AnyCharacter) -> None:
        """Refuse a character these packs cannot start; the seam admits anyone."""
        return

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
        if state.generation is not None:
            raise Refusal("the save carries a pending generation request")
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
        family = self.family_sections(draft)
        return self._render(world.source, draft.scenario.scope, family, intent, guidance, answer)

    def render_opening(
        self, source: str, scope: str, *, intent: str, guidance: str, answer: type[BaseModel]
    ) -> str:
        return self._render(source, scope, self.opening_sections, intent, guidance, answer)

    def _render(
        self,
        source: str,
        scope: str,
        family: Sections,
        intent: str,
        guidance: str,
        answer: type[BaseModel],
    ) -> str:
        return sections(
            (
                ("YOUR ROLE", read_cached_text(self.family_dir / "worldsmith.md")),
                ("SOURCE MATERIAL", source or SOURCELESS),
                ("THE SCOPE OF PLAY", scope),
                *family,
                ("WHAT COMES NEXT", intent),
                ("ENGINE GUIDANCE", guidance),
                ("ANSWER WITH", schema_text(answer)),
            )
        )

    def sheet_character(
        self, name: str, payload: BaseModel, packs: PackSelection | None = None
    ) -> AnyCharacter:
        return self.character(id=slug(name, ()), engine=self.id, packs=packs, payload=payload)

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

    def tick(self, draft: G, *, counted: bool) -> None:
        """One player turn against the clock; a family spends the flag by overriding this."""
        if counted:
            self.world_of(draft).count_turn(self.meanwhile_turns)

    def disarm(self, state: G) -> None:
        self.world_of(state).disarm()

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

    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter:
        check_picks(self.creation_steps(picks), picks)
        return self.build_character(name, brief, picks)

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
    def build_character(self, name: str, brief: str, picks: Picks, /) -> AnyCharacter: ...
    @abstractmethod
    def world_of(self, state: G) -> World[M, P]: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> World[M, P]: ...
    @abstractmethod
    def master_sections(self, state: G) -> Sections: ...
    @abstractmethod
    def family_sections(self, draft: G, /) -> Sections: ...
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
