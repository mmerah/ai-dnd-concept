from nicegui import Client, ui
from nicegui.elements.colors import Colors
from support.table import ENGINES_BUILT

from aidm.core.entities import EngineId
from aidm.ui import theme


def _colors(client: Client) -> Colors:
    (last, *_) = (
        element for element in reversed(client.elements.values()) if isinstance(element, Colors)
    )
    return last


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


def test_set_engine_writes_the_engines_accent_as_the_primary_colour() -> None:
    theme.seed({engine_id: engine.palette for engine_id, engine in ENGINES_BUILT.items()})
    client = Client(ui.page("/"))
    try:
        with client:
            theme.set_engine(EngineId("loner3e"))
        colors = _colors(client)
        loner3e = ENGINES_BUILT[EngineId("loner3e")]
        assert colors.props["primary"] == loner3e.palette["game-accent"]
        assert colors.props["secondary"] == loner3e.palette["game-muted"]
        assert colors.props["negative"] == theme.NEUTRAL_PALETTE["game-danger"]
        assert colors.props["positive"] == theme.NEUTRAL_PALETTE["game-success"]
    finally:
        client.delete()


def test_set_engine_falls_back_to_the_neutral_palette() -> None:
    client = Client(ui.page("/"))
    try:
        with client:
            theme.set_engine(None)
        colors = _colors(client)
        assert colors.props["primary"] == theme.NEUTRAL_PALETTE["game-accent"]
    finally:
        client.delete()


def test_the_generated_css_carries_each_engines_palette() -> None:
    theme.seed({engine_id: engine.palette for engine_id, engine in ENGINES_BUILT.items()})
    css = theme._palette_css()  # pyright: ignore[reportPrivateUsage]
    for engine_id in ENGINES_BUILT:
        assert f"game-theme-{engine_id}" in css
