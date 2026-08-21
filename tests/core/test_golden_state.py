import pytest
from core_test_support import game
from golden_test_support import FIXTURES, dumped, golden

from aidm.app.registry import engine_ids
from aidm.content.io import SavedGame
from aidm.state.model import EngineId


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_initial_state_of_a_shipped_game_serializes_unchanged(engine_id: EngineId) -> None:
    _, state = game(engine_id)
    golden(FIXTURES / "state" / f"{engine_id}.json", dumped(SavedGame.of(state)))
