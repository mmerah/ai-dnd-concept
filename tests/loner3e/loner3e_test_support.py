from pathlib import Path
from random import Random

from core_test_support import LONER3E, character, offline_settings, scenario

from aidm.app.runtime import GameSession, LaunchTarget
from aidm.content.io import FileStore
from aidm.engines.registry import build_engine
from aidm.turn.run import advisor_agent, build_turn_agents

TARGET = LaunchTarget(slug="poc", scenario_id="whispering-vault", character_id="kael")


def loner3e_session(directory: Path) -> GameSession:
    settings = offline_settings()
    engine = build_engine(LONER3E)
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        stages=build_turn_agents(engine, settings),
        advisor=advisor_agent(engine.advancement, settings),
        store=FileStore(directory),
        settings=settings,
        rng=Random(1),
    )
