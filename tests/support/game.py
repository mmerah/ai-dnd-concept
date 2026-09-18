from functools import partial
from pathlib import Path
from random import Random

from aidm.app.runtime import GameService, LaunchTarget
from aidm.core.entities import Slug
from aidm.engines.engine import AnyEngine
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eCharacter, Loner3eEntity, Loner3eGame, Loner3eScenario
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    game,
    narrowed,
    open_table,
)

TARGET = LaunchTarget(scenario_id="whispering-vault", character_id="kael")
MAP: Slug = "vault-map"
MARA: Slug = "mara"
SITUATION = (
    "A frost-rimed colonnade around a dead garden, and the way down is somewhere under it. "
    "Nothing here has been swept in a long while."
)
ENGINE = narrowed(ENGINES_BUILT[LONER3E], Loner3eEngine)


def with_entity(state: Loner3eGame, entity: Loner3eEntity) -> Loner3eGame:
    """Added to the cast and to the scene; `known` alone decides present or hidden."""
    draft = state.draft()
    draft.world.cast[entity.id] = entity
    draft.world.scene.here.append(entity.id)
    return draft.commit()


def loner_sheet(state: Loner3eGame, entity_id: Slug) -> Loner3eEntity:
    return state.world.require(entity_id)


def scenario() -> Loner3eScenario:
    return narrowed(LIBRARY.read_scenario("whispering-vault", SCENARIO_MODELS), Loner3eScenario)


def character() -> Loner3eCharacter:
    return narrowed(LIBRARY.read_character("kael", ENGINE.id, ENGINE.character), Loner3eCharacter)


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    return engine, narrowed(state, Loner3eGame)


open_game = partial(open_table, engine_id=LONER3E, state_type=Loner3eGame)


def session(directory: Path) -> GameService:
    return open_game(directory, rng=Random(1)).service
