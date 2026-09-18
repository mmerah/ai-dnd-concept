import json
import re
from asyncio import Event, create_task, sleep
from pathlib import Path
from random import Random

import pytest
from support.game import TARGET, open_game, session, with_entity
from support.table import (
    TWENTYFOURXX,
    ScriptedSpawner,
    narrated,
    offline_settings,
    play_turn,
    scenario_for,
    tool_call,
    updated,
)

from aidm.app.runtime import IN_FLIGHT_ELSEWHERE, GameService, LaunchTarget, Runtime
from aidm.config import Role
from aidm.core.entities import EngineId, Refusal
from aidm.core.io import FileStore
from aidm.core.model import AnyGame, Commission, ScenarioMeta
from aidm.core.play import Answer
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.world import Loner3eEntity


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
            "title",
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
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), spawner=ScriptedSpawner())
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened


async def test_delete_save_drops_the_session_and_its_media_but_not_during_a_turn(
    tmp_path: Path,
) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), spawner=ScriptedSpawner())
    opened = runtime.session(TARGET)
    opened.save(opened.state)
    media = runtime.store.media_dir(TARGET.slug)
    media.mkdir(parents=True)
    opened.working_role = "master"

    with pytest.raises(Refusal, match="taking a turn"):
        await runtime.delete_save(TARGET.slug)

    opened.working_role = None
    await runtime.delete_save(TARGET.slug)

    assert runtime.store.read(TARGET.slug) is None
    assert not media.exists()
    assert runtime.session(TARGET) is not opened


async def test_the_opening_is_narrated_once_and_costs_a_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["narrator"] = [narrated("The abbot's study holds its breath.")]

    await table.service.open()

    history = table.service.state.exchanges()
    assert [exchange.mark for exchange in history] == ["opening"]
    assert len(history) == 1

    await table.service.open()
    assert len(table.service.state.exchanges()) == 1


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await play_turn(table, "I take the map.")

    assert (table.service.working_role, table.service.turn) == (None, None)


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
    place = table.state.world.scene.place
    here_before = list(table.state.world.scene.here)
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
    assert state.world.scene.place == place
    assert all(entity_id in state.world.cast for entity_id in here_before)
    assert [role for role, _ in table.spawner.prompts] == ["master", "worldsmith", "narrator"]
    assert state.commission is None


async def test_a_failed_write_after_a_complication_leaves_the_turn_committed(
    tmp_path: Path,
) -> None:
    table = open_game(tmp_path)
    title = table.state.world.scene.title

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
    assert state.commission is None
    assert state.world.scene.title == title


async def test_no_generation_runs_once_the_game_is_over(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch, whatever comes.",
        tool_call("kill", target_id=PLAYER_ID),
        tool_call("next_scene", complication="A second crew breaches the study door."),
    )

    assert table.service.engine.ending(state) is not None
    assert not any(role == "worldsmith" for role, _ in table.spawner.prompts)
    assert len(state.world.scenes) == 1
    assert state.commission is None
    assert table.saved().commission is None


def test_a_save_never_carries_a_request(tmp_path: Path) -> None:
    game = session(tmp_path)
    draft = game.state.draft()
    draft.commission = Commission(operation="complication", detail="A crew breaks in.")
    FileStore(tmp_path).write(TARGET.slug, draft)

    assert "commission" not in json.loads(FileStore(tmp_path).read(TARGET.slug) or "")


def _party_of_one(service: GameService) -> Loner3eEntity:
    """One chatty companion, met and travelling: she passes the d10 on three faces in ten."""
    member = Loner3eEntity(
        id="vessa-rune",
        name="Vessa Rune",
        brief="A sharp-eyed pilot.",
        known=True,
        chattiness="chatty",
    )
    state = with_entity(service.state, member)
    draft = state.draft()
    draft.world.party.append(member.id)
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

    await table.service.let_party_speak()

    prompt = table.spawner.prompt("narrator")
    assert f"YOUR ROLE:\nYou are {member.name}. {member.brief}" in prompt
    exchange = table.service.state.exchanges()[-1]
    assert exchange.mark == "interjection"
    assert [line.speaker_id for line in exchange.lines] == [member.id]
    assert exchange.proposal == "I check the airlock seal."
    assert table.service.working_role is None


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
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), spawner=spawner)
    first = runtime.session(TARGET)
    second = runtime.session(
        LaunchTarget(scenario_id=scenario_for(TWENTYFOURXX), character_id="kael")
    )
    spawner.turns.append(lambda: None)
    spawner.answers["narrator"] = [narrated("You wait.")]

    first_play = create_task(first.play(Answer(text="I wait.")))
    await sleep(0)

    with pytest.raises(Refusal, match=re.escape(IN_FLIGHT_ELSEWHERE)):
        await second.play(Answer(text="I wait."))

    gate.set()
    await first_play

    assert len(first.state.exchanges()) == 1


def test_pack_boxes_refuses_an_unknown_engine_or_pack_and_reports_a_shipped_pack_as_read_only(
    tmp_path: Path,
) -> None:
    runtime = Runtime(offline_settings(tmp_path))

    with pytest.raises(Refusal, match="no rules"):
        runtime.pack_boxes(EngineId("no-such-engine"), "srd")

    with pytest.raises(Refusal, match="not installed"):
        runtime.pack_boxes(runtime.default_engine, "no-such-pack")

    _, written, _ = runtime.pack_boxes(runtime.default_engine, runtime.default_pack)
    assert written is False
