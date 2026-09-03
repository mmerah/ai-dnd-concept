from collections.abc import Sequence
from pathlib import Path
from random import Random

from core_test_support import (
    ENGINES_BUILT,
    LONER3E,
    ScriptedSpawner,
    character,
    scenario,
)

from aidm.app.runtime import GameService, LaunchTarget
from aidm.core.entities import EngineId, EntityId
from aidm.core.io import FileStore
from aidm.core.model import ScenarioMeta
from aidm.engines.core import PLAYER_ID, load_packs
from aidm.engines.hub import Job, Offer
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.tools import Oracle, twist_table
from aidm.engines.loner3e.world import Loner3eGame, LonerCharacter, LonerWorld
from aidm.engines.scenes.world import SceneRun

TARGET = LaunchTarget(scenario_id="whispering-vault", character_id="kael")
PACKS = load_packs((Loner3eEngine.directory / "packs",), Pack)
TWISTS = twist_table(PACKS)
ORACLE = Oracle(PACKS)

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


def hub_world() -> Loner3eGame:
    """A campaign world: a hub run with a known keeper, then one job run away from it."""
    keeper = LonerCharacter(
        id=KEEPER, name="Keeper", brief="Runs the guild hall's board", known=True
    )
    hub_run = _hub_scene(here=[KEEPER])
    job_run = _job_scene()
    world = LonerWorld(
        cast={KEEPER: keeper},
        player=_player(),
        runs=[hub_run, job_run],
        hub=HUB_PLACE,
        board=(
            Offer(title="Job One", pitch="I take job one."),
            Offer(title="Job Two", pitch="I take job two."),
        ),
        jobs=[Job(title="The Sealed Cairn", place=JOB_PLACE, terms=JOB, started=1)],
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


def _player() -> LonerCharacter:
    return LonerCharacter(
        id=PLAYER_ID,
        name="Kael",
        brief="A wary relic-hunter",
        known=True,
        concept="A Wary Relic-Hunter",
        skills=("Reads Old Stonework",),
        frailties=("Never Walks Away",),
        gear=("Pry Bar",),
        goal="Find what has been sealed away",
        motive="Whatever was worth sealing is worth more unsealed",
    )
