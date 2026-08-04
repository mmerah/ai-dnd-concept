from fivee_test_support import ruleset
from pydantic import BaseModel, JsonValue
from pydantic_ai.toolsets import FunctionToolset

from aidm.plugins.dnd5e.tools import Dnd5eTools
from aidm.plugins.story.tools import story_toolset
from aidm.workflow.tools import TurnContext, world_toolset

TOOLSETS: tuple[FunctionToolset[TurnContext], ...] = (
    world_toolset(),
    story_toolset(),
    Dnd5eTools(ruleset()).toolset(),
)


class _Parameters(BaseModel):
    """A validated read of the tool schema, so the assertion below stays typed."""

    properties: dict[str, dict[str, JsonValue]] = {}


def test_every_director_tool_documents_itself_and_its_parameters() -> None:
    """The guidance every Director reads now lives on the tool schemas, not on a prompt string.
    Kept here because building the 5e toolset needs the shipped ruleset."""
    for toolset in TOOLSETS:
        for name, tool in toolset.tools.items():
            definition = tool.tool_def
            assert definition.description
            parameters = _Parameters.model_validate(definition.parameters_json_schema)
            for parameter, schema in parameters.properties.items():
                assert schema.get("description"), f"{name}.{parameter} has no description"
