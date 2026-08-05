# Progress — structured-plan redesign (PLAN.md)

## Phase 0 — harness prep — DONE

- `scripts/evals/run.py`: `RunRecord.duration_s` (default 0.0, ge 0.0), timed with
  `time.perf_counter()` around the `_turn` call in `run_case`; timed on the error path too.
- `CaseRecord.mean_duration_s` and `SuiteRecord.mean_duration_s`, both from one `_mean_duration`
  helper over all runs (failed runs included).
- `summarise` prints `mean duration/turn: <x>s` under the interpretation line.
- Gate green: pytest 89 passed, ruff check, ruff format --check, basedpyright 0 errors.
- Staged, not committed. Suggested message: `feat(evals): time each run`.

## Phase 1 — baseline — DONE

- Three suites on ba6455d (207 turns, ~5 min each, not the 1–2 h the plan guessed):
  overall 45% / 17% / 38%, pooled 33%; interpretation pooled 37%; mean 15.6s/turn.
- `baseline.md` written from all three, pooled column as the comparison number.
- Drift is the headline: 28 points overall, 38 on interpretation, up to 50 per tag, on an
  unchanged commit. Phase 6 must compare against pooled 37% over a 207-turn budget, and only
  `combat` (n=135) and `spells` (n=54) have enough turns to read per-tag.
- Run 2 anomaly: completion 99% but the director called no mutating tool at all. Provider
  routing suspected, unconfirmed — run 3 has run 1's latency and fails similarly.
- Result JSONs are gitignored (`scripts/evals/results/`), so only `baseline.md` is committed.

## Phase 2 — core types — DONE

- `core/dice.py`: lifted `mechanics._evaluate`/`_rolled` here as `roll(expr, reason, rng, vs=,
  mode=)` returning `(Rolled, Fact)`. `RollMode` is now `normal | advantage | disadvantage` (was
  `sum | keep-highest | keep-lowest`); the fact's kind, shape, and `data` keys are unchanged, so
  the eval probes still read it, but the mode's new name shows in an advantage roll's trace.
- `core/effects.py`: the 12-member `Effect` union (`reveal`, `move-actor`, `take-item`,
  `drop-item`, `give-item`, `gain-improvised-item`, `adjust-counter`, `spend-counter`, `add-tag`,
  `remove-tag`, `set-note`, `set-number`) + `apply_effect`. Bodies ported from `tools.py` /
  `mechanics.py`: same fact kinds, same trace wording, same reveal/leak rules (acting on an actor
  reveals them, acting on an item or a place does not; an unknown entity narrates nothing).
  `ModelRetry` became `ValueError` — the plan check trial-applies, so preconditions live once.
  Only `apply_effect` and `require_actor_here` are exported; `sheet_of` sits with `player_sheet` in
  `sheet.py`, and the rest of the lookups stay private until a resolver needs one.
- `core/plan.py`: `TurnPlanBase` (intent/tone/speaker_id/effects/branches), `OutcomeBranch`,
  `apply_branch`, and `check_plan_base` (speaker guard, one branch per label, only labels the
  action allows, then a trial apply of *each branch plus the unconditional effects* on a throwaway
  draft — branches are alternatives, so trialling them together would refuse legal plans).
- `core/engine.py`: `plan_type`, `check_plan`, `resolve_action` on `Engine`, all three required;
  `PlanCheck` / `ActionResolver` type aliases.
- `tests/core/test_effects.py`: 5 tests, one apply case and one refusal case per effect.
- Old tool-era code is untouched and still wired: `mechanics.py`, the mutating half of `tools.py`,
  the referee. Phase 5 deletes them.

## Phase 3 — Story engine — DONE

- `engines/story/engine.py`: `Risk` (actor/approach/difficulty/helping+hindering tag/stakes),
  `StoryPlan`, `_check_plan`, `_resolve_action`.
  - check: actor here, TAKEN OUT when `stress` is at maximum, a helping tag must sit on the actor
    or on gear they carry, a hindering tag on the actor alone, then `check_plan_base` with the
    labels `strong | mixed | setback` (no action → no labels, so branches are refused).
  - resolve: one `2d6 + approach + 1 helping − 1 hindering − difficulty` vs 7; `strong` ≥10,
    `mixed` 7–9, `setback` ≤6; a player `setback` marks `growth` +1 intrinsically; then the
    matching branch's effects. A label with no branch is fine.
