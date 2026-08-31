import pytest
from core_test_support import ENGINE_IDS, game
from golden_test_support import FIXTURES, golden_json

from aidm.core.entities import EngineId
from aidm.core.tools import schema_of


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_the_master_is_offered_the_same_tools(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    golden_json(
        FIXTURES / "schemas" / engine_id / "master_tools.json",
        [
            {"name": one.name, "description": one.description, "parameters": schema_of(one.args)}
            for one in engine.tools
        ],
    )
