from pathlib import Path

from aidm.core.entities import EngineId
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine


def build_engines(packs_dir: Path) -> dict[EngineId, AnyEngine]:
    """`packs_dir / <engine id>` holds the packs the player wrote for that engine."""
    engines = tuple(
        engine(packs_dir / engine.id)
        for engine in (Loner3eEngine, TunnelGoonsEngine, TwentyfourxxEngine)
    )
    ids = [engine.id for engine in engines]
    if len(set(ids)) != len(ids):
        raise ValueError(f"engine ids are not unique: {ids}")
    return {engine.id: engine for engine in engines}
