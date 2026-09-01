from collections.abc import Sequence

from pydantic import BaseModel

from aidm.core.entities import DEAD
from aidm.core.facts import Fact, cards
from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.kits.scenes.state import SceneState

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


def scene_spent[S: BaseModel](world: SceneState[S]) -> str | None:
    """Deliberately blunt: catches only what no reading of the fiction can miss."""
    run = world.run
    if run.spent:
        return run.spent
    if any(one.trait(DEAD) is not None for one in world.here()):
        return "someone here is dead"
    if len(run.exchanges) >= SCENE_TURN_CAP:
        return f"{SCENE_TURN_CAP} turns have passed here"
    return None


def history[S: BaseModel](world: SceneState[S]) -> tuple[Exchange, ...]:
    return world.exchanges()


def record[S: BaseModel](
    state: AnyGame,
    world: SceneState[S],
    prompt: str,
    lines: tuple[SpokenLine, ...],
    facts: Sequence[Fact],
) -> tuple[str, ...]:
    world.run.exchanges.append(
        Exchange(
            prompt=prompt,
            lines=lines,
            facts=cards(facts),
            decision="" if state.pending is None else state.pending.prompt,
        )
    )
    if world.run.settled or len(world.run.exchanges) <= 1:
        return ()
    reason = scene_spent(world)
    return () if reason is None else (SPENT_NOTE.format(reason=reason),)
