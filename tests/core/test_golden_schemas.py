import pytest
from support.golden import FIXTURES, golden_json, golden_schema
from support.table import ENGINE_IDS, game

from aidm.core.entities import EngineId
from aidm.core.play import Interjection, Narration
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


def test_the_narrator_answer_shapes_are_shared_by_every_engine() -> None:
    golden_schema(FIXTURES / "schemas" / "narration.json", Narration)
    golden_schema(FIXTURES / "schemas" / "interjection.json", Interjection)
