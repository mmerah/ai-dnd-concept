# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

## Phase 1 — The engine owns its plan lifecycle — DONE

- `EnginePlugin.actions` → `check` + `resolve` callables; `Engine.check_plan`/`resolve_action` are
  one-line delegations. `ActionSpec`, `_spec`, `_action`, the label machinery: deleted.
  loader.py 380 → 335 lines.
- Shared trial helper `check_plan_with_trial` in `state/plan.py` beside `apply_branch`; takes the
  engine's resolve callable, so `plan.py` never imports `Engine`.
- story: `check`/`resolve` in `rules.py`; `resolve_risk` narrowed to `tuple[list[Fact], Slug]`
  (it always names an outcome), so the None-check disappears.
- dnd5e: `resolve.py` gains `resolve` + `resolve_action` (a `match` over `actions.Action` — the
  union is the registry, spelled once); `rules.py` folds `improvise_labels`/`cast_labels` into `_labels` and
  `check_cast`/`check_feature` into `_paid_by_engine`.
- Deviation from the plan, deliberate: dnd5e's double-spend check now runs *before* the trial
  resolve rather than after. It judges the plan's own effects against untouched state and does not
  depend on the resolve; only a plan with both faults sees a different first message.
- Tests touched: `test_loader.py` (stub plugin takes the two callables), `test_resolve.py`
  (`ACTS` is derived from the `Action` union instead of counting a table that no longer exists,
  so a seventh action with no worked example still fails).
- Verified: `grep -r ActionSpec src tests scripts` empty, no `getattr(plan, "action")` in core,
  no fixture moved, no `SAVE_VERSION` bump.

## Phase 2 — One explicit run_turn — DONE

- `run_turn` is one explicit async function, ~85 lines, reading draft → scene → director →
  resolve → hooks → narrator → worldkeeper → commit. Locals replace the workspace; the nullable
  `plan`/`directive` and their unwrap guards are gone. pipeline.py 354 → 299 lines.
- Deleted: `TurnWorkspace`, `StepFn`, `TurnScript`, the six step factories, `default_workflow`.
- Three plain functions the evals call standalone: `resolve_plan`, `apply_hooks`,
  `apply_creations`. The first two return the revalidated draft alongside their facts, which is
  what the workspace's `ws.draft = ws.draft.committed().draft()` did in place.
- `Stages` (scene/director/narrator/worldkeeper) + `build_stages`, built once by the session;
  the four `*_stage` builders are unchanged. `played()` stubs the bundle per role.
- `session.role_names` → `TURN_STEPS` literal; step names byte-identical, so no `turn/*`
  fixture moved (130 tests pass, no fixture file in the diff). No `SAVE_VERSION` bump.
- `scripts/evals/run.py` calls the same plain functions. `_worldkeeper_turn` now runs the agent
  directly instead of a step closure, so it reports real retries and tokens where it used to
  hardcode `retries=(), tokens=0`.
- Second deviation, deliberate: the empty-narration guard now raises before the worldkeeper call
  rather than after the whole script. The turn is discarded either way; the only difference is one
  model call not made on a narrator that answered nothing.
- Tests: `test_a_script_takes_an_extra_step_without_core_edits` deleted with the abstraction it
  tested (a new role is an explicit call site now, which needs no framework test); `played()`
  lost its `extra` parameter. `test_pipeline.py` ties the observed step order to `TURN_STEPS`,
  which the UI progress panel reads. Net −1 test, 130 passing.

## Phase 3 — Effect vocabulary: 19 ops → 12 — DONE

- Twelve ops. `Move` (actor + item), `CounterChange(mode: adjust|spend)`,
  `TagChange(mode: add|remove)`, `RelationChange(mode: add|remove|untag|reveal)`; `TagRelation`
  deleted with no replacement (authored blocked ways are `Relation.tags` in world.json, and
  `mode: untag` is the only writer that lifts them). `Reveal`, `GainImprovisedItem`,
  `GrantCounter`, `Refill`, `SetNote`, `SetNumber`, `AddRef`, `AdvanceThread` unchanged.
