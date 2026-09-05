import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import Random

import pytest
from pydantic import BaseModel, JsonValue
from support.loner import open_game
from support.table import (
    BREATHLESS,
    ScriptedSpawner,
    change_args,
    narrated,
    offline_settings,
    play_turn,
    scenario_for,
    take,
    the_way_on,
    tool_call,
    updated,
)

import aidm.app.spawn as spawn_module
from aidm.app.launch import LaunchTarget
from aidm.app.mcp import call, list_tools
from aidm.app.runtime import STORY_MARK
from aidm.app.spawn import CliSpawner, RunResult, final_message
from aidm.config import Role
from aidm.core.entities import EngineId, EntityId, Refusal
from aidm.core.model import ScenarioMeta
from aidm.core.play import Answer, Narration, narration_text
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eSheet
from aidm.engines.scenes.drafts import SceneDraft
from aidm.engines.scenes.world import MOVE_ON
from aidm.turn.run import NO_TURN, Turn


@dataclass(frozen=True, slots=True)
class _Watched:
    """The scripted spawner, with a look at the game before each worldsmith spawn."""

    inner: ScriptedSpawner
    seen: Callable[[], None]

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        if role == "worldsmith":
            self.seen()
        return await self.inner.run(role, prompt, session)


VAULT_MAP = EntityId("vault-map")
PURSUIT = "Out into the cloister walk."
LEFT = tool_call("next_scene", pursuit=PURSUIT)
MARA = EntityId("mara")
A_CONFLICT: dict[str, JsonValue] = {
    "actor_id": PLAYER_ID,
    "question": "Does he wrest the ledger out of her hands?",
    "opponent_id": MARA,
}
ARC = "Farther in, the chapter house still holds what Mara came for, and has not yet been found."
A_SCENE = {
    "place": "cloister-walk",
    "title": "The Cloister Walk",
    "situation": "Rain drums the open arcade and the flagstones run black with it, and Mara waits "
    "at the far end with the lantern shuttered to a slit.",
    "present": ["mara"],
    "hidden": ["tomas"],
    "focus": "Can you reach the chapter house before the lantern gives you away?",
    "arc": ARC,
}
RECAP = (
    "The player left the abbot's study behind, lantern shuttered, and made for the cloister "
    "walk with Mara close behind them."
)


def _scene(**changes: object) -> str:
    return json.dumps(A_SCENE | {"recap": RECAP} | changes)


def _bare_scene(**changes: object) -> str:
    """An authored opening validates against `SceneDraft`, which carries no recap."""
    return json.dumps(A_SCENE | changes)


def test_no_tool_runs_before_a_turn_is_open(tmp_path: Path) -> None:
    table = open_game(tmp_path)

    assert list_tools(table.runtime) == []
    with pytest.raises(ValueError, match=NO_TURN):
        _ = call(table.runtime, "change_world", {})


async def test_a_second_game_in_flight_crashes_the_call_rather_than_routing_it(
    tmp_path: Path,
) -> None:
    """Two turns at once is a bug, not a message: the master's call is not answered, it crashes."""
    table = open_game(tmp_path)
    other = table.runtime.session(
        LaunchTarget(scenario_id=scenario_for(BREATHLESS), character_id="kael")
    )

    def script() -> None:
        other.turn = table.service.turn
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP))

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("Dust hangs.")]
    with pytest.raises(ValueError, match="turns are in flight"):
        await table.service.play(Answer(text="I look around."))
    assert not table.refusals


async def test_a_change_lands_on_the_draft_as_it_is_made_and_on_disk_at_the_end(
    tmp_path: Path,
) -> None:
    counts: list[int] = []

    table = open_game(tmp_path)

    def script() -> None:
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP) | {"junk": 1})
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP))
        turn = table.service.turn
        assert turn is not None
        counts.append(len(turn.facts))

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("A chart, under the stone.")]
    await table.service.play(Answer(text="I lever up the flagstone."))

    assert "not permitted" in table.refusals[0]
    assert counts == [1]
    saved = table.saved()
    assert saved.payload.require(VAULT_MAP).known
    assert len(saved.payload.exchanges()[-1].facts) == 1


async def test_an_open_decision_blocks_every_other_tool_until_the_player_answers(
    tmp_path: Path,
) -> None:
    """An unfinished conflict: nothing else lands until the player's next message answers it."""
    table = open_game(tmp_path, rng=Random(0))

    state = await play_turn(
        table,
        "I grab for the ledger in her hands.",
        ("roll_question", A_CONFLICT),
        ("change_world", change_args("reveal", entity_id=VAULT_MAP)),
        narration="She holds on.",
    )

    assert state.pending is not None
    assert any("waiting on the player" in answer for answer in table.answers)
    assert not state.payload.require(VAULT_MAP).known

    state = await play_turn(table, "I let it be.", narration="You step back.")
    assert state.pending is None


