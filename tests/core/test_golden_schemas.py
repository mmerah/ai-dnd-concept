import pytest
from core_test_support import capability, game
from golden_test_support import FIXTURES, golden_json
from pydantic import BaseModel
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset, WrapperToolset

from aidm.app.registry import engine_ids
from aidm.engines.engine import PlanContext
from aidm.state.base import EngineId, EntityDetail
from aidm.turn.reports import WorldkeeperReport
from aidm.turn.tools import core_toolset

# A role's output schema is sent to the model, so its field descriptions steer it exactly as the
# instructions do. Every one of these is engine-independent: what each engine's calls mean is
# taught by its instructions, not by its wire shape.
SHARED_OUTPUTS: dict[str, type[BaseModel]] = {
    "worldkeeper_report": WorldkeeperReport,
    "entity_detail": EntityDetail,
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
    toolsets: tuple[AbstractToolset[PlanContext], ...] = (core_toolset(), *engine.director_toolsets)
    golden_json(
        FIXTURES / "schemas" / engine_id / "director_tools.json",
        [tool for toolset in toolsets for tool in _definitions(toolset)],
    )


def test_the_shared_role_output_schemas_are_unchanged() -> None:
    for name, output in SHARED_OUTPUTS.items():
        golden_json(FIXTURES / "schemas" / f"{name}.json", output.model_json_schema())


def _definitions(toolset: AbstractToolset[PlanContext]) -> list[dict[str, object]]:
    # The golden pins the fixed vocabulary; a wrapper's per-step narrowing has its own test.
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
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
