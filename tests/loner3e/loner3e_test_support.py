from pathlib import Path
from random import Random

from core_test_support import LONER3E, character, scenario, settings

from aidm.app.session import Advancer, GameSession, LaunchTarget, build_engine
from aidm.content.store import FileStore
from aidm.state.world import GameState
from aidm.turn.roles import build_stages

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
        stages=build_stages(engine, config),
        advancer=Advancer.of(engine, config),
        store=FileStore(directory),
        settings=config,
        rng=Random(1),
    )


def at_milestone(state: GameState) -> GameState:
    """The state a resolved thread leaves behind: one milestone earned, advancement on offer."""
    draft = state.draft()
    draft.world.threads["vault-seal"].status = "resolved"
    return draft.committed()
