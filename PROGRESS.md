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

## Next

Phase 3 — effect vocabulary 19 ops → 12. Starts with the `Move` merge; note working rule 2 (probe
the Director live before cutting fixtures) and the `SAVE_VERSION` bump it requires.
