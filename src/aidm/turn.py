from typing import Annotated, Literal

from pydantic import Field

from .base import Entity, Frozen, Role
from .growth import Growth, RejectedGrowth
from .transition import Direction, Fact
from .world import GameState


class Turn(Frozen):
    entry: Literal["turn"] = "turn"
    prompt: str
    direction: Direction
    facts: tuple[Fact, ...] = ()
    narrator_evidence: str
    narration: str
    growth: Growth
    created: tuple[Entity, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()
    state: GameState
    prompts: dict[Role, str] = Field(default_factory=dict)


class Advance(Frozen):
    """A level-up: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advance"] = "advance"
    facts: tuple[Fact, ...] = ()
    state: GameState


type TraceEntry = Annotated[Turn | Advance, Field(discriminator="entry")]
