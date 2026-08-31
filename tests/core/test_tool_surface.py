import asyncio
import json
from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    LONER3E,
    Table,
    change_args,
    narrated,
    offline_settings,
    opened,
    played,
    updated,
)
from pydantic import JsonValue

from aidm.app.mcp import ALREADY_OPEN, DECIDING, START_FIRST, call, offered
from aidm.app.runtime import NO_TURN
from aidm.app.spawn import CliSpawner, final_message
from aidm.kits.scenes.boundary import scene_spent
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.model import SceneWrite
from aidm.state.play import Narration

VAULT_MAP = EntityId("vault-map")
MARA = EntityId("mara")
A_CONFLICT: dict[str, JsonValue] = {
    "actor_id": PLAYER_ID,
    "question": "Does he wrest the ledger out of her hands?",
    "opponent_id": MARA,
}
A_SCENE = {
    "place": "cloister-walk",
    "title": "The Cloister Walk",
    "situation": "Rain drums the open arcade and the flagstones run black with it, and Mara waits "
    "at the far end with the lantern shuttered to a slit.",
    "present": ["mara"],
    "hidden": ["tomas"],
    "note": "Tomas is listening from the chapter house door.",
}


def _scene(**changes: object) -> str:
    return json.dumps(A_SCENE | changes)


def test_the_surface_publishes_four_fixed_tools_plus_the_engines(tmp_path: Path) -> None:
    table = opened(tmp_path)

    names = [tool.name for tool in offered(table.runtime)]

    assert names[:3] == ["start_turn", "scene", "next_scene"]
    assert {"change_world", "roll_question"} <= set(names)
    assert "end_turn" not in names


def test_no_tool_runs_before_a_turn_is_open(tmp_path: Path) -> None:
    table = opened(tmp_path)

    with pytest.raises(ValueError, match=NO_TURN):
        _ = call(table.runtime, "scene", {})


async def test_the_legality_table_says_what_to_do_instead(tmp_path: Path) -> None:
    table = opened(tmp_path)

    def script() -> None:
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP))
        _ = table.call("start_turn", {})
        _ = table.call("start_turn", {})
        _ = table.call("scene", {"junk": 1})

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("Dust hangs.")]
    await table.service.play("I look around.")

    assert table.refusals[0] == START_FIRST
    assert table.refusals[1] == ALREADY_OPEN
    assert "junk" in table.refusals[2]


async def test_a_change_lands_on_the_draft_as_it_is_made_and_on_disk_at_the_end(
    tmp_path: Path,
) -> None:
    landed: list[int] = []

    table = opened(tmp_path)

    def script() -> None:
        _ = table.call("start_turn", {})
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP))
        turn = table.service.turn
        assert turn is not None
        landed.append(len(turn.draft.turn_facts))

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("A chart, under the stone.")]
    await table.service.play("I lever up the flagstone.")

    assert landed == [1]
    saved = table.saved()
    assert saved.world.require(VAULT_MAP).known
    assert saved.turn_facts == ()
    assert len(saved.history[-1].facts) == 1


async def test_an_open_decision_blocks_every_other_tool_until_the_player_answers(
    tmp_path: Path,
) -> None:
    """An unfinished conflict: nothing else lands until the player's next message answers it."""
    table = opened(tmp_path, rng=Random(0))

    state = await played(
        table,
        "I grab for the ledger in her hands.",
        ("roll_question", A_CONFLICT),
        ("change_world", change_args("reveal", entity_id=VAULT_MAP)),
        narration="She holds on.",
    )

    assert state.pending is not None
    assert any("waiting on the player" in one for one in table.answers)
    assert not state.world.require(VAULT_MAP).known

    state = await played(table, "I let it be.", narration="You step back.")
    assert state.pending is None


