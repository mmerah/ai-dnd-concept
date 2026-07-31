from collections.abc import Sequence
from random import Random
from typing import Literal, overload

from aidm.engines.dnd5e.advancement import Dnd5eAdvancementDecisions
from aidm.engines.dnd5e.direction import Dnd5eDirection
from aidm.engines.dnd5e.engine import Dnd5eEngine, build_dnd5e_engine
from aidm.engines.dnd5e.facts import Dnd5eFactBase
from aidm.engines.dnd5e.state import Dnd5eState
from aidm.engines.story.advancement import StoryAdvancementDecision
from aidm.engines.story.direction import StoryDirection
from aidm.engines.story.engine import StoryEngine, build_story_engine
from aidm.engines.story.facts import StoryFactBase
from aidm.engines.story.state import StoryState

from .base import EngineId
from .config import Settings
from .facts import (
    ActorMoved,
    EntityCreated,
    EntityDiscovered,
    ItemMoved,
    core_fact_summary,
)
from .prompts import EntityRenderer
from .transition import Direction, Fact, Transition
from .world import GameState

type Engine = StoryEngine | Dnd5eEngine
type AdvancementDecision = StoryAdvancementDecision | Dnd5eAdvancementDecisions

NOTHING_MECHANICAL = "- (nothing mechanical happened)"


@overload
def engine_for(engine: Literal["story"], config: Settings) -> StoryEngine: ...


@overload
def engine_for(engine: Literal["dnd5e"], config: Settings) -> Dnd5eEngine: ...


def engine_for(engine: EngineId, config: Settings) -> Engine:
    match engine:
        case "story":
            return build_story_engine()
        case "dnd5e":
            return build_dnd5e_engine(config.dnd5e.pack_paths)


def resolve(engine: Engine, direction: Direction, state: GameState, rng: Random) -> Transition:
    match engine, direction:
        case StoryEngine(), StoryDirection():
            return engine.rules.resolve(direction, state, rng)
        case Dnd5eEngine(), Dnd5eDirection():
            return engine.rules.resolve(direction, state, rng)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(direction).__name__}")


def resolve_advancement(
    engine: Engine,
    decision: AdvancementDecision,
    state: GameState,
    rng: Random,
) -> Transition:
    if isinstance(decision, Dnd5eAdvancementDecisions):
        if isinstance(engine, Dnd5eEngine):
            return engine.advancement.advance(state, decision, rng)
    elif isinstance(engine, StoryEngine):
        return engine.advancement.advance(state, decision, rng)
    raise TypeError(f"{engine.id!r} engine received a {type(decision).__name__}")


def trace_direction(engine: Engine, direction: Direction) -> str:
    match engine, direction:
        case StoryEngine(), StoryDirection():
            return engine.presentation.trace_direction(direction)
        case Dnd5eEngine(), Dnd5eDirection():
            return engine.presentation.trace_direction(direction)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(direction).__name__}")


def narrator_evidence(engine: Engine, facts: Sequence[Fact]) -> str:
    lines = [
        f"- {rendered}" for fact in facts if (rendered := narrator_fact(engine, fact)) is not None
    ]
    return "\n".join(lines) or NOTHING_MECHANICAL


def narrator_fact(engine: Engine, fact: Fact) -> str | None:
    match engine, fact:
        case _, (EntityCreated() | EntityDiscovered() | ActorMoved() | ItemMoved()):
            return core_fact_summary(fact)
        case StoryEngine(), StoryFactBase():
            return engine.presentation.narrator_fact(fact)
        case Dnd5eEngine(), Dnd5eFactBase():
            return engine.presentation.narrator_fact(fact)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(fact).__name__}")


def trace_fact(engine: Engine, fact: Fact) -> str:
    """Core renders its own facts and delegates the engine's; the dispatch moves, it does not go."""
    match engine, fact:
        case _, (EntityCreated() | EntityDiscovered() | ActorMoved() | ItemMoved()):
            return core_fact_summary(fact)
        case StoryEngine(), StoryFactBase():
            return engine.presentation.trace_fact(fact)
        case Dnd5eEngine(), Dnd5eFactBase():
            return engine.presentation.trace_fact(fact)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(fact).__name__}")


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    """Bind the engine presenter to the state it reads, so scene builders stay engine-blind."""
    match engine, state.engine:
        case StoryEngine(presentation=presentation), StoryState() as engine_state:
            return lambda entity: presentation.entity_state(entity, engine_state)
        case Dnd5eEngine(presentation=presentation), Dnd5eState() as engine_state:
            return lambda entity: presentation.entity_state(entity, engine_state)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(state.engine).__name__} state")
