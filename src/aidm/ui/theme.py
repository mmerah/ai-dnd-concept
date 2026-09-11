from collections.abc import Mapping
from dataclasses import dataclass

from nicegui import ui

from aidm.core.entities import EngineId, Frozen

type Palette = Mapping[str, str]


class DiceLook(Frozen):
    """An engine's dice on the table: the body, the ink of the numbers, the glow of a kept die."""

    body: str
    ink: str
    glow: str


# The single source for every hex value: the first paint, `set_engine` and the Quasar colours.
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
NEUTRAL_DICE = DiceLook(body="#232c33", ink="#eeeae0", glow="#dbc18b")


@dataclass(frozen=True, slots=True)
class Theme:
    palette: Palette
    dice: DiceLook


# The one place the UI names an engine; an engine not listed here gets the neutral look.
THEMES: dict[EngineId, Theme] = {
    EngineId("loner3e"): Theme(
        palette={
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
        dice=DiceLook(body="#efe4c8", ink="#7a2e2e", glow="#c89b5a"),
    ),
    EngineId("tunnelgoons"): Theme(
        palette={
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
        dice=DiceLook(body="#3b4048", ink="#f3efe6", glow="#7fb069"),
    ),
    EngineId("breathless"): Theme(
        palette={
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
        dice=DiceLook(body="#5a1216", ink="#efe1d3", glow="#e0393e"),
    ),
    EngineId("twentyfourxx"): Theme(
        palette={
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
        dice=DiceLook(body="#101418", ink="#5ee1ff", glow="#5ee1ff"),
    ),
}

# Offline the fallback stacks in the tokens above apply, which is why every stack names one.
FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2'
    '?family=EB+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&display=swap">'
)

STATIC_CSS = """
.q-page {
  background: radial-gradient(ellipse at 15% 0, var(--game-wash), transparent 65%), var(--game-bg);
}
body, body.body--dark {
  background: var(--game-bg);
  color: var(--game-text);
  font-family: var(--game-body);
  -webkit-font-smoothing: antialiased;
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
.game-panel {
  background: var(--game-surface);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  overflow: hidden;
}
.game-main { margin: var(--game-inset) }
/* The page's 420px drawer would hang off a phone's left edge, clipping the panel. */
.q-drawer { max-width: 100% }
.game-drawer { background: var(--game-bg); border: 0; padding: 0; align-items: stretch }
/* Beside the centre panel the two share one gutter; narrower, the drawer overlays instead. */
.game-drawer-panel {
  margin: var(--game-inset) var(--game-inset) var(--game-inset) 0;
  height: calc(100% - 2 * var(--game-inset));
}
.game-drawer .q-tab-panels { background: transparent }
/* One padding, on the scroll content: Quasar's tab panel and NiceGUI's scroll default would
   each add their own. */
.game-drawer .q-tab-panel { padding: 0 }
.game-drawer .q-scrollarea__content { padding: var(--game-inset) }

.q-header {
  background: var(--game-surface);
  border-bottom: 1px solid var(--game-border);
  box-shadow: 0 4px 24px #0002;
  gap: 1rem;
}
.q-header .game-title { font-size: 1.4rem }

.q-tab { color: var(--game-muted); text-transform: none; letter-spacing: .03em }
.q-tab--active { color: var(--game-accent) }
.q-tab__indicator { background: var(--game-accent) }
/* Quasar's hover helper paints currentColor, the muted grey; a tab hovers in the accent. */
.q-tab .q-focus-helper { background: var(--game-accent) }

.game-rail {
  flex: none; width: 6rem;
  background: var(--game-surface);
  border-right: 1px solid var(--game-border);
}
.game-rail-btn {
  width: 4.5rem; height: 4.5rem;
  border-radius: calc(var(--game-radius) * .9) !important;
  color: var(--game-muted) !important;
}
.game-rail-btn .q-btn__content { flex-direction: column; gap: .15rem; font-size: .72rem }
.game-rail-btn .q-icon { font-size: 1.5rem }
.game-rail-btn:hover { color: var(--game-text) !important }
.game-rail-on {
  color: var(--game-accent) !important;
  background: var(--game-wash);
  box-shadow: inset 0 0 0 1px var(--game-accent);
}

.text-h4, .text-h5, .text-h6, .game-title {
  font-family: var(--game-heading);
  letter-spacing: -.015em;
}
.game-title { color: var(--game-text) }
.game-lead { color: var(--game-muted) }
.game-eyebrow {
  color: var(--game-accent);
  font-size: .72rem; letter-spacing: .18em; text-transform: uppercase; font-weight: 600;
}

.game-card {
  color: var(--game-text);
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  padding: 1rem 1.25rem;
  box-shadow: none;
}
/* An expansion brings its own padding, so the card around it only lends surface and edge. */
.q-expansion-item.game-card, .q-tab-panels.game-card { padding: 0; overflow: hidden }
.q-expansion-item.game-card .q-item { min-height: 2.75rem }
.q-menu {
  color: var(--game-text);
  background: var(--game-surface);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  box-shadow: 0 8px 28px #0002;
}
.q-menu .q-item--active { color: var(--game-accent) }
.q-separator { background: var(--game-border) }

.game-stat {
  display: flex; width: 100%; justify-content: space-between; align-items: baseline;
  gap: 1rem; padding: .55rem 0;
}
.game-stat + .game-stat { border-top: 1px solid var(--game-border) }
.game-stat-label { color: var(--game-muted); font-size: .85rem }
.game-stat-value { font-size: .9rem; text-align: right; font-variant-numeric: tabular-nums }
.game-stat-long { flex-direction: column; align-items: stretch; gap: .15rem }
.game-stat-long .game-stat-value { text-align: left }

.game-entity { display: flex; width: 100%; align-items: center; gap: .75rem; padding: .4rem 0 }
.game-entity-name { font-size: 1.05rem; font-weight: 600 }
.game-entity-sub { color: var(--game-muted); font-size: .8rem; line-height: 1.35 }
.game-portrait .q-avatar {
  font-size: 64px !important;  /* beats the inline `size` */
  box-shadow: 0 0 0 2px var(--game-accent);
}
.game-card-icon { color: var(--game-accent) }
.game-decision {
  border-color: var(--game-accent);
  background: linear-gradient(110deg, var(--game-wash), transparent), var(--game-surface);
  box-shadow: 0 4px 20px #0002;
}
.game-outcome { color: var(--game-accent); letter-spacing: .08em; text-transform: uppercase }

.q-btn {
  border-radius: calc(var(--game-radius) * .65);
  font-weight: 600;
  letter-spacing: .01em;
  transition: background-color 160ms, box-shadow 160ms;
}
.q-btn--round { border-radius: 50% }
.q-btn--rectangle { min-height: 2.5rem }
/* Gold is a light fill: its words are the page's own dark, never Quasar's white. */
.q-btn.bg-primary { color: var(--game-bg) !important; box-shadow: 0 3px 12px #0002 }
.q-btn--outline { background: var(--game-wash) }
.q-btn--outline:before { border-color: var(--game-border) }
.q-btn--outline:hover:before { border-color: var(--game-accent) }
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

.q-field__control { background: var(--game-wash); border-radius: calc(var(--game-radius) * .65) }
.q-field--outlined .q-field__control:before { border-color: var(--game-border) }
.q-field--outlined .q-field__control:hover:before { border-color: var(--game-muted) }
.q-field--outlined.q-field--focused .q-field__control:after { border-color: var(--game-accent) }
.q-field__native, .q-field__input { color: var(--game-text) }
.q-field__label, .q-field__marginal, .q-field__bottom { color: var(--game-muted) }
.q-field__native::placeholder { color: var(--game-muted); opacity: .8 }
.q-field--focused .q-field__label { color: var(--game-accent) }
.q-uploader { background: var(--game-surface-raised); border: 1px solid var(--game-border) }
.q-uploader__header { background: var(--game-surface-raised); color: var(--game-text) }

/* One measure down the page: the scene title, every bubble and the composer share a left edge. */
.game-measure, .game-transcript { max-width: var(--game-measure); margin-inline: auto }
.game-scene {
  --game-scene-height: clamp(9rem, 24vh, 15rem);
  position: relative; overflow: hidden; flex: none;
  align-self: stretch; margin: var(--game-inset);
  border: 1px solid var(--game-border);
  border-radius: calc(var(--game-radius) * .8);
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
/* The gutter the centred transcript leaves, less the inset this card holds, so the title
   starts where the bubbles do. */
.game-scene-text {
  flex: 1 1 auto; min-width: 0;
  height: 100%; overflow-y: auto;
  padding: 1.1rem 1rem;
  padding-left: calc(
    max(0px, (100% + 2 * var(--game-inset) - var(--game-measure)) / 2) + 1rem - var(--game-inset)
  );
}
.game-scene-title { font-size: 2.125rem; font-weight: 700; line-height: 1.1 }
.game-scene-chevron {
  position: absolute; right: .6rem; top: .6rem; z-index: 2;
  color: var(--game-accent); font-size: 1.5rem; transition: transform 200ms;
}
.game-scene-open .game-scene-chevron { transform: rotate(180deg) }

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
.game-message .q-message-text-content {
  color: var(--game-text); line-height: 1.7; font-size: .95rem;
}
.game-message .q-message-text--sent {
  background: linear-gradient(130deg, var(--game-wash), transparent), var(--game-surface);
  border-color: var(--game-accent);
}
.game-message.q-message-sent .q-message-name { color: var(--game-accent) }
.game-narration .q-message-text { border-left: 3px solid var(--game-border) }
.game-avatar { border: 1px solid var(--game-border); background: var(--game-surface) }
.game-avatar-dm { color: var(--game-accent); border-color: var(--game-accent) }

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

@media (max-width: 1023.98px) {
  .game-rail { display: none }
  .game-drawer-panel { margin-left: var(--game-inset) }
}
@media (max-width: 599.98px) {
  .q-header { gap: .25rem }
  /* A phone has no room for the inset frames: every panel runs edge to edge. */
  .game-main, .game-drawer-panel, .game-scene {
    margin: 0; border-left: 0; border-right: 0; border-radius: 0;
  }
  .game-main, .game-scene { border-top: 0 }
  .game-drawer-panel { height: 100% }
  .game-scene { cursor: pointer }
  /* Open: no room beside the text, so the frame goes full width on top and fades into the words. */
  .game-scene:has(.game-scene-art) { height: auto }
  .game-scene-body { flex-direction: column-reverse }
  .game-scene-art {
    /* Capped for a short or landscape phone, where a full-width 16:9 would fill the screen. */
    width: 100%; height: auto; aspect-ratio: 16 / 9; max-height: 30dvh;
    -webkit-mask-image: linear-gradient(to bottom, #000 68%, transparent);
    mask-image: linear-gradient(to bottom, #000 68%, transparent);
  }
  .game-scene-text { height: auto; padding: .2rem .9rem .9rem }
  .game-scene-title { font-size: 1.25rem }
  /* Closed: a strip, the art a dim band cropped behind the title, the situation put away. */
  .game-scene:not(.game-scene-open) { height: 5.5rem }
  .game-scene:not(.game-scene-open) .game-scene-art {
    position: absolute; inset: 0;
    width: 100%; height: 100%; aspect-ratio: auto; opacity: .55;
    -webkit-mask-image: linear-gradient(to top, transparent 15%, #000 70%);
    mask-image: linear-gradient(to top, transparent 15%, #000 70%);
  }
  /* `fit=contain` is an inline style Quasar writes on the frame, so the band has to shout. */
  .game-scene:not(.game-scene-open) .game-scene-art .q-img__image { object-fit: cover !important }
  .game-scene:not(.game-scene-open) .game-scene-text {
    position: relative; z-index: 1;
    height: 100%; justify-content: flex-end; padding: .2rem 3rem .7rem .9rem;
  }
  .game-scene:not(.game-scene-open) .game-scene-situation { display: none }
  .game-message .q-message-text { padding: .65rem .75rem }
}
@media (prefers-reduced-motion: reduce) {
  .game-die-live, .game-dictating { animation: none }
  .q-btn, .game-dice-overlay, .game-scene-chevron { transition: none }
}
"""


def apply(engine: EngineId | None = None) -> None:
    ui.dark_mode(True)
    set_engine(engine)


def set_engine(engine: EngineId | None) -> None:
    theme = THEMES.get(engine) if engine is not None else None
    palette = {**NEUTRAL_PALETTE, **(theme.palette if theme is not None else {})}
    ui.query("body").style("; ".join(f"--{key}: {value}" for key, value in palette.items()))
    ui.colors(
        primary=palette["game-accent"],
        secondary=palette["game-muted"],
        dark=palette["game-surface"],
        dark_page=palette["game-bg"],
        positive=palette["game-success"],
        negative=palette["game-danger"],
    )


def dice_look(engine: EngineId) -> DiceLook:
    theme = THEMES.get(engine)
    return NEUTRAL_DICE if theme is None else theme.dice


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
    # NiceGUI layers Quasar's own `!important` rules; only a layer before theirs outranks them.
    # The palette lands on `body` only once the page mounts; `:root` keeps the first paint dark.
    root = "".join(f"--{key}: {value};" for key, value in NEUTRAL_PALETTE.items())
    ui.add_css(f":root {{{root}}}@layer overrides {{{STATIC_CSS}}}", shared=True)
