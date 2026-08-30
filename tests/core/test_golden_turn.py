from importlib import import_module
from random import Random
from typing import cast

import pytest
from core_test_support import ENGINE_IDS, Recorder, game, narrated, played, recorded
from golden_test_support import FIXTURES, dumped, golden, golden_json
from golden_turn_support import NARRATION
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.function import FunctionModel

from aidm.state.entities import EngineId
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import Exchange, Line

PROMPT = "I lever up the loose flagstone and listen at the vault door."
# Use played turns so history rendering and replay cover real exchanges.
HISTORY = (
    Exchange(
        prompt="I try the vault door.",
        scene="the sealed vault",
        lines=(Line(text="The iron handle does not turn."),),
    ),
    Exchange(
        prompt="I look for another way in.",
        scene="the sealed vault",
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


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_scripted_turn_renders_and_records_unchanged(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    roles: dict[str, Recorder] = {
        "director": recorded(*_script(engine_id)),
        "narrator": recorded(narrated(NARRATION)),
    }
    facts: list[Fact] = []

    played_state = await played(
        engine,
        _behind(state),
        PROMPT,
        director=FunctionModel(roles["director"].stub),
        narrator=FunctionModel(roles["narrator"].stub),
        rng=Random(SEED),
        on_fact=facts.append,
    )

    for name, role in roles.items():
        golden(FIXTURES / "prompts" / engine_id / f"{name}.txt", role.prompt())
    # The prompts live in their own fixtures; these are everything else the turn produced.
    golden_json(
        FIXTURES / "turn" / f"{engine_id}.json", [fact.model_dump(mode="json") for fact in facts]
    )
    golden(FIXTURES / "save" / f"{engine_id}.json", dumped(played_state))
