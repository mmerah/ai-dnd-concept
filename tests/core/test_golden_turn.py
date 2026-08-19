from collections.abc import Mapping
from random import Random

import pytest
from core_test_support import (
    LONER3E,
    TWENTYFOURXX,
    game,
    narrated,
    played,
    scripted,
    structured,
    text,
    tool_call,
)
from golden_test_support import FIXTURES, dumped, golden
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.function import FunctionModel

from aidm.app.registry import engine_ids
from aidm.state.base import EngineId
from aidm.state.history import Exchange, Line
from aidm.state.world import GameState
from aidm.turn.pipeline import TurnResult

PROMPT = "I lever up the loose flagstone and listen at the vault door."
# Played turns, so the history window, its rendering, and its replay as messages all run on real
# exchanges rather than on an empty tuple.
HISTORY = (
    Exchange(
        prompt="I try the vault door.",
        lines=(Line(text="The iron handle does not turn."),),
    ),
    Exchange(
        prompt="I look for another way in.",
        lines=(Line(text="A flagstone by the wall sits proud of its neighbours."),),
    ),
)
NARRATION = "The flagstone lifts. Beyond the door, something shifts its weight and waits."
SEED = 11
# One unconditional tool call every engine shares, so the two traces differ only by their roll.
TAKE_THE_MAP = tool_call("move", entity_id="vault_map", to_id="player")
# What the last tool call writes once the roll has landed: the same shape under every engine.
LISTENING = tool_call(
    "add_trait",
    entity_id="player",
    trait_id="listening",
    text="(condition) Listening for the next shift of weight behind the door.",
)
MEMORIES = [
    {
        "owner_id": "mara",
        "text": "Mara confirmed the vault door has not opened in thirty years.",
    }
]
TURN_STEPS = ("director", "hooks", "narrator", "worldkeeper")
# The fiction resolved by the engine's own roll.
SCRIPTS: Mapping[EngineId, tuple[ModelResponse, ...]] = {
    LONER3E: (
        TAKE_THE_MAP,
        tool_call(
            "roll_question",
            actor_id="player",
            question="Does he hear what waits past the vault door without being heard?",
            position="advantage",
            edge="Quiet Hands",
        ),
        LISTENING,
        text(NARRATION),
    ),
    TWENTYFOURXX: (
        TAKE_THE_MAP,
        tool_call(
            "roll_attempt",
            actor_id="player",
            goal="Listen at the vault door without being heard",
            skill="Stealth",
            helped="the relic-hunter's ear for old stone",
            luck_test="something behind the door is already listening back",
        ),
        LISTENING,
        text(NARRATION),
    ),
}


def _behind(state: GameState) -> GameState:
    draft = state.draft()
    draft.history = HISTORY
    return draft.committed()


async def _played(engine_id: EngineId) -> TurnResult:
    engine, state = game(engine_id)
    return await played(
        engine,
        _behind(state),
        PROMPT,
        director=FunctionModel(scripted(*SCRIPTS[engine_id])),
        narrator=FunctionModel(scripted(narrated(NARRATION))),
        worldkeeper=FunctionModel(scripted(structured(memories=MEMORIES))),
        rng=Random(SEED),
    )


@pytest.mark.parametrize("engine_id", engine_ids())
async def test_a_scripted_turn_renders_and_records_unchanged(engine_id: EngineId) -> None:
    result = await _played(engine_id)

    assert tuple(step.name for step in result.turn.steps) == TURN_STEPS
    for step in result.turn.steps:
        if step.prompt is not None:
            golden(FIXTURES / "prompts" / engine_id / f"{step.name}.txt", step.prompt)
    # The prompts live in their own fixtures; the trace holds everything else the turn recorded.
    golden(
        FIXTURES / "turn" / f"{engine_id}.json",
        dumped(result.turn, exclude={"steps": {"__all__": {"prompt"}}}),
    )
    golden(FIXTURES / "save" / f"{engine_id}.json", dumped(result.state))
