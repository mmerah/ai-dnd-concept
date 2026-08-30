from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path

from aidm.engines.core import Engine
from aidm.kernel.protocol import AnyEngine
from aidm.state.entities import EngineId, Slug
from aidm.state.model import Character, Game, Scenario

# A new engine registers by existing; its folder name is the id its `build` must declare.
ENGINES: Mapping[EngineId, Callable[[Path], Engine]] = {
    EngineId(path.parent.name): import_module(f"aidm.engines.{path.parent.name}.engine").build
    for path in sorted(Path(__file__).parent.glob("*/engine.py"))
}


def build_engines(packs_dir: Path) -> dict[EngineId, Engine]:
    built: dict[EngineId, Engine] = {}
    for engine_id, build in ENGINES.items():
        one = build(packs_dir / engine_id)
        if one.id != engine_id:
            raise ValueError(f"the {engine_id!r} package builds the {one.id!r} engine")
        built[engine_id] = one
    return built


def begin_game(
    engine: AnyEngine, scenario_id: Slug, scenario: Scenario, character: Character
) -> Game:
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
        turn_facts=(),
        payload=engine.new_game(scenario, character),
    )
    engine.validate(state)
    return state.committed()
