from aidm.core.entities import EngineId, require_unique
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine


def build_engines() -> dict[EngineId, AnyEngine]:
    engines = (Loner3eEngine(), TunnelGoonsEngine(), BreathlessEngine(), TwentyfourxxEngine())
    require_unique("engine ids", (engine.id for engine in engines))
    return {engine.id: engine for engine in engines}
