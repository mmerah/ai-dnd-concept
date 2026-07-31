from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap
from .base import TRACE_VERSION, Role
from .direction import DirectionRecord
from .entities import Entity
from .events import Event
from .growth import Growth, RejectedGrowth
from .state import GameState


class Turn(Frozen):
    trace_version: int = TRACE_VERSION
    prompt: str
    direction: DirectionRecord
    events: tuple[Event, ...] = ()
    narrator_evidence: str
    narration: str
    growth: Growth
    created: tuple[Entity, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()
    state: GameState
    prompts: FrozenMap[Role, str] = EMPTY_FROZEN_MAP
