from collections.abc import Callable, Sequence
from random import Random
from typing import ClassVar, Protocol

from pydantic_ai import RunContext
from pydantic_ai.output import OutputSpec

from aidm.engines.dnd5e.engine import build_dnd5e_engine
from aidm.engines.story.engine import build_story_engine

from .base import ActorEntity, AdvancementDecision, EngineId, Entity, ItemEntity, LocationEntity
from .config import Settings
from .content import AuthoredWorld
from .prompts import EntityRenderer
from .transition import Direction, Fact, Transition
from .world import CharacterEngineData, EntityRules, GameState, WorldState

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Engine(Protocol):
    """One ruleset seen flat, so core never names a concrete engine."""

    id: ClassVar[EngineId]

    def initial_world(
        self,
        authored: AuthoredWorld,
        character: CharacterEngineData,
    ) -> WorldState: ...

    def validate_state(self, state: GameState) -> None: ...

    def default_rules(self, entity: Entity) -> EntityRules | None:
        """Baseline rules for an entity the Creator just narrated; `None` for a location."""
        ...

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

    def entity_state(self, entity: Entity, rules: EntityRules) -> str: ...

    def trace_direction(self, direction: Direction) -> str: ...


ENGINES: dict[EngineId, Callable[[Settings], Engine]] = {
    "story": lambda _: build_story_engine(),
    "dnd5e": lambda config: build_dnd5e_engine(config.dnd5e.pack_paths),
}


def engine_for(engine: EngineId, config: Settings) -> Engine:
    return ENGINES[engine](config)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator_summary) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    def describe(entity: Entity) -> str:
        match entity:
            case ActorEntity():
                return engine.entity_state(entity, state.world.actor(entity.id).rules)
            case ItemEntity():
                return engine.entity_state(entity, state.world.item(entity.id).rules)
            case LocationEntity():
                return ""

    return describe
