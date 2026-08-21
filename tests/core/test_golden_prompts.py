import pytest
from core_test_support import at_boundary, capability, game
from golden_test_support import FIXTURES, golden

from aidm.app.registry import engine_ids
from aidm.state.model import EngineId
from aidm.turn import context as prompts
from aidm.turn.context import render_proposal

WANTED = "I want to strike harder."


@pytest.mark.parametrize("engine_id", engine_ids())
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    roles = {
        "director": prompts.director_instructions(engine.director_instructions),
        "narrator": prompts.NARRATOR,
        "advisor": prompts.advisor_instructions(capability(engine).instructions),
    }
    for name, instructions in roles.items():
        golden(FIXTURES / "instructions" / engine_id / f"{name}.txt", instructions)


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_advisor_prompt_renders_unchanged(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    earned = at_boundary(state)
    offers = capability(engine).offers(earned)
    assert offers
    golden(
        FIXTURES / "prompts" / engine_id / "advisor.txt",
        render_proposal(engine, earned, offers[0], WANTED),
    )
