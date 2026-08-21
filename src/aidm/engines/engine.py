from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import ClassVar

from pydantic import JsonValue
from pydantic_ai.toolsets import AbstractToolset

from aidm.content.authored import CreatedCharacter
from aidm.content.store import SavedGame, engine_text
from aidm.state.model import (
    AnyStep,
    EngineId,
    Entity,
    Fact,
    Game,
    Mutable,
    Picks,
    StepTrace,
    WorldState,
)

from .advancement import Advancement

type EntityRenderer = Callable[[Entity], str]


@dataclass(slots=True)
class TurnLog:
    facts: list[Fact] = field(default_factory=list)
    steps: list[StepTrace] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PlanContext:
    """What a Director tool resolves against; `state` is the turn's own draft, never committed
    state."""

    engine: "Engine"
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


class Engine(ABC):
    """One object per engine: its metadata, its plan lifecycle, and the mechanics half of state."""

    id: ClassVar[EngineId]
    badge: ClassVar[tuple[str, str]]
    engine_dir: ClassVar[Path]
    mechanics_type: type[Mutable]

    def __init__(self, extra_packs: Path | None = None) -> None:
        # Read once here so a missing declaration fails the build, not the turn that first needs it.
        _ = self.mechanics_type
        self.director_instructions: str = engine_text(self.engine_dir / "director.md")
        # An engine's own mechanics reach the Director as tools; core's world vocabulary is shared.
        self.director_toolsets: tuple[AbstractToolset[PlanContext], ...] = ()
        # Optional capabilities an engine plugs in; the app offers only what it finds.
        self.advancement: Advancement | None = None
        self.creation: CharacterCreation | None = None

    @abstractmethod
    def check_overlay(self, rules: dict[str, JsonValue]) -> None:
        """Refuses authored character rules this engine cannot play."""

    @abstractmethod
    def opening_mechanics(
        self, world: WorldState, player_rules: dict[str, JsonValue]
    ) -> Mutable: ...

    def restored(self, saved: SavedGame) -> Game:
        return saved.game(self.mechanics_type.model_validate(saved.mechanics))

    @abstractmethod
    def validate(self, state: Game) -> None:
        """Refuses a state this engine cannot play, rather than repairing one."""

    def seed(self, draft: Game, entity: Entity, rng: Random) -> None:  # noqa: B027
        """Whatever this engine must give an entity created during play; a hook, not abstract."""

    def renderer(self, state: Game) -> EntityRenderer:
        return lambda entity: self.describe(state, entity)

    @abstractmethod
    def describe(self, state: Game, entity: Entity) -> str: ...

    @abstractmethod
    def sheet_view(self, state: Game) -> tuple[tuple[str, str], ...]:
        """Ordered (label, value) pairs summarising the player's own sheet for the player."""