- The three audience unions keep their membership exactly: `TurnEffect` is 7 members,
  `SheetEffect` 6, and no mode is policed at runtime — the unions still carry the whole permission
  story. The Director's plan schema lost ~480 lines.
- Naming deviation from the plan, deliberate: the mode field is `mode` on all three merged ops,
  never `op` — `op` is the union discriminator and cannot double as the mode.
- Two new validators, both stopping a real bug rather than a cosmetic one: a `spend` with a
  negative `amount` would refill the pool it claims to pay from, and `tag` is required exactly
  when `mode: untag`. `TagChange` gets none: `text` on a remove is inert.
- `apply_effect`'s match dispatches on `(op, mode)` patterns; every `Fact` kind and every
  `fact.data` field is preserved, so hook matching and eval probes do not move.
  `_require_carried` folded into `_move_item`, `_tag_relation` deleted.
- Three observable deltas beyond the vocabulary movement, all found by review and all kept:
  `relation_revealed` now carries the effect's `why` in its trace (`RevealRelation` had no `why`;
  `RelationChange` does, and a silently dropped field is worse than a longer trace); a `move`
  that omits `entity_id` now reads as a player move rather than failing a required-field check,
  so a malformed item move gets a movement refusal instead of a validation error; and spend's
  `ge=1` moved from the JSON schema into a validator, since the constraint is per-mode — the
  model now learns it from the field description and the retry message.
- `_effect_vocabulary` (loader.py) now checks per *mode*, not per op: `turn_effect_keys()` expands
  each merged op into one key per mode, `effect_key()` reads one back off an example. The check
  relaxed from "exactly once" to "nothing missing", because `move` legitimately wants two worked
  examples (an actor and an item) and has no mode to tell them apart.
- Rewritten authored surfaces: `engines/examples.json` (13 examples, all 12 keys),
  `engines/{story,dnd5e}/examples.json`, whispering-vault's `warded` hook, both `director.md`,
  both `advancement.md`, and `_IDS`/`_EXITS` in `turn/prompts.py`.
- `SAVE_VERSION` 46 → 47 (hooks in saved state carry effects); `schemas/*`, `instructions/*`,
  `save/*`, `state/*`, `turn/*` regenerated. Diff read: only the vocabulary movement plus the
  version bump. 130 tests pass, ruff and basedpyright clean.

- Live probe (working rule 2) passed: whispering-vault plays under both engines on the merged
  schema, and the Director still writes effects — the shrink did not land on gpt-oss-120b's
  zero-effect failure mode. The `--only director` eval pair is skipped: evals are suspended until
  Part I lands (working rule 3), and phase 5 re-baselines the settled tree anyway.

## Phase 4 — Collapse the authored-world intermediate — DONE

- `begin_game` (`app/session.py`) composes `WorldState` directly from `Scenario` + `Character`:
  build the player entity, merge the two overlays, one loop building each `Record` through
  `engine.sheet`, then `WorldState` + threads + hooks. 15 → 38 lines there, −60 in `authored.py`.
- Deleted: `AuthoredWorld`, `AuthoredEntity`, `authored_world`, `compose_world` (authored.py 210 →
  150 lines) and `Engine.initial_world` + `Engine._entity_rules`. `Engine._sheet` is public
  `sheet(kind, rules)` — the one thing composition needs from the engine.
- The deep copies stay where they were, per entity/relation/thread: loaded content is `Mutable`
  and `restart()` re-runs `begin_game` against the same `Scenario` object, so game state must
  never alias it. Only `hooks` passes through by reference, as before — `Hook` is frozen.
- The duplicate-id check moved into the same loop, message unchanged.
- Tests: `test_an_engine_refuses_an_authored_payload_it_cannot_read` now poisons the scenario
  overlay and calls `begin_game`, so it exercises the real launch path rather than a hand-built
  intermediate; `test_an_authored_ref_backs_the_sheet_and_renders_its_other_facts` calls
  `engine.sheet` directly. No test added — the composition has no new branch.
- Verified: `AIDM_GOLDEN_REGEN=1 uv run pytest` rewrote every fixture and `git status` on
  `tests/core/fixtures` stayed empty — byte-identical, no `SAVE_VERSION` bump. 130 tests pass,
  ruff and basedpyright clean.

