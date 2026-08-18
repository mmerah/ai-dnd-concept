from typing import Annotated, Literal

from pydantic import Field, JsonValue

from .base import SAVE_VERSION, EntityId, Frozen
from .facts import Fact


class StepTrace(Frozen):
    name: str
    prompt: str | None = None
    output: dict[str, JsonValue] | str | None = None


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    save_version: int = SAVE_VERSION
    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    entry: Literal["turn"] = "turn"
    prompt: str
    narration: str
    steps: tuple[StepTrace, ...] = ()


class Applied(TraceEntryBase):
    """One advancement change: the same transaction as a turn, without a prompt or a narration."""

    entry: Literal["advancement"] = "advancement"
    subject_id: EntityId


type TraceEntry = Annotated[Turn | Applied, Field(discriminator="entry")]
