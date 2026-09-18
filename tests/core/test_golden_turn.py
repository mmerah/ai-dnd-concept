from pathlib import Path
from random import Random

import pytest
from pydantic import BaseModel
from support.golden import FIXTURES, golden, golden_json, golden_schema, masked, masked_master
from support.golden_turn import INTERJECTION, NARRATION, SCRIPTS
from support.table import ENGINE_IDS, ENGINES_BUILT, drain, game, open_table, play_turn

from aidm.core.entities import EngineId, Refusal
from aidm.core.model import Check, Generation
from aidm.engines.tools import HIRE

PROMPT = "I lever up the loose flagstone and listen at the vault door."
SEED = 19


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_scripted_turn_renders_and_records_unchanged(
    engine_id: EngineId, tmp_path: Path
) -> None:
    table = open_table(
        tmp_path, engine_id=engine_id, state_type=ENGINES_BUILT[engine_id].game, rng=Random(SEED)
    )
    # Deterministic so the interjection this engine's script triggers fires every run.
    table.service.chatter = Random(SEED)
    script, behind = SCRIPTS[engine_id]
    table.service.save(behind(table.state))

    await play_turn(table, PROMPT, *script, narration=NARRATION, then=(INTERJECTION,))
    await drain(table.service)

    engine = table.service.engine
    golden(
        FIXTURES / "prompts" / engine_id / "master.txt",
        masked_master(table.spawner.prompt("master"), engine.instructions),
    )
    golden(
        FIXTURES / "prompts" / engine_id / "narrator.txt",
        masked(table.spawner.prompt("narrator")),
    )
    # The prompts live in their own fixtures; these are everything else the turn produced.
    golden_json(
        FIXTURES / "turn" / f"{engine_id}.json",
        [fact.model_dump(mode="json") for fact in table.facts],
    )
    # Only a party spawns the interjection; an engine with none leaves the answer unused.
    if table.state.world.members():
        golden(
            FIXTURES / "prompts" / engine_id / "interjection.txt",
            masked(table.spawner.prompt("narrator", 1)),
        )


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_worldsmith_request_renders_unchanged(engine_id: EngineId) -> None:
    engine, state = game(engine_id)
    prompts: list[str] = []
    models: list[type[BaseModel]] = []

    async def recording[M: BaseModel](prompt: str, model: type[M], _check: Check[M]) -> M:
        prompts.append(prompt)
        models.append(model)
        raise Refusal("recorded")

    # The family's own write, not the seam's `hire`: the detail is a place to go.
    operation = next(operation for operation in engine.unwritten if operation != HIRE)
    request = Generation(operation=operation, detail="Deeper in, toward the sound.")
    with pytest.raises(Refusal, match="recorded"):
        await engine.advance(state.draft(), request, recording)
    golden(FIXTURES / "prompts" / engine_id / "worldsmith.txt", masked(prompts[0]))
    golden_schema(FIXTURES / "schemas" / engine_id / "worldsmith_answer.json", models[0])
