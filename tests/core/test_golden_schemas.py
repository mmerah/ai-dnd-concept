import pytest
from support.golden import FIXTURES, golden_json
from support.table import ENGINE_IDS, game

from aidm.core.entities import EngineId
from aidm.core.tools import schema_of


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_the_master_is_offered_the_same_tools(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    golden_json(
        FIXTURES / "schemas" / engine_id / "master_tools.json",
        [
            {"name": tool.name, "description": tool.description, "parameters": schema_of(tool.args)}
            for tool in engine.tools.values()
        ],
    )
