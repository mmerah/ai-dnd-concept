from importlib import import_module
from random import Random
from typing import cast

import pytest
from core_test_support import game, narrated, played, scripted
from golden_test_support import FIXTURES, dumped, golden
from golden_turn_support import NARRATION
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.function import FunctionModel

from aidm.app.launch import engine_ids
from aidm.state.entities import EngineId
from aidm.state.model import Game
from aidm.state.play import Exchange, Line
from aidm.turn.run import TurnResult

PROMPT = "I lever up the loose flagstone and listen at the vault door."
# Use played turns so history rendering and replay cover real exchanges.
HISTORY = (
    Exchange(
        prompt="I try the vault door.",
        place="the sealed vault",
        lines=(Line(text="The iron handle does not turn."),),
    ),
    Exchange(
        prompt="I look for another way in.",
        place="the sealed vault",
        lines=(Line(text="A flagstone by the wall sits proud of its neighbours."),),
    ),
)
SEED = 11


def _script(engine_id: EngineId) -> tuple[ModelResponse, ...]:
    """Each engine's own package holds its scripted turn, so a new engine needs no core edit."""
    return cast(tuple[ModelResponse, ...], import_module(f"tests.{engine_id}.golden_turn").SCRIPT)


def _behind(state: Game) -> Game:
    draft = state.draft()
    draft.history = HISTORY
    return draft.committed()


async def _played(engine_id: EngineId) -> TurnResult:
    engine, state = game(engine_id)
    return await played(
        engine,
        _behind(state),
        PROMPT,
        director=FunctionModel(scripted(*_script(engine_id))),
        narrator=FunctionModel(scripted(narrated(NARRATION))),
        rng=Random(SEED),
    )


@pytest.mark.parametrize("engine_id", engine_ids())
async def test_a_scripted_turn_renders_and_records_unchanged(engine_id: EngineId) -> None:
    result = await _played(engine_id)

    for step in result.turn.steps:
        golden(FIXTURES / "prompts" / engine_id / f"{step.name}.txt", step.prompt)
    # The prompts live in their own fixtures; the trace holds everything else the turn recorded.
    golden(
        FIXTURES / "turn" / f"{engine_id}.json",
        dumped(result.turn, exclude={"steps": {"__all__": {"prompt"}}}),
    )
    golden(FIXTURES / "save" / f"{engine_id}.json", dumped(result.state))
