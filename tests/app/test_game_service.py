import json
import re
from asyncio import CancelledError, Event, create_task, sleep
from pathlib import Path
from random import Random

import pytest
from support.game import TARGET, open_game, session, with_entity
from support.table import (
    BREATHLESS,
    TUNNELGOONS,
    ScriptedSpawner,
    narrated,
    offline_settings,
    open_table,
    play_turn,
    scenario_for,
    the_way_on,
    tool_call,
    updated,
)

from aidm.app.roles import REQUESTED
from aidm.app.runtime import GameService, LaunchTarget, Runtime
from aidm.config import Role
from aidm.core.entities import Refusal
from aidm.core.io import FileStore
from aidm.core.model import AnyGame, Generation, ScenarioMeta
from aidm.core.play import Answer
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.loner3e.world import Loner3eCast
from aidm.engines.rooms.engine import MORE_MAP
from aidm.engines.tunnelgoons.world import TunnelGoonsGame

IN_FLIGHT = re.escape("A turn is in flight in 'whispering-vault--kael'.")


class _UnsavableStore(FileStore):
    """Overrides `save` alone: `FileStore` is frozen and slotted, so this cannot monkeypatch it."""

    def write(self, _slug: str, _state: AnyGame, /) -> None:
        raise OSError("disk is gone")


async def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    assert store.slugs() == ()

    store.write(TARGET.slug, game.state.model_copy(update={"notes": ["kept"]}).commit())
    assert session(tmp_path).state.notes == ["kept"]

    game = session(tmp_path)
    await game.restart()
    assert game.state.notes == []
    assert store.read(TARGET.slug) is None


async def test_restart_keeps_scene_art_a_replayed_scene_would_reuse(tmp_path: Path) -> None:
    game = session(tmp_path)
    art = FileStore(tmp_path).media_dir(TARGET.slug) / "abc123def456.jpg"
    art.parent.mkdir(parents=True, exist_ok=True)
    _ = art.write_bytes(b"art")

    await game.restart()

    assert art.read_bytes() == b"art"


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"character_id": "someone-else"}, "save is 'whispering-vault'/'someone-else'"),
        (
            {
                "scenario": ScenarioMeta(
                    title="Another Vault", premise="Elsewhere.", scope="A single visit, brief."
                )
            },
            "Another Vault",
        ),
    ),
    ids=("another origin", "a scenario edited since the save"),
)
def test_resume_refuses_a_save_that_is_not_this_game(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    game = session(tmp_path)
    FileStore(tmp_path).write(TARGET.slug, game.state.model_copy(update=change).commit())

    with pytest.raises(Refusal, match=message):
        session(tmp_path)


def test_one_open_game_per_slug(tmp_path: Path) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), lambda _: ScriptedSpawner())
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened


async def test_the_opening_is_narrated_once_and_costs_a_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["narrator"] = [narrated("The abbot's study holds its breath.")]

    await table.service.open()

    history = table.service.state.exchanges()
    assert [exchange.mark for exchange in history] == ["opening"]
    assert len(history) == 1

    await table.service.open()
    assert len(table.service.state.exchanges()) == 1


async def test_an_opening_the_narrator_will_not_write_commits_nothing(tmp_path: Path) -> None:
    """The premise still stands in for it; a page reload asks again."""
    table = open_game(tmp_path)

    await table.service.open()

    assert table.service.state.exchanges() == ()
    assert not table.service.busy


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await play_turn(table, "I take the map.")

    assert (table.service.busy, table.service.turn) == (False, None)


