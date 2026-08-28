# PLAN — SRD fidelity, engine shape, and the third engine

Phases 0–2 shipped (git log). Cairn Barebones was built whole on `cairn-shelved` (`8a9ed4b`) and
scrapped on 2026-08-28; Fate Condensed is dropped with it. This file is the authority for what
remains. Progress is tracked in `PROGRESS.md`. Verify every phase with `uv run pytest && uv run
ruff check && uv run ruff format --check && uv run basedpyright`, with `UV_CACHE_DIR` unset.

Standing rule: **SRD fidelity outranks minimality.** Cutting an optional dial or a GM-advice tool
is fine. Cutting a rule a player would notice missing is not. Every cut is recorded as a deviation.

| # | Item | Touches core? |
|---|------|---------------|
| 3 | Preparation: port the kept core work, `ItemSheet`, tool bar, test touchpoints | yes, small |
| 4 | Breathless engine | no |

## Settled: why Cairn was scrapped (2026-08-28)

Recorded so it is not re-litigated. Cairn shipped 12 deviations, 22 Director tools (12 engine +
10 core), a 6.3 KB director prompt, and an eval that ran 33–100% unstable on the weak model; 24XX
runs 8 + 10 tools at 5.7 KB, Loner 4 + 10 at 3.7 KB. The deviation count tracked SRD size (1,476
lines against 24XX's 367), not architecture: five were GM procedures cut whole, three were
solo-play fiction gates, two were core-shape choices every engine shares. The plan's claim that
Cairn "ships with no edit outside its package" was false: 15 files outside it.

Three causes were measured, and each has a fix in Phase 3:

1. Items had no typed home, so every engine invented a trait convention (Cairn's `MARK` regex,
   24XX's `bulky`/`broken`), guarded it in `validate`, and spent a director.md paragraph reserving
   slugs from `add_trait`.
2. No tool budget. The weak model breaks with the tool surface, so the surface is the bar.
3. Two hand-written per-engine lists in tests.

Decided against, with the reason: an opt-in `CORE_COMMANDS` bundle per engine (Loner and 24XX use
all ten; the `USE_ITEM` pattern is already the rule — it becomes text, not code); a Loner/24XX
fidelity pass before engine three (Phase 2 did it; the 7 remaining deviations are deliberate
rulings, none a core gap); rules-as-data; one "resolve" mega-tool (same schema size); typed
conditions on the sheet instead of traits (traits are the one-tool path the weak model handles).

## Phase 3 — preparation

Minimal and clean: every step is the smallest change that leaves the repo in its final shape.
Master never received Cairn or the clock, so nothing is deleted from code; the work is a port from
`cairn-shelved` of what survives without Cairn, plus the three fixes.

1. **Port from `cairn-shelved`**, and nothing else: core `PlayerAction`/`play_action` (an engine
   offers what the player can do now, applied through `transact`, recorded as an exchange) with
   the sheet-panel buttons and the MCP `player_action` tool. Not ported:
   `Game.hour`, `pass_time`, `advance_clock`, `Engine.elapse` — no engine on
   master reads them, and Breathless has no clock — and `Entity.uses`/`use_item`, reversed
   mid-phase: its one consumer is 24XX's break budget, which is engine data and lives on the item
   sheet of step 2, so `Entity.rules` stays the only engine channel on `Entity`. `player_actions`
   is kept without a consumer because Phase 4 is its consumer (Catch Your Breath); that is the
   one exception, stated here.
2. **`ItemSheet`.** `Entity.rules` is already the engine-owned, engine-validated bag, but
   `SheetEngine` reads it for actors only. An engine that declares an item sheet type validates
   `rules` on items too, renders it through `describe` and refuses it in `check_scenario` like an
   actor's. 24XX is the first consumer: `bulky`, `broken` and the break budget (`breaks`, a
   `Counter`) move off traits onto the item sheet; `add_trait` can no longer corrupt them, and
   the "engine owns the marks" paragraph leaves director.md. Breathless is the second (the item
   die).
3. **The tool bar, in `AGENTS.md`.** An engine ships one Director tool per SRD procedure, never
   more than 24XX's eight,
   shaped like 24XX's `roll_attempt`: the engine rolls everything the procedure needs
   and hands back one result. Core exposes a tool only when an engine rule reads it.
4. **Test touchpoints reflect.** `tests/core/test_package_boundary.py`'s engine tuple comes from
   `engine_ids()`; the per-engine scripted turn in `test_golden_turn.py` moves next to that
   engine's own tests, so a new engine adds a package and a fixture directory and touches no
   core test. `AIDM_GOLDEN_REGEN=1` already regenerates fixtures.
5. **Docs.** Delete `docs/CAIRN-BAREBONES.md`, `docs/FATE-CONDENSED.md`, `plans/L5-*`,
   `plans/L6-*`; drop their README rows and the Fate attribution paragraph. Add
   `docs/BREATHLESS.md` in the shape of `docs/24XX.md`: official URLs, version, ORC licence and
   the exact attribution string, an empty deviation list.

## Phase 4 — Breathless

Source: the Breathless SRD v2.1 (2026-05-08), Fari RPGs, ORC License — accepted 2026-08-28.
Transcribe from the official page, never from a summary. What the SRD holds, as read on
2026-08-28 (verify against the page before building):

- Six skills (Bash, Dash, Sneak, Shoot, Think, Sway) rated d4 by default, d10/d8/d6 assigned at
  creation. A risky action rolls the skill's die or an item's: 1–2 fail with a complication, 3–4
  succeed with a complication, 5+ succeed. **Every skill rolled steps down one size** until Catch
  Your Breath resets them all and introduces a complication.
- A loot die starting at d12 that steps down with each use; its result is trouble, an item of a
  given rating, or a med kit. Three items and one med kit carried at most. **Items carry a die
  that steps down with use and break at d4.**
- Stress: at 4 the character is vulnerable, and a failed dangerous check may kill them. A med kit
  clears 2 stress; rest clears some.

What that buys against the architecture: a game state that changes on every roll with no Director
judgment (skill and item dice), the first `ItemSheet` after 24XX, the first `player_actions`
consumer (Catch Your Breath, use a med kit — each returning a `MechanicEvent` card, like a roll),
and a Director surface of three or four tools. The MCP side is one tool, `player_action`, whose
refusal lists the offers; there is no separate listing tool. Hard
constraint from the scrapping: if Breathless needs a new core hook, stop and write it down — that
is evidence about the boundary, not a task.

Shape, as every engine: `engines/breathless/` with `rules.py`, `engine.py`, `director.md`,
`packs/srd.json`; `characters/kael/breathless.json`; one single-engine scenario with
`grows: true`; a `CANON` entry in `evals/turn_eval.py`; deviations in `docs/BREATHLESS.md`.

## Not in scope

Tests are not a focus: correct them minimally to keep the suite green. L1, L2, L7, L8, L9 and
I1–I6 stay in `IDEAS.md`; L7 onward follows Phase 4.
