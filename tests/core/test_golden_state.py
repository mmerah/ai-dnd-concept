import pytest
from core_test_support import SHIPPED, game
from golden_test_support import FIXTURES, dumped, golden

from aidm.core.entities import EngineId
from aidm.core.model import ScenarioKind


@pytest.mark.parametrize(("engine_id", "kind"), SHIPPED)
def test_the_initial_state_of_a_shipped_game_serializes_unchanged(
    engine_id: EngineId, kind: ScenarioKind
) -> None:
    _, state = game(engine_id, kind)
    suffix = "" if kind == "one-shot" else "-campaign"
    golden(FIXTURES / "state" / f"{engine_id}{suffix}.json", dumped(state))
