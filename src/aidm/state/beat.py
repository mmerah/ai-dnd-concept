from collections.abc import Callable
from typing import Literal

from pydantic import ValidationError

from .base import Frozen
from .facts import Fact
from .world import GameState

# Shared verbatim by every engine's own beat model (see `<engine>/actions.py`), so the two beats'
# prompt text cannot drift apart by a wording tweak made to only one of them.
BEAT_DOC = (
    "One thing put to the dice and what it causes. A turn is one beat, or several when what the "
    "dice settled asks for another."
)
BEAT_ROLL_DESCRIPTION = (
    "The one thing this beat puts to the dice, or null when nothing that happens is uncertain "
    "enough to roll."
)
BEAT_EFFECTS_DESCRIPTION = (
    "What this beat causes in the world, applied once the roll has settled. Empty when nothing "
    "changes."
)

type Followup = Literal["none", "settle", "continue"]


class Resolution(Frozen):
    facts: tuple[Fact, ...] = ()
    followup: Followup = "continue"


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
