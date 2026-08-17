import pytest
from core_test_support import at_boundary, capability, game, settings
from golden_test_support import FIXTURES, golden

from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId
from aidm.turn.prompts import render_proposal
from aidm.turn.roles import advancement_stage, director_stage, narrator_stage, worldkeeper_stage

WANTED = "I want to strike harder."


@pytest.mark.parametrize("engine_id", engine_ids())
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    config = settings()
    roles = {
        "director": director_stage(engine, config).instructions,
        "narrator": narrator_stage(config).instructions,
        "worldkeeper": worldkeeper_stage(config).instructions,
        "advisor": advancement_stage(capability(engine), config).instructions,
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
