import pytest
from core_test_support import game
from golden_test_support import FIXTURES, golden_json
from pydantic import BaseModel

from aidm.app.launch import engine_ids
from aidm.engines.world import commands
from aidm.state.entities import EngineId, EntityDetail
from aidm.turn.run import schema_of

# Schema descriptions steer the model; engine-specific meaning belongs in instructions.
SHARED_OUTPUTS: dict[str, type[BaseModel]] = {
    "entity_detail": EntityDetail,
}


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_director_is_offered_the_same_tools(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    golden_json(
        FIXTURES / "schemas" / engine_id / "director_tools.json",
        [
            {"name": one.name, "description": one.description, "parameters": schema_of(one.args)}
            for one in commands(engine)
        ],
    )


def test_the_shared_role_output_schemas_are_unchanged() -> None:
    for name, output in SHARED_OUTPUTS.items():
        golden_json(FIXTURES / "schemas" / f"{name}.json", output.model_json_schema())
