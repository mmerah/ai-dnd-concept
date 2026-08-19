from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import CreatedCharacter, EngineBinding
from aidm.content.store import SavedGame, engine_text
from aidm.state.base import EngineId, Entity, EntityId
from aidm.state.creation import AnyStep, Picks
from aidm.state.facts import Fact
from aidm.state.trace import StepTrace
from aidm.state.world import Game, WorldState

from .advancement import Advancement
from .sheets import SheetBase, SheetMechanics, actor_sheets, check_sheets

type EntityRenderer = Callable[[Entity], str]


@dataclass(slots=True)
class TurnLog:
    facts: list[Fact] = field(default_factory=list)
    steps: list[StepTrace] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PlanContext:
    """What a Director tool resolves against; `state` is the turn's own draft, never committed
    state."""

    engine: "Engine[SheetBase]"
    state: Game
    rng: Random
    log: TurnLog


class CharacterCreation(ABC):
    """The optional creation capability: an engine without one offers no new-character page."""

    @abstractmethod
    def steps(self, picks: Picks) -> tuple[AnyStep, ...]:
        """Tolerates partial or stale picks, so follow-up steps appear as parents are picked."""

    @abstractmethod
    def create(self, name: str, brief: str, picks: Picks) -> CreatedCharacter:
        """Raises ValueError with the reason the page shows when the pick set is illegal."""


class Engine[S: SheetBase](ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of state."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    # The engine's own wording for the boundary `complete_chapter` records.
    chapter_ending: ClassVar[str]
    engine_dir: ClassVar[Path]
    sheet_type: type[S]
    mechanics_type: type[SheetMechanics[S]]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.sheet_type, self.mechanics_type, self.chapter_ending
        self.director_instructions: str = engine_text(self.engine_dir / "director.md")
        # An engine's own mechanics reach the Director as tools; core's world vocabulary is shared.
        self.director_toolsets: tuple[AbstractToolset[PlanContext], ...] = ()
        # An engine with no growth mechanic plugs in none; the app offers only what it finds.
        self.advancement: Advancement | None = None
        # An engine that creates characters replaces this; the app offers only what it finds.
        self.creation: CharacterCreation | None = None

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        for rules in payloads:
            _ = self.sheet_type.model_validate(rules)

    def binding(self) -> EngineBinding:
        return EngineBinding(engine=self.id, check_overlay=self.check_overlay)

    def opening_mechanics(
        self, world: WorldState, rules: Mapping[EntityId, dict[str, JsonValue]]
    ) -> SheetMechanics[S]:
        return self.mechanics_type(sheets=actor_sheets(world, rules, self.sheet_type, self.id))

    def restored(self, saved: SavedGame) -> Game:
        return saved.game(self.mechanics_type.model_validate(saved.mechanics))

    def validate(self, state: Game) -> None:
        check_sheets(state.world, self.mechanics_type.of(state).sheets, self.id)
        self.check_mechanics(state)

    def check_mechanics(self, state: Game) -> None:  # noqa: B027 (a hook, not abstract)
        """Whatever this engine tracks beyond one sheet per actor."""

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:
        mechanics = self.mechanics_type.of(draft)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        mechanics.sheets[entity.id] = self.new_sheet(draft, rng)

    @abstractmethod
    def new_sheet(self, draft: Game, rng: Random) -> S: ...

    def renderer(self, state: Game) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    @abstractmethod
    def describe(self, state: Game, entity: Entity) -> str: ...

    @abstractmethod
    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""
