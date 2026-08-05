from fivee_test_support import ruleset
from pydantic import BaseModel, JsonValue

from aidm.core.mechanics import Mechanics
from aidm.core.packs import Content
from aidm.core.tools import world_toolset
from aidm.engines.dnd5e.tools import Dnd5eTools

TOOLSETS = (
    world_toolset(),
    Mechanics(content=Content(packs=(), records={}), refills={}).toolset(),
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
