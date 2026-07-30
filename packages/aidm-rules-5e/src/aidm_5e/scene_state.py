from aidm.agents.context import DirectorScene
from aidm.domain.definitions import ScenarioMeta
from aidm.domain.engine import EngineStamp
from aidm.domain.state import GameState

_UNUSED_SCENARIO = ScenarioMeta(title="(scene projection)", premise="(scene projection)")


def state_from_scene(scene: DirectorScene, stamp: EngineStamp) -> GameState:
    """A DirectorScene carries no scenario meta; only world and rules are read."""
    return GameState(
        engine=stamp,
        scenario=_UNUSED_SCENARIO,
        world=scene.canon,
        rules=scene.game_rules,
    )
