from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from copy import deepcopy
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel, JsonValue

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Refusal, Slug, parse
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
from aidm.core.play import DecisionOption, Exchange, Mark, PendingOption, SpokenLine
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
    family_prompt: Path
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    instructions: str
    tools: dict[str, MasterTool[G]]
    unwritten: dict[Slug, Fact]  # the requests this engine writes, and what a failed one tells

    def __init__(self) -> None:
        self.instructions = (
            f"{read_prompt(self.directory / 'rules.md')}\n{read_prompt(self.family_prompt)}"
        )
        tools = self.master_tools()
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ValueError(f"the {self.id!r} engine names a tool twice: {names}")
        self.tools = {tool.name: tool for tool in tools}

    def master_tools(self) -> tuple[MasterTool[G], ...]:
        """Each layer adds its own after `super()`'s: family, then `hire`, then the engine."""
        return ()

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def preview_character(self, character: AnyCharacter) -> Pairs:
        return self.player_of(character).rows()

    def restore(self, value: JsonValue) -> G:
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

        def refusal(answer: M) -> str | None:
            try:
                return playable(build(answer))
            except Refusal as unbuildable:
                return str(unbuildable)

        return build(await worldsmith(prompt, model, refusal))

    def close(
        self,
        draft: G,
        lines: tuple[SpokenLine, ...],
        facts: tuple[Fact, ...],
        *,
        prompt: str = "",
        mark: Mark = "",
        proposal: str = "",
    ) -> G:
        exchange = Exchange(
            prompt=prompt,
            mark=mark,
            lines=lines,
            facts=facts,
            decision="" if draft.pending is None else draft.pending.prompt,
            proposal=proposal,
        )
        self.world(draft).record(exchange)
        return self.land(draft)

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
        return self.land(state)

    def player_of(self, character: AnyCharacter) -> P:
        if character.payload.id != PLAYER_ID or not character.payload.known:
            raise Refusal("a character sheet is the player's: id 'player', known")
        return deepcopy(character.payload)

    def over(self, state: G) -> str | None:
        return "You died." if not self.world(state).player.alive else None

    def validate(self, state: G) -> None:
        """Refuse a state this engine cannot play; a family adds its check after `super()`."""
        request = state.generation
        if request is not None and request.operation not in self.unwritten:
            raise Refusal(f"the {self.id!r} engine writes no {request.operation!r}")

    @abstractmethod
    def creation_steps(self, picks: Picks, /) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def create_character(self, name: str, brief: str, picks: Picks, /) -> AnyCharacter: ...
    @abstractmethod
    def world(self, state: G) -> World[Person, P]: ...
    @abstractmethod
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> World[Person, P]: ...
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
    def act(self, draft: G, action: Slug, words: str, /) -> None:
        """The page's action against the state now: refuse it stale, else request or note."""

    @abstractmethod
    async def advance(
        self, draft: G, request: Generation, worldsmith: WorldsmithAnswer
    ) -> tuple[tuple[Fact, ...], str | None]:
        """Write and install on `draft`; the facts, and what to tell the narrator, if anything."""
