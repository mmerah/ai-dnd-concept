from collections.abc import Sequence
from pathlib import Path
from random import Random

from aidm.app.runtime import GameService, LaunchTarget
from aidm.config import Settings
from aidm.core.entities import EngineId, EntityId
from aidm.core.io import FileStore, read_character, read_scenario
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID
from aidm.engines.hub import Attempt, Campaign, Job, Offer
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import (
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eSheet,
    Loner3eWorld,
)
from aidm.engines.scenes.world import SceneRun
from aidm.engines.seam import AnyEngine
from support.table import (
    CHARACTERS,
    ENGINES_BUILT,
    LONER3E,
    SCENARIO_MODELS,
    SCENARIOS,
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


def with_entity(state: Loner3eGame, entity: Loner3eSheet) -> Loner3eGame:
    """Added to the cast and to the scene; `known` alone decides present or hidden."""
    draft = state.draft()
    draft.payload.cast[entity.id] = entity
    draft.payload.run.here.append(entity.id)
    return draft.commit()


def loner_sheet(state: Loner3eGame, entity_id: EntityId) -> Loner3eSheet:
    return state.payload.require(entity_id)


def scenario() -> Loner3eScenario:
    loaded = read_scenario(SCENARIOS, "whispering-vault", SCENARIO_MODELS)
    if not isinstance(loaded, Loner3eScenario):
        raise AssertionError("the Loner scenario parsed as another engine")
    return loaded


def character() -> Loner3eCharacter:
    engine = ENGINES_BUILT[LONER3E]
    loaded = read_character(CHARACTERS, "kael", engine.id, engine.character)
    if not isinstance(loaded, Loner3eCharacter):
        raise AssertionError("the Loner character parsed as another engine")
    return loaded


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    if not isinstance(state, Loner3eGame):
        raise AssertionError("the Loner engine began another game type")
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
    """A campaign world: a hub run with a known keeper, then one job run away from it."""
    keeper = Loner3eSheet(id=KEEPER, name="Keeper", brief="Runs the guild hall's board", known=True)
    hub_run = _hub_scene(here=[KEEPER])
    job_run = _job_scene()
    world = Loner3eWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=[hub_run, job_run],
        campaign=Campaign(
            place=HUB_PLACE,
            board=(
                Offer(title="Job One", pitch="I take job one."),
                Offer(title="Job Two", pitch="I take job two."),
            ),
            jobs=[
                Job(
                    title="The Sealed Cairn",
                    place=JOB_PLACE,
                    terms=JOB,
                    attempts=[Attempt(started=1)],
                )
            ],
        ),
    )
    return Loner3eGame(
        scenario_id="guild-hall",
        character_id="kael",
        scenario=ScenarioMeta(title="The Guild Hall", premise="A hub campaign.", kind="campaign"),
        engine=EngineId("loner3e"),
        payload=world,
    )


def loner3e_session(directory: Path) -> GameService:
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


def _hub_scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place=HUB_PLACE,
        title="The Guild Hall",
        question="What keeps Kael coming back to the guild hall tonight?",
        situation=HUB_SITUATION,
        here=list(here),
    )


def _job_scene(*, here: Sequence[EntityId] = ()) -> SceneRun:
    return SceneRun(
        place=JOB_PLACE,
        title="The Sealed Cairn",
        question="Can Kael break the cairn's seal before whatever is inside wakes?",
        situation=JOB_SITUATION,
        here=list(here),
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
