from pathlib import Path
from random import Random

from core_test_support import (
    ENGINES_BUILT,
    LONER3E,
    ScriptedSpawner,
    character,
    offline_settings,
    scenario,
)

from aidm.app.runtime import Conversations, GameService, LaunchTarget
from aidm.core.io import FileStore
from aidm.engines.core import load_packs
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.engine import ENGINE_DIR
from aidm.engines.loner3e.rules import twist_table
from aidm.engines.loner3e.state import SRD_PACK

TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")
TWISTS = twist_table(load_packs((ENGINE_DIR / "packs",), Pack), SRD_PACK)


def loner3e_session(directory: Path) -> GameService:
    settings = offline_settings()
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
        sessions=Conversations(spawner, store, settings),
        settings=settings,
        rng=Random(1),
    )
