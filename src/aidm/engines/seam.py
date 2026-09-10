from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel, JsonValue

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, parse, require_unique
from aidm.core.facts import Fact
from aidm.core.io import read_prompt
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    EngineHeader,
    Game,
    Generation,
    ScenarioMeta,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption, Exchange, PendingOption, SceneRecord, SpokenLine
from aidm.core.tools import MasterTool
from aidm.core.views import DiceLook, NarratorView, Pairs, Palette, PlayerView
from aidm.engines.base import PLAYER_ID, Person, World

type AnyEngine = Engine[Any, Any]


class Engine[P: Person, G: Game[Any]](ABC):
    # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    art_style: str
    dice_look: DiceLook
    palette: Palette
    directory: Path  # rules.md; a scene engine's packs/
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    instructions: str
    tools: dict[str, MasterTool[G]]
    operations: tuple[Slug, ...]  # the requests this engine writes

    def __init__(self) -> None:
        self.instructions = read_prompt(self.directory / "rules.md")
        tools = self.master_tools()
        require_unique(f"tool names of the {self.id!r} engine", (tool.name for tool in tools))
        self.tools = {tool.name: tool for tool in tools}
        self.instructions = f"{self.instructions}\n{self.family_rules()}"

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def check_character(self, character: AnyCharacter) -> None:
        if character.engine != self.id:
            raise Refusal(f"{self.title} received an incompatible character")
        if character.payload.id != PLAYER_ID or not character.payload.known:
            raise Refusal("a character sheet is the player's: id 'player', known")

    def preview_character(self, character: AnyCharacter) -> Pairs:
        return self.player_of(character).rows()

    def restore(self, value: JsonValue) -> G:
        if (header := parse(EngineHeader, value)).engine != self.id:
            raise Refusal(f"the save plays {header.engine!r}, not {self.id!r}")
        state = parse(self.game, value)
        self.validate(state)
        return state

    def tool(self, name: str) -> MasterTool[G]:
        found = self.tools.get(name)
        if found is None:
            raise Refusal(f"{name!r} is not a tool of the {self.id!r} engine.")
        return found

    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        try:
            found = self.tool(chosen.name)
        except Refusal as missing:
            raise Refusal(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            ) from missing
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

    def close(
        self,
        draft: G,
        prompt: str,
        lines: tuple[SpokenLine, ...],
        facts: tuple[Fact, ...],
        proposal: str = "",
    ) -> G:
        exchange = Exchange(
            prompt=prompt,
            lines=lines,
            facts=facts,
            decision="" if draft.pending is None else draft.pending.prompt,
            proposal=proposal,
        )
        self.record(draft, exchange)
        return self.commit(draft)

    def commit(self, draft: G) -> G:
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
        return self.commit(state)

    def player_of(self, character: AnyCharacter) -> P:
        self.check_character(character)
        return deepcopy(character.payload)

    def check_scenario(self, scenario: AnyScenario) -> None:
        if scenario.engine != self.id:
            raise Refusal(f"{self.title} received an incompatible scenario")

    def over(self, state: G) -> str | None:
        return "You died." if not self.world(state).player.alive else None

    def record(self, state: G, exchange: Exchange) -> None:
        self.world(state).record(exchange)

    def history(self, state: G) -> tuple[Exchange, ...]:
        return self.world(state).exchanges()

    def scenes(self, state: G) -> tuple[SceneRecord, ...]:
        return self.world(state).records()

    def unwritten(self, request: Generation) -> Fact:
        """What the player reads when the worldsmith could not write this request."""
        raise ValueError(f"the {self.id!r} engine writes no {request.operation!r}")

    def check_request(self, state: G) -> None:
        """The hook the hiring mixin fills; a request needs no check of its own."""
        return None  # ruff B027: an empty method on an ABC

    @abstractmethod
    def master_tools(self) -> tuple[MasterTool[G], ...]: ...
    @abstractmethod
    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter: ...
    @abstractmethod
    def family_rules(self) -> str:
        """What every engine of this family is told, after its own rules."""

    @abstractmethod
    def world(self, state: G) -> World[P]: ...
    @abstractmethod
    def validate(self, state: G) -> None: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> World[P]: ...
    @abstractmethod
    def master_sections(self, state: G) -> Pairs: ...
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
    def act(self, draft: G, action: Slug, words: str) -> None:
        """The page's action against the state now: refuse it stale, else request or note."""

    @abstractmethod
    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        """Write and install on `draft`; the facts, and what to tell the narrator, if anything."""
