from collections.abc import Callable, Sequence
from random import Random
from typing import ClassVar, Protocol

from pydantic_ai import RunContext
from pydantic_ai.output import OutputSpec

from aidm.engines.dnd5e.engine import build_dnd5e_engine
from aidm.engines.story.engine import build_story_engine

from .base import AdvancementDecision, EngineId, Entity
from .config import Settings
from .content import AuthoredWorld
from .facts import (
    ActorMoved,
    EntityCreated,
    EntityDiscovered,
    ItemMoved,
    core_fact_summary,
)
from .prompts import EntityRenderer
from .transition import Direction, Fact, Transition
from .world import CharacterEngineData, EngineState, GameState

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Engine(Protocol):
    """One ruleset seen flat, so core never names a concrete engine."""

    id: ClassVar[EngineId]

    def initial_state(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> EngineState: ...

    def validate_state(self, state: GameState) -> None: ...

    def created(self, draft: GameState, entity: Entity) -> None: ...

    def resolve(self, direction: Direction, state: GameState, rng: Random) -> Transition: ...

    def advance(
        self,
        decision: AdvancementDecision,
        state: GameState,
        rng: Random,
    ) -> Transition: ...

    def advancement_available(self, state: GameState) -> bool: ...

    def director_output(self) -> OutputSpec[Direction]: ...

    def director_instructions(self) -> str: ...

    def validate_direction(
        self,
        ctx: RunContext[GameState],
        direction: Direction,
    ) -> Direction: ...

    def entity_state(self, entity: Entity, state: GameState) -> str: ...

    def narrator_fact(self, fact: Fact) -> str | None: ...

    def trace_fact(self, fact: Fact) -> str: ...

    def trace_direction(self, direction: Direction) -> str: ...


ENGINES: dict[EngineId, Callable[[Settings], Engine]] = {
    "story": lambda _: build_story_engine(),
    "dnd5e": lambda config: build_dnd5e_engine(config.dnd5e.pack_paths),
}


def engine_for(engine: EngineId, config: Settings) -> Engine:
    return ENGINES[engine](config)


def narrator_evidence(engine: Engine, facts: Sequence[Fact]) -> str:
    lines = [
        f"- {rendered}" for fact in facts if (rendered := narrator_line(engine, fact)) is not None
    ]
    return "\n".join(lines) or NOTHING_MECHANICAL


def narrator_line(engine: Engine, fact: Fact) -> str | None:
    if isinstance(fact, EntityCreated | EntityDiscovered | ActorMoved | ItemMoved):
        return core_fact_summary(fact)
    return engine.narrator_fact(fact)


def trace_line(engine: Engine, fact: Fact) -> str:
    if isinstance(fact, EntityCreated | EntityDiscovered | ActorMoved | ItemMoved):
        return core_fact_summary(fact)
    return engine.trace_fact(fact)


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    return lambda entity: engine.entity_state(entity, state)
