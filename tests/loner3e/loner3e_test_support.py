from pathlib import Path
from random import Random

from core_test_support import ENGINES_BUILT, LONER3E, character, offline_settings, scenario

from aidm.app.runtime import GameSession, LaunchTarget
from aidm.content.io import FileStore
from aidm.engines.core import load_packs
from aidm.engines.loner3e.engine import ENGINE_DIR
from aidm.engines.loner3e.rules import SRD_PACK, Pack, twist_table
from aidm.turn.run import build_turn_agents

TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")
TWISTS = twist_table(load_packs((ENGINE_DIR / "packs",), Pack), SRD_PACK)


def loner3e_session(directory: Path) -> GameSession:
    settings = offline_settings()
    engine = ENGINES_BUILT[LONER3E]
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        stages=build_turn_agents(engine, settings),
        store=FileStore(directory),
        settings=settings,
        rng=Random(1),
    )
