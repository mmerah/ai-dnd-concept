# PROGRESS

One entry per PLAN.md phase. `src` counts are Python and JavaScript together, the vendored
library excluded (How to work 4).

## Phases 1-4 as one — the table: phone layout, a safe composer, physics dice, dictation

`src`: 9,698 → 9,771 lines (+73; plan target ≈ +100). `dice_overlay.js` (220) and the
polyhedron CSS went; `dice_tray.js` (95), `dictation.js` (83) and `dictation.py` (9) came.
Vendored, uncounted: `ui/lib/dice-box-threejs.es.js` 0.0.12 with its LICENSE, 28 mp3 files
under `ui/dice_assets/sounds/`.

Standing decisions, unchanged: Python is the only RNG; only `told` dice reach the browser; no
save model field; sound preference in `localStorage`; no flag between renderers.

### Decided off-plan

- **The dice box lives outside Vue's reactive data** (`created()` sets `this.box`): a reactive
  proxy around it breaks Three.js's read-only matrices and `roll()` throws before a die spawns.
- **The drawer carries a close button below 600px**: at 420px it covers a 390px phone whole,
  header included, and a swipe was the only way out.
- **The header never wraps**: `no-wrap`, an `ellipsis` title, the engine badge hidden below
  600px, and the header gap in CSS (1rem, .25rem under 600px) instead of an inline style.
- **The dice assets route is a prop** of `DiceTray`, so `/dice/` is spelled once, in Python.
- **`toggleSound` emits `sound`** instead of returning a value; Python never awaits the browser.
- **The Restart dialog is built once** in `build()`; `confirm_restart` sets its text and opens it.
- **`--game-scene-height`** is the one place the scene cap is written.
- **`own_move` clears after every `_run`**, so a refused move never pulls the reader down later,
  and scrolling back to the end by hand hides "New activity".

### Refuted findings

- "The first game page of a fresh process arrives unstyled because `_game` awaits `connected()`
  before `theme.apply()`": NiceGUI's `_add_javascript` (style.py:64-70) pushes shared CSS through
  `run_javascript` when the response is already built and a slot stack exists, which is exactly
  the case inside the page function after the await. The `@cache` and `shared=True` stay.

### Known and accepted

- Looked at in Chromium at 390, 768 and 1280px and as iPhone 13: layout, drawer, long draft,
  Enter as newline on touch, draft back after reload, Restart dialog, dice in flight and cleared,
  mute remembered. The toss was driven by calling the component with prescribed values: no
  model runs offline, so a Loner, Breathless or 24XX turn with real dice was not played.
- Dictation was checked structurally only (the button appears in Chromium, hidden where
  `SpeechRecognition` is absent); recognition itself needs a browser with a recogniser and a
  secure context, which the container has not. The error map and caret insertion are the
  tested seams.
- Reviews: Fable and a second Opus reviewer (no `codex` on the machine).
