from collections.abc import Callable

from pydantic import ValidationError

from .base import Frozen
from .facts import Fact
from .world import GameState


class Resolution(Frozen):
    facts: tuple[Fact, ...] = ()


def check_draft(
    state: GameState, act: Callable[[GameState], object], what: str = "the state this leaves"
) -> str | None:
    draft = state.draft()
    try:
        _ = act(draft)
        _ = draft.committed()
    except ValidationError as broken:
        return f"{what} is invalid: {broken.errors()[0]['msg']}"
    except ValueError as refused:
        return str(refused)
    return None
