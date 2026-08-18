from pathlib import Path
from random import Random

from core_test_support import LONER3E, character, scenario, settings

from aidm.app.session import GameSession, LaunchTarget, build_advisor, build_engine
from aidm.content.store import FileStore
from aidm.turn.agents import build_turn_agents

TARGET = LaunchTarget(
    slug="poc", scenario_id="whispering-vault", character_id="kael", engine=LONER3E
)


def loner3e_session(directory: Path) -> GameSession:
    config = settings()
    engine = build_engine(LONER3E)
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        stages=build_turn_agents(engine, config),
        advisor=build_advisor(engine, config),
        store=FileStore(directory),
        settings=config,
        rng=Random(1),
    )
