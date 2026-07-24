"""The record of one played turn — what the trace panel and the trace file both hold."""

from pydantic import Field

from .base import Frozen, Role
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
    rejected: list[RejectedGrowth] = Field(default_factory=list)  # growth refused, kept visible
    state: GameState
    prompts: dict[Role, str] = Field(default_factory=dict)  # exactly what each role was shown
