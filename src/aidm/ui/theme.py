from collections.abc import Mapping, Sequence
from functools import cache
from typing import cast

from nicegui import ui

from aidm.core.entities import EngineId

type Tokens = Mapping[str, str]

# The single source for every hex value: the CSS block and the Quasar colours below both read it.
NEUTRAL_PALETTE: Tokens = {
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
    "game-measure": "46rem",
    "game-heading": "Georgia, 'Times New Roman', serif",
}
ENGINE_PALETTES: dict[EngineId, Tokens] = {
    EngineId("loner3e"): {
        "game-bg": "#14121e",
        "game-surface": "#201c2d",
        "game-surface-raised": "#2c263c",
        "game-text": "#eee7f4",
        "game-muted": "#bdb0ce",
        "game-border": "#443951",
        "game-accent": "#c5a4ed",
        "game-wash": "rgba(197, 164, 237, .09)",
        "game-radius": "18px",
    },
    EngineId("tunnelgoons"): {
        "game-bg": "#191411",
        "game-surface": "#261e18",
        "game-surface-raised": "#34281f",
        "game-text": "#f4e7d5",
        "game-muted": "#c6b29c",
        "game-border": "#534030",
        "game-accent": "#eab078",
        "game-wash": "rgba(234, 176, 120, .08)",
        "game-radius": "8px",
    },
    EngineId("breathless"): {
        "game-bg": "#0d1818",
        "game-surface": "#162525",
        "game-surface-raised": "#203332",
        "game-text": "#e0eeea",
        "game-muted": "#a8c1bb",
        "game-border": "#35504b",
        "game-accent": "#94d5be",
        "game-wash": "rgba(148, 213, 190, .07)",
        "game-radius": "5px",
        "game-heading": "'Arial Narrow', 'Helvetica Neue', Arial, sans-serif",
    },
    EngineId("twentyfourxx"): {
        "game-bg": "#0f1624",
        "game-surface": "#182236",
        "game-surface-raised": "#22314b",
        "game-text": "#e3edf9",
        "game-muted": "#afc0da",
        "game-border": "#354968",
        "game-accent": "#91c8ff",
        "game-wash": "rgba(145, 200, 255, .08)",
        "game-radius": "10px",
        "game-heading": "'SFMono-Regular', Consolas, 'Liberation Mono', monospace",
    },
}

