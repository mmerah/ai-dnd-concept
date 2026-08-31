import pytest
from core_test_support import ENGINE_IDS, game
from golden_test_support import FIXTURES, dumped, golden

from aidm.core.entities import EngineId


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_the_initial_state_of_a_shipped_game_serializes_unchanged(engine_id: EngineId) -> None:
    _, state = game(engine_id)
    golden(FIXTURES / "state" / f"{engine_id}.json", dumped(state))
