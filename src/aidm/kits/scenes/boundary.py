from aidm.state.entities import DEAD
from aidm.state.model import Game

# The safety net: a scene nobody ends is ended for them.
SCENE_TURN_CAP = 12
QUIET_TURNS = 2

SPENT_NOTE = (
    "This scene looks finished — {reason}. Call `next_scene` with what comes next if it is."
)


def scene_spent(state: Game) -> str | None:
    """Why this scene looks finished, or None. Computed, because a model left to notice an
    ending on its own sits in one scene forever."""
    world = state.world
    if world.spent:
        return world.spent
    # Every installed scene ships something to find, so an empty `hidden` means it was found.
    if not world.current.hidden:
        return "everything here has been found"
    if any(one.trait(DEAD) is not None for one in world.here()):
        return "someone here is dead"
    played = state.turn - world.opened_at
    if played >= QUIET_TURNS and not any(one.facts for one in state.history[-QUIET_TURNS:]):
        return f"nothing landed for {QUIET_TURNS} turns"
    if played >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None