- `core/enginepack.py`: `EngineParts` (content + spec + default_rules) handed to the two factory
  parameters, plus `plan_type`; `load_engine` keeps them optional with `_no_plan_yet` /
  `_resolves_nothing` stand-ins **only** until 5e has its own (Phase 4 makes all three required
  and deletes both stubs).
- `engines/story/director.md` rewritten: sheet vocabulary, the plan shape, how to fill a `risk`,
  the TAKEN OUT rule, the three outcome labels, and what belongs in a branch versus what the
  engine keeps (the roll, the outcome, the growth mark).
- `tests/story/test_story_engine.py` drives `check_plan`/`resolve_action` directly, no model. The
  outcome is forced by an out-of-range approach number rather than a known seed, so the assertions
  survive a change of dice seed.

## Phase 4 — 5e engine — DONE

- `core/packs.py`: `parse_ref` — a `pack/collection/index` string from model output, refused with a
  model-readable reason. Phase 5's `read_content` reuses it instead of `mechanics._reference`.
- `core/effects.py`: `_entity_fact` is now public `entity_fact` (the rest resolver needs the leak
  rule: an entity the player has not learned of narrates nothing).
- `engines/dnd5e/content5e.py`: pack-record normalisers. `WeaponFacts` (dice from
  `damage-dice-count`/`damage-die`, the versatile pair, `ranged`/`finesse` tags), `SpellFacts`
  (level/attack/save/half-on-save/damage/heal/scaling/concentration out of the importer's notes),
  `Amount` (dice plus the "+ spellcasting modifier" flag the resolver substitutes), `weapon_of`,
  `spell_of`, `spellcasting_ability` (read off the class record's `notes["spellcasting"]`).
  Unparseable → `None` → the plan check says "resolve it with `improvise` instead".
- `engines/dnd5e/actions.py`: the six actions (`attack`, `cast-spell`, `check`, `use-feature`,
  `rest`, `improvise`), `Dnd5ePlan.milestone_earned`, and the `success`/`failure` label sets.
- `engines/dnd5e/resolve.py`: `check_plan` + `resolve_action`, one function per action.
  - Every precondition raises a `ValueError` carrying its own reason and one handler turns it into
    the refusal, so the check cannot raise (a raise would kill the turn instead of retrying).
  - The action's own cost is checked by trial-spending on a throwaway draft, so the refusal a
    drained pool raises is written once, in `effects.py`.
  - `_slot_spent` and `_attack_terms` are shared by the check and the resolver: the one-of rule
    (weapon item XOR stat-block numbers) and the slot a cast costs cannot drift.
  - Order for a cast: spend the slot, then the attack roll or the target's save, then the scaling
    row for the slot actually spent (a cantrip scales by caster level), then the concentration note.
- `engines/dnd5e/engine.py` wires all three; `ADVANCEMENT_READY`/`LEVEL` moved to `resolve.py`
  (engine.py imports them — the reverse would cycle).
- `core/enginepack.py`: `plan_type`/`check_plan`/`resolve_action` are now **required** and the
  Phase 2 stubs are gone. `tests/core/test_enginepack.py` builds its loader engine with no-op ones.
- Verified against the real pack, matching every eval window before any test was written:
  longsword `1d20+5` / `1d8+3` (versatile `1d10+3`), shortbow `1d20+4` / `1d6+2`, rat AC 12,
  spell save DC 12 = 8 + 2 + 2, magic missile `3d4+3` at slot 1 and `4d4+4` at slot 2, an empty
  `slot-1` refusing the cast outright.
- `engines/dnd5e/director.md` rewritten: the sheet vocabulary, the six actions and when to pick
  each, the two outcome labels, and what the engine owns and the plan must never write.
- Tests: `tests/dnd5e/test_content5e.py` (the normalisers against the shipped pack) and
  `test_resolve.py` (per action: a hit, a miss, the one-of refusal, the slot spent before anything
  follows plus an empty slot refusing, the save DC and its half-on-save, and the bookkeeping
  actions). `fivee_test_support.armed`/`wizardly` arm and re-class Kael, who ships with neither a
  weapon nor a spell. Outcomes are forced by the target's `armor-class` or ability score, never by
  a dice seed, and damage is asserted as a window.
- Gate green: pytest 108 passed, ruff check, ruff format --check, basedpyright 0 errors.
- Staged, not committed. Suggested message: `feat(dnd5e): six actions resolved from the sheet`.

## Phase 4.5 — engine shape and prompt examples — DONE

- Both engines now have the same skeleton, and only `engine.py` may be imported by nobody:
  `engine.py` (the `load_engine` call and `PLUGIN`), `actions.py` (action models, plan type, outcome
  labels), `resolve.py` (`check_plan`, `resolve_action`), `advance.py` (`offered`, `check`), and
  `content.py` for the one engine that ships packs. Story: 32 / 47 / 104 / 38 lines. 5e: 41 / 135 /
  423 / 55 / 210.
- Pure moves — no rule, fact, or trace wording changed. `git mv` where a file was renamed:
  `dnd5e/content5e.py` → `content.py`, and the tests followed (`tests/dnd5e/test_content.py` →
  `test_packs.py`, since it tests the shipped pack; `test_content5e.py` → `test_content.py`).
- The acyclic rule that makes the layout hold: no sibling imports `engine.py`, so a constant two
  modules share lives with the module owning the vocabulary — `advance.py` owns `ADVANCEMENT_READY`
  and `LEVEL` (5e) and `actions.py` owns `APPROACHES` (story).
- Worked examples ship as `engines/<pkg>/examples.json`, one plan per action, each written lean
  (only the fields it sets, discriminators kept). **Changed from PLAN.md's validated instances on
  the maintainer's call**: sixty lines of nested constructors buried the action models in
  `actions.py`. `enginepack._examples` validates every entry against the engine's `plan_type` as it
  reads the file, so a drifted example fails every test that builds the engine, and `load_engine`
  appends the rendered block to `director_instructions`. PLAN.md was amended to match.
- Tests: one per engine asserting the rendered instructions name each `act` exactly once, plus a
  length check against the action union so a seventh 5e action cannot land without its example.
- Gate green: pytest 110 passed, ruff check, ruff format --check, basedpyright 0 errors.
- Staged, not committed. Suggested message:
  `refactor(engines): one shape per engine, and examples in the prompt`.

## Review pass over phases 2–4.5 — DONE

Adversarial review of the staged tree; two defects confirmed and fixed, three cuts applied.

- **5e `check_plan` now trial-runs its own resolver** on a throwaway draft with a fixed seed, instead
  of restating each precondition: `_check_action` and `_trial_spend` are gone (−33 lines). The
  duplication had already drifted — a heal-only spell (cure-wounds and 9 others in the pack) named a
  target nobody checked, so `check_plan` passed and `resolve_action` raised, killing the turn
  instead of retrying. `_cast` now resolves its target first, so the check catches it.
- **Rolls no longer name unrevealed actors.** `roll()`'s fact bypasses `entity_fact`'s leak guard
  and the 5e resolvers build the reason from entity names, so a missed attack narrated "Kael attacks
  a bloated rat" while the rat stayed unknown. Every resolver now reveals the actors its action
  touches (`_seen`), which is what `_rest` already did and what applying an effect to an actor does.
- **Factory closures flattened**: `check_plan(parts, state, plan)` / `resolve_action(parts, draft,
  plan, rng)` are module functions, bound by `load_engine` (`PartsPlanCheck` / `PartsResolver`).
- **One sign-formatter left**: `dice.roll(..., bonus=)` folds it in, deleting `_with`, story's inline
  f-string, and `Amount.expression` (now `Amount.bonus`). `_fivee` → `_dnd5e_plan`; six docstrings
  that restated a signature deleted; `"mode": "normal"` dropped from the examples.
- Net: `src` 5841 → 5790 lines, one new regression test (111 passing), gate green.
- **Left alone, deliberately**: the pack's `sleep` note reads `"damage": "5d8"` where 5d8 is hit
  points affected, so casting it deals damage — the fix belongs in the importer, which lives in an
  external checkout, and hand-editing the vendored pack would diverge from importer output. PLAN.md
  now records that `SheetDelta` and `Effect` stay separate for good, with the reason.
- Phase 5 note: `core/plan.py` imports `check_speaker` from `core/tools.py`; move those 15 lines
  into `plan.py` when the deletion pass guts `tools.py`.

## Phase 5 — pipeline rewire — NOT STARTED
