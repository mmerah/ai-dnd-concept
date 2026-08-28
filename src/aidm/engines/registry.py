from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path

from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.entities import PLAYER_ID, EngineId, Entity, Slug
from aidm.state.model import Game

# A new engine registers by existing; its folder name is the id its `build` must declare.
ENGINES: Mapping[EngineId, Callable[[PackSources], Engine]] = {
    EngineId(path.parent.name): import_module(f"aidm.engines.{path.parent.name}.engine").build
    for path in sorted(Path(__file__).parent.glob("*/engine.py"))
}


def build_engine(engine_id: EngineId, sources: PackSources = SHIPPED_PACKS) -> Engine:
    build = ENGINES.get(engine_id)
    if build is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    built = build(sources)
    if built.id != engine_id:
        raise ValueError(f"the {engine_id!r} package builds the {built.id!r} engine")
    return built


def begin_game(engine: Engine, scenario_id: Slug, scenario: Scenario, character: Character) -> Game:
    if scenario.engine != engine.id:
        raise ValueError(
            f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
            f"which the {engine.id!r} engine does not play"
        )
    engine.check_scenario(scenario)
    world = scenario.world.model_copy(deep=True)
    player = Entity(
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        parent_id=scenario.starting_location_id,
        traits=list(character.profile.traits),
        rules=dict(character.rules),
    )
    for entity in (*(item.model_copy(deep=True) for item in character.profile.items), player):
        if world.find(entity.id) is not None:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        world.entities.append(entity)
    state = Game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        player_id=PLAYER_ID,
        world=world,
        turn_events=(),
    )
    engine.validate(state)
    return state.committed()
