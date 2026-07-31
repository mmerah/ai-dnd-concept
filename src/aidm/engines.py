from random import Random

from aidm_5e.advancement import Dnd5eAdvancement
from aidm_5e.domain.models.direction import Dnd5eDirection
from aidm_5e.factory import Dnd5eEngine, build_dnd5e_engine
from aidm_5e.models import Dnd5eState
from aidm_story.advancement import StoryAdvancement
from aidm_story.direction import StoryDirection
from aidm_story.factory import StoryEngine, build_story_engine
from aidm_story.models import StoryState

from .agents.context import EntityRenderer
from .config import Settings
from .domain.base import EngineId
from .domain.direction import DirectionRecord
from .domain.events import Event
from .domain.state import GameState

type Engine = StoryEngine | Dnd5eEngine
type Direction = StoryDirection | Dnd5eDirection
type Advancement = StoryAdvancement | Dnd5eAdvancement


def engine_for(engine: EngineId, config: Settings) -> Engine:
    match engine:
        case "story":
            return build_story_engine()
        case "dnd5e":
            return build_dnd5e_engine(config.dnd5e.pack_paths)


def resolve(engine: Engine, direction: Direction, state: GameState, rng: Random) -> list[Event]:
    match engine, direction:
        case StoryEngine(), StoryDirection():
            return engine.rules.resolve(direction, state, rng)
        case Dnd5eEngine(), Dnd5eDirection():
            return engine.rules.resolve(direction, state, rng)
        case _:
            raise TypeError(_mismatch(engine, direction))


def record(engine: Engine, direction: Direction) -> DirectionRecord:
    match engine, direction:
        case StoryEngine(), StoryDirection():
            return engine.director.record(direction)
        case Dnd5eEngine(), Dnd5eDirection():
            return engine.director.record(direction)
        case _:
            raise TypeError(_mismatch(engine, direction))


def entity_renderer(engine: Engine, state: GameState) -> EntityRenderer:
    """Bind the engine presenter to the state it reads, so scene builders stay engine-blind."""
    match engine, state.engine:
        case StoryEngine(presentation=presentation), StoryState() as engine_state:
            return lambda entity: presentation.entity_state(entity, engine_state)
        case Dnd5eEngine(presentation=presentation), Dnd5eState() as engine_state:
            return lambda entity: presentation.entity_state(entity, engine_state)
        case _:
            raise TypeError(f"{engine.id!r} engine received a {type(state.engine).__name__} state")


def _mismatch(engine: Engine, direction: Direction) -> str:
    return f"{engine.id!r} engine received a {type(direction).__name__}"
