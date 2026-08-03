from typing import Annotated, Literal

from pydantic import Field

from .base import SAVE_VERSION, Entity, Frozen, Role
from .facts import Fact
from .growth import Growth, RejectedGrowth
from .transition import Direction


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    save_version: int = SAVE_VERSION
    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    entry: Literal["turn"] = "turn"
    prompt: str
    direction: Direction
    narrator_evidence: str
    narration: str
    growth: Growth
    created: tuple[Entity, ...] = ()
    rejected: tuple[RejectedGrowth, ...] = ()
    prompts: dict[Role, str] = Field(default_factory=dict)


class Advance(TraceEntryBase):
    """A level-up: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advance"] = "advance"


type TraceEntry = Annotated[Turn | Advance, Field(discriminator="entry")]
