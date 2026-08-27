import pytest
from core_test_support import game
from golden_test_support import FIXTURES, golden

from aidm.app.launch import engine_ids
from aidm.state.entities import EngineId
from aidm.turn import context


@pytest.mark.parametrize("engine_id", engine_ids())
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    roles = {
        "director": context.director_instructions(engine.director_instructions),
        "narrator": context.NARRATOR,
    }
    for name, instructions in roles.items():
        golden(FIXTURES / "instructions" / engine_id / f"{name}.txt", instructions)
