import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel, JsonValue

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
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Chapter, DecisionOption, Exchange, Mark, PendingOption, SpokenLine
from aidm.core.prompt import Sections, sections
from aidm.core.tools import MasterTool, master_tool, schema_text
from aidm.core.views import Companion, Look, NarratorView, PlayerView, Rows
from aidm.engines.base import PLAYER_ID, Person, World
from aidm.engines.packs import (
    BODY_ASK,
    HEAD_ASK,
    PROVENANCE,
    SRD_PACK,
    Pack,
    PackBody,
    PackHead,
    PackSet,
    read_packs,
)
from aidm.engines.tools import (
    HIRE,
    HIRE_TOOL,
    HIRE_UNWRITTEN,
    JOIN_PARTY,
    KILL,
    LEAVE_PARTY,
    REVEAL,
    SIGNED_ON,
    Hire,
    JoinParty,
    Kill,
    LeaveParty,
    Reveal,
)

SOURCELESS = "(none — write from what is below)"
SCOPELESS = "(none — this is a pack, not a scenario: a genre kit, not one adventure)"
PACK_SO_FAR = "THE PACK SO FAR"

type AnyEngine = Engine[Any, Any, Any, Any]


@dataclass(frozen=True, slots=True)
class Written:
    facts: tuple[Fact, ...]
    telling: str | None


@dataclass(frozen=True, slots=True)
class Request[G: Game[Any]]:
    unwritten: Fact
    write: Callable[[G, Generation, WorldsmithAnswer], Awaitable[Written]]


