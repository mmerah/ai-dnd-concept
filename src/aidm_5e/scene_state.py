from aidm.agents.context import DirectorScene
from aidm.domain.base import SAVE_VERSION
from aidm.domain.definitions import ScenarioMeta
from aidm.domain.state import GameState

_UNUSED_SCENARIO = ScenarioMeta(title="(scene projection)", premise="(scene projection)")


def state_from_scene(scene: DirectorScene) -> GameState:
    """A DirectorScene carries no scenario meta; only world and engine state are read."""
    return GameState(
        save_version=SAVE_VERSION,
        scenario=_UNUSED_SCENARIO,
        world=scene.canon,
        engine=scene.engine,
    )
