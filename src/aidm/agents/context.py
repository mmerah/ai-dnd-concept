"""The per-turn context and the block shapes prompts are built from."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..domain.models import Direction, Event, Exchange, GameState, GrowthRequest


@dataclass(frozen=True, slots=True)
class TurnContext:
    """What is always present by the time any role renders. Per-stage payloads (`Direction`,
    `GrowthRequest`) are passed to `prompt_for` instead, so no renderer must None-guard."""

    state: GameState
    prompt: str
    events: Sequence[Event] = ()
    narration: str = ""
    recent: Sequence[Exchange] = ()  # already windowed by the pipeline; the single history slice


# Three block shapes: a plain block reads only the context; a direction/request block also takes
# its stage payload, non-optional — which is what keeps the payload types free of `| None`.
@dataclass(frozen=True, slots=True)
class Block:
    label: str
    render: Callable[[TurnContext], str]


@dataclass(frozen=True, slots=True)
class DirectionBlock:
    label: str
    render: Callable[[TurnContext, Direction], str]


@dataclass(frozen=True, slots=True)
class RequestBlock:
    label: str
    render: Callable[[TurnContext, GrowthRequest], str]


AnyBlock = Block | DirectionBlock | RequestBlock


@dataclass(frozen=True, slots=True)
class RolePolicy:
    """A role's whole view: the blocks its prompt is built from, and whether it also receives play
    history as native messages (the Creator alone reads it as the RECENT_PLAY text instead)."""

    blocks: tuple[AnyBlock, ...]
    native_history: bool = False
