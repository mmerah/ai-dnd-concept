import asyncio
import json
from dataclasses import replace
from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    LONER3E,
    change_args,
    changed,
    narrated,
    offline_settings,
    opened,
    played,
    scenario_for,
    the_way_on,
    updated,
)
from pydantic import JsonValue

import aidm.app.spawn as spawn_module
from aidm.app.launch import LaunchTarget
from aidm.app.mcp import call, offered
from aidm.app.spawn import CliSpawner, final_message
from aidm.core.entities import EngineId, EntityId
from aidm.core.model import WorldsmithAnswer
from aidm.core.play import Narration, narration_text
from aidm.engines.core import PLAYER_ID, Transition
from aidm.engines.loner3e import worldsmith
from aidm.engines.loner3e.world import Loner3eGame
from aidm.engines.loner3e.worldsmith import SceneDraft
from aidm.turn.run import ALREADY_OPEN, NO_TURN, START_FIRST, TURN_TOOLS, Turn

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
    "question": "Can you reach the chapter house before the lantern gives you away?",
    "secret": "Tomas is listening from the chapter house door.",
}


def _scene(**changes: object) -> str:
    return json.dumps(A_SCENE | changes)


def test_the_surface_publishes_turn_and_engine_tools(tmp_path: Path) -> None:
    table = opened(tmp_path)

    names = [tool.name for tool in offered(table.runtime)]

    assert names[:2] == ["start_turn", "scene"]
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


async def test_a_second_game_in_flight_refuses_the_call_rather_than_routing_it(
    tmp_path: Path,
) -> None:
    """Two tabs, two saves: a tool call belongs to one turn, and guessing would play the wrong."""
    table = opened(tmp_path)
    other = table.runtime.session(
        LaunchTarget(slug="rival", scenario_id=scenario_for(LONER3E), character_id="kael")
    )

    def script() -> None:
        _ = table.call("start_turn", {})
        other.turn = table.service.turn
        _ = table.call("scene", {})

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("Dust hangs.")]
    await table.service.play("I look around.")

    assert "turns are in flight" in table.refusals[0]


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
        landed.append(len(turn.facts))

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("A chart, under the stone.")]
    await table.service.play("I lever up the flagstone.")

    assert landed == [1]
    saved = table.saved()
    assert saved.payload.world.require(VAULT_MAP).known
    assert len(saved.payload.world.exchanges()[-1].facts) == 1


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
    assert not state.payload.world.require(VAULT_MAP).known

    state = await played(table, "I let it be.", narration="You step back.")
    assert state.pending is None


