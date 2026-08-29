import pytest
from core_test_support import ENGINE_IDS, game
from golden_test_support import FIXTURES, golden

from aidm.state.entities import EngineId
from aidm.turn import context


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    roles = {
        "director": context.director_instructions(engine.instructions),
        "narrator": context.NARRATOR,
    }
    for name, instructions in roles.items():
        golden(FIXTURES / "instructions" / engine_id / f"{name}.txt", instructions)
