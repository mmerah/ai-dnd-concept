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

## Phase 2 — Story on the Sheet, advancement as a proposal flow — done, staged, not committed

- [x] Story is data + a 55-line shim: `spec.json` (approach numbers, stress/growth counters),
      `director.md` (the risk procedure), `advancement.md` (advisor guidance), `engine.py`
- [x] **Deleted**: `story/{state,tools,rules,advancement,presentation,ui}.py` (1,089 lines)
- [x] Re-authored `characters/kael/story.json` and `scenarios/whispering-vault/story.json` as
      `SheetDefinition` payloads (same authored facts: approaches, stress cap, edges/burdens, gear)
- [x] `core/sheet.py` — `SheetDelta` (7 typed changes, each with a `why`), `apply_delta`,
      `player_sheet`
- [x] `core/engine.py` — `AdvancementOffer`, `ProposalSpec`, `offer_violation`; **deleted**
      `advance`, `advancement_available`, `advancement_panel`, `Transition`, `entered_text` and the
      panel aliases. `AdvancementDecision` deleted from `core/base.py`
- [x] `workflow/proposals.py` (69) — the `advisor` role, its instructions, the one legality rule
      (`violation`) shared by the retry and the commit, and the prompt renderer
- [x] `workflow/session.py` — `advance` → `offer` / `propose` / `preview` / `apply_proposal`
- [x] `ui/panels/advancement.py` (86) — the one generic panel: intent → Propose → the drafted
      changes with their reasons → Confirm
- [x] 5e keeps building: its shim passes a `ProposalSpec` that offers nothing and refuses
      everything; `dnd5e/ui.py` deleted
- [x] `SAVE_VERSION` 24 → 25
- [x] Evals: probes read `Sheet` payloads as well as typed 5e, `dice_rolled` with a `vs` counts as a
      contested roll, and three `story` scenarios were added
- [x] Gates green: 197 tests pass, `ruff check`, `ruff format --check`, `basedpyright` clean
- [x] **src 8,200 lines** (budget ≤ 8,400; phase 1 left 9,149)

Not done, and it needs a live model: playing a Story risk and a growth advancement through
`uv run aidm`, and recording a `story` eval rate in `results/`. Every eval *setup* was verified
offline (all 24 cases compose and apply).

### Decisions taken

- **The offer carries its content, not a ref.** `AdvancementOffer` holds `prompt`, `text`,
  `options`, `choose` — already resolved — so neither the panel nor the advisor reaches into a
  pack. `load_engine` hands `Content` to the engine's `offered`, which is the one place that reads
  it. `ProposalSpec.check` therefore takes `(state, offer, delta)` and no `LenientRecord`.
- **The mechanical half of legality is core's, not each engine's.** `offer_violation` checks the
  picks against `options`/`choose` *and* trial-applies the delta to a copy, so the advisor retries
  on anything `apply_delta` would refuse and no engine repeats those checks. `check` is left with
  the engine's own caps — Story's is 12 lines.
- **The advisor retries through pydantic-ai, not a hand-rolled loop**: an output validator raises
  `ModelRetry` with the violation, so the role's configured `retries` govern it like every other.
- **`SetNumber` writes a key the sheet does not have; counters must be granted.** Advancement is
  where a sheet grows, and the player reads every change before confirming — but a counter needs
  bounds, so `GrantCounter` is explicit and `ChangeCounter` refuses an unknown key.
- **`Record.rules` became `SerializeAsAny`.** With one payload type shared by every engine, dumping
  a foreign payload silently serialised it down to a blank `Sheet` and the commit accepted it. The
  integrity suite caught it; the annotation makes the foreign fields survive the dump so
  forbid-extra refuses them. This restores a guarantee the typed unions gave for free.
- **5e level-up is offline for this phase**, as the plan accepts: `offered` returns None so the
  panel simply says nothing is on offer, and `check` raises. `AdvancementDecision` and `Transition`
  moved into `dnd5e/advancement.py`, which phase 3 deletes whole.
- **Story keeps no recharge labels.** Stress comes back through the fiction (`adjust`), not through
  a rest, so `spec.json` maps nothing and `recharge` refills nothing for Story.
- **The probe vocabulary now spans both eras.** `pool`/`tag`/`set_number` resolve against `Sheet`
  counters, tags and numbers when the payload is a sheet, and against `StatBlock`/`Progression`
  when it is typed 5e — so the 5e scenarios and the new Story ones run from one suite.

### What Story stopped verifying in code

Accepted with eyes open, per the plan. Three of the four are now eval scenarios
(`story-risk-single-roll`, `story-taken-out-cannot-risk`, `story-no-risk-needed`). The fourth — a
claimed helpful tag that does not exist — is not reachable by outcome-level probes, because the
`+1` lives inside the dice expression the Director wrote; `BASELINE.md` records why no probe was
built for it.

### Limits this shape accepts

- **A proposal writes the player's sheet and nothing else.** Story's old `acquire_gear`, which
  created a carried item, is no longer expressible; gear now arrives through the fiction (the
  Maintainer creates the item, the Director tags it). An engine whose advancement touches a
  companion or the world would need more than a `SheetDelta`.
- **`choose` is exact, not a maximum.** "Pick up to two" cannot be offered; a record that means it
  has to be split into offers that each take a fixed count.

### Review pass

- **The legality rule became `ProposalSpec.violation`** — `offer_violation` and the workflow's
  `violation()` were two names for halves of one rule; the method holds the whole rule where the
  spec lives, and the deps type is now `AdvisorContext` (the proposal is the delta, not the deps).
- **Fixed: the trial-apply now revalidates the trial sheet.** `apply_delta` never raised on a
  delta that leaves an invalid sheet (`SetNumber` on a counter key — the misname crossover — or a
  counter maximum below its minimum), so such a proposal passed the advisor's retry and only blew
  up as a ValidationError at commit. The retry now catches everything the commit would refuse.
- **Fixed: `restart()` clears `drafted`** — a stale draft survived a restart and reappeared in the
  panel when growth next filled.
- **Fixed: the review panel no longer crashes on a stale draft** — a turn between propose and
  confirm can change the sheet under the draft, and `preview` raised mid-render.
- Cut: the picks-vs-options rule gained the test the plan asked for; the shipped-content
  value-pinning test in `tests/story/` deleted (composition is `test_shipped_content`'s job,
  merging is `test_sheet`'s); `preview` copies the player's sheet, not the whole state.
- **Instruction text stays split on purpose**: engine-owned procedure is data (`.md` in the engine
  dir, loaded by `load_engine`), core role text is code (`prompts.py`/`proposals.py` constants
  coupled to the output types and renderers beside them). 5e's `DIRECTOR_INSTRUCTIONS` is the one
  outlier and phase 3 deletes it with its module.

### Carried into phase 3

1. 5e's `ProposalSpec` is a stub. 3.1 gives it the real one: the `advancement-ready` tag opens the
   offer, the level record's `options`/`choose` bind the picks.
2. `dnd5e/advancement.py` still exports `status`/`Section`/`benefit_sections`/`plan_sections`,
   reachable only from its own tests now that the panel is gone. They die with the module.
3. `probes._actor` is still the typed-5e-only path, used by `set_level`; phase 3 deletes it along
   with `_resource`, `_progression` and the `attack_rolled`/`dc_rolled` fact kinds.
4. Story's template is per kind, so every NPC carries an unused `growth 0/3` counter in its render.
   Harmless, and the price of templates keyed by kind rather than by entity.
5. `phase 3 entry gate`: re-read `scripts/evals/BASELINE.md` before starting.
