import pytest
from core_test_support import game

from aidm.app.launch import engine_ids
from aidm.state.entities import EngineId


@pytest.mark.parametrize("engine_id", engine_ids())
def test_a_begun_game_summarises_the_players_own_sheet(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    pairs = engine.sheet_view(state)

    assert pairs
    assert all(label for label, _ in pairs)
    assert any(value for _, value in pairs)
