from pathlib import Path
from random import Random

from core_test_support import ORACLE, character, scenario, settings

from aidm.app.session import Advancer, GameSession, LaunchTarget, build_engine
from aidm.content.store import FileSaves, FileTraces
from aidm.state.world import GameState
from aidm.turn.roles import build_stages

TARGET = LaunchTarget(
    slug="poc", scenario_id="whispering-vault", character_id="kael", engine=ORACLE
)


def oracle_session(directory: Path) -> GameSession:
    config = settings()
    engine = build_engine(ORACLE)
    return GameSession(
        target=TARGET,
        scenario=scenario(),
        character=character(),
        engine=engine,
        stages=build_stages(engine, config),
        advancer=Advancer.of(engine, config),
        saves=FileSaves(directory),
        traces=FileTraces(directory),
        history_window=6,
        max_growth=3,
        max_memories=2,
        rng=Random(1),
    )


def at_milestone(state: GameState) -> GameState:
    """The state a resolved thread leaves behind: one milestone earned, advancement on offer."""
    draft = state.draft()
    draft.world.threads["vault-seal"].status = "resolved"
    return draft.committed()
