from collections.abc import Callable, Mapping

import pytest
from core_test_support import DND5E, STORY, capability, game, settings
from fivee_test_support import ready
from golden_test_support import FIXTURES, golden
from story_test_support import grown

from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId
from aidm.state.world import GameState
from aidm.turn.advancement import advisor, render_proposal
from aidm.turn.pipeline import director_stage, narrator_stage, scene_stage, worldkeeper_stage

WANTED = "I want to strike harder."

type OfferReady = Callable[[GameState], GameState]

# What each engine needs of a state before it offers an advancement to render the prompt from.
READY_FOR_ADVANCEMENT: Mapping[EngineId, OfferReady] = {STORY: grown, DND5E: ready}


@pytest.mark.parametrize("engine_id", engine_ids())
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    config = settings()
    roles = {
        "director": director_stage(engine, config).instructions,
        "narrator": narrator_stage(config).instructions,
        "worldkeeper": worldkeeper_stage(config).instructions,
        "advisor": advisor(capability(engine), config).instructions,
        "scene": scene_stage(config).instructions,
    }
    for name, instructions in roles.items():
        golden(FIXTURES / "instructions" / engine_id / f"{name}.txt", instructions)


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_advisor_prompt_renders_unchanged(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    earned = READY_FOR_ADVANCEMENT[engine_id](state)
    offer = capability(engine).offered(earned)
    assert offer is not None
    golden(
        FIXTURES / "prompts" / engine_id / "advisor.txt",
        render_proposal(engine, earned, offer, WANTED),
    )
