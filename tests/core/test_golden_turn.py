from asyncio import gather
from importlib import import_module
from pathlib import Path
from random import Random
from typing import cast

import pytest
from support.golden import FIXTURES, golden, golden_json
from support.golden_turn import INTERJECTION, NARRATION
from support.table import ENGINE_IDS, Call, open_game_for, play_turn

from aidm.core.entities import EngineId
from aidm.core.model import AnyGame

PROMPT = "I lever up the loose flagstone and listen at the vault door."
SEED = 19


def _script(engine_id: EngineId) -> tuple[Call, ...]:
    """Each engine's own package holds its scripted turn, so a new engine needs no core edit."""
    return cast(tuple[Call, ...], import_module(f"tests.{engine_id}.golden_turn").SCRIPT)


def _behind(engine_id: EngineId, state: AnyGame) -> AnyGame:
    """Each engine's own package holds how one prior exchange is added to its state."""
    return cast(AnyGame, import_module(f"tests.{engine_id}.golden_turn").behind(state))


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_scripted_turn_renders_and_records_unchanged(
    engine_id: EngineId, tmp_path: Path
) -> None:
    table = open_game_for(tmp_path, engine_id, rng=Random(SEED))
    table.service.commit(_behind(engine_id, table.state))

    await play_turn(table, PROMPT, *_script(engine_id), narration=NARRATION, then=(INTERJECTION,))
    await gather(*table.service._background)  # pyright: ignore[reportPrivateUsage]

    golden(FIXTURES / "prompts" / engine_id / "master.txt", table.spawner.prompt("master"))
    golden(FIXTURES / "prompts" / engine_id / "narrator.txt", table.spawner.prompt("narrator"))
    # The prompts live in their own fixtures; these are everything else the turn produced.
    golden_json(
        FIXTURES / "turn" / f"{engine_id}.json",
        [fact.model_dump(mode="json") for fact in table.facts],
    )
    # Only a party spawns the interjection; an engine with none leaves the answer unused.
    if table.service.engine.world(table.state).members():
        golden(
            FIXTURES / "prompts" / engine_id / "interjection.txt",
            table.spawner.prompt("narrator", 1),
        )
