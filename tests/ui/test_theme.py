from nicegui import Client, ui
from nicegui.elements.colors import Colors

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
    client = Client(ui.page("/"))
    try:
        with client:
            theme.set_engine(EngineId("loner3e"))
        colors = _colors(client)
        assert colors.props["primary"] == theme.ENGINE_PALETTES[EngineId("loner3e")]["game-accent"]
        assert colors.props["secondary"] == theme.ENGINE_PALETTES[EngineId("loner3e")]["game-muted"]
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
    css = theme._palette_css()  # pyright: ignore[reportPrivateUsage]
    for engine, overrides in theme.ENGINE_PALETTES.items():
        assert f"game-theme-{engine}" in css
        for value in overrides.values():
            assert value in css
    for value in theme.NEUTRAL_PALETTE.values():
        assert value in css
