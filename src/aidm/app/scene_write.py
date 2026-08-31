from aidm.core.facts import Fact
from aidm.core.model import Game, SceneWrite
from aidm.engines.core import Engine
from aidm.kits.scenes.worldsmith import apply_scene, scene_refusal
from aidm.turn.context import render_worldsmith

from .spawn import Ask, answered


async def write_next(snapshot: Game, intent: str, engine: Engine, ask: Ask) -> SceneWrite:
    prompt = render_worldsmith(
        snapshot.world, intent, engine.guidance(snapshot.packs), engine.sheet_rows(snapshot)
    )
    return await answered(
        "worldsmith",
        prompt,
        SceneWrite,
        lambda written: scene_refusal(written, snapshot.world),
        ask,
    )


def install_scene(engine: Engine, draft: Game, written: SceneWrite) -> tuple[Fact, ...]:
    closed = engine.scene_closed(draft)
    # A deep copy: the trial run and the real one must not share the entities the scene brings.
    apply_scene(draft.world, written.model_copy(deep=True))
    # Companions cross by code, so nothing else would tell the narrator they came along.
    came = [draft.world.require(one).name for one in draft.world.companions]
    trace = f"the story moves to {written.title}"
    if came:
        trace += f", and {', '.join(came)} travels there with the player"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}")
    return (*closed, opened)
