import pytest
from core_test_support import game
from golden_test_support import FIXTURES, dumped, golden

from aidm.engines.loader import engine_ids
from aidm.state.base import SAVE_VERSION, EngineId

# The version the golden state and turn fixtures were cut at. A save-shape change moves it, and
# must regenerate those fixtures in the same commit.
FIXTURE_SAVE_VERSION = 56


def test_the_save_version_the_fixtures_were_cut_at_has_not_moved() -> None:
    assert SAVE_VERSION == FIXTURE_SAVE_VERSION


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_initial_state_of_a_shipped_game_serializes_unchanged(engine_id: EngineId) -> None:
    _, state = game(engine_id)
    golden(FIXTURES / "state" / f"{engine_id}.json", dumped(state))
