from pathlib import Path
from random import Random

from aidm.app.roles import Roles
from aidm.app.runtime import GameService, LaunchTarget
from aidm.config import Settings
from aidm.core.entities import Slug
from aidm.core.io import FileStore
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eCharacter, Loner3eGame, Loner3eScenario, Loner3eSheet
from aidm.engines.seam import AnyEngine
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    ScriptedSpawner,
    Table,
    game,
    narrowed,
    open_table,
)

TARGET = LaunchTarget(scenario_id="whispering-vault", character_id="kael")
ENGINE = narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine)


def with_entity(state: Loner3eGame, entity: Loner3eSheet) -> Loner3eGame:
    """Added to the cast and to the scene; `known` alone decides present or hidden."""
    draft = state.draft()
    draft.payload.cast[entity.id] = entity
    draft.payload.run.here.append(entity.id)
    return draft.commit()


def loner_sheet(state: Loner3eGame, entity_id: Slug) -> Loner3eSheet:
    return state.payload.require(entity_id)


def scenario() -> Loner3eScenario:
    return narrowed(LIBRARY.read_scenario("whispering-vault", SCENARIO_MODELS), Loner3eScenario)


def character() -> Loner3eCharacter:
    return narrowed(LIBRARY.read_character("kael", ENGINE.id, ENGINE.character), Loner3eCharacter)


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    return engine, narrowed(state, Loner3eGame)


def open_game(
    saves: Path,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
    engine: AnyEngine | None = None,
) -> Table[Loner3eGame]:
    return open_table(
        saves,
        rng=rng,
        settings=settings,
        engine=engine,
        engine_id=LONER3E,
        state_type=Loner3eGame,
    )


def session(directory: Path) -> GameService:
    spawner = ScriptedSpawner()
    store = FileStore(directory)
    return GameService(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=ENGINE,
        roles=Roles(spawner, ENGINE),
        store=store,
        rng=Random(1),
    )