async def test_a_decision_on_the_table_holds_the_next_scene_back_too(tmp_path: Path) -> None:
    table = opened(tmp_path, rng=Random(0))

    _ = await played(
        table,
        "I grab for the ledger in her hands.",
        ("roll_question", A_CONFLICT),
        the_way_on(),
        narration="She holds on.",
    )

    assert "waiting on the player" in table.answers[-1]
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_next_scene_asks_the_player_and_writes_nothing_yet(tmp_path: Path) -> None:
    table = opened(tmp_path)

    state = await played(
        table,
        "I have what I came for.",
        the_way_on(),
        narration="The flagstone settles back.",
    )

    assert state.turn == 1
    # An offer, not a decision: nothing waits on the player and the scene is still playable.
    assert state.pending is None
    assert state.payload.world.run.settled
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_the_offer_does_not_close_the_scene_or_stop_the_player(tmp_path: Path) -> None:
    """The way on is an offer: the player may keep playing here for as long as they like."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "I go back to the shelves and read the spines.",
        ("change_world", change_args("reveal", entity_id=VAULT_MAP)),
        narration="Dust comes away on your sleeve.",
    )

    assert state.payload.world.current.title == "The Abbot's Study"
    assert state.payload.world.run.settled
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)

    state = await played(
        table,
        "Down the stair the map marks.",
        arrival="The cold comes up to meet you.",
        moving_on=True,
    )
    assert state.payload.world.current.title == "The Cloister Walk"


async def test_a_transition_without_an_arrival_brief_extends_without_a_turn(tmp_path: Path) -> None:
    table = opened(tmp_path)
    engine = table.service.engine

    def ready(_state: Loner3eGame) -> bool:
        return True

    async def write(state: Loner3eGame, _intent: str, _answer: WorldsmithAnswer) -> SceneDraft:
        written = SceneDraft.model_validate_json(_scene())
        if (refused := worldsmith.scene_refusal(written, state.payload.world)) is not None:
            raise ValueError(refused)
        return written

    table.service.engine = replace(
        engine,
        transition=Transition(
            ready=ready,
            write=write,
            install=engine.transition.install,
            arrival_brief=None,
        ),
    )
    before = table.state.turn
    runs = len(table.state.payload.world.runs)

    await table.service.play("Out into the cloister walk.", moving_on=True)

    assert table.state.turn == before
    assert len(table.state.payload.world.runs) == runs + 1
    assert not any(role == "master" for role, _ in table.spawner.prompts)


def test_authoring_build_raises_on_an_unmet_bar(tmp_path: Path) -> None:
    table = opened(tmp_path)
    scene = SceneDraft.model_validate(json.loads(_scene(present=[], hidden=[])))

    with pytest.raises(ValueError, match="the scene needs"):
        _ = table.service.engine.authoring.build("T", "p", "", table.state.packs, scene, "")


async def test_a_turn_that_dies_after_asking_to_move_takes_its_write_with_it(
    tmp_path: Path,
) -> None:
    """Left alive, that write installs its scene on a later turn the player never asked to leave."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]
    table.spawner.answers["narrator"] = []

    _ = await played(table, "I have what I came for.", the_way_on())
    with pytest.raises(ValueError):
        _ = await played(table, "Out into the cloister walk.", moving_on=True, narration="")
    state = await played(table, "I look at the ledgers again.", narration="Dust, and more dust.")

    assert state.payload.world.current.title == "The Abbot's Study"


async def test_a_player_who_died_moving_on_does_not_arrive(tmp_path: Path) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "Down the stair, and quickly.",
        changed("kill", entity_id=PLAYER_ID),
        moving_on=True,
    )

    assert state.payload.world.current.title == "The Abbot's Study"
    assert table.service.engine.over(state) is not None