async def test_a_decision_on_the_table_holds_the_next_scene_back_too(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(0))

    _ = await play_turn(
        table,
        "I grab for the ledger in her hands.",
        ("roll_question", A_CONFLICT),
        the_way_on(),
        narration="She holds on.",
    )

    assert "waiting on the player" in table.answers[-1]
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_next_scene_asks_the_player_and_writes_nothing_yet(tmp_path: Path) -> None:
    table = open_game(tmp_path)

    state = await play_turn(
        table,
        "I have what I came for.",
        the_way_on(),
        narration="The flagstone settles back.",
    )

    assert len(table.service.engine.history(state)) == 1
    # An offer, not a decision: nothing waits on the player and the scene is still playable.
    assert state.pending is None
    assert state.payload.run.offered
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_the_offer_does_not_close_the_scene_or_stop_the_player(tmp_path: Path) -> None:
    """The way on is an offer: the player may keep playing here for as long as they like."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table,
        "I go back to the shelves and read the spines.",
        ("change_world", change_args("reveal", entity_id=VAULT_MAP)),
        narration="Dust comes away on your sleeve.",
    )

    assert state.payload.run.title == "The Abbot's Study"
    assert state.payload.run.offered
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_moving_on_from_an_offer_is_a_turn_the_master_adjudicates(tmp_path: Path) -> None:
    """The page's button bypasses no obstacle: the master plays the leaving, or refuses it."""
    table = open_game(tmp_path)
    _ = await play_turn(table, "I have what I came for.", the_way_on())

    state = await play_turn(table, PURSUIT, action=MOVE_ON.id)

    assert state.payload.run.title == "The Abbot's Study"
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_a_departure_crosses_after_the_leaving_turn_and_keeps_the_notes(
    tmp_path: Path,
) -> None:
    """One adjudication: the master played the leaving, so the crossing needs no second turn."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]
    table.service.commit(updated(table.state, notes=["the adventure's end applies"]))

    state = await play_turn(table, "I go.", LEFT, arrival="The cold meets you.")

    assert [role for role, _ in table.spawner.prompts] == [
        "master",
        "narrator",
        "worldsmith",
        "narrator",
    ]
    assert state.notes == []
    assert state.payload.runs[-2].exchanges[-1].prompt == "I go."
    assert state.payload.run.title == "The Cloister Walk"
    assert not state.payload.run.offered


async def test_an_action_over_an_open_decision_is_refused(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    state = await play_turn(
        table, "I grab for it.", the_way_on(), tool_call("roll_question", **A_CONFLICT)
    )
    assert state.pending is not None
    before = state.model_dump_json()

    with pytest.raises(Refusal, match="decision"):
        _ = await take(table, MOVE_ON.id, PURSUIT)

    assert table.state.model_dump_json() == before


async def test_a_turn_that_suspends_tells_the_narrator_where_play_pauses(tmp_path: Path) -> None:
    table = open_game(tmp_path)

    state = await play_turn(
        table, "I grab for the ledger.", tool_call("roll_question", **A_CONFLICT)
    )

    pending = state.pending
    assert pending is not None
    narrator = table.spawner.prompt("narrator")
    assert f'play pauses here on the player\'s decision: "{pending.prompt}"' in narrator


async def test_authoring_raises_when_the_worldsmith_never_meets_the_bar(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    thin = SceneDraft[Loner3eSheet].model_validate(json.loads(_bare_scene(present=["nobody-here"])))

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        answer = model.model_validate(thin.model_dump())
        if (refused := refusal(answer)) is not None:
            raise ValueError(f"the worldsmith answered nothing usable: {refused}")
        return answer

    with pytest.raises(ValueError, match="the scene needs"):
        _ = await table.service.engine.author(
            ScenarioMeta(title="T", premise="p", scope="s"),
            "",
            table.state.packs,
            answer,
            lambda _built: None,
        )


async def test_a_turn_that_dies_after_the_leaving_takes_its_request_with_it(
    tmp_path: Path,
) -> None:
    """A leaving the narrator never told is not committed, so no crossing is written after it."""
    table = open_game(tmp_path)
    table.spawner.answers["narrator"] = []
    table.spawner.answers["worldsmith"] = [_scene()]

    with pytest.raises(Refusal):
        _ = await play_turn(table, PURSUIT, LEFT, narration="")

    assert table.state.generation is None
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)


async def test_the_way_on_is_offered_once_and_a_departure_consumes_it(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I go.", the_way_on())
    _ = await play_turn(table, "I linger.", the_way_on())
    assert "already offers" in table.refusals[-1]

    state = await play_turn(table, PURSUIT, LEFT, action=MOVE_ON.id, arrival="Rain.")

    assert state.payload.run.title == "The Cloister Walk"
    assert not state.payload.run.offered


async def test_a_crossing_the_narrator_will_not_write_still_keeps_the_scene(
    tmp_path: Path,
) -> None:
    """The scene cost a spawn of its own; a refused arrival must not throw it away."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(table, "I go.", LEFT)

    assert state.payload.run.title == "The Cloister Walk"
    assert state.payload.exchanges()[-1].narration == ""


