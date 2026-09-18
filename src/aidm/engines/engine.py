from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
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
    Commission,
    EngineHeader,
    Game,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Chapter, Exchange, Mark, PendingOption, SpokenLine
from aidm.core.prompt import Sections
from aidm.core.tools import MasterTool, tool, tools_of
from aidm.core.views import Companion, Look, NarratorView, PlayerView, Rows
from aidm.engines.base import PLAYER_ID, Person, World
from aidm.engines.packs import (
    Pack,
    PackAuthor,
    PackBody,
    PackHead,
    PackSet,
    read_packs,
    render_worldsmith,
)
from aidm.engines.tools import JoinParty, Kill, LeaveParty, Reveal

type AnyEngine = Engine[Any, Any]


@dataclass(frozen=True, slots=True)
class Written:
    facts: tuple[Fact, ...]
    narrator_prompt: str | None


@dataclass(frozen=True, slots=True)
class Operation[W: World[Any]]:
    write: Callable[[Game[W], Commission, WorldsmithAnswer], Awaitable[Written]]
    failure_fact: Fact


class Engine[W: World[Any], K: Pack](ABC):
    # Declared, not `ClassVar`: `type[W]` cannot be one.
    id: EngineId
    title: str
    authoring: str
    art_style: str
    directory: Path  # rules.md, look.json and a shipped packs/
    family_dir: Path
    world: type[W]
    pack: type[K]
    head: type[PackHead] = PackHead
    body: type[PackBody] = PackBody
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    packs: PackSet[K]
    instructions: str
    look: Look
    tools: dict[str, MasterTool]
    worldsmith_role: str
    pack_author: PackAuthor[K]

    def __init__(self, player_packs: Path) -> None:
        self.packs = read_packs(self.id, self.directory / "packs", player_packs, self.pack)
        self.packs.srd()  # an engine that ships no srd pack is a bug, not a refusal
        self.instructions = (
            f"{read_cached_text(self.directory / 'rules.md')}\n"
            f"{read_cached_text(self.family_dir / 'rules.md')}"
        )
        self.look = read_model(self.directory / "look.json", Look)
        if self.world.tempo < 2:
            raise ValueError(f"the {self.id!r} engine ticks every {self.world.tempo} turns")
        self.tools = tools_of(self)
        self.worldsmith_role = read_cached_text(self.family_dir / "worldsmith.md")
        self.pack_author = PackAuthor(
            pack_model=self.pack,
            head_model=self.head,
            body_model=self.body,
            authoring=self.authoring,
            role=self.worldsmith_role,
        )

    @tool
    def reveal(self, draft: Game[W], args: Reveal, _rng: Random) -> list[Fact]:
        """Make a hidden entity here known to the player."""
        return draft.world.reveal_hidden(args.target_id)

    @tool
    def kill(self, draft: Game[W], args: Kill, _rng: Random) -> list[Fact]:
        """Kill someone here."""
        return draft.world.kill(args.target_id)

    @tool
    def join_party(self, draft: Game[W], args: JoinParty, _rng: Random) -> list[Fact]:
        """Make a person here travel with the player."""
        return draft.world.join_party(args.target_id)

    @tool
    def leave_party(self, draft: Game[W], args: LeaveParty, _rng: Random) -> list[Fact]:
        """Make a party member stop travelling with the player."""
        return draft.world.leave_party(args.target_id)

    def install_pack(self, pack_id: Slug, pack: K) -> None:
        packs = self.packs
        self.packs = PackSet(packs.engine, packs.shipped, {**packs.written, pack_id: pack})

    def guidance(self, pack_id: Slug, /, *, opening: bool) -> str:
        block = self.packs.guidance(pack_id, opening=opening)
        return f"{self.authoring}\n\n{block}" if block else self.authoring

    def preview_character(self, character: AnyCharacter) -> Rows:
        return self.player_of(character).rows()

    def companions(self, state: Game[W]) -> tuple[Companion, ...]:
        return tuple(
            Companion(
                id=member.id,
                name=member.name,
                brief=member.brief,
                sheet=member.rows(),
                chattiness=member.chattiness,
            )
            for member in state.world.members()
        )

    def restore(self, raw: str) -> Game[W]:
        if (header := parse(EngineHeader, decode(raw))).engine != self.id:
            raise Refusal(f"the save plays {header.engine!r}, not {self.id!r}")
        state = parse_json(Game[self.world], raw)
        if state.commission is not None:
            raise Refusal("the save carries a pending commission")
        self.validate(state)
        self.packs.require(state.pack_id)
        return state

    def require_tool(self, name: str) -> MasterTool:
        found = self.tools.get(name)
        if found is None:
            raise Refusal(f"{name!r} is not a tool of the {self.id!r} engine.")
        return found

    def play_option(self, draft: Game[W], chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        return self.require_tool(chosen.tool_name).call(draft, chosen.args, rng)

    def render_commission(
        self, draft: Game[W], *, intent: str, guidance: str, answer_model: type[BaseModel]
    ) -> str:
        return render_worldsmith(
            self.worldsmith_role,
            source=draft.source,
            scope=draft.scenario.scope,
            world_sections=self.worldsmith_sections(draft),
            intent=intent,
            guidance=guidance,
            answer_model=answer_model,
        )

    def sheet_character(self, name: str, sheet: BaseModel) -> AnyCharacter:
        return self.character(id=slug(name, ()), engine=self.id, sheet=sheet)

    def build_scenario(
        self,
        meta: ScenarioMeta,
        pack_id: Slug,
        draft: BaseModel,
        source: str,
        premise: str,
    ) -> AnyScenario:
        """No check here: `begin` is the one check an opening meets, and `check` always runs it."""
        return self.scenario(
            meta=meta.model_copy(update={"premise": meta.premise or premise}),
            engine=self.id,
            pack_id=pack_id,
            source=source,
            opening=draft,
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
        return self.accept(draft)

    def open_chapter(self, draft: Game[W]) -> None:
        """The title and focus the narrator sees are the ones the history keeps."""
        if draft.log and not draft.log[-1].exchanges:
            draft.log.pop()
        view = self.narrator_view(draft)
        draft.log.append(Chapter(title=view.title, focus=view.focus))

    def accept(self, draft: Game[W]) -> Game[W]:
        self.validate(draft)
        return draft.commit()

    def tick(self, draft: Game[W], *, counted: bool) -> None:
        draft.world.tick(counted=counted)

    def disarm(self, state: Game[W]) -> None:
        state.world.disarm()

    def begin(self, scenario_id: Slug, scenario: AnyScenario, character: AnyCharacter) -> Game[W]:
        if scenario.engine != self.id:
            raise Refusal(
                f"{scenario_id!r} is authored for the {scenario.engine!r} rules. "
                f"The {self.id!r} engine does not play them."
            )
        if character.engine != self.id:
            raise Refusal(
                f"{character.id!r} is written for the {character.engine!r} rules. "
                f"The {self.id!r} engine does not play them."
            )
        self.packs.require(scenario.pack_id)
        state = parse(
            Game[self.world],
            {
                "scenario_id": scenario_id,
                "character_id": character.id,
                "scenario": scenario.meta,
                "engine": self.id,
                "pack_id": scenario.pack_id,
                "source": scenario.source,
                "world": self.new_game(scenario, character),
            },
        )
        self.open_chapter(state)
        return self.accept(state)

    def player_as[S: Person](self, character: AnyCharacter, sheet: type[S]) -> S:
        if character.sheet.id != PLAYER_ID or not character.sheet.known:
            raise Refusal("a character sheet is the player's: the id is 'player', and it is known")
        if not isinstance(character.sheet, sheet):
            raise Refusal(f"{character.id!r} is not a {self.title} sheet")
        return deepcopy(character.sheet)

    def ending(self, state: Game[W]) -> str | None:
        return "You died." if not state.world.player.alive else None

    def create_character(self, name: str, brief: str, pack_id: Slug, picks: Picks) -> AnyCharacter:
        check_picks(self.creation_steps(pack_id, picks), picks)
        return self.build_character(name, brief, pack_id, picks)

    def validate(self, state: Game[W]) -> None:
        """A family adds its own check after `super()`."""
        if not state.log:
            raise Refusal(f"a {self.id!r} game has no chapter open")
        commission = state.commission
        if commission is not None and commission.operation not in self.operations():
            raise Refusal(f"the {self.id!r} engine writes no {commission.operation!r}")

    @abstractmethod
    def player_of(self, character: AnyCharacter) -> Person: ...
    @abstractmethod
    def creation_steps(self, pack_id: Slug, picks: Picks, /) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def build_character(
        self, name: str, brief: str, pack_id: Slug, picks: Picks, /
    ) -> AnyCharacter: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> W: ...
    @abstractmethod
    def master_sections(self, state: Game[W]) -> Sections: ...
    @abstractmethod
    def worldsmith_sections(self, draft: Game[W], /) -> Sections: ...
    @abstractmethod
    def narrator_view(self, state: Game[W]) -> NarratorView: ...
    @abstractmethod
    def player_view(self, state: Game[W]) -> PlayerView: ...
    @abstractmethod
    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        pack_id: Slug,
        worldsmith: WorldsmithAnswer,
        check: Callable[[AnyScenario], None],
    ) -> AnyScenario: ...
    @abstractmethod
    def act(self, draft: Game[W], action_id: Slug, words: str, /) -> None:
        """The page's action against the state now: refuse it stale, else request or note."""

    def operations(self) -> Mapping[Slug, Operation[W]]:
        return {}

    async def advance(
        self, draft: Game[W], commission: Commission, worldsmith: WorldsmithAnswer
    ) -> Written:
        return await self.operations()[commission.operation].write(draft, commission, worldsmith)
