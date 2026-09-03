from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path
from random import Random
from typing import Any

from pydantic import BaseModel

from aidm.core.creation import CreationStep, Picks
from aidm.core.entities import EngineId, Slug, require_unique
from aidm.core.facts import Fact
from aidm.core.io import ENCODING, decoded
from aidm.core.model import (
    AnyCharacter,
    AnyScenario,
    EngineHeader,
    Game,
    ScenarioKind,
    WorldsmithAnswer,
)
from aidm.core.play import DecisionOption, Exchange, PendingOption, SceneRecord
from aidm.core.tools import MasterTool
from aidm.core.views import NarratorView, PlayerView, Rows

type AnyEngine = Engine[Any]


class Engine[G: Game[Any]](ABC):
    """The seam joining an engine's rules to the platform; a subclass answers for one engine."""

    # Declared, not `ClassVar`: `type[G]` cannot be one, and a test sets them on its own instance.
    id: EngineId
    title: str
    art_style: str
    directory: Path  # rules.md; a scene engine's packs/; Tunnel Goons' worldsmith.md
    game: type[G]
    scenario: type[AnyScenario]
    character: type[AnyCharacter]
    # The narrator's brief for the arrival, `{pursuit}` the player's words; None when the world
    # is extended without a turn, as Tunnel Goons grows its map.
    crossing: str | None = None
    instructions: str
    tools: tuple[MasterTool[G], ...]

    def __init__(self) -> None:
        self.instructions = (self.directory / "rules.md").read_text(encoding=ENCODING)
        self.tools = self.master_tools()
        require_unique(f"tool names of the {self.id!r} engine", (one.name for one in self.tools))

    def pack_options(self) -> tuple[DecisionOption, ...]:
        return ()

    def restored(self, raw: str) -> G:
        value = decoded(raw)
        if (header := EngineHeader.model_validate(value)).engine != self.id:
            raise ValueError(f"the save plays {header.engine!r}, not {self.id!r}")
        state = self.game.model_validate(value)
        self.validate(state)
        return state

    def answer(self, draft: G, chosen: PendingOption, rng: Random) -> tuple[Fact, ...]:
        found = next((one for one in self.tools if one.name == chosen.name), None)
        if found is None:
            raise ValueError(
                f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}"
            )
        return found.call(draft, chosen.args, rng)

    @abstractmethod
    def master_tools(self) -> tuple[MasterTool[G], ...]: ...
    @abstractmethod
    def creation_steps(self, picks: Picks) -> tuple[CreationStep, ...]: ...
    @abstractmethod
    def create_character(self, name: str, brief: str, picks: Picks) -> AnyCharacter: ...
    @abstractmethod
    def preview_character(self, character: AnyCharacter) -> Rows: ...
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
    def scenes(self, state: G) -> tuple[SceneRecord, ...]: ...
    @abstractmethod
    def master_sections(self, state: G) -> Rows: ...
    @abstractmethod
    def narrator_view(self, state: G) -> NarratorView: ...
    @abstractmethod
    def player_view(self, state: G) -> PlayerView: ...
    @abstractmethod
    async def author(
        self,
        title: str,
        premise: str,
        source: str,
        packs: Sequence[Slug],
        kind: ScenarioKind,
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


async def authored[M: BaseModel](
    worldsmith: WorldsmithAnswer,
    prompt: str,
    model: type[M],
    build: Callable[[M], AnyScenario],
    playable: Callable[[AnyScenario], str | None],
) -> AnyScenario:
    """The build runs the engine's bar, so an unbuildable opening is re-prompted, not raised."""

    def refusal(written: M) -> str | None:
        try:
            return playable(build(written))
        except ValueError as unbuildable:
            return str(unbuildable)

    return build(await worldsmith(prompt, model, refusal))
