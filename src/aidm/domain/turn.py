from typing import Annotated, Literal

from pydantic import Field

from ..utils.models import Frozen
from .base import Role
from .entities import Entity
from .growth import Growth, RejectedGrowth
from .state import GameState
from .transition import Direction, Fact


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
