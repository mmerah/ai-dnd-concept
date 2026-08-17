import pytest
from core_test_support import capability, game
from golden_test_support import FIXTURES, golden_json
from pydantic import BaseModel
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId, EntityDetail
from aidm.state.plan import DirectorBeat
from aidm.state.turn import WorldkeeperReport

# A role's output schema is sent to the model, so its field descriptions steer it exactly as the
# instructions do. Every one of these is engine-independent: the Director's wire contract is one
# shape for every engine, and what each engine's calls mean is taught by its instructions.
SHARED_OUTPUTS: dict[str, type[BaseModel]] = {
    "worldkeeper_report": WorldkeeperReport,
    "entity_detail": EntityDetail,
    "turn_beat": DirectorBeat,
}


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_proposal_schema_the_advisor_answers_with_is_unchanged(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    golden_json(
        FIXTURES / "schemas" / engine_id / "proposal.json",
        capability(engine).proposal_type.model_json_schema(),
    )


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_director_is_offered_the_same_tools(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    golden_json(
        FIXTURES / "schemas" / engine_id / "director_tools.json",
        [tool for toolset in engine.director_toolsets for tool in _definitions(toolset)],
    )


def test_the_shared_role_output_schemas_are_unchanged() -> None:
    for name, output in SHARED_OUTPUTS.items():
        golden_json(FIXTURES / "schemas" / f"{name}.json", output.model_json_schema())


def _definitions(toolset: AbstractToolset[object]) -> list[dict[str, object]]:
    if not isinstance(toolset, FunctionToolset):
        raise TypeError(f"{type(toolset).__name__} declares no tools to lock")
    return [
        {
            "name": tool.tool_def.name,
            "description": tool.tool_def.description,
            "parameters": tool.tool_def.parameters_json_schema,
        }
        for tool in toolset.tools.values()
    ]