## Phase 5 — The prompt pass — DONE

- Re-baseline: one `--only director` suite on HEAD (maintainer chose one over the planned two),
  `results/2026-08-11-7e848d4.json` — overall 78%, completion 98%. Per-case comparison against
  PLAN.md's 2026-08-07 list retired two of its four entries outright and re-attributed a third.
- Step 3 was already landed: `dnd5e/examples.json` carries the `poisoned`-lifting worked example
  (a `check` success branch, an effects-only removal, and a `prone`-adding branch) from phase 3's
  rewrite, and `director.md`'s WHAT BELONGS WHERE already mirrors it. No change made.
- Advantage taught in two places — 3 sentences in `dnd5e/director.md` and the trigger list in the
  three `mode` field descriptions (`dnd5e/actions.py`) — and `advantage-attack` stayed 0/9 through
  both. Identical plan every run, zero retries; the schema golden proves the description ships.
  Closed as a gpt-oss-120b limit, not a prompt gap. The teaching stays: it is correct, and a
  stronger model will read it.
- **Both directors now read the whole canon side.** `render_director` substituted the
  `SCENE DIRECTIVE` for `EXISTS BUT THE PLAYER DOES NOT KNOW IT YET` / `ACTIVE THREADS` /
  `SCENARIO NOTES`; it now appends. Neither director writes prose, so the leak rule (which binds
  the narrator) is untouched. Three instruction claims that had gone false were rewritten:
  `SCENE_DIRECTOR`'s "You alone are shown…" and "The Rules Director cannot see these", and
  `_DIRECTIVE_BRIEF`'s "The directive is also your only view…".
- **`_require_exit` distinguishes an absent way from an unfound one** (`state/apply.py`). One
  refusal covered both and read as a flat illegal destination, so the model dropped the move
  instead of revealing the way: 8/9 runs shipped `effects: []`. The unfound case now names the
  reveal-then-move fix in the refusal text. Core, so both engines get it.
- `movement-follows-exits` 0% → 11% (canon fix; retry deaths 6/9 → 1/9) → 67% (refusal fix), all
  at n=9. Re-attributed numbers: `long-rest-recharge` 78% (the 0/67/0 swing was noise),
  `condition-rider` 100%, `condition-lifted` 67–100%, `self-heal-scaling` 56% (a Scene Director
  misread, not an engine fault — left alone).
- Tests: `test_a_scene_directive_replaces_the_directors_own_canon_view` asserted the old
  substitution and became `test_both_directors_read_the_canon_and_only_the_narrator_is_kept_from_it`,
  trimmed to the three assertions that carry it. `test_movement_follows_the_connections_the_world_authors`
  matches the new unfound-way refusal. Net 0 tests, 130 passing.
- Scene-role goal substitution is the standing open problem behind `self-heal-scaling` (56%) and
  `story-check-both-directions`: the Scene Director replaces what the player declared with a goal
  of its own. One clause was tried on the quiet-turn list and reverted — 0→22% against 56→22%,
  both inside the noise floor at n=9. Recorded in PLAN.md so it is not re-tried blind.
- Prompt clarity-and-size pass over every model-facing surface (`prompts.py` instruction
  constants, both `director.md` and `advancement.md`, `effects.py` field descriptions): same
  information, plainer language, `_DIRECTIVE_BRIEF`/`_EXITS`/`WORLDKEEPER` restructured from
  chained prose into bullet lists where each rule stands alone. **Mean tokens/turn 9631 → 8522
  (−11%)** at an unchanged overall rate (80.2% → 80.5%).
- One clause was restored to its pre-pass wording: `_EXITS`'s reveal-then-move rule. Compressed to
  a noun-phrase fragment it read 33% at n=9; back as "Walking an exit the player has not found yet
  is one plan, not two: …" it reads 67% twice. The lesson is worth keeping — a rule the model must
  *act* on survives compression worse than one it must merely know.
- Goldens: `instructions/*` (all 10), `prompts/{dnd5e,story}/director`,
  `schemas/dnd5e/turn_plan.json`. No `SAVE_VERSION` bump — no persisted bytes change.

## Phase 6 — Small proven deletions — DONE

