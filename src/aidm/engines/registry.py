from importlib import import_module
from pathlib import Path

from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine
from aidm.engines.sources import SHIPPED_PACKS, PackSources
from aidm.state.entities import PLAYER_ID, EngineId, Entity, Slug
from aidm.state.model import Game


def _declared(package: str) -> type[Engine]:
    """A new engine registers by existing; the class must be declared there, not imported in."""
    module = import_module(f"aidm.engines.{package}.engine")
    found = [
        value
        for value in vars(module).values()
        if isinstance(value, type)
        and issubclass(value, Engine)
        and value.__module__ == module.__name__
    ]
    if len(found) != 1:
        raise ValueError(f"{module.__name__} declares {len(found)} engine classes, not one")
    return found[0]


ENGINES: tuple[type[Engine], ...] = tuple(
    _declared(path.parent.name) for path in sorted(Path(__file__).parent.glob("*/engine.py"))
)


def engine_class(engine_id: EngineId) -> type[Engine]:
    found = next((engine for engine in ENGINES if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def build_engine(engine_id: EngineId, sources: PackSources = SHIPPED_PACKS) -> Engine:
    return engine_class(engine_id)(sources)


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
        mechanics=engine.opening_mechanics(world, character.rules),
        turn_events=(),
    )
    engine.validate(state)
    return state.committed()