async def test_a_decision_on_the_table_holds_the_next_scene_back_too(tmp_path: Path) -> None:
    table = opened(tmp_path, rng=Random(0))

    _ = await played(
        table,
        "I grab for the ledger in her hands.",
        ("roll_question", A_CONFLICT),
        ("next_scene", {"intent": "Out into the cloister walk."}),
        narration="She holds on.",
    )

    assert table.refusals == [DECIDING]
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_a_scene_the_world_has_outgrown_is_dropped_rather_than_killing_the_turn(
    tmp_path: Path,
) -> None:
    """The write reads the committed state, so this turn's own changes can undo its scene."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(
        table,
        "I call the porter over.",
        ("next_scene", {"intent": "Into the cloister walk."}),
        ("change_world", change_args("enter", entity_id="tomas")),
    )
    await _settled(table)
    state = await played(table, "I follow him out.")

    assert "already met" in table.service.write_failure
    assert state.turn == 2
    assert state.world.current.title == "The Abbot's Study"


async def test_next_scene_does_not_end_the_turn_and_installs_at_the_next_start(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await played(
        table,
        "I follow her out into the rain.",
        ("next_scene", {"intent": "They step into the cloister walk.", "include": ["mara"]}),
        narration="The door swings wide.",
    )

    assert state.turn == 1
    assert state.world.current.title == "The Abbot's Study"
    await _settled(table)

    state = await played(table, "I look for the lantern.", narration="The rain answers.")

    assert state.world.current.title == "The Cloister Walk"
    assert state.world.require(EntityId("tomas")).id in state.world.current.hidden
    assert state.history[-1].scene == "The Cloister Walk"


async def test_the_scene_bar_refuses_a_thin_scene(tmp_path: Path) -> None:
    table = opened(tmp_path)
    thin = _scene(hidden=[], present=[])
    table.spawner.answers["worldsmith"] = [thin, thin]

    _ = await played(
        table,
        "I go.",
        ("next_scene", {"intent": "They step into the cloister walk."}),
    )
    await _settled(table)

    assert "something to find" in table.service.write_failure
    assert table.service.state.world.current.title == "The Abbot's Study"


async def test_a_scene_written_for_a_world_the_player_has_left_is_discarded_and_rewritten(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(), _scene(title="The Chapter House")]

    _ = await played(table, "I go.", ("next_scene", {"intent": "Into the cloister walk."}))
    await _settled(table)
    # Two turns where the game master never asks for the picture, so nothing installs the scene.
    _ = await played(table, "I wait.", start=False)
    _ = await played(table, "I wait again.", start=False)
    _ = await played(table, "I look up.")
    await _settled(table)

    assert table.service.state.world.current.title == "The Abbot's Study"
    written = [prompt for role, prompt in table.spawner.prompts if role == "worldsmith"]
    assert len(written) == 2
    assert "Into the cloister walk." in written[1]

    _ = await played(table, "I go through.")
    assert table.service.state.world.current.title == "The Chapter House"


async def test_a_worldsmith_that_fails_leaves_the_scene_unchanged_and_says_why(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)

    _ = await played(table, "I go.", ("next_scene", {"intent": "Into the cloister walk."}))
    await _settled(table)

    assert "no answer left" in table.service.write_failure
    assert table.service.state.world.current.title == "The Abbot's Study"


async def test_the_boundary_starts_the_write_before_the_master_asks(tmp_path: Path) -> None:
    """`scene_spent` fires once everything hidden here is found; the wait starts then."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(
        table, "I search the study.", ("change_world", change_args("reveal", entity_id=VAULT_MAP))
    )
    await _settled(table)

    assert scene_spent(table.service.state) == "everything here has been found"
    assert any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_the_worldsmith_is_shown_the_source_the_cast_and_the_shape_it_answers_in(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I go.", ("next_scene", {"intent": "Into the cloister walk."}))
    await _settled(table)

    prompt = table.spawner.prompt("worldsmith")
    assert "Brother Tomas" in prompt
    assert "Into the cloister walk." in prompt
    assert json.dumps(SceneWrite.model_json_schema()["properties"]["place"]["title"]) not in prompt


async def test_abandoning_a_spawn_kills_the_process_group_it_started(tmp_path: Path) -> None:
    """The CLI's own children must not outlive the turn."""
    settings = updated(
        offline_settings(tmp_path),
        roles={"master": {"command": "sh -c 'sleep 30' --", "timeout": 0.5}},
    )

    with pytest.raises(asyncio.TimeoutError):
        await CliSpawner(settings).act("go")


async def _settled(table: Table) -> None:
    """Let the background scene write finish; nothing in it awaits anything real."""
    del table
    for _ in range(4):
        await asyncio.sleep(0)


def test_the_engine_is_the_one_the_surface_publishes_for(tmp_path: Path) -> None:
    assert opened(tmp_path).runtime.engine.id == LONER3E


# What `codex exec --json` actually printed, banner line and all.
CODEX_STREAM = """Reading additional input from stdin...
{"type":"thread.started","thread_id":"01a055c7"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\\"lines\\": \
[{\\"speaker_id\\": null, \\"text\\": \\"ok\\"}]}"}}
{"type":"turn.completed","usage":{"input_tokens":16174,"output_tokens":20}}
"""


@pytest.mark.parametrize(
    ("output", "wanted"),
    (
        (CODEX_STREAM, '{"lines": [{"speaker_id": null, "text": "ok"}]}'),
        ('{"lines": [{"speaker_id": null, "text": "ok"}]}', None),
        ('Here it is:\n{"lines": [{"speaker_id": null, "text": "ok"}]}', None),
        ('```json\n{"lines": [{"speaker_id": null, "text": "ok"}]}\n```', None),
        (
            'I read:\n```py\nx = 1\n```\nAnswer:\n{"lines": [{"speaker_id": null, "text": "ok"}]}',
            None,
        ),
    ),
    ids=("a codex event stream", "bare", "after prose", "fenced", "a fence that is not the answer"),
)
def test_every_shape_a_cli_answers_in_parses_to_the_same_narration(
    output: str, wanted: str | None
) -> None:
    narration = Narration.model_validate_json(final_message(output))

    assert narration.text == "ok"
    if wanted is not None:
        assert final_message(output) == wanted