- **One content lookup surface.** `Content` exposes `record`/`require`/`provides` only. Deleted:
  the generic type parameter, the `kind` argument, the `wrong_type` miss reason, `get()`,
  `resolves()`, and `SerializeAsAny` on `Pack.records`. Every caller already passed `Record`
  (loader ×4, `dnd5e/advance.py`, `evals/probes.py`, `tests/dnd5e/test_content.py`), and the SRD
  importer already flattens `Interpreted` through `.generic()` before a pack is written — so no
  `Record` subclass ever entered a runtime `Pack`. `validate_state` now probes the same
  `record()` it uses everywhere else. packs.py 285 → 256 lines; pack round-trip bytes unchanged.
- **One frozen value base.** `state.packs.Value` and the `Frozen.__hash__` override are gone;
  `ContentRef`, `Record`, `Manifest`, `Pack`, `ContentMiss`, `EngineSpec`, the sheet templates,
  and the SRD importer's authoring values all subclass `state.base.Frozen`. `Value` existed only
  to keep Pydantic's generated hash that `Frozen` threw away, so `ContentRef` could key
  `Content.records`; deleting the override made the second base pointless. `FrozenMap` stays —
  `frozen=True` does not freeze a contained dict.
- **One UI panel module.** `chat`, `role_badges`, `trace_panel`, `advancement_panel`,
  `state_panel`, and `show_engine_badge` moved verbatim into `src/aidm/ui/panels.py` (170 lines);
  the `panels/` and `components/` packages are deleted. Import consolidation only — no callback
  ownership or rendered output changed, and `test_package_boundary` still walks the package.
- `read_trace` inlined into its sole caller `FileTraces.load`. `FileSaves`/`FileTraces` stay
  split, per PLAN.
- Net Python delta: **−43 lines** (166 added, 209 deleted). 130 tests pass, ruff and basedpyright
  clean, no fixture regenerated, no `SAVE_VERSION` bump.

## Phase 7 — Test-only Ironsworn-shaped boundary probe — DONE

- `tests/probe/probe_engine.py` (137 lines): a `Fighter` with bounded momentum under a per-fighter
  `ceiling` (10 minus its debilities) and `Track`s that refuse to be `resolved` below 40 ticks —
  two cross-field invariants no shared `Sheet` can express. One typed action (`Strike`) resolved
  by an action die against two challenge dice into strong/weak/miss, mutating mechanics directly
  and emitting `Fact`s. Five functions are the whole contract: `create`, `commit`, `initialize`,
  `render`, `resolve`. Not in `ENGINE_MODULES`, not in the launcher.
- Its entire import list is `aidm.state.base`, `aidm.state.dice`, `aidm.state.facts` — no `Sheet`,
  no sheet effect, no `EngineSpec`, no packs, no advancement, no shipped engine.
- `tests/probe/test_probe_boundary.py` (5 tests): authored JSON → mechanics → byte round trip;
  three corruptions only the engine can judge are refused (momentum over its ceiling, ticks past
  40, a resolved-but-unfilled track); the strike is deterministic per seed and reaches all three
  outcomes across 20 seeds; an actor created during play gains mechanics before the commit while
  an item gains none, and both render; and an **AST assertion** that the fixture imports nothing
  core must not own, plus that it exposes no advancement or content capability. The last one is
  the durable pressure — pushing engine concepts back into core now fails a test, not a review.
- `docs/adr/0001-world-mechanics-boundary.md` records what the fixture proves and gives phase 8
  the method-by-method contract: core owns fiction (entities, placement, discovery, relations,
  threads, hooks, facts, uninterpreted traits), an engine owns every number and its whole plan
  lifecycle, persisted mechanics is opaque JSON to core and a strict model inside the engine, one
  engine-owned commit validates both halves, and core hooks write world operations only.
- `tests/probe` added to pytest `pythonpath` and basedpyright `extraPaths`. 137 tests pass (+7),
  ruff and basedpyright clean, no fixture moved, no production file touched.

## Next

Phase 8 — separate fictional world from engine mechanics, against the contract in ADR-0001.
Story first, then 5e, reading state/turn fixture diffs at each step; bump `SAVE_VERSION`; finish
by running the probe engine through the real paths.