async def test_a_turn_whose_narrator_never_answers_still_lands_and_saves_the_facts(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.turns.append(
        table.plays(
            (tool_call("change_tags", entity_id="player", kind="condition", gained=["Listening"]),)
        )
    )

    await table.service.play(Answer(text="I listen hard."))

    exchange = table.service.state.exchanges()[-1]
    assert exchange.lines == ()
    assert exchange.facts and "Listening" in exchange.facts[0].trace
    assert table.saved().exchanges()[-1].facts == exchange.facts


def _scene(**changes: object) -> str:
    scene = {
        "place": "abbots-study",
        "title": "The Abbot's Study, Disturbed",
        "situation": "A second crew has forced the outer door, and torchlight swings wild across "
        "the ledgers while Mara flattens herself against the shelves.",
        "present": ["mara"],
        "hidden": [],
        "focus": "Can you deal with the second crew before they find the stair down?",
        "recap": "The player was keeping watch on the study door when a second crew broke in.",
        "arc": "",
    }
    return json.dumps(scene | changes)


async def test_a_complication_writes_and_installs_at_the_same_place(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    place = table.state.payload.run.place
    here_before = list(table.state.payload.run.here)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
        arrival="Torchlight swings wild across the ledgers.",
    )

    exchanges = state.exchanges()
    assert len(exchanges) == 2
    assert exchanges[0].words == "I keep watch on the study door."
    assert exchanges[1].mark == "story"
    assert state.payload.run.place == place
    assert all(entity_id in state.payload.cast for entity_id in here_before)
    assert [role for role, _ in table.spawner.prompts] == ["master", "worldsmith", "narrator"]
    assert state.generation is None


async def test_a_write_requested_after_something_told_ends_the_narration_there(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    _ = await play_turn(
        table,
        "I go down.",
        tool_call("next_scene", pursuit="Down the stair."),
        arrival="Rain takes the arcade.",
    )

    roles = [role for role, _ in table.spawner.prompts]
    assert roles == ["master", "narrator", "worldsmith", "narrator"]
    leaving = table.spawner.prompt("narrator")
    assert "the player has left this place" in leaving
    assert REQUESTED in leaving


async def test_a_complication_does_not_refill_the_players_spent_luck(tmp_path: Path) -> None:
    """The scene turns, it does not end: a complication runs no scene-closing refill."""
    table = open_game(tmp_path)
    table.state.payload.player.luck.current = 2
    table.service.save(table.state)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
        arrival="Torchlight swings wild across the ledgers.",
    )

    installed = state.exchanges()[-1]
    assert installed.mark == "story"
    assert state.payload.player.luck.current == 2


async def test_a_failed_write_after_a_complication_leaves_the_turn_committed(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    title = table.state.payload.run.title

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
    )

    exchange = state.exchanges()[-1]
    assert exchange.mark == "story"
    assert exchange.facts[0].card == (
        "Nothing new came down on this place after all. You are still where you were."
    )
    assert state.generation is None
    assert state.payload.run.title == title


async def test_a_failed_write_after_a_hire_names_the_hire(tmp_path: Path) -> None:
    table = open_table(tmp_path, engine_id=BREATHLESS, state_type=BreathlessGame)

    state = await play_turn(
        table,
        "I ask Ovid to guide us across the flats.",
        tool_call("hire", entity_id="ovid-sarn", terms="Guide us across the flats."),
    )

    exchange = state.exchanges()[-1]
    assert exchange.facts[0].card == "The hire could not be written; nobody signed on."
    assert state.generation is None


async def test_a_complication_after_an_offer_clears_it_only_once_installed(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    complication = tool_call("next_scene", complication="A second crew breaches the study door.")
    _ = await play_turn(table, "I have what I came for.", the_way_on())

    state = await play_turn(table, "I keep watch.", complication)
    assert state.payload.run.offered

    table.spawner.answers["worldsmith"] = [_scene()]
    state = await play_turn(table, "I keep watching.", complication, arrival="Torchlight.")
    assert not state.payload.run.offered
    assert state.payload.run.title == "The Abbot's Study, Disturbed"


async def test_no_generation_runs_once_the_game_is_over(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch, whatever comes.",
        tool_call("kill", entity_id=PLAYER_ID),
        tool_call("next_scene", complication="A second crew breaches the study door."),
    )

    assert table.service.engine.over(state) is not None
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)
    assert len(state.payload.runs) == 1
    assert state.generation is None
    assert table.saved().generation is None


def test_a_save_never_carries_a_request(tmp_path: Path) -> None:
    game = session(tmp_path)
    draft = game.state.draft()
    draft.generation = Generation(operation="complication", detail="A crew breaks in.")
    FileStore(tmp_path).write(TARGET.slug, draft)

    assert "generation" not in json.loads(FileStore(tmp_path).read(TARGET.slug) or "")


def _party_of_one(service: GameService) -> Loner3eCast:
    """One chatty companion, met and travelling: she passes the d10 on three faces in ten."""
    member = Loner3eCast(
        id="vessa-rune",
        name="Vessa Rune",
        brief="A sharp-eyed pilot.",
        known=True,
        chattiness="chatty",
    )
    state = with_entity(service.state, member)
    draft = state.draft()
    draft.payload.party.append(member.id)
    service.save(draft.commit())
    return member


async def test_a_member_who_passes_the_d10_speaks_after_the_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.chatter = Random(1)
    member = _party_of_one(table.service)
    table.spawner.answers["narrator"] = [
        json.dumps(
            {
                "lines": [{"speaker_id": member.id, "text": "Careful out there."}],
                "proposal": "I check the airlock seal.",
            }
        )
    ]

    await table.service.interject()

    prompt = table.spawner.prompt("narrator")
    assert f"YOUR ROLE:\nYou are {member.name}. {member.brief}" in prompt
    exchange = table.service.state.exchanges()[-1]
    assert exchange.mark == "interjection"
    assert [line.speaker_id for line in exchange.lines] == [member.id]
    assert exchange.proposal == "I check the airlock seal."
    assert table.service.phase is None


async def test_nobody_passing_the_d10_spawns_no_narrator(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.chatter = Random(0)
    _party_of_one(table.service)

    await table.service.interject()

    assert table.spawner.prompts == []
    assert table.service.state.exchanges() == ()


async def test_a_turn_that_lands_first_drops_the_interjection(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.chatter = Random(1)
    member = _party_of_one(table.service)
    table.spawner.answers["narrator"] = [narrated("Wait.", member.id)]

    async def land_turn_first(role: Role, prompt: str) -> None:
        del prompt
        if role == "narrator":
            table.service.save(
                table.service.engine.close(table.service.state.draft(), (), (), mark="story")
            )

    table.spawner.hooks.append(land_turn_first)

    await table.service.interject()

    assert table.service.state.exchanges()[-1].mark == "story"


async def test_an_answer_with_no_lines_records_nothing(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.chatter = Random(1)
    _party_of_one(table.service)
    before = table.service.state.exchanges()
    table.spawner.answers["narrator"] = [json.dumps({"lines": []})]

    await table.service.interject()

    assert table.service.state.exchanges() == before


async def test_interjections_disabled_starts_no_background_task(tmp_path: Path) -> None:
    table = open_game(tmp_path, rng=Random(1))
    _party_of_one(table.service)
    table.service.interjections = False

    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")

    assert not table.service.speaking


async def test_a_new_turn_silences_the_member_still_speaking(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.chatter = Random(1)
    _party_of_one(table.service)
    cancelled = [False]

    async def still_speaking(role: Role, prompt: str) -> None:
        if role == "narrator" and prompt.startswith("YOUR ROLE:\nYou are Vessa Rune"):
            try:
                await Event().wait()
            except CancelledError:
                cancelled[0] = True
                raise

    table.spawner.hooks.append(still_speaking)
    _ = await play_turn(table, "I wait.", narration="Nothing stirs.")
    await sleep(0)
    assert table.service.speaking
    table.service.interjections = False

    _ = await play_turn(table, "I wait on.", narration="Still nothing.")
    await sleep(0)

    assert not table.service.speaking
    assert cancelled[0]


async def test_two_concurrent_plays_on_different_sessions_cannot_both_open_a_turn(
    tmp_path: Path,
) -> None:
    spawner = ScriptedSpawner()
    gate = Event()

    async def hold_master(role: Role, prompt: str) -> None:
        del prompt
        if role == "master":
            await gate.wait()

    spawner.hooks.append(hold_master)
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), lambda _: spawner)
    first = runtime.session(TARGET)
    second = runtime.session(
        LaunchTarget(scenario_id=scenario_for(BREATHLESS), character_id="kael")
    )
    spawner.turns.append(lambda: None)
    spawner.answers["narrator"] = [narrated("You wait.")]

    first_play = create_task(first.play(Answer(text="I wait.")))
    await sleep(0)

    with pytest.raises(Refusal, match=IN_FLIGHT):
        await second.play(Answer(text="I wait."))

    gate.set()
    await first_play

    assert len(first.state.exchanges()) == 1


async def test_a_failing_background_task_is_logged_and_close_leaves_no_live_task(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    game = session(tmp_path)

    async def _boom() -> None:
        raise ValueError("boom")

    async def _hang() -> None:
        await Event().wait()

    game.tasks.retain(create_task(_boom()))
    game.tasks.retain(create_task(_hang()))
    await sleep(0)

    await game.close()

    assert game.tasks.running == set()
    assert "background task failed" in caplog.text


async def test_act_hushes_before_it_asks_the_worldsmith_to_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_grow` alone can run 900s; a stale narrator spawn must not outlive the write."""
    table = open_table(tmp_path, engine_id=TUNNELGOONS, state_type=TunnelGoonsGame)
    draft = table.state.draft()
    for place in draft.payload.places.values():
        place.known = True
    table.service.save(draft.commit())
    calls: list[str] = []
    original_hush = GameService.hush

    def _tracked_hush(self: GameService) -> None:
        calls.append("hush")
        original_hush(self)

    monkeypatch.setattr(GameService, "hush", _tracked_hush)

    async def record_worldsmith(role: Role, prompt: str) -> None:
        del prompt
        if role == "worldsmith":
            calls.append("worldsmith")

    table.spawner.hooks.append(record_worldsmith)

    await table.service.act(MORE_MAP.id, "Deeper in.")

    assert calls[0] == "hush"
    assert "worldsmith" in calls