class Engine[P: Person, M: Person, W: World[Any, Any], K: Pack](ABC):
    # Declared, not `ClassVar`: `type[W]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    authoring: str
    art_style: str
    hires: bool = False
    directory: Path  # rules.md, look.json and a shipped packs/
    family_dir: Path
    world: type[W]
    game: type[Game[W]]
    member: type[M]
    pack: type[K]
    head: type[PackHead] = PackHead
    body: type[PackBody] = PackBody
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    # Derived by __init__ from the above.
    packs: PackSet[K]
    instructions: str
    look: Look
    tools: dict[str, MasterTool[Game[W]]]
    requests: dict[Slug, Request[Game[W]]]

    def __init__(self, written: Path) -> None:
        self.packs = read_packs(self.id, self.directory / "packs", written, self.pack)
        self.packs.srd()  # an engine that ships no srd pack is a bug, not a refusal
        self.instructions = (
            f"{read_cached_text(self.directory / 'rules.md')}\n"
            f"{read_cached_text(self.family_dir / 'rules.md')}"
        )
        self.look = read_model(self.directory / "look.json", Look)
        tools = self.master_tools()
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError(f"the {self.id!r} engine names a tool twice: {names}")
        if self.world.tempo < 2:
            raise ValueError(f"the {self.id!r} engine ticks every {self.world.tempo} turns")
        self.tools = {tool.name: tool for tool in tools}
        self.requests = self.worldsmith_requests()

    def master_tools(self) -> tuple[MasterTool[Game[W]], ...]:
        """Each layer adds its own after `super()`'s: the seam, then the family, then the engine."""
        world_of = self.world_of
        return (
            master_tool(
                "reveal", REVEAL, Reveal, lambda d, a, _: world_of(d).reveal_hidden(a.target_id)
            ),
            master_tool("kill", KILL, Kill, self.kill),
            master_tool("join_party", JOIN_PARTY, JoinParty, self.join_party),
            master_tool("leave_party", LEAVE_PARTY, LeaveParty, self.leave_party),
            *((master_tool("hire", HIRE_TOOL, Hire, self.hire),) if self.hires else ()),
        )

    def worldsmith_requests(self) -> dict[Slug, Request[Game[W]]]:
        if not self.hires:
            return {}
        return {HIRE: Request(HIRE_UNWRITTEN, self.write_hire)}

    def kill(self, draft: Game[W], args: Kill, _rng: Random) -> list[Fact]:
        return self.world_of(draft).kill(args.target_id)

    def join_party(self, draft: Game[W], args: JoinParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).join_party(args.target_id)

    def leave_party(self, draft: Game[W], args: LeaveParty, _rng: Random) -> list[Fact]:
        return self.world_of(draft).leave_party(args.target_id)

    async def write_sheet(
        self, _draft: Game[W], _member: M, _terms: str, _worldsmith: WorldsmithAnswer, /
    ) -> str:
        raise ValueError(f"the {self.id!r} engine hires nobody")

    def hire(self, draft: Game[W], args: Hire, _rng: Random) -> list[Fact]:
        member = self.world_of(draft).require_hireable(args.target_id)
        draft.generation = Generation(operation=HIRE, detail=args.terms, target=member.id)
        trace = (
            f"the worldsmith writes {member.name}'s sheet once this turn ends: {args.terms}. "
            "Nothing more lands this turn; stop and exit"
        )
        return [Fact(trace=trace)]

    async def write_hire(
        self, draft: Game[W], request: Generation, worldsmith: WorldsmithAnswer
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

    async def advance(
        self, draft: Game[W], request: Generation, worldsmith: WorldsmithAnswer
    ) -> Written:
        return await self.requests[request.operation].write(draft, request, worldsmith)

    def install_pack(self, pack_id: Slug, pack: K) -> None:
        self.packs = self.packs.installing(pack_id, pack)

    def pack_of(
        self, head: PackHead, body: PackBody | None, *, name: str, origin: str, license: str
    ) -> K:
        """Every id the pack carries is made here, by code, from the labels the worldsmith wrote."""
        return parse(
            self.pack,
            {
                "name": name,
                "source": origin,
                "license": license,
                **head.pack_fields(),
                **({} if body is None else body.model_dump()),
            },
        )

    async def author_pack(
        self,
        pack_id: Slug,
        *,
        name: str,
        source: str,
        origin: str,
        license: str,
        worldsmith: WorldsmithAnswer,
    ) -> K:
        """Head, then body; each checked by building the pack; nothing is written here."""

        def built(from_head: PackHead, from_body: PackBody | None) -> K:
            return self.pack_of(from_head, from_body, name=name, origin=origin, license=license)

        def check_head(answer: PackHead) -> None:
            self.packs.check_addable(pack_id, built(answer, None))

        head = await worldsmith(
            self.render_worldsmith(source, "", (), HEAD_ASK, self.authoring, self.head),
            self.head,
            check_head,
        )
        so_far = ((PACK_SO_FAR, sections(built(head, None).sections(opening=True))),)

        def check_body(answer: PackBody) -> None:
            built(head, answer)

        body = await worldsmith(
            self.render_worldsmith(source, "", so_far, BODY_ASK, self.authoring, self.body),
            self.body,
            check_body,
        )
        return built(head, body)

    def edited(self, pack: K, values: Mapping[str, str]) -> K:
        """The boxes decoded over the pack's own dump; a field no box holds keeps its value."""
        dumped: dict[str, JsonValue] = pack.model_dump(mode="json")
        for field_id, box in values.items():
            if field_id in PROVENANCE:
                raise Refusal(f"{field_id} is the pack's own and is not edited here")
            try:
                dumped[field_id] = decode(box)
            except Refusal as refused:
                raise Refusal(f"{field_id}: {refused}") from refused
        # Through JSON, not `parse`: strict mode reads a tuple field from a JSON array alone.
        return parse_json(self.pack, json.dumps(dumped))

    def supplement_options(self) -> tuple[DecisionOption, ...]:
        return tuple(
            DecisionOption(id=key, label=pack.name) for key, pack in self.packs.supplements()
        )

    def select_packs(self, supplements: Sequence[Slug]) -> tuple[Slug, ...]:
        """The packs a choice selects, in order: every game plays its engine's SRD."""
        return self.packs.select((SRD_PACK, *supplements))

    def admit(self, packs: tuple[Slug, ...], character: AnyCharacter) -> None:
        """Refuse packs that cannot start a game and a character these packs cannot start."""
        self.packs.select(packs)
        if not set(character.packs) <= set(packs):
            raise Refusal(
                f"{character.id!r} was made with {', '.join(character.packs)}; "
                f"this scenario plays {', '.join(packs) or 'no pack'}"
            )

    def guidance(self, selection: tuple[Slug, ...], /, *, opening: bool) -> str:
        packs = self.packs.guidance(selection, opening=opening)
        return f"{self.authoring}\n\n{packs}" if packs else self.authoring

    def preview_character(self, character: AnyCharacter) -> Rows:
        return self.player_of(character).rows()

    def companions(self, state: Game[W]) -> tuple[Companion, ...]:
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

    def restore(self, raw: str) -> Game[W]:
        if (header := parse(EngineHeader, decode(raw))).engine != self.id:
            raise Refusal(f"the save plays {header.engine!r}, not {self.id!r}")
        state = parse_json(self.game, raw)
        if state.generation is not None:
            raise Refusal("the save carries a pending generation request")
        self.validate(state)
        self.packs.select(state.packs)
        return state

    def tool(self, name: str) -> MasterTool[Game[W]]:
        found = self.tools.get(name)
        if found is None:
            raise Refusal(f"{name!r} is not a tool of the {self.id!r} engine.")
        return found

    def answer(self, draft: Game[W], chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        return self.tool(chosen.name).call(draft, chosen.args, rng)

    def render_request(
        self, draft: Game[W], *, intent: str, guidance: str, answer: type[BaseModel]
    ) -> str:
        family = self.family_sections(draft)
        return self.render_worldsmith(
            draft.source, draft.scenario.scope, family, intent, guidance, answer
        )

    def render_worldsmith(
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
                ("THE SCOPE OF PLAY", scope or SCOPELESS),
                *family,
                ("WHAT COMES NEXT", intent),
                ("ENGINE GUIDANCE", guidance),
                ("ANSWER WITH", schema_text(answer)),
            )
        )

    def sheet_character(
        self, name: str, payload: BaseModel, packs: tuple[Slug, ...]
    ) -> AnyCharacter:
        return self.character(id=slug(name, ()), engine=self.id, packs=packs, payload=payload)

    def build_scenario(
        self,
        meta: ScenarioMeta,
        packs: tuple[Slug, ...],
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
        draft: Game[W],
        lines: tuple[SpokenLine, ...],
        facts: tuple[Fact, ...],
        *,
        words: str = "",
        mark: Mark = "",
        proposal: str = "",
    ) -> Game[W]:
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

    def open_chapter(self, draft: Game[W]) -> None:
        """The title and focus the narrator sees are the ones the history keeps."""
        if draft.log and not draft.log[-1].exchanges:
            draft.log.pop()
        view = self.narrator_view(draft)
        draft.log.append(Chapter(title=view.title, focus=view.focus))

    def land(self, draft: Game[W]) -> Game[W]:
        self.validate(draft)
        return draft.commit()

    def tick(self, draft: Game[W], *, counted: bool) -> None:
        self.world_of(draft).tick(counted=counted)

    def disarm(self, state: Game[W]) -> None:
        self.world_of(state).disarm()

    def begin(self, scenario_id: Slug, scenario: AnyScenario, character: AnyCharacter) -> Game[W]:
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
        self.admit(scenario.packs, character)
        state = parse(
            self.game,
            {
                "scenario_id": scenario_id,
                "character_id": character.id,
                "scenario": scenario.meta,
                "engine": self.id,
                "packs": scenario.packs,
                "source": scenario.source,
                "payload": self.new_game(scenario, character),
            },
        )
        self.open_chapter(state)
        return self.land(state)

    def world_of(self, state: Game[W]) -> W:
        return state.payload

    def player_of(self, character: AnyCharacter) -> P:
        if character.payload.id != PLAYER_ID or not character.payload.known:
            raise Refusal("a character sheet is the player's: id 'player', known")
        return deepcopy(character.payload)

    def over(self, state: Game[W]) -> str | None:
        return "You died." if not self.world_of(state).player.alive else None

    def create_character(
        self, name: str, brief: str, packs: tuple[Slug, ...], picks: Picks
    ) -> AnyCharacter:
        check_picks(self.creation_steps(packs, picks), picks)
        return self.build_character(name, brief, packs, picks)

    def validate(self, state: Game[W]) -> None:
        """Refuse a state this engine cannot play; a family adds its check after `super()`."""
        if not state.log:
            raise Refusal(f"a {self.id!r} game has no chapter open")
        request = state.generation
        if request is not None and request.operation not in self.requests:
            raise Refusal(f"the {self.id!r} engine writes no {request.operation!r}")
        if SRD_PACK not in state.packs:
            raise Refusal(f"a {self.id!r} game plays the {SRD_PACK!r} tables")

    @abstractmethod
    def creation_steps(
        self, packs: tuple[Slug, ...], picks: Picks, /
    ) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def build_character(
        self, name: str, brief: str, packs: tuple[Slug, ...], picks: Picks, /
    ) -> AnyCharacter: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> W: ...
    @abstractmethod
    def master_sections(self, state: Game[W]) -> Sections: ...
    @abstractmethod
    def family_sections(self, draft: Game[W], /) -> Sections: ...
    @abstractmethod
    def narrator_view(self, state: Game[W]) -> NarratorView: ...
    @abstractmethod
    def player_view(self, state: Game[W]) -> PlayerView: ...
    @abstractmethod
    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: tuple[Slug, ...],
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario: ...
    @abstractmethod
    def act(self, draft: Game[W], action: Slug, words: str, /) -> None:
        """The page's action against the state now: refuse it stale, else request or note."""