async def test_the_spent_note_never_reaches_the_scene_it_is_not_about(tmp_path: Path) -> None:
    """The original defect: the master read 'this scene looks spent' beside a brand-new scene."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "Out into the cloister walk.",
        changed("kill", entity_id=MARA),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    assert state.payload.world.current.title == "The Cloister Walk"
    assert not any("looks spent" in note for note in state.notes)

    # The body came with them: the note it earns is this scene's second exchange, not its first.
    state = await played(table, "I look at what she wrote.", narration="Ledgers, nothing more.")
    assert any("looks spent" in note for note in state.notes)


async def test_the_way_on_is_offered_once(tmp_path: Path) -> None:
    """Offering again would move the player out of a scene they have not played yet."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I go.", the_way_on())
    state = await played(
        table,
        "Out into the cloister walk.",
        the_way_on(),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    assert "already settled" in table.refusals[-1]
    assert state.payload.world.current.title == "The Cloister Walk"
    assert not state.payload.world.run.settled


async def test_a_crossing_the_narrator_will_not_write_still_keeps_the_scene(
    tmp_path: Path,
) -> None:
    """The scene cost a spawn of its own; a refused arrival must not throw it away."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I go.", the_way_on())
    state = await played(table, "Out into the cloister walk.", moving_on=True)

    assert state.payload.world.current.title == "The Cloister Walk"
    assert state.payload.world.exchanges()[-1].narration == ""


async def test_the_players_own_answer_is_the_brief_and_the_crossing_lands_in_that_turn(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I have what I came for.", the_way_on())
    state = await played(
        table,
        "Out through the cloister walk, before Tomas hears the door.",
        narration="You pull the door to.",
        arrival="Rain finds you before the arcade does.",
        moving_on=True,
    )

    assert state.payload.world.current.title == "The Cloister Walk"
    assert EntityId("tomas") in state.payload.world.run.hidden
    # Lands as the new run's own exchange, not tacked onto the scene the player just left.
    assert len(state.payload.world.run.exchanges) == 1
    assert "Rain finds you" in state.payload.world.run.exchanges[-1].narration
    assert "before Tomas hears the door" in table.spawner.prompt("worldsmith")


async def test_a_scene_the_world_has_outgrown_is_dropped_rather_than_killing_the_turn(
    tmp_path: Path,
) -> None:
    """The write reads a copy taken as the turn opened, so the turn itself can undo its scene."""
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(table, "I go.", the_way_on())
    state = await played(
        table,
        "Out into the cloister walk.",
        ("change_world", change_args("enter", entity_id="tomas")),
        moving_on=True,
    )

    assert "already met" in table.service.write_failure
    assert state.payload.world.current.title == "The Abbot's Study"


async def test_the_scene_bar_refuses_a_thin_scene(tmp_path: Path) -> None:
    table = opened(tmp_path)
    thin = _scene(present=[], hidden=[])
    table.spawner.answers["worldsmith"] = [thin, thin]

    _ = await played(table, "I go.", the_way_on())
    _ = await played(table, "Out into the cloister walk.", moving_on=True)

    assert "besides the player" in table.service.write_failure
    assert table.service.state.payload.world.current.title == "The Abbot's Study"


async def test_a_scene_with_nothing_hidden_in_it_is_allowed(tmp_path: Path) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(hidden=[])]

    _ = await played(table, "I go.", the_way_on())
    state = await played(
        table, "Out into the cloister walk.", arrival="The rain has the arcade.", moving_on=True
    )

    assert table.service.write_failure == ""
    assert state.payload.world.current.title == "The Cloister Walk"


async def test_a_worldsmith_that_fails_leaves_the_scene_unchanged_and_says_why(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)

    _ = await played(table, "I go.", the_way_on())
    _ = await played(table, "Out into the cloister walk.", moving_on=True)

    assert "no answer left" in table.service.write_failure
    assert table.service.state.payload.world.current.title == "The Abbot's Study"


async def test_the_worldsmith_is_shown_the_source_the_cast_and_what_actually_happened(
    tmp_path: Path,
) -> None:
    table = opened(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await played(
        table, "I search the study.", narration="A flagstone sits proud of its neighbours."
    )
    _ = await played(table, "I have what I came for.", the_way_on())
    _ = await played(
        table, "Out into the cloister walk.", arrival="Rain takes the arcade.", moving_on=True
    )

    prompt = table.spawner.prompt("worldsmith")
    assert "Brother Tomas" in prompt
    assert "Out into the cloister walk." in prompt
    # What the scene was authored as is not what the scene became; the next one follows the second.
    assert "A flagstone sits proud of its neighbours." in prompt
    assert json.dumps(SceneDraft.model_json_schema()["properties"]["place"]["title"]) not in prompt


async def test_abandoning_a_spawn_kills_the_process_group_it_started(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The CLI's own children must not outlive the turn."""
    killed: list[tuple[int, int]] = []

    class FakeProcess:
        pid = 1234
        returncode = None

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.Future()
            return b"", b""

    async def fake_create(*_argv: str, **_kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(spawn_module.subprocess, "create_subprocess_exec", fake_create)

    def fake_killpg(pid: int, signal: int) -> None:
        killed.append((pid, signal))

    monkeypatch.setattr(spawn_module, "killpg", fake_killpg)
    settings = updated(
        offline_settings(tmp_path),
        roles={"master": {"timeout": 0.01}},
    )

    with pytest.raises(asyncio.TimeoutError):
        await CliSpawner(settings).run("master", "go", None)
    assert killed == [(1234, spawn_module.SIGKILL)]


def test_the_surface_publishes_for_the_engine_whose_turn_is_in_flight(tmp_path: Path) -> None:
    table = opened(tmp_path)
    toolless = replace(table.service.engine, id=EngineId("mirror"), tools=())
    # First of the installed engines, so reading the engines instead of the turn would show it.
    table.runtime.engines = {toolless.id: toolless, **table.runtime.engines}
    state = table.service.state
    table.service.turn = Turn.begin(table.service.engine, state, "I look.", Random(0), 1)

    assert "roll_question" in [one.name for one in table.runtime.published_tools()]

    table.service.turn = None
    assert [one.name for one in table.runtime.published_tools()] == [one.name for one in TURN_TOOLS]


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

    assert narration_text(narration.lines) == "ok"
    if wanted is not None:
        assert final_message(output) == wanted
