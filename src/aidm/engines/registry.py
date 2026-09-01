from pathlib import Path

from aidm.core.entities import EngineId, Slug
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario
from aidm.engines.core import AnyEngine
from aidm.engines.loner3e.engine import build as build_loner3e
from aidm.engines.tunnelgoons.engine import build as build_tunnelgoons


def build_engines(packs_dir: Path) -> dict[EngineId, AnyEngine]:
    """User packs sit in a folder named for the engine, beside the ones the package ships."""
    engines = (build_loner3e(packs_dir / "loner3e"), build_tunnelgoons())
    return {engine.id: engine for engine in engines}


def begin_game(
    engine: AnyEngine,
    scenario_id: Slug,
    scenario: AnyScenario,
    character: AnyCharacter,
) -> AnyGame:
    if scenario.engine != engine.id:
        raise ValueError(
            f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
            f"which the {engine.id!r} engine does not play"
        )
    if character.engine != engine.id:
        raise ValueError(
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
    return state.committed()
