import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    LONER3E,
    ScriptedSpawner,
    change_args,
    changed,
    narrated,
    offline_settings,
    open_game,
    play_turn,
    scenario_for,
    the_way_on,
    updated,
)
from pydantic import BaseModel, JsonValue

import aidm.app.spawn as spawn_module
from aidm.app.launch import LaunchTarget
from aidm.app.mcp import call, list_tools
from aidm.app.runtime import CROSSED
from aidm.app.spawn import CliSpawner, RunResult, final_message
from aidm.config import Role
from aidm.core.entities import EngineId, EntityId
from aidm.core.facts import Fact
from aidm.core.model import ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Answer, Narration, narration_text
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet
from aidm.engines.scenes.drafts import SceneDraft
from aidm.engines.scenes.worldsmith import scene_refusal
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


class _SilentEngine(Loner3eEngine):
    """A Loner engine whose world grows with no crossing to narrate."""

    def crossing(self, pursuit: str) -> None:
        return None

    def ready(self, state: Loner3eGame) -> bool:
        return True

    async def advance(
        self, draft: Loner3eGame, intent: str, worldsmith: WorldsmithAnswer
    ) -> tuple[Fact, ...]:
        written = SceneDraft[Loner3eSheet].model_validate_json(_bare_scene())
        if (refused := scene_refusal(written, self.world(draft))) is not None:
            raise ValueError(refused)
        return (*self.leaving(draft), *self.install(draft, written))


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
        LaunchTarget(scenario_id=scenario_for(LONER3E, "campaign"), character_id="kael")
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
    landed: list[int] = []

    table = open_game(tmp_path)

    def script() -> None:
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP) | {"junk": 1})
        _ = table.call("change_world", change_args("reveal", entity_id=VAULT_MAP))
        turn = table.service.turn
        assert turn is not None
        landed.append(len(turn.facts))

    table.spawner.turns.append(script)
    table.spawner.answers["narrator"] = [narrated("A chart, under the stone.")]
    await table.service.play(Answer(text="I lever up the flagstone."))

    assert "not permitted" in table.refusals[0]
    assert landed == [1]
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
    assert any("waiting on the player" in one for one in table.answers)
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

    assert state.turn == 1
    # An offer, not a decision: nothing waits on the player and the scene is still playable.
    assert state.pending is None
    assert state.payload.run.left is not None
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
    assert state.payload.run.left is not None
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)

    state = await play_turn(
        table,
        "Down the stair the map marks.",
        arrival="The cold comes up to meet you.",
        moving_on=True,
    )
    assert state.payload.run.title == "The Cloister Walk"


