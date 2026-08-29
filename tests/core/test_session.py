from pathlib import Path

import pytest
from core_test_support import offline_settings, updated
from loner3e_test_support import TARGET
from loner3e_test_support import loner3e_session as session

from aidm.app.runtime import Runtime
from aidm.content.io import FileStore
from aidm.content.model import ScenarioMeta


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    game = session(tmp_path)
    assert store.slugs() == ()

    store.save("poc", game.state.model_copy(update={"turn": 7}).committed())
    assert session(tmp_path).state.turn == 7

    game = session(tmp_path)
    game.restart()
    assert game.state.turn == 0
    assert game.entries == []
    assert store.load("poc") is None


def test_restart_keeps_scene_art_a_replayed_scene_would_reuse(tmp_path: Path) -> None:
    game = session(tmp_path)
    art = FileStore(tmp_path).media_dir("poc") / "abc123def456.jpg"
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
    FileStore(tmp_path).save("poc", game.state.model_copy(update=change).committed())

    with pytest.raises(ValueError, match=message):
        session(tmp_path)


def test_one_open_game_per_slug_and_it_keeps_the_origin_it_was_opened_with(tmp_path: Path) -> None:
    runtime = Runtime(updated(offline_settings(), saves_dir=tmp_path))
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened
    assert runtime.session(updated(TARGET, slug="second")).engine is opened.engine
    with pytest.raises(ValueError, match="open session 'poc' plays"):
        runtime.session(updated(TARGET, character_id="someone-else"))
