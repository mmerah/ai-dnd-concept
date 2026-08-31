from aidm.state.entities import DEAD
from aidm.state.facts import Fact
from aidm.state.model import Game

# The safety net: a scene nobody ends is ended for them.
SCENE_TURN_CAP = 12

SPENT_NOTE = "This scene looks spent — {reason}. If its question is settled, call `next_scene`."
SCENE_SETTLED = Fact(
    kind="scene_settled",
    trace=(
        "this scene is settled. Bring it to a close, then ask the player what they want to "
        "pursue next — in the fiction, naming what the scene left open, never as a list of "
        "choices. They may also stay and keep playing here, so ask; do not push them out"
    ),
    told=True,
)


def scene_spent(state: Game) -> str | None:
    """Why this scene looks spent, or None. Deliberately blunt: the scene's own question is what
    ends it, and these are only the cases no reading of the fiction can miss."""
    world = state.world
    if world.spent:
        return world.spent
    if any(one.trait(DEAD) is not None for one in world.here()):
        return "someone here is dead"
    if state.turn - world.opened_at >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None