_STATIC_CSS = """
.q-page {
  background: radial-gradient(ellipse at 15% 0, var(--game-wash), transparent 65%), var(--game-bg);
}
body, body.body--dark {
  background: var(--game-bg);
  color: var(--game-text);
  font-family: 'Inter', 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
}
.q-header {
  background: var(--game-surface);
  border-bottom: 1px solid var(--game-border);
  box-shadow: 0 4px 24px #0002;
  gap: 1rem;
}
.q-page-container { height: 100dvh; box-sizing: border-box; display: flex; flex-direction: column }
.q-page { flex: 1 1 0; min-height: 0 !important; display: flex; flex-direction: column }
.nicegui-content { flex: 1 1 0; min-height: 0 }
.game-foot {
  flex: none; gap: .5rem;
  max-height: 50dvh; overflow-y: auto;
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--game-bg); border-top: 1px solid var(--game-border);
}
.game-drawer { background: var(--game-surface); border-color: var(--game-border) }
.game-drawer .q-tab-panels { background: transparent }
.q-tab { color: var(--game-muted); text-transform: none; letter-spacing: .03em }
.q-tab--active { color: var(--game-accent) }
.q-tab__indicator { background: var(--game-accent) }

.game-rail {
  flex: none; width: 5.25rem;
  background: var(--game-surface);
  border-right: 1px solid var(--game-border);
}
.game-rail-btn {
  width: 3.4rem; height: 3.4rem;
  border-radius: calc(var(--game-radius) * .9) !important;
  color: var(--game-muted) !important;
}
.game-rail-btn .q-btn__content { flex-direction: column; gap: .15rem; font-size: .6rem }
.game-rail-btn:hover { color: var(--game-text) !important }
.game-rail-on {
  color: var(--game-accent) !important;
  background: var(--game-wash);
  box-shadow: inset 0 0 0 1px var(--game-border);
}

.text-h4, .text-h5, .text-h6, .game-title {
  font-family: var(--game-heading);
  letter-spacing: -.025em;
}
.game-title { color: var(--game-text) }
.game-heading { color: var(--game-muted); letter-spacing: .1em; text-transform: uppercase }
.game-eyebrow {
  color: var(--game-accent); opacity: .8;
  letter-spacing: .22em; text-transform: uppercase; font-weight: 600;
}

.q-card, .game-card, .q-menu {
  color: var(--game-text);
  background: var(--game-surface);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  box-shadow: 0 8px 28px #0002;
}
.q-menu .q-item--active { color: var(--game-accent) }
.q-separator { background: var(--game-border) }
.q-btn {
  border-radius: calc(var(--game-radius) * .65);
  text-transform: none;
  font-weight: 600;
  letter-spacing: .01em;
  transition: background-color 160ms, box-shadow 160ms;
}
.q-btn--round { border-radius: 50% }
.q-btn--rectangle { min-height: 2.5rem }
.q-btn.bg-primary { color: var(--game-bg) !important; box-shadow: 0 3px 12px #0002 }
.q-btn--outline { background: var(--game-wash) }
.q-btn--outline:before { border-color: var(--game-border) }
.q-btn--outline:hover:before { border-color: var(--game-accent) }
.q-btn--flat.text-white { color: var(--game-muted) !important }
.q-btn:focus-visible, .q-field:focus-within .q-field__control {
  outline: 2px solid var(--game-accent);
  outline-offset: 3px;
}
.q-btn.disabled { opacity: .45 !important }
.q-badge {
  --q-primary: var(--game-accent);
  border-radius: 999px;
  padding: .35em .75em;
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: .04em;
}
.q-badge.bg-primary { background: var(--game-wash) !important; color: var(--game-accent) !important;
  border: 1px solid var(--game-border) }
.q-field__control { background: var(--game-wash); border-radius: calc(var(--game-radius) * .65) }
.q-field--outlined .q-field__control:before { border-color: var(--game-border) }
.q-field__native, .q-field__input { color: var(--game-text) }
.q-field__label, .q-field__marginal, .q-field__bottom { color: var(--game-muted) }
.q-field__native::placeholder { color: var(--game-muted); opacity: .8 }
.q-field--focused .q-field__label { color: var(--game-accent) }
.q-uploader { background: var(--game-surface-raised); border: 1px solid var(--game-border) }
.q-uploader__header { background: var(--game-surface-raised); color: var(--game-text) }

/* One measure down the page: the scene title, every bubble and the composer share a left edge. */
.game-measure, .game-transcript { max-width: var(--game-measure); margin-inline: auto }
.game-scene {
  --game-scene-height: clamp(9rem, 26vh, 16rem);
  position: relative; overflow: hidden; flex: none;
  border-bottom: 1px solid var(--game-border);
  background: var(--game-surface);
}
.game-scene:has(.game-scene-art) { height: var(--game-scene-height) }
/* The frame again, blurred past reading, so the letterboxed art sits on its own colour. */
.game-scene-wash {
  position: absolute; inset: 0; height: 100%; width: 100%;
  filter: blur(28px) saturate(1.3); transform: scale(1.15); opacity: .55;
}
.game-scene:has(.game-scene-wash):after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(100deg, var(--game-bg) 22%, #000a 62%, transparent);
}
.game-scene-body { position: relative; z-index: 1; height: 100% }
/* Its own 16:9 box, so a column too narrow for the full band shortens the art, never crops it. */
.game-scene-art {
  flex: none; align-self: center;
  width: min(55%, calc(var(--game-scene-height) * 16 / 9)); aspect-ratio: 16 / 9;
  /* Bled to the edges and dissolved on the left: the whole 16:9 frame, cropped nowhere. */
  -webkit-mask-image: linear-gradient(to right, transparent, #000 24%);
  mask-image: linear-gradient(to right, transparent, #000 24%);
}
/* The gutter the centred transcript leaves, so the title starts where the bubbles do. */
.game-scene-text {
  flex: 1 1 auto; min-width: 0;
  height: 100%; overflow-y: auto;
  padding: 1.1rem 1rem;
  padding-left: calc(max(0px, (100% - var(--game-measure)) / 2) + 1rem);
}
.game-scene-title { color: var(--game-text); line-height: 1.1 }
/* No side padding: an avatar starts on the measure's edge, where the scene title starts. */
.game-message { padding-inline: 0 }
.game-message .q-message-name { color: var(--game-muted); font-size: .75rem; font-weight: 600 }
.game-message .q-message-text {
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  padding: .85rem 1rem;
  box-shadow: 0 4px 16px #0002;
}
.game-message .q-message-text:before { display: none }
.game-message .q-message-text-content { color: var(--game-text); line-height: 1.7 }
.game-message .q-message-text--sent {
  background: linear-gradient(130deg, var(--game-wash), transparent), var(--game-surface);
  border-color: var(--game-accent);
}
.game-message.q-message-sent .q-message-name { color: var(--game-accent) }
.game-narration .q-message-text { border-left: 3px solid var(--game-border) }
.game-avatar {
  border: 1px solid var(--game-border); background: var(--game-surface-raised) !important;
}
.game-avatar-dm { color: var(--game-accent); border-color: var(--game-accent) }

.game-card { padding: .6rem .9rem; margin: .35rem 0 }
/* An expansion brings its own padding, so the card around it only lends surface and edge. */
.q-expansion-item.game-card { padding: 0; overflow: hidden }
.q-expansion-item.game-card .q-item { min-height: 2.75rem }
.game-portrait .q-avatar { font-size: 64px !important }  /* beats the inline `size` */
.game-decision {
  border-color: var(--game-accent);
  background: linear-gradient(110deg, var(--game-wash), transparent), var(--game-surface);
  box-shadow: 0 4px 20px #0002;
}
.game-card-icon { color: var(--game-accent) }
.game-outcome { color: var(--game-accent); letter-spacing: .08em; text-transform: uppercase }
.game-die {
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: calc(var(--game-radius) * .6);
  min-width: 2.4rem;
  padding: .2rem .4rem;
  align-items: center;
}
.game-die-face { font-size: .6rem; color: var(--game-muted); text-transform: uppercase }
.game-die-value {
  font-size: 1.15rem; font-weight: 700; text-align: center; font-variant-numeric: tabular-nums;
}
.game-die-kept { border-color: var(--game-accent); box-shadow: 0 0 0 1px var(--game-accent) }
.game-die-live { animation: game-die-tumble 600ms cubic-bezier(.2, .8, .3, 1) both }
@keyframes game-die-tumble {
  from { opacity: 0; transform: perspective(240px) rotateX(-220deg) rotateY(160deg) scale(.5) }
  60% { opacity: 1; transform: perspective(240px) rotateX(20deg) rotateY(-15deg) scale(1.08) }
  to { transform: none }
}
.game-dice-overlay {
  position: fixed; inset: 0; overflow: hidden; pointer-events: none; z-index: 5000;
  transition: opacity .5s;
}
.game-dictating { box-shadow: 0 0 0 4px #f0969659; animation: game-pulse 1.2s infinite }
@keyframes game-pulse { 50% { box-shadow: 0 0 0 8px #f0969600 } }
.game-composer {
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  box-shadow: 0 6px 24px #0003;
}
.game-composer:focus-within { border-color: var(--game-accent) }
.game-composer .q-field__control { background: transparent }
.game-send {
  background: var(--game-accent); color: var(--game-bg) !important; box-shadow: 0 2px 10px #0003;
}

@media (max-width: 1023.98px) { .game-rail { display: none } }
@media (max-width: 599.98px) {
  .q-header { gap: .25rem }
  /* No room beside the text: the frame goes full width on top and fades into the words below. */
  .game-scene:has(.game-scene-art) { height: auto }
  .game-scene-body { flex-direction: column-reverse }
  .game-scene-art {
    /* Capped for a short or landscape phone, where a full-width 16:9 would fill the screen. */
    width: 100%; max-width: none; height: auto; aspect-ratio: 16 / 9; max-height: 30dvh;
    -webkit-mask-image: linear-gradient(to bottom, #000 68%, transparent);
    mask-image: linear-gradient(to bottom, #000 68%, transparent);
  }
  .game-scene-text { height: auto; padding: .2rem .9rem .9rem }
  .game-scene-title { font-size: 1.25rem }
  .game-message .q-message-text { padding: .65rem .75rem }
}
@media (prefers-reduced-motion: reduce) {
  .game-die-live, .game-dictating { animation: none }
  .q-btn, .game-dice-overlay { transition: none }
}
"""


