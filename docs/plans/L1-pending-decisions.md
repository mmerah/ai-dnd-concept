# L1: Make a pending decision unmistakable

A pending decision reaches the player as two faint copies of one sentence and nothing else.
`src/aidm/ui/game.py:354-365` draws `pending.prompt` as one `text-sm font-bold` label in a
`game-card` plus an empty options row; `src/aidm/ui/game.py:82-83` already printed that same string
as `Paused: …` in `text-xs italic opacity-60`. Loner's options-less hand-back
(`src/aidm/engines/loner3e/rules.py:216-218`, text at `rules.py:82-84`) hits that path with zero
buttons, so the card is one bold line: nothing says the game stopped, names the mode, or points at
the composer, which keeps its idle placeholder throughout (`src/aidm/ui/game.py:176`).

## Approach

Renderer-side only. `PendingDecision.kind` is already the engine's mark of the mode — every engine
must declare its kinds through `Engine.check_pending` (`src/aidm/engines/core.py:230`), so
`conflict` / `defence` / `stake` are authoritative and free. The panel gets a header row (pause
icon + `kind` in the existing `.game-outcome` accent-uppercase style + "the game is waiting on
you"), the prompt at readable size, the option buttons it already draws, and — when `free_text` —
one line pointing at the composer, whose placeholder also switches. The duplicate `Paused:` line is
dropped while the decision is still open. One accent border in `theme.py` separates the waiting card
from mechanic cards. Loner's prompt is reworded to name the moves, since it is the one hand-back
with no buttons to imply them.

Skipped: a `title`/`icon`/`urgency` field on `PendingDecision`, and a kind→label table in the UI
(the maintainer rejects name-keyed tables; `kind` reflects). Add a model field when two decisions
share a kind but need different headlines, or a kind slug stops reading as English.
Skipped: options on the loner conflict (press on / break away). That needs `Loner3eEngine.resume`
and its resolvers; worth it only if free-text answers measurably drift in an eval.
Skipped: luck pools in the card — the `counter_changed` event card above it already prints them.

## Steps

1. `src/aidm/ui/theme.py` — one rule beside `.game-card`:
   `.game-decision { border-color: var(--game-accent); background: var(--game-surface-raised); }`
2. `src/aidm/ui/game.py` `decision_panel` (line 344) — rebuild the body:
   ```python
   with ui.column().classes("game-card game-decision w-full").style("gap: 0.5rem"):
       with ui.row().classes("items-center no-wrap").style("gap: 0.4rem"):
           ui.icon("pause_circle").classes("game-card-icon")
           ui.label(pending.kind).classes("text-xs font-bold game-outcome")
           ui.label("the game is waiting on you").classes("text-xs opacity-60")
       ui.label(pending.prompt).classes("text-base whitespace-pre-wrap")
   ```
   then the existing `viewing` branch and option-button loop, and finally
   `if pending.free_text: ui.label("Or answer in your own words below.").classes("text-xs opacity-60")`.
3. `src/aidm/ui/game.py` `_composer_placeholder` — take the `GameView` instead of the step so it can
   read `view.session.state.pending`; return `"Answer the question above…"` when a free-text
   decision is open, the step line when a step runs, `"What do you do?"` otherwise. Move it below
   `class GameView` (3.13 evaluates annotations eagerly); the three call sites — `on_step` (273),
   `_send` (326), `composer` (372) — all already hold `view`.
4. `src/aidm/ui/game.py` `chat` (line 82) — bind
   `last = session.state.history[-1] if session.state.pending is not None else None` before the loop
   and render the `Paused:` line only for `exchange is not last`. Identity, not string equality:
   repeated loner conflicts against the same foe produce identical prompts.
5. `src/aidm/engines/loner3e/rules.py:82-84` `conflict_prompt` — reword to name the moves, e.g.
   `f"The exchange with {foe.name} is over and the conflict goes on. Press it, try something else, or break away — say what you do."`
   This string is also replayed to the director (`turn/run.py:164`, `run.py:302`), so keep it
   mechanical and short.
6. `src/aidm/harness/codemode.py:411` `_waiting` — prefix the mode: `f"{pending.kind}: {pending.prompt}"`.
   It already lists ids, labels and the free-text fallback; `harness/mcp.py` is transport, unchanged.

## Risk / size

Roughly 35 added, 12 removed across four files; no model, save-format or engine-API change, so no
save invalidation. What could break: the `_composer_placeholder` signature change (three call sites,
all typed) and the `props()` quoted-string form `on_step`/`_send` already use for it.
`tests/loner3e/test_loner3e_engine.py:189` calls
`conflict_prompt` symbolically, so step 5 is free; `tests/core/test_decisions.py` covers the plumbing
untouched here. Check: `uv run aidm`, take a loner fight to a surviving exchange, and confirm one
accent card reading `CONFLICT / the game is waiting on you`, no `Paused:` echo above it, and the
composer prompting for an answer.
