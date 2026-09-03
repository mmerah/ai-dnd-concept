from pathlib import Path

from aidm.core.entities import EngineId, Refusal, Slug, require_unique
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine


def build_engines(packs_dir: Path) -> dict[EngineId, AnyEngine]:
    """User packs sit in a folder named for the engine, beside the ones the package ships."""
    engines = (
        Loner3eEngine(packs_dir / "loner3e"),
        TunnelGoonsEngine(),
        BreathlessEngine(packs_dir / "breathless"),
        TwentyfourxxEngine(packs_dir / "twentyfourxx"),
    )
    require_unique("engine ids", (engine.id for engine in engines))
    return {engine.id: engine for engine in engines}


def begin_game(
    engine: AnyEngine,
    scenario_id: Slug,
    scenario: AnyScenario,
    character: AnyCharacter,
) -> AnyGame:
    if scenario.engine != engine.id:
        raise Refusal(
            f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
            f"which the {engine.id!r} engine does not play"
        )
    if character.engine != engine.id:
        raise Refusal(
            f"{character.id!r} is written for the {character.engine!r} rules, "
            f"which the {engine.id!r} engine does not play"
        )
    state = engine.game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        packs=scenario.packs,
        payload=engine.new_game(scenario, character),
    )
    engine.validate(state)
    return state.commit()