def apply(engine: EngineId | None = None) -> None:
    ui.dark_mode(True)
    _inject_css()
    set_engine(engine)


def set_engine(engine: EngineId | None) -> None:
    layout = ui.context.client.layout
    previous = " ".join(
        name for name in cast(Sequence[str], layout.classes) if name.startswith("game-theme-")
    )
    layout.classes(remove=previous, add=f"game-theme-{engine}" if engine else "")
    palette = _palette(engine)
    ui.colors(
        primary=palette["game-accent"],
        secondary=palette["game-muted"],
        dark=palette["game-surface"],
        dark_page=palette["game-bg"],
        positive=palette["game-success"],
        negative=palette["game-danger"],
    )


def _palette(engine: EngineId | None) -> dict[str, str]:
    overrides: Tokens = ENGINE_PALETTES.get(engine, {}) if engine is not None else {}
    return {**NEUTRAL_PALETTE, **overrides}


def _declarations(palette: Tokens) -> str:
    return "\n".join(f"  --{key}: {value};" for key, value in palette.items())


def _engine_block(engine: EngineId, overrides: Tokens) -> str:
    selector = f".q-layout.game-theme-{engine}"
    return f"body:has({selector}), .game-theme-{engine} {{\n{_declarations(overrides)}\n}}"


def _palette_css() -> str:
    root = f":root {{\n{_declarations(NEUTRAL_PALETTE)}\n}}"
    engines = "\n\n".join(
        _engine_block(engine, overrides) for engine, overrides in ENGINE_PALETTES.items()
    )
    return f"{root}\n\n{engines}\n"


@cache
def _inject_css() -> None:
    # `shared=True` appends to the app-wide head on every call; injected once per process.
    ui.add_css(_palette_css() + _STATIC_CSS, shared=True)
