from pathlib import Path

from aidm.core.entities import EngineId, Slug
from aidm.core.model import Character, Game, Scenario
from aidm.engines.core import Engine
from aidm.engines.loner3e.engine import build as build_loner3e


def build_engines(packs_dir: Path) -> dict[EngineId, Engine]:
    """User packs sit in a folder named for the engine, beside the ones the package ships."""
    engine = build_loner3e(packs_dir / "loner3e")
    return {engine.id: engine}


def begin_game(engine: Engine, scenario_id: Slug, scenario: Scenario, character: Character) -> Game:
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
    state = Game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        packs=scenario.packs,
        payload=engine.new_game(scenario, character),
    )
    engine.validate(state)
    return state.committed()
