from aidm.core.entities import DEAD
from aidm.core.facts import Fact
from aidm.core.model import Game

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
    """Deliberately blunt: catches only what no reading of the fiction can miss."""
    run = state.world.run
    if run.spent:
        return run.spent
    if any(one.trait(DEAD) is not None for one in state.world.here()):
        return "someone here is dead"
    if len(run.exchanges) >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None
