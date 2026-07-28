from pydantic import Field

from ...utils.models import Frozen
from .base import Role
from .direction import Direction
from .entities import Entity, Growth, RejectedGrowth
from .events import Event
from .state import GameState


class Turn(Frozen):
    prompt: str
    direction: Direction
    events: list[Event] = Field(default_factory=list)
    narration: str
    growth: Growth
    created: list[Entity] = Field(default_factory=list)
    rejected: list[RejectedGrowth] = Field(default_factory=list)
    state: GameState
    prompts: dict[Role, str] = Field(default_factory=dict)
