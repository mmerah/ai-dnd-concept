from typing import Literal

import pytest

from aidm.core.entities import Frozen
from aidm.core.model import AnyGame
from aidm.core.tools import MasterTool, master_tool, schema_of

type Kind = Literal["gear", "condition"]


def test_a_tool_parameter_the_model_cannot_read_is_refused() -> None:
    class Undescribed(Frozen):
        entity_id: str

    with pytest.raises(ValueError, match="carry no description"):
        tool: MasterTool[AnyGame] = master_tool(
            "touch", "Touch a thing.", Undescribed, lambda _draft, _args, _rng: ()
        )
        _ = tool


def test_a_schema_is_one_tree_with_no_class_name_in_it() -> None:
    class Marked(Frozen):
        kind: Kind | None = None

    assert schema_of(Marked) == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"enum": ["gear", "condition"], "type": ["string", "null"], "default": None}
        },
    }
