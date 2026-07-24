"""The record of one played turn — what the trace panel and the trace file both hold."""

from pydantic import Field

from .events import Event
from .models import Direction, Entity, Frozen, GameState, Growth, RejectedGrowth, Role


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
