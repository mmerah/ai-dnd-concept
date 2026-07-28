"""The per-turn context every role's prompt is built from."""

from collections.abc import Sequence
from dataclasses import dataclass

from ..content import Library
from ..domain.models import Event, Exchange, GameState


@dataclass(frozen=True, slots=True)
class TurnContext:
    """What is always present by the time any role renders. Per-stage payloads (`Direction`,
    `GrowthRequest`) are arguments to the builder that needs them, so none is ever `None`."""

    state: GameState
    prompt: str
    library: Library  # the loaded packs, injected so a test can play against a synthetic one
    events: Sequence[Event] = ()
    narration: str = ""
    recent: Sequence[Exchange] = ()  # already windowed by the pipeline; the single history slice
