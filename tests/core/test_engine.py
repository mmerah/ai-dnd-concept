import pytest

from aidm.engines.core import director_tool
from aidm.state.entities import Frozen


def test_a_tool_parameter_the_model_cannot_read_is_refused() -> None:
    class Undescribed(Frozen):
        entity_id: str

    with pytest.raises(ValueError, match="carry no description"):
        _ = director_tool("touch", "Touch a thing.", Undescribed, lambda _draft, _args, _rng: ())
