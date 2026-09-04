from pathlib import Path
from random import Random

from aidm.app.runtime import GameService, LaunchTarget
from aidm.config import Settings
from aidm.core.entities import EngineId, EntityId
from aidm.core.io import FileStore
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import (
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eSheet,
    Loner3eWorld,
)
from aidm.engines.seam import AnyEngine
from support.scenes import HubNames, hub_campaign, hub_runs
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    ScriptedSpawner,
    Table,
    game,
    open_table,
)

TARGET = LaunchTarget(scenario_id="whispering-vault", character_id="kael")
ENGINE = Loner3eEngine()

HUB_PLACE = "guild-hall"
JOB_PLACE = "sealed-cairn"
HUB_SITUATION = (
    "The guild hall is quiet before the evening crowd, and the keeper's board is chalked up on "
    "the wall."
)
JOB_SITUATION = (
    "The cairn's outer stones have been pried loose, and something older than the hill waits "
    "under them."
)
JOB = (
    "Orsa wants the cairn's seal broken and whatever is inside brought back whole; she pays in "
    "silver."
)
KEEPER = EntityId("keeper")
NAMES = HubNames(
    hub_place=HUB_PLACE,
    hub_title="The Guild Hall",
    hub_question="What keeps Kael coming back to the guild hall tonight?",
    hub_situation=HUB_SITUATION,
    job_place=JOB_PLACE,
    job_title="The Sealed Cairn",
    job_question="Can Kael break the cairn's seal before whatever is inside wakes?",
    job_situation=JOB_SITUATION,
    terms=JOB,
)


def with_entity(state: Loner3eGame, entity: Loner3eSheet) -> Loner3eGame:
    """Added to the cast and to the scene; `known` alone decides present or hidden."""
    draft = state.draft()
    draft.payload.cast[entity.id] = entity
    draft.payload.run.here.append(entity.id)
    return draft.commit()


def loner_sheet(state: Loner3eGame, entity_id: EntityId) -> Loner3eSheet:
    return state.payload.require(entity_id)


def scenario() -> Loner3eScenario:
    loaded = LIBRARY.read_scenario("whispering-vault", SCENARIO_MODELS)
    assert isinstance(loaded, Loner3eScenario), "the Loner scenario parsed as another engine"
    return loaded


def character() -> Loner3eCharacter:
    engine = ENGINES_BUILT[LONER3E]
    loaded = LIBRARY.read_character("kael", engine.id, engine.character)
    assert isinstance(loaded, Loner3eCharacter), "the Loner character parsed as another engine"
    return loaded


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    assert isinstance(state, Loner3eGame), "the Loner engine began another game type"
    return engine, state


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


def hub_world() -> Loner3eGame:
    keeper = Loner3eSheet(id=KEEPER, name="Keeper", brief="Runs the guild hall's board", known=True)
    world = Loner3eWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=hub_runs(NAMES, keeper=KEEPER),
        campaign=hub_campaign(NAMES),
    )
    return Loner3eGame(
        scenario_id="guild-hall",
        character_id="kael",
        scenario=ScenarioMeta(title="The Guild Hall", premise="A hub campaign.", kind="campaign"),
        engine=EngineId("loner3e"),
        payload=world,
    )


def session(directory: Path) -> GameService:
    engine = ENGINES_BUILT[LONER3E]
    spawner = ScriptedSpawner()
    store = FileStore(directory)
    return GameService(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        spawner=spawner,
        store=store,
        rng=Random(1),
    )


def _player() -> Loner3eSheet:
    return Loner3eSheet(
        id=PLAYER_ID,
        name="Kael",
        brief="A wary relic-hunter",
        known=True,
        concept="A Wary Relic-Hunter",
        tags={
            "skill": ["Reads Old Stonework"],
            "frailty": ["Never Walks Away"],
            "gear": ["Pry Bar"],
        },
        goal="Find what has been sealed away",
        motive="Whatever was worth sealing is worth more unsealed",
    )
