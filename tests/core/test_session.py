from pathlib import Path

import pytest
from core_test_support import (
    ScriptedSpawner,
    narrated,
    offline_settings,
    opened,
    played,
    updated,
)
from loner3e_test_support import TARGET
from loner3e_test_support import loner3e_session as session

from aidm.app.runtime import BEGUN, Runtime
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

    store.save(TARGET.slug, game.state.model_copy(update={"turn": 7}).committed())
    assert session(tmp_path).state.turn == 7

    game = session(tmp_path)
    game.restart()
    assert game.state.turn == 0
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
        ({"scenario": ScenarioMeta(title="Another Vault", premise="Elsewhere.")}, "Another Vault"),
    ),
    ids=("another origin", "a scenario edited since the save"),
)
def test_resume_refuses_a_save_that_is_not_this_game(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    game = session(tmp_path)
    FileStore(tmp_path).save(TARGET.slug, game.state.model_copy(update=change).committed())

    with pytest.raises(ValueError, match=message):
        session(tmp_path)


def test_one_open_game_per_slug(tmp_path: Path) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path), ScriptedSpawner())
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened


async def test_the_opening_is_narrated_once_and_costs_a_turn(tmp_path: Path) -> None:
    table = opened(tmp_path)
    table.spawner.answers["narrator"] = [narrated("The abbot's study holds its breath.")]

    await table.service.open()

    history = table.service.engine.history(table.service.state)
    assert [exchange.prompt for exchange in history] == [BEGUN]
    assert table.service.state.turn == 1

    await table.service.open()
    assert len(table.service.engine.history(table.service.state)) == 1


async def test_an_opening_the_narrator_will_not_write_commits_nothing(tmp_path: Path) -> None:
    """The premise still stands in for it; a page reload asks again."""
    table = opened(tmp_path)

    await table.service.open()

    assert table.service.engine.history(table.service.state) == ()
    assert (table.service.state.turn, table.service.busy) == (0, False)


async def test_a_failed_commit_still_frees_the_game(tmp_path: Path) -> None:
    table = opened(tmp_path)
    table.service.store = _UnsavableStore(table.service.store.directory)

    with pytest.raises(OSError):
        _ = await played(table, "I take the map.")

    assert (table.service.busy, table.service.turn) == (False, None)
