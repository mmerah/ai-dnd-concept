from pathlib import Path

from aidm.content.authored import Character, Scenario
from aidm.engines.engine import Engine
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.engines.sheets import SheetBase
from aidm.engines.twentyfourxx.rules import TwentyfourxxEngine
from aidm.state.base import PLAYER_ID, EngineId, Entity, Slug
from aidm.state.world import Game

# Engine's sheet type param is invariant, so each concrete engine's own sheet type doesn't
# statically widen to SheetBase here even though every engine satisfies the bound.
ENGINES: tuple[type[Engine[SheetBase]], ...] = (
    Loner3eEngine,  # pyright: ignore[reportAssignmentType]
    TwentyfourxxEngine,  # pyright: ignore[reportAssignmentType]
)


def engine_ids() -> tuple[EngineId, ...]:
    return tuple(engine.id for engine in ENGINES)


def engine_class(engine_id: EngineId) -> type[Engine[SheetBase]]:
    found = next((engine for engine in ENGINES if engine.id == engine_id), None)
    if found is None:
        raise ValueError(f"unknown engine {engine_id!r}")
    return found


def build_engine(engine_id: EngineId, extra_packs: Path | None = None) -> Engine[SheetBase]:
    return engine_class(engine_id)(extra_packs)


def begin_game(
    engine: Engine[SheetBase], scenario_id: Slug, scenario: Scenario, character: Character
) -> Game:
    """One opening state, so the app, the evals, and the tests all start a game the same way."""
    # Loaded content outlives the mutable game state, which restart() rebuilds from it.
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
    rules = {
        **character.overlay.entities,
        PLAYER_ID: character.overlay.character,
    }
    state = Game(
        scenario_id=scenario_id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        world=world,
        mechanics=engine.opening_mechanics(world, rules),
    )
    engine.validate(state)
    # The world was composed here by hand, so the commit is the only thing that validates it.
    return state.committed()
