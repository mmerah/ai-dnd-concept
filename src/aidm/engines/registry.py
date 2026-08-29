from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path

from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.state.entities import PLAYER_ID, EngineId, Entity, Slug
from aidm.state.model import Game

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


def begin_game(engine: Engine, scenario_id: Slug, scenario: Scenario, character: Character) -> Game:
    if scenario.engine != engine.id:
        raise ValueError(
            f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
            f"which the {engine.id!r} engine does not play"
        )
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
    items = (
        Entity.model_validate(
            {**item.model_dump(mode="json"), "rules": character.item_rules.get(item.id, {})}
        )
        for item in character.profile.items
    )
    for entity in (*items, player):
        if entity.id in world.entities:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        world.entities[entity.id] = entity
    state = Game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        packs=scenario.packs,
        player_id=PLAYER_ID,
        world=world,
        turn_facts=(),
    )
    engine.validate(state)
    return state.committed()