async def test_a_transition_without_an_arrival_brief_extends_on_a_lineless_exchange(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    shown: list[str] = []

    class Watching(_SilentEngine):
        async def advance(
            self, draft: Loner3eGame, intent: str, worldsmith: WorldsmithAnswer
        ) -> tuple[Fact, ...]:
            shown.append(table.service.intent)
            return await super().advance(draft, intent, worldsmith)

    table.service.engine = Watching()
    before = table.state.turn
    runs = len(table.state.payload.runs)

    await table.service.play(Answer(text="Out into the cloister walk."), moving_on=True)

    # The page has no turn to read the bubble from here, so the service holds the words.
    assert (shown, table.service.intent) == (["Out into the cloister walk."], "")
    assert table.state.turn == before + 1
    assert len(table.state.payload.runs) == runs + 1
    new_run = table.state.payload.runs[-1]
    assert len(new_run.exchanges) == 1
    exchange = new_run.exchanges[0]
    assert exchange.lines == ()
    assert exchange.prompt == "Out into the cloister walk."
    assert any(fact.card.startswith("New scene: The Cloister Walk") for fact in exchange.facts)
    assert not any(role == "master" for role, _ in table.spawner.prompts)


async def test_authoring_raises_when_the_worldsmith_never_meets_the_bar(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    thin = SceneDraft[Loner3eSheet].model_validate(json.loads(_bare_scene(present=[], hidden=[])))

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        written = model.model_validate(thin.model_dump())
        if (refused := refusal(written)) is not None:
            raise ValueError(f"the worldsmith answered nothing usable: {refused}")
        return written

    with pytest.raises(ValueError, match="the scene needs"):
        _ = await table.service.engine.author(
            ScenarioMeta(title="T", premise="p"), "", table.state.packs, answer, lambda _built: None
        )


async def test_a_turn_that_dies_after_asking_to_move_takes_its_write_with_it(
    tmp_path: Path,
) -> None:
    """Left alive, that write installs its scene on a later turn the player never asked to leave."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]
    table.spawner.answers["narrator"] = []

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    with pytest.raises(ValueError):
        _ = await play_turn(table, "Out into the cloister walk.", moving_on=True, narration="")
    state = await play_turn(table, "I look at the ledgers again.", narration="Dust, and more dust.")

    assert state.payload.run.title == "The Abbot's Study"


async def test_a_player_who_died_moving_on_does_not_arrive(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table,
        "Down the stair, and quickly.",
        changed("kill", entity_id=PLAYER_ID),
        moving_on=True,
    )

    assert state.payload.run.title == "The Abbot's Study"
    assert table.service.engine.over(state) is not None


async def test_the_way_on_is_offered_once(tmp_path: Path) -> None:
    """Offering again would move the player out of a scene they have not played yet."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(
        table,
        "Out into the cloister walk.",
        the_way_on(),
        arrival="Rain takes the arcade.",
        moving_on=True,
    )

    assert "already settled" in table.refusals[-1]
    assert state.payload.run.title == "The Cloister Walk"
    assert state.payload.run.left is None


async def test_a_crossing_the_narrator_will_not_write_still_keeps_the_scene(
    tmp_path: Path,
) -> None:
    """The scene cost a spawn of its own; a refused arrival must not throw it away."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(table, "Out into the cloister walk.", moving_on=True)

    assert state.payload.run.title == "The Cloister Walk"
    assert state.payload.exchanges()[-1].narration == ""


async def test_the_players_own_answer_is_the_brief_and_the_crossing_lands_in_that_turn(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I have what I came for.", the_way_on())
    state = await play_turn(
        table,
        "Out through the cloister walk, before Tomas hears the door.",
        narration="You pull the door to.",
        arrival="Rain finds you before the arcade does.",
        moving_on=True,
    )

    assert state.payload.run.title == "The Cloister Walk"
    assert EntityId("tomas") in state.payload.hidden()
    # Lands as the new run's own exchange, not tacked onto the scene the player just left.
    assert len(state.payload.run.exchanges) == 1
    assert "Rain finds you" in state.payload.run.exchanges[-1].narration
    assert "before Tomas hears the door" in table.spawner.prompt("worldsmith")


async def test_the_turn_is_filed_before_the_worldsmith_is_asked(tmp_path: Path) -> None:
    """The turn's own narration must reach the player while the slow write runs."""
    table = open_game(tmp_path)
    filed: list[int] = []
    table.service.spawner = _Watched(
        table.spawner, lambda: filed.append(len(table.service.engine.history(table.service.state)))
    )
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(table, "I go.", the_way_on())
    before = len(table.service.engine.history(table.service.state))
    table.spawner.turns.append(table.plays(()))
    table.spawner.answers["narrator"] = [narrated("You pull the door to."), narrated("Rain.")]
    await table.service.play(Answer(text="Out into the cloister walk."), moving_on=True)

    assert filed == [before + 1]


async def test_a_scene_the_world_has_outgrown_is_dropped_rather_than_killing_the_turn(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The bar sees the turn's own changes."""
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(), _scene()]

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(
        table,
        "Out into the cloister walk.",
        ("change_world", change_args("enter", entity_id="tomas")),
        moving_on=True,
    )

    assert "already met" in caplog.text
    unwritten = table.service.engine.history(state)[-1]
    assert unwritten.prompt == CROSSED  # the turn filed the player's words already
    assert unwritten.facts[0].kind == "way_unwritten"
    assert state.payload.run.title == "The Abbot's Study"


async def test_the_scene_bar_refuses_a_thin_scene(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    table = open_game(tmp_path)
    thin = _scene(present=[], hidden=[])
    table.spawner.answers["worldsmith"] = [thin, thin]

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(table, "Out into the cloister walk.", moving_on=True)

    assert "besides the player" in caplog.text
    assert table.service.engine.history(state)[-1].facts[0].kind == "way_unwritten"
    assert table.service.state.payload.run.title == "The Abbot's Study"


async def test_a_scene_with_nothing_hidden_in_it_is_allowed(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene(hidden=[])]

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(
        table, "Out into the cloister walk.", arrival="The rain has the arcade.", moving_on=True
    )

    assert all(
        fact.kind != "way_unwritten" for fact in table.service.engine.history(state)[-1].facts
    )
    assert state.payload.run.title == "The Cloister Walk"


async def test_a_worldsmith_that_fails_leaves_the_scene_unchanged_and_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    table = open_game(tmp_path)

    _ = await play_turn(table, "I go.", the_way_on())
    state = await play_turn(table, "Out into the cloister walk.", moving_on=True)

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
    _ = await play_turn(table, "I have what I came for.", the_way_on())
    _ = await play_turn(
        table, "Out into the cloister walk.", arrival="Rain takes the arcade.", moving_on=True
    )

    prompt = table.spawner.prompt("worldsmith")
    assert "Brother Tomas" in prompt
    assert "Out into the cloister walk." in prompt
    # What the scene was authored as is not what the scene became; the next one follows the second.
    assert "A flagstone sits proud of its neighbours." in prompt
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

    assert "roll_question" in [one.name for one in table.runtime.published_tools()]

    table.service.turn = None
    assert [one.name for one in table.runtime.published_tools()] == []


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
