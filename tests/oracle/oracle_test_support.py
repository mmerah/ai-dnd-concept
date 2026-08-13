from core_test_support import game

from aidm.app.session import LaunchTarget
from aidm.engines.loader import Engine
from aidm.state.base import EngineId
from aidm.state.world import GameState

ORACLE = EngineId("oracle")
TARGET = LaunchTarget(
    slug="poc", scenario_id="whispering-vault", character_id="kael", engine=ORACLE
)


def oracle_game() -> tuple[Engine, GameState]:
    return game(ORACLE)


def at_milestone(state: GameState) -> GameState:
    """The state a resolved thread leaves behind: one milestone earned, advancement on offer."""
    draft = state.draft()
    draft.world.threads["vault-seal"].status = "resolved"
    return draft.committed()
