# Refactor progress

Plan: `REFACTOR-LENIENT.md`. One commit per phase; gates green before each commit.

## Phase 0 — eval harness — done, staged, not committed

- [x] `scripts/evals/probes.py` — era adapter: 12 probe models, resolved against today's typed state
- [x] `scripts/evals/run.py` — case model, runner, three-way scoring, results writer, CLI
- [x] `scripts/evals/characters/{bram,elowen}/` — eval-only fighter and wizard fixtures
- [x] `scripts/evals/scenarios/*.json` — 21 cases, 15 tagged `combat`
- [x] Every setup verified offline; every numeric bound verified by Monte Carlo against the real
      resolution code (`procedures.swing`, `spells.cast`, `features.use`)
- [x] Baseline measured twice against identical code, both records committed to `results/`
- [x] `scripts/evals/BASELINE.md` — rates, measured drift, pre-registered phase-3 thresholds
- [x] Gates green: 182 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean

Baseline at `e174637`, `openai/gpt-oss-120b`, `retries=3`, 63 turns per suite, mean of two runs:
**interpretation 74.2%, completion 95.2%, combat 67.8%, overall 70.6%.**

### Decisions taken

- **Three numbers, not one.** The first runs showed most failures were
  `UnexpectedModelBehavior: Tool 'X' exceeded max retries`, not bad arithmetic. A single blended rate
  would gate the refactor on this model's function-calling reliability, so every run is now recorded as
  completed / passed / failed and the suite reports **completion**, **interpretation** (pass rate among
  completed turns — the rules-reading signal) and **overall**.
- **Bands sized from measured drift, not guessed.** Two runs of identical code drifted 1.6–6.3 points on
  the three gate metrics, and up to 33 points on tags with ≤6 runs. Hence 12/10/12-point bands, and a
  tag-level rather than scenario-level collapse condition — at 3 runs a scenario swings 100%→33% on one
  turn, so a per-scenario floor would fire on noise.
- **Reuse `director_step`/`TurnWorkspace` from `aidm.workflow.pipeline`** instead of re-rendering the
  director prompt in the runner, so the eval exercises the code path the app uses.
- **Eval-only characters under `scripts/evals/characters/`.** Shipped `kael` carries only a lantern, so
  `procedures._held_weapon` refuses him every swing, and he casts nothing — no shipped character can
  exercise the arithmetic chains the eval exists to measure. `bram` (fighter, longsword + shortbow) and
  `elowen` (wizard) fill that gap; `kael` still covers the three non-mechanical cases, keeping shipped
  content in the suite. The scenario is always the shipped `whispering-vault`.
- **Probe vocabulary is written in post-refactor terms** (`pool` = `hp` / `slot-N` / feature index,
  `tag` = a condition name or `advancement-ready`, `set_number` keys like `armor-class`). Today those
  resolve into `StatBlock`/`Progression`; after phase 3 they are literally `Sheet` keys, so phase 3
  edits probe internals and touches no scenario file.
- **Typed 5e cannot express a starting level above 1** (`Dnd5eCharacterData` has no level field), so the
  `set_level` probe plays the level-ups out through `engine.advance`, answering each pending choice with
  its first legal option.
- **`pyproject.toml` gained `scripts/evals` in basedpyright's `extraPaths`**, matching how `scripts` and
  each `tests/` directory are already listed.

### Findings to carry into phase 1

1. **Multi-action turns are the largest single source of failures** — the director casts twice, swings
   twice, or adds a `damage` call after an `attack`, even when the prompt says "and do nothing else this
   turn". `single-action-discipline` scores 100%, so it *can* hold to one action. An explicit
   one-action-per-turn line in the phase-1 director procedure is the cheapest available win, and this
   suite will show whether it landed.
2. **Tool-argument compliance costs ~5% of turns** at `retries=3`. The lenient toolset in
   `core/mechanics.py` should prefer flat, obvious argument shapes over the fussier ones that fail today
   (`damage`'s `Magnitude`, `rest`'s enum). Watch `completion`, not just `overall`.
3. **The player's `armor-class` is hard-coded to 10** in `engines/dnd5e/engine.py`'s `initial_world` —
   never derived from dexterity or worn armour. When 5e moves onto the Sheet, `armor-class` has to be a
   number the content and the level rows actually set, or every player character stays at AC 10.
