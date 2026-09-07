from nicegui import Client, ui

from aidm.core.entities import EngineId
from aidm.ui import theme


def test_switching_engines_is_local_to_the_current_page() -> None:
    first = Client(ui.page("/"))
    second = Client(ui.page("/"))
    try:
        with first:
            first.layout.classes("keep-layout")
            theme.set_engine(EngineId("loner3e"))
        with second:
            theme.set_engine(EngineId("breathless"))
        with first:
            theme.set_engine(EngineId("twentyfourxx"))

        assert "game-theme-twentyfourxx" in first.layout.classes
        assert "game-theme-loner3e" not in first.layout.classes
        assert "keep-layout" in first.layout.classes
        assert "game-theme-breathless" in second.layout.classes
        assert "game-theme-twentyfourxx" not in second.layout.classes

        with first:
            theme.set_engine(None)
        assert "game-theme-twentyfourxx" not in first.layout.classes
        assert "game-theme-breathless" in second.layout.classes
    finally:
        first.delete()
        second.delete()