async def test_the_players_own_words_are_the_brief_and_the_crossing_is_its_own_entry(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]
    pursuit = "Out through the cloister walk, before Tomas hears the door."

    state = await play_turn(
        table,
        pursuit,
        tool_call("next_scene", pursuit=pursuit),
        narration="You pull the door to.",
        arrival="Rain finds you before the arcade does.",
    )

    assert state.payload.run.title == "The Cloister Walk"
    assert EntityId("tomas") in state.payload.hidden()
    # Lands as the new run's own exchange, not tacked onto the scene the player just left.
    assert len(state.payload.run.exchanges) == 1
    assert state.payload.run.exchanges[-1].prompt == STORY_MARK
    assert "Rain finds you" in state.payload.run.exchanges[-1].narration
    assert "before Tomas hears the door" in table.spawner.prompt("worldsmith")
    # `prompt` hands back the first match; the crossing's brief is the narrator's last spawn.
    crossing_prompt = next(
        text for role, text in reversed(table.spawner.prompts) if role == "narrator"
    )
    assert "The player is leaving The Abbot's Study" in crossing_prompt


async def test_the_turn_is_filed_before_the_worldsmith_is_asked(tmp_path: Path) -> None:
    """The turn's own narration must reach the player while the slow write runs."""
    table = open_game(tmp_path)
    filed: list[int] = []
    table.service.spawner = _Watched(
        table.spawner, lambda: filed.append(len(table.service.engine.history(table.service.state)))
    )
    table.spawner.answers["worldsmith"] = [_scene()]
    before = len(table.service.engine.history(table.service.state))

    _ = await play_turn(
        table,
        "I keep watch.",
        tool_call("next_scene", complication="A second crew breaches the door."),
        arrival="Torchlight.",
    )

    assert filed == [before + 1]


async def test_a_scene_the_world_has_outgrown_is_dropped_and_the_offer_kept(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The bar sees the turn's own changes; a failed write leaves the way on as it was."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(), _scene()]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table, PURSUIT, ("change_world", change_args("enter", entity_id="tomas")), LEFT
    )

    assert "already met" in caplog.text
    unwritten = table.service.engine.history(state)[-1]
    assert unwritten.prompt == STORY_MARK
    assert unwritten.facts[0].kind == "way_unwritten"
    assert state.payload.run.title == "The Abbot's Study"
    assert state.payload.run.offered
    assert state.generation is None


async def test_the_scene_bar_refuses_a_scene_naming_nobody(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    table = open_game(tmp_path)
    thin = _scene(present=["nobody-here"], hidden=[])
    table.spawner.answers["worldsmith"] = [thin, thin]

    state = await play_turn(table, "I go.", LEFT)

    assert "these name nobody" in caplog.text
    assert table.service.engine.history(state)[-1].facts[0].kind == "way_unwritten"
    assert table.service.state.payload.run.title == "The Abbot's Study"


async def test_a_scene_with_nothing_hidden_in_it_is_allowed(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(hidden=[])]

    state = await play_turn(table, "I go.", LEFT, arrival="The rain has the arcade.")

    assert all(
        fact.kind != "way_unwritten" for fact in table.service.engine.history(state)[-1].facts
    )
    assert state.payload.run.title == "The Cloister Walk"


async def test_a_worldsmith_that_fails_leaves_the_scene_unchanged_and_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    table = open_game(tmp_path)

    state = await play_turn(table, "I go.", LEFT)

    assert "no answer left" in caplog.text
    assert table.service.engine.history(state)[-1].facts[0].kind == "way_unwritten"
    assert table.service.state.payload.run.title == "The Abbot's Study"


async def test_the_worldsmith_is_shown_the_source_the_cast_and_what_actually_happened(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(
        table, "I search the study.", narration="A flagstone sits proud of its neighbours."
    )
    table.state.payload.arc = ARC
    _ = await play_turn(table, "I go.", LEFT, arrival="Rain takes the arcade.")

    prompt = table.spawner.prompt("worldsmith")
    assert "Brother Tomas" in prompt
    assert PURSUIT in prompt
    # What the scene was authored as is not what the scene became; the next one follows the second.
    assert "A flagstone sits proud of its neighbours." in prompt
    assert f"The arc as last written: {ARC}" in prompt
    schema = SceneDraft[Loner3eSheet].model_json_schema()
    assert json.dumps(schema["properties"]["place"]["title"]) not in prompt


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
    table = open_game(tmp_path)
    toolless = Loner3eEngine()
    toolless.id = EngineId("mirror")
    toolless.tools = {}
    # First of the installed engines, so reading the engines instead of the turn would show it.
    table.runtime.engines = {toolless.id: toolless, **table.runtime.engines}
    state = table.service.state
    table.service.turn = Turn.begin(table.service.engine, state, Answer(text="I look."), Random(0))

    assert "roll_question" in [tool.name for tool in table.runtime.published_tools()]

    table.service.turn = None
    assert [tool.name for tool in table.runtime.published_tools()] == []


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