4. **Two required coverage items are unmeasurable today** and must gain scenarios in the phase that
   creates them: advantage via keep-highest (phase 1's `roll(mode=...)`) and concentration replacing a
   previous spell (a phase-3 `Sheet` note).

## Phase 1 — substrate — done, staged, not committed

- [x] `git mv src/aidm/engines/dnd5e/dice.py src/aidm/core/dice.py`, importers moved to absolute
      `aidm.core.dice` (11 src files, 3 test files); the file itself is byte-identical
- [x] `core/sheet.py` (146) — `Counter`, `CounterTemplate`, `SheetTag`, `SheetTemplate`, `Sheet`,
      `SheetDefinition.runtime`, `render_sheet`
- [x] `core/mechanics.py` (370) — `Mechanics` toolset: `roll`, `adjust`, `spend`, `recharge`,
      `add_tag`, `remove_tag`, `set_note`, `set_number`, `read_content`
- [x] `core/enginepack.py` (107) — `EngineSpec`, `load_engine`
- [x] `core/packs.py` — `LenientRecord` + `lenient_format`
- [x] CLAUDE.md's first Design rule amended as the plan quotes
- [x] Tests: `tests/core/test_sheet.py`, `test_mechanics.py`, `test_enginepack.py`, and the
      ride-along `test_shipped_content.py` (both engines compose shipped kael + whispering-vault)
- [x] Adversarial review pass applied (below)
- [x] Gates green: 200 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean
- [x] **src 9,149 lines** (budget ≤ 9,150; baseline 8,497)

Both engines still build and run unchanged; nothing was deleted.

### Decisions taken

- **`load_engine` takes the engine id as an argument** rather than reading it from `spec.json`.
  `identity.py` stays the single source of the id the plugin registers, so a spec and a plugin
  cannot disagree.
- **`mechanics.py` takes the recharge map, not the `EngineSpec`.** `enginepack` imports `mechanics`;
  passing the spec back would close the cycle, so the leaf shape (`Mapping[str, Sequence[str]]`)
  crosses instead.
- **`add_tag` takes flat arguments** (`tag_id`, `name`, `text`) rather than the plan's nested
  `SheetTag`, per the phase-0 finding that nested tool arguments cost ~5% of turns.
- **`read_content` takes the ref as one `pack/collection/index` string** — exactly the spelling
  `render_sheet` shows — so the model copies rather than decomposes. Authored overlays still use the
  structured `ContentRef` object; only the tool boundary is flat.
- **`roll` evaluates the whole expression twice for `keep-highest`/`keep-lowest`** and reports the
  dropped total in the trace, so advantage never needs a second call.
- **Notes and numbers carry `narrator=None` always**, not only while the entity is unknown: they are
  bookkeeping, and the fiction behind them is already the Director's `intent` to write.
- **`Sheet.refs` numbers land through the template** — a key the template declares a counter becomes
  that counter full (`hp: 7` → 7/7); any other key becomes a number.

### Review pass

- **Fixed a hole in `validate_state`**: the missing-key check unioned the template's numbers and
  counters before subtracting the sheet's, so a sheet holding `hp` as a *number* satisfied a
  template that declares `hp` a *counter* — the exact crossover the misname guard exists to refuse.
  Each side is now checked against its own.
- **Fixed `runtime` precedence**: a key the author declares as a counter and a backing record ships
  as a number raised "both a number and a counter" instead of letting the author win. Record numbers
  now skip any key the definition itself states.
- **Two invariants moved to load time**: `CounterTemplate` validates that it instantiates, so a bad
  `spec.json` fails when the engine loads rather than on the turn that first grows an entity; and a
  counter with a `recharge` label but no `maximum` is refused, since `recharge` can never refill it.
- Cut: `read_content` now uses `Content.get`, single-use constants and `EMPTY_TEMPLATE` inlined,
  a misleading docstring and four tests deleted or merged (director-instructions wiring, a
  tautological `player.known`, two validator tests, one single-use fixture).

### Carried into phase 2

1. `load_engine` is not wired to an engine yet — phase 2's Story shim is its first consumer, and the
   `advance`/`advancement_available`/`advancement_panel` pass-throughs die with it in 2.2.
2. No `director.md` exists yet; the one-action-per-turn line from phase-0 finding 1 goes into the
   first one written.
3. `EngineSpec.collections` carries no entity kind, so `CollectionSpec.entity` (the 5e kind guard on
   authored refs) has no lenient equivalent — accepted, as the plan's "legality thins out".

## Phases 2–3

Not started.
