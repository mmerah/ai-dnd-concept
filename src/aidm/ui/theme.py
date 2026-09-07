from functools import cache

from nicegui import ui

_CSS = """
:root {
  --game-bg: #0f1115;
  --game-surface: #171a21;
  --game-surface-raised: #1e222b;
  --game-text: #f3efe6;
  --game-muted: #a9afbd;
  --game-border: rgba(255, 255, 255, .08);
  --game-accent: #c89b5a;
  --game-success: #5fa777;
  --game-danger: #c96b6b;
  --game-radius: 14px;
}

body, body.body--dark, .nicegui-content, .q-page {
  background: var(--game-bg);
  color: var(--game-text);
}

.q-header { background: var(--game-surface); }

.game-transcript { max-width: 46rem; margin: 0 auto; }

.game-card {
  background: var(--game-surface);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
  padding: .6rem .9rem;
  margin: .35rem 0;
}

.game-decision {
  border-color: var(--game-accent);
  background: var(--game-surface-raised);
}

.game-card-icon { color: var(--game-accent); }

.game-outcome { color: var(--game-accent); letter-spacing: .04em; text-transform: uppercase; }

.game-die {
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: 8px;
  min-width: 2.4rem;
  padding: .2rem .4rem;
  align-items: center;
}

.game-die-face { font-size: .6rem; color: var(--game-muted); text-transform: uppercase; }

.game-die-value { font-size: 1.15rem; font-weight: 700; text-align: center; }

.game-die-kept { border-color: var(--game-accent); box-shadow: 0 0 0 1px var(--game-accent); }

.game-die-live { animation: game-die-tumble 600ms cubic-bezier(.2, .8, .3, 1) both; }
@keyframes game-die-tumble {
  from { opacity: 0; transform: perspective(240px) rotateX(-220deg) rotateY(160deg) scale(.5); }
  60% { opacity: 1; transform: perspective(240px) rotateX(20deg) rotateY(-15deg) scale(1.08); }
  to { transform: none; }
}
@media (prefers-reduced-motion: reduce) { .game-die-live { animation: none; } }

.game-dice-overlay, .game-dice-layer {
  position: fixed; inset: 0; overflow: hidden; pointer-events: none; z-index: 7000;
}

.game-dice-die { position: absolute; left: 0; top: 0; perspective: 800px; }

/* Behind the solid: a floor shadow, and the glow of a die that landed kept. */
.game-dice-die::before, .game-dice-die::after {
  content: ""; position: absolute; inset: -25%; border-radius: 50%; z-index: -1;
}
.game-dice-die::after {
  background: radial-gradient(closest-side, rgba(0, 0, 0, .6), transparent);
  transform: translateY(28%) scale(1.1, .7);
}
.game-dice-die::before {
  background: radial-gradient(closest-side, var(--die-glow), transparent);
  opacity: 0; transition: opacity .4s;
}
.game-dice-landed.game-dice-kept::before { opacity: .75; }

.game-dice-spin, .game-dice-body { position: absolute; inset: 0; transform-style: preserve-3d; }

.game-dice-face {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  backface-visibility: hidden;
  font-family: Georgia, "Times New Roman", serif; font-weight: 800; color: var(--die-ink);
  text-shadow: 0 1px 1px rgba(0, 0, 0, .35);
  background: linear-gradient(
    155deg,
    color-mix(in srgb, var(--die-body) 70%, white),
    var(--die-body) 45%,
    color-mix(in srgb, var(--die-body) 65%, black)
  );
}

.game-dice-landed:not(.game-dice-kept) { opacity: .45; transition: opacity .4s; }

.game-composer {
  background: var(--game-surface-raised);
  border: 1px solid var(--game-border);
  border-radius: var(--game-radius);
}
"""


def apply() -> None:
    ui.dark_mode(True)
    _inject_css()


@cache
def _inject_css() -> None:
    # `shared=True` appends to the app-wide head on every call; injected once per process.
    ui.add_css(_CSS, shared=True)
