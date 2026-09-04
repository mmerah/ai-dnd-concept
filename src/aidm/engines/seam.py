from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, parse, require_unique
from aidm.core.facts import Fact
from aidm.core.io import ENCODING, decode
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    EngineHeader,
    Game,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import Commission, DecisionOption, Exchange, HistoryRecord, Line, PendingOption
from aidm.core.tools import MasterTool, Play
from aidm.core.views import NarratorView, PlayerView, Rows, Sections
from aidm.engines.base import PLAYER_ID, Person

type AnyEngine = Engine[Any]

COMMISSION = "commission"
COMMISSION_BRIEF = (
    "Ask the worldsmith for what the scene needs and the cast lacks. Written now, the turn "
    "pauses and you are spawned again with the answer under NOTES FROM THE RULES; with "
    "`later`, it is written into the next scene or region. What you ask for becomes canon."
)
WORLDSMITH_WAIT = (
    "the worldsmith is writing what you asked for. Stop here and exit; you will be spawned "
    "again with the answer."
)


class Engine[G: Game[Any]](ABC):
    """The seam joining an engine's rules to the platform; a subclass answers for one engine."""

    # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    art_style: str
    directory: Path  # rules.md; a scene engine's packs/
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    instructions: str
    tools: dict[str, MasterTool[G]]

    def __init__(self) -> None:
        self.instructions = (self.directory / "rules.md").read_text(encoding=ENCODING)
        tools = (*self.master_tools(), self.commission_tool())
        require_unique(f"tool names of the {self.id!r} engine", (tool.name for tool in tools))
        self.tools = {tool.name: tool for tool in tools}

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def crossing(self, state: G, pursuit: str) -> str | None:
        """The narrator's brief for the arrival; None where the world grows without a turn."""
        return None

    def check_character(self, character: AnyCharacter) -> None:
        """The file is this engine's and its sheet is the player's."""
        if not isinstance(character, self.character):
            raise Refusal(f"{self.title} received an incompatible character")
        if character.payload.id != PLAYER_ID or not character.payload.known:
            raise Refusal("a character sheet is the player's: id 'player', known")

    def preview_character(self, character: AnyCharacter) -> Rows:
        return self.player_of(character).rows()

    def restore(self, raw: str) -> G:
        value = decode(raw)
        if (header := parse(EngineHeader, value)).engine != self.id:
            raise Refusal(f"the save plays {header.engine!r}, not {self.id!r}")
        state = parse(self.game, value)
        self.validate(state)
        return state

    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = self.tools.get(chosen.name)
        if found is None:
            raise Refusal(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)

    async def compose[M: BaseModel](
        self,
        worldsmith: WorldsmithAnswer,
        prompt: str,
        model: type[M],
        build: Callable[[M], AnyScenario],
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario:
        """The build runs the engine's bar, so an unbuildable opening is re-prompted, not raised."""
        built: AnyScenario | None = None

        def refusal(answer: M) -> str | None:
            nonlocal built
            try:
                built = build(answer)
            except Refusal as unbuildable:
                return str(unbuildable)
            return playable(built)

        answer = await worldsmith(prompt, model, refusal)
        # The accepted answer was built by its own check; one never checked is built here.
        return build(answer) if built is None else built

    def commission(self, draft: G, kind: str, brief: str, *, later: bool) -> list[Fact]:
        """One `later` on order at a time: the next write owes one entry, never a backlog."""
        if later and (on_order := draft.on_order()):
            raise Refusal(
                f"a {on_order[0].kind} is already on order for the next write: {on_order[0].brief}"
            )
        draft.commissions.append(Commission(kind=kind, brief=brief, later=later))
        if later:
            trace = f"the worldsmith will write a {kind} into the next scene or region: {brief}"
            draft.note(trace)
        else:
            trace = f"waiting on the worldsmith for a {kind}: {brief}"
        return [Fact(kind="commission_asked", trace=trace)]

    def close(self, draft: G, prompt: str, lines: tuple[Line, ...], facts: tuple[Fact, ...]) -> G:
        exchange = Exchange(
            prompt=prompt,
            lines=self.narrator_view(draft).spoken(lines),
            facts=tuple(facts),
            decision="" if draft.pending is None else draft.pending.prompt,
        )
        self.record(draft, exchange)
        draft.turn += 1
        return draft.commit()

    @abstractmethod
    def master_tools(self) -> tuple[MasterTool[G], ...]: ...
    @abstractmethod
    def commission_tool(self) -> MasterTool[G]: ...
    @abstractmethod
    async def fulfil(self, draft: G, asked: Commission, worldsmith: WorldsmithAnswer) -> Play[G]:
        """Ask the worldsmith from the draft as it stands; the install comes back to run under
        the turn's gate."""

    @abstractmethod
    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter: ...
    @abstractmethod
    def player_of(self, character: AnyCharacter) -> Person: ...
    @abstractmethod
    def validate(self, state: G) -> None: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> BaseModel: ...
    @abstractmethod
    def over(self, state: G) -> str | None: ...
    @abstractmethod
    def record(self, state: G, exchange: Exchange) -> None: ...
    @abstractmethod
    def history(self, state: G) -> tuple[Exchange, ...]: ...
    @abstractmethod
    def scenes(self, state: G) -> tuple[HistoryRecord, ...]: ...
    @abstractmethod
    def master_sections(self, state: G) -> Sections: ...
    @abstractmethod
    def narrator_view(self, state: G) -> NarratorView: ...
    @abstractmethod
    def player_view(self, state: G) -> PlayerView: ...
    @abstractmethod
    async def author(
        self,
        meta: ScenarioMeta,
        source: str,
        packs: Sequence[Slug],
        worldsmith: WorldsmithAnswer,
        playable: Callable[[AnyScenario], str | None],
    ) -> AnyScenario: ...
    @abstractmethod
    def ready(self, state: G) -> bool: ...
    @abstractmethod
    async def advance(
        self, draft: G, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        """Write the world on, then install it on `draft`; raise when either will not hold."""
