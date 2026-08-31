from importlib import import_module
from pathlib import Path
from random import Random
from typing import cast

import pytest
from core_test_support import ENGINE_IDS, Call, opened, played
from golden_test_support import FIXTURES, dumped, golden, golden_json
from golden_turn_support import NARRATION

from aidm.state.entities import EngineId
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.state.play import Exchange, SpokenLine

PROMPT = "I lever up the loose flagstone and listen at the vault door."
# Real played turns behind it, so RECENT PLAY and the told passages render something.
HISTORY = (
    Exchange(
        prompt="I try the vault door.",
        scene="the sealed vault",
        lines=(SpokenLine(text="The iron handle does not turn."),),
    ),
    Exchange(
        prompt="I look for another way in.",
        scene="the sealed vault",
        lines=(SpokenLine(text="A flagstone by the wall sits proud of its neighbours."),),
    ),
)
SEED = 11


def _script(engine_id: EngineId) -> tuple[Call, ...]:
    """Each engine's own package holds its scripted turn, so a new engine needs no core edit."""
    return cast(tuple[Call, ...], import_module(f"tests.{engine_id}.golden_turn").SCRIPT)


def _behind(state: Game) -> Game:
    draft = state.draft()
    draft.history = HISTORY
    return draft.committed()


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_scripted_turn_renders_and_records_unchanged(
    engine_id: EngineId, tmp_path: Path
) -> None:
    table = opened(tmp_path, rng=Random(SEED))
    table.service.commit(_behind(table.service.state))
    facts: list[Fact] = []

    await played(table, PROMPT, *_script(engine_id), narration=NARRATION, on_fact=facts.append)

    golden(FIXTURES / "prompts" / engine_id / "master.txt", table.spawner.prompt("master"))
    golden(FIXTURES / "prompts" / engine_id / "narrator.txt", table.spawner.prompt("narrator"))
    golden(FIXTURES / "prompts" / engine_id / "picture.txt", table.answers[0])
    # The prompts live in their own fixtures; these are everything else the turn produced.
    golden_json(
        FIXTURES / "turn" / f"{engine_id}.json", [fact.model_dump(mode="json") for fact in facts]
    )
    golden(FIXTURES / "save" / f"{engine_id}.json", dumped(table.service.state))
