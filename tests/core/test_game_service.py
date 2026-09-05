import json
from pathlib import Path

import pytest
from support.loner import TARGET, open_game, session
from support.table import (
    ScriptedSpawner,
    narrated,
    offline_settings,
    play_turn,
    tool_call,
    updated,
)

from aidm.app.runtime import OPENING_MARK, TURNING_MARK, Runtime
from aidm.core.entities import Refusal
from aidm.core.io import FileStore
from aidm.core.model import AnyGame, ScenarioMeta


class _UnsavableStore(FileStore):
    """Overrides `save` alone: `FileStore` is frozen and slotted, so this cannot monkeypatch it."""

    def save(self, slug: str, state: AnyGame) -> None:
        raise OSError("disk is gone")


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    assert store.slugs() == ()

    store.save(TARGET.slug, game.state.model_copy(update={"notes": ["kept"]}).commit())
    assert session(tmp_path).state.notes == ["kept"]

    game = session(tmp_path)
    game.restart()
    assert game.state.notes == []
    assert store.load(TARGET.slug) is None


def test_restart_keeps_scene_art_a_replayed_scene_would_reuse(tmp_path: Path) -> None:
    game = session(tmp_path)
    art = FileStore(tmp_path).media_dir(TARGET.slug) / "abc123def456.jpg"
    art.parent.mkdir(parents=True, exist_ok=True)
    _ = art.write_bytes(b"art")

    game.restart()

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
    FileStore(tmp_path).save(TARGET.slug, game.state.model_copy(update=change).commit())

    with pytest.raises(Refusal, match=message):
        session(tmp_path)


def test_one_open_game_per_slug(tmp_path: Path) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), ScriptedSpawner())
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened


async def test_the_opening_is_narrated_once_and_costs_a_turn(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.spawner.answers["narrator"] = [narrated("The abbot's study holds its breath.")]

    await table.service.open()

    history = table.service.engine.history(table.service.state)
    assert [exchange.prompt for exchange in history] == [OPENING_MARK]
    assert len(history) == 1

    await table.service.open()
    assert len(table.service.engine.history(table.service.state)) == 1


async def test_an_opening_the_narrator_will_not_write_commits_nothing(tmp_path: Path) -> None:
    """The premise still stands in for it; a page reload asks again."""
    table = open_game(tmp_path)

    await table.service.open()

    assert table.service.engine.history(table.service.state) == ()
    assert not table.service.busy


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = open_game(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await play_turn(table, "I take the map.")

    assert (table.service.busy, table.service.turn) == (False, None)


def _scene(**changes: object) -> str:
    scene = {
        "place": "abbots-study",
        "title": "The Abbot's Study, Disturbed",
        "situation": "A second crew has forced the outer door, and torchlight swings wild across "
        "the ledgers while Mara flattens herself against the shelves.",
        "present": ["mara"],
        "hidden": [],
        "question": "Can you deal with the second crew before they find the stair down?",
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

    exchanges = state.payload.exchanges()
    assert len(exchanges) == 2
    assert exchanges[0].prompt == "I keep watch on the study door."
    assert exchanges[1].prompt == TURNING_MARK
    assert state.payload.run.place == place
    assert all(entity_id in state.payload.cast for entity_id in here_before)
    assert [role for role, _ in table.spawner.prompts].count("master") == 1
    assert state.handoff == ""


async def test_a_complication_does_not_refill_the_players_spent_luck(tmp_path: Path) -> None:
    """The scene turns, it does not end: a handoff must not run Loner's own scene-closing refill."""
    table = open_game(tmp_path)
    table.state.payload.player.luck.current = 2
    table.service.commit(table.state)
    table.spawner.answers["worldsmith"] = [_scene()]

    state = await play_turn(
        table,
        "I keep watch on the study door.",
        tool_call("next_scene", complication="A second crew breaches the study door."),
        arrival="Torchlight swings wild across the ledgers.",
    )

    installed = state.payload.exchanges()[-1]
    assert installed.prompt == TURNING_MARK
    assert all(fact.kind != "counter_changed" for fact in installed.facts)
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

    exchange = state.payload.exchanges()[-1]
    assert exchange.prompt == TURNING_MARK
    assert exchange.facts[0].kind == "way_unwritten"
    assert state.handoff == ""
    assert state.payload.run.title == title


def test_a_reload_clears_a_saved_brief(tmp_path: Path) -> None:
    game = session(tmp_path)
    saved = game.state.model_copy(update={"handoff": "A crew breaks in."}).commit()
    FileStore(tmp_path).save(TARGET.slug, saved)

    reloaded = session(tmp_path)

    assert reloaded.state.handoff == ""
