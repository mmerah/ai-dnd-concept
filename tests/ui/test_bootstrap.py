from pathlib import Path

import pytest
from ui_test_support import ui_settings

from aidm_ui.advancement.fivee import Dnd5eAdvancementUi
from aidm_ui.advancement.story import StoryAdvancementUi
from aidm_ui.bootstrap import create_composition
from aidm_ui.session import SessionRegistry
from aidm_ui.view import GameView


def test_both_engines_compose_through_one_registry(tmp_path: Path) -> None:
    composition = create_composition(ui_settings(tmp_path))

    story = composition.application("story", "whispering_vault", "kael")
    dnd5e = composition.application("fivee", "whispering_vault_5e", "kael_5e")

    assert (story.engine.stamp.id, dnd5e.engine.stamp.id) == ("story", "dnd5e")
    assert story.state.engine == story.engine.stamp
    assert dnd5e.state.engine == dnd5e.engine.stamp
    assert isinstance(composition.advancement_ui(story.engine), StoryAdvancementUi)
    assert isinstance(composition.advancement_ui(dnd5e.engine), Dnd5eAdvancementUi)


def test_engines_are_constructed_once_per_process(tmp_path: Path) -> None:
    composition = create_composition(ui_settings(tmp_path))

    first = composition.application("a", "whispering_vault_5e", "kael_5e")
    second = composition.application("b", "whispering_vault_5e", "kael_5e")

    assert first.engine is second.engine


def test_one_slug_reuses_one_session_and_refuses_conflicting_definitions(
    tmp_path: Path,
) -> None:
    sessions = SessionRegistry(create_composition(ui_settings(tmp_path)))

    first = sessions.session("shared", "whispering_vault", "kael")

    assert sessions.session("shared", "whispering_vault", "kael") is first
    with pytest.raises(ValueError, match="open session.*uses"):
        sessions.session("shared", "whispering_vault_5e", "kael_5e")


def test_refreshable_panels_bind_the_target_view_instance(tmp_path: Path) -> None:
    sessions = SessionRegistry(create_composition(ui_settings(tmp_path)))
    session = sessions.session("shared", "whispering_vault", "kael")
    first = GameView(session)
    second = GameView(session)

    assert first.chat.refresh != second.chat.refresh
