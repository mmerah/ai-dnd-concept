from pathlib import Path

import pytest
from core_test_support import settings, updated
from story_test_support import TARGET
from story_test_support import story_session as session

from aidm.core.content import ScenarioMeta
from aidm.core.store import FileSaves, FileTraces
from aidm.workflow.session import Runtime


def test_opening_does_not_save_and_restart_discards_durable_state(tmp_path: Path) -> None:
    saves, traces = FileSaves(tmp_path), FileTraces(tmp_path)
    game = session(tmp_path)
    assert saves.slugs() == ()

    saves.save("poc", updated(game.state, turn=7))
    assert session(tmp_path).state.turn == 7

    game = session(tmp_path)
    game.restart()
    assert game.state.turn == 0
    assert game.entries == []
    assert saves.load("poc", game.engine.state_type) is None
    assert traces.load("poc") == ()


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
    """A save names its own origin by id; the meta comparison catches an edit under a kept id."""
    game = session(tmp_path)
    FileSaves(tmp_path).save("poc", updated(game.state, **change))

    with pytest.raises(ValueError, match=message):
        session(tmp_path)


def test_one_open_game_per_slug_and_it_keeps_the_origin_it_was_opened_with(tmp_path: Path) -> None:
    """A page render resolves the session by slug; rebuilding it drops the turn in flight."""
    runtime = Runtime(updated(settings(), saves_dir=tmp_path))
    opened = runtime.session(TARGET)

    assert runtime.session(TARGET) is opened
    assert runtime.session(updated(TARGET, slug="second")).engine is opened.engine
    with pytest.raises(ValueError, match="open session 'poc' plays"):
        runtime.session(updated(TARGET, character_id="someone-else"))
