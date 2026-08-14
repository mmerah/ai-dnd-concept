from collections.abc import Callable, Mapping

import pytest
from core_test_support import CAIRN2E, LONER3E, TWENTYFOURXX, capability, game, settings
from golden_test_support import FIXTURES, golden
from loner3e_test_support import at_milestone

from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId
from aidm.state.world import GameState
from aidm.turn.prompts import render_proposal
from aidm.turn.roles import (
    beat_stage,
    director_stage,
    narrator_stage,
    subsystem_stage,
    worldkeeper_stage,
)

WANTED = "I want to strike harder."

type OfferReady = Callable[[GameState], GameState]

# What each engine needs of a state before it offers an advancement to render the prompt from.
# One helper serves both engines: a resolved thread is both engines' advancement trigger.
READY_FOR_ADVANCEMENT: Mapping[EngineId, OfferReady] = {
    LONER3E: at_milestone,
    TWENTYFOURXX: at_milestone,
    CAIRN2E: at_milestone,
}


@pytest.mark.parametrize("engine_id", engine_ids())
def test_every_role_assembles_the_same_instructions(engine_id: EngineId) -> None:
    engine, _ = game(engine_id)
    config = settings()
    roles = {
        "director": director_stage(engine, config).instructions,
        "beat": beat_stage(engine, config).instructions,
        "narrator": narrator_stage(config).instructions,
        "worldkeeper": worldkeeper_stage(config).instructions,
        "advisor": subsystem_stage(capability(engine), config).instructions,
    }
    for name, instructions in roles.items():
        golden(FIXTURES / "instructions" / engine_id / f"{name}.txt", instructions)


@pytest.mark.parametrize("engine_id", engine_ids())
def test_the_advisor_prompt_renders_unchanged(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    earned = READY_FOR_ADVANCEMENT[engine_id](state)
    offers = capability(engine).offers(earned)
    assert offers
    golden(
        FIXTURES / "prompts" / engine_id / "advisor.txt",
        render_proposal(engine, earned, offers[0], WANTED),
    )
