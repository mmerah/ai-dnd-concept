from importlib import import_module
from pathlib import Path
from random import Random
from typing import cast

import pytest
from core_test_support import ENGINE_IDS, Call, opened_for, played
from golden_test_support import FIXTURES, dumped, golden, golden_json
from golden_turn_support import NARRATION

from aidm.core.entities import PLAYER_ID, EngineId
from aidm.core.facts import Fact
from aidm.core.model import AnyGame
from aidm.core.play import Exchange, SpokenLine
from aidm.engines.loner3e.state import Loner3eGame
from aidm.engines.mazerats.state import MazeRatsGame
from aidm.kits.scenes.state import Scene, SceneRun

PROMPT = "I lever up the loose flagstone and listen at the vault door."
SEED = 11


def _script(engine_id: EngineId) -> tuple[Call, ...]:
    """Each engine's own package holds its scripted turn, so a new engine needs no core edit."""
    return cast(tuple[Call, ...], import_module(f"tests.{engine_id}.golden_turn").SCRIPT)


def _behind(state: AnyGame) -> AnyGame:
    """One played turn in the scene before this one: RECENT PLAY has to group by run, not title."""
    if isinstance(state, MazeRatsGame):
        return _maze_behind(state)
    if not isinstance(state, Loner3eGame):
        raise AssertionError(f"unsupported golden engine state: {type(state).__name__}")
    draft = state.draft()
    draft.payload.world.runs.insert(
        0,
        SceneRun(
            scene=Scene(
                place="vault-stair",
                title="The Vault Stair",
                question="Is there a way past the vault door from the stair?",
                situation=(
                    "A short flight of steps ends at an iron door, sealed, "
                    "the abbey's dust undisturbed on its sill."
                ),
            ),
            present=[PLAYER_ID],
            exchanges=[
                Exchange(
                    prompt="I try the vault door.",
                    lines=(SpokenLine(text="The iron handle does not turn."),),
                )
            ],
        ),
    )
    draft.payload.world.run.exchanges = [
        Exchange(
            prompt="I look for another way in.",
            lines=(SpokenLine(text="A flagstone by the wall sits proud of its neighbours."),),
        )
    ]
    return draft.committed()


def _maze_behind(state: MazeRatsGame) -> MazeRatsGame:
    draft = state.draft()
    draft.payload.world.visit.exchanges = [
        Exchange(
            prompt="I study the boot prints.",
            lines=(SpokenLine(text="The prints disappear beneath the silver arch."),),
        )
    ]
    return draft.committed()


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
async def test_a_scripted_turn_renders_and_records_unchanged(
    engine_id: EngineId, tmp_path: Path
) -> None:
    table = opened_for(tmp_path, engine_id, rng=Random(SEED))
    table.service.commit(_behind(table.state))
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
