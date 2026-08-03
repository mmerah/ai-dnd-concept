from dataclasses import dataclass

from pydantic import JsonValue

from .base import EngineId, EntityId, Frozen
from .facts import Fact
from .world import GameState


class Direction(Frozen):
    """The Director's proposal seen flat: core reads the three strings, the engine owns the rest."""

    engine: EngineId
    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: JsonValue = None


@dataclass(frozen=True, slots=True)
class Transition:
    """One engine transaction: a revalidated state and the facts that produced it."""

    state: GameState
    facts: tuple[Fact, ...]
