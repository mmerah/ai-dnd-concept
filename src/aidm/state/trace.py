from pydantic import JsonValue

from .base import EntityId, Frozen
from .facts import Fact


class StepTrace(Frozen):
    name: str
    prompt: str | None = None
    output: dict[str, JsonValue] | str | None = None


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    facts: tuple[Fact, ...] = ()


class Turn(TraceEntryBase):
    prompt: str
    narration: str
    steps: tuple[StepTrace, ...] = ()


class Applied(TraceEntryBase):
    """One advancement change: the same transaction as a turn, without a prompt or a narration."""

    subject_id: EntityId


type TraceEntry = Turn | Applied
