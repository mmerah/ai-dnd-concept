from collections.abc import Mapping
from pathlib import Path

from nicegui import ui

from aidm.core.io import read_prompt
from aidm.core.views import Look

type Palette = Mapping[str, str]


# The single source for every hex value: the first paint, `set_look` and the Quasar colours.
NEUTRAL_PALETTE: Palette = {
    "game-bg": "#111519",
    "game-surface": "#1a2026",
    "game-surface-raised": "#232c33",
    "game-text": "#eeeae0",
    "game-muted": "#b0b8be",
    "game-border": "#39434b",
    "game-accent": "#dbc18b",
    "game-wash": "rgba(219, 193, 139, .07)",
    "game-success": "#85c6a3",
    "game-danger": "#f09696",
    "game-radius": "14px",
    "game-inset": ".75rem",
    "game-measure": "60rem",
    "game-body": "'Inter', 'Segoe UI', system-ui, sans-serif",
    "game-heading": "'EB Garamond', Georgia, 'Times New Roman', serif",
}

# Offline the fallback stacks in the tokens above apply, which is why every stack names one.
FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    '?family=EB+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&display=swap">'
)


def apply(look: Look | None) -> None:
    ui.dark_mode(True)
    set_look(look)


def set_look(look: Look | None) -> None:
    palette = {**NEUTRAL_PALETTE, **(look.palette if look is not None else {})}
    ui.query("body").style("; ".join(f"--{key}: {value}" for key, value in palette.items()))
    ui.colors(
        primary=palette["game-accent"],
        secondary=palette["game-muted"],
        dark=palette["game-surface"],
        dark_page=palette["game-bg"],
        positive=palette["game-success"],
        negative=palette["game-danger"],
    )


def install() -> None:
    # One look for every call site: the defaults live here so no widget repeats a prop.
    ui.button.default_props("no-caps")
    ui.badge.default_props("outline")
    ui.input.default_props("outlined stack-label")
    ui.textarea.default_props("outlined stack-label")
    ui.select.default_props("outlined stack-label")
    ui.number.default_props("outlined stack-label")
    ui.card.default_classes("game-card")
    # `shared=True` appends to the app-wide head on every call; `start` calls this once.
    ui.add_head_html(FONT_LINK, shared=True)
    # A layer before Quasar's own outranks it; `:root` keeps the first paint dark before `body`.
    root = "".join(f"--{key}: {value};" for key, value in NEUTRAL_PALETTE.items())
    css = read_prompt(Path(__file__).parent / "theme.css")
    ui.add_css(f":root {{{root}}}@layer overrides {{{css}}}", shared=True)
