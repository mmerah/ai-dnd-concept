# Kernel refactor — progress

## Phase 1 — Worldkeeper + generic steps and trace — DONE (not committed, staged)

- [x] `state/turn.py`: `Creation` / `WorldkeeperReport` / `StepTrace`; `Turn` is now
      `prompt` + `narration` + `facts` + `steps`. `Growth`, `GrowthRequest`,
      `GrowthRejectionReason`, `RejectedGrowth`, `ScreenedGrowth`, `screen_growth` deleted.
- [x] `SAVE_VERSION` 38 → 39; `test_golden_state.FIXTURE_SAVE_VERSION` follows.
- [x] `turn/prompts.py`: `render_worldkeeper` + `WORLDKEEPER` replace the maintainer/creator
      pair; `_history` deleted (the role gets history as messages, not a rendered section).
      The rendered prompt is byte-identical to the old maintainer prompt.
- [x] `turn/pipeline.py`: one `worldkeeper_step` (1 model call, not 1 + N); screening is code
      in `admitted()` — casefold dedupe vs world + report, cap, locations applied first.
      `Cast`/`default_cast` dissolved into `default_workflow` + `director_stage` /
      `narrator_stage` / `worldkeeper_stage`. `ws.prompts` and `ws.recent` gone; steps append
      their own `StepTrace`.
- [x] `ui/panels/trace.py`: one generic section per step; **no role name in the file**.
- [x] `app/session.py` on `default_workflow`; `scripts/evals/run.py` on `director_stage`
      (its `TurnWorkspace(...)` dropped `recent=()`).
- [x] Tests: `test_growth.py` → `test_worldkeeper.py`; `core_test_support.played()` replaces
      every per-test `ExitStack` + `default_cast` block (test_pipeline −124 lines).
- [x] Fixtures regenerated: `instructions/*`, `prompts/*`, `turn/*`, `save/*`, `state/*`,
      `schemas/growth.json` → `schemas/worldkeeper_report.json`. Diff reviewed: turn traces
      are the same content restructured, saves/states moved only by `save_version`.
- [x] `uv run pytest` (122 passed) / `ruff check` / `ruff format --check` / `basedpyright` green.

**LOC:** `src/aidm` +119 −222 = **−103** (budget −200). The budget was wrong, not the work:
it counted the ~195 lines of deletions but not the additions the generic design requires —
per-step `StepTrace` appends in four steps, three per-role stage builders, `admitted`/`_placed`,
and `WORLDKEEPER` absorbing most of `CREATOR`'s text rather than deleting it. Tests net −116.

Adversarial review (fable) found no correctness defect: `admitted()` + `_placed` match HEAD's
`screen_growth` + creator loop line for line (dedupe before cap, same casefolded seen-set,
stable location-first sort, same player-location fallback). It cut `StepTrace.kind` (written
four times, read zero — the trace panel splits role/code steps on `prompt is not None`) and the
duplicate NARRATION section in the trace panel.

### Live checks — done 2026-08-07

- Played a real turn in the UI: worldkeeper on `NativeOutput` creates entities, trace panel
  renders one section per step, stale v38 save refused (deleted, as intended).
- `scripts/evals/run.py --only story --runs 1`: 100%. Full re-run skipped — the director
  schema did not change this phase.

Kept `NativeOutput` for the worldkeeper rather than copying the director's
`ToolOutput`/`TextOutput` pair: `TextOutput` is the patch `ToolOutput` needs (models answering
in prose instead of calling the tool), not an independent safety net, and the schema is flat
and ~1.3 KB against the director's unions. Degradation is visible for free — the trace panel
shows `{"creations": []}` every turn — and the fix is one line in `worldkeeper_stage`.

### Open

- No worldkeeper eval exists; the suite gates only the director. Same gap phase 5 lists for
  the advisor — write both together rather than guessing at output modes.

### Config note for the commit message

Role settings key is now `worldkeeper`; `ROLES__MAINTAINER__*` / `ROLES__CREATOR__*` env
entries silently stop applying (`Settings.roles` is an open dict, by design).

## Phase 2 — Action registry, one TurnPlan — DONE (not committed, staged)

- [x] `engines/loader.py`: `ActionSpec[A]` (model + labels + resolve + optional check).
      `EnginePlugin` drops `plan_type`, `check_plan`, `resolve_action`; gains `actions` and
      `action_doc`; `offered`/`check_delta` stay plain plugin fields as at HEAD.
- [x] The loader builds the Director's plan model once per engine (`_plan_model`): the actions as
      one `act`-discriminated union, a lone action plain (a discriminator on a non-union raises),
      no actions at all → `TurnPlanBase` (the fake engine in `test_loader.py`). `Engine.plan_type`
      is now a field, not a plugin passthrough.
- [x] `Engine.check_plan` is the kernel's: trial resolve on a throwaway draft with `Random(0)`
      wrapped in `try/except ValueError`, then the spec's `check`, then `check_plan_base` with the
      spec's labels. `Engine.resolve_action` applies the matching branch itself — no resolver calls
      `apply_branch` any more.
- [x] dnd5e: `_resolved`'s six match arms are six `resolve_*` functions, `_labels` is per-spec
      (`cast_labels`/`improvise_labels`; the four constant cases are plain frozensets on the
      spec), `_double_spend` is shared by `check_cast`/`check_feature`. `Dnd5ePlan`,
      `Dnd5eAction`, `_dnd5e_plan` deleted.
- [x] story: `resolve_risk` + `check_risk` (was `_refused`); `StoryPlan` and `_story_plan` deleted.
- [x] `milestone_earned` deleted outright — plan field, `MILESTONE_TAG` path, director.md
      paragraph, worked example, its test, and the IDEAS.md entry that tracked it. Scenario-marked
      `milestone-level` stays the only path (`dnd5e/advance.py`, covered by `test_advancement.py`).
- [x] Fixtures regenerated: `schemas/{story,dnd5e}/turn_plan.json`, `instructions/dnd5e/director.txt`,
      `turn/dnd5e.json`. Diff reviewed: the union moved inline under `action` (same members, same
      discriminator), title `Dnd5ePlan`/`StoryPlan` → `TurnPlan`, milestone gone. Saves and states
      did not move, so no `SAVE_VERSION` bump.
- [x] `uv run pytest` (122 passed) / `ruff check` / `ruff format --check` / `basedpyright` green.

**LOC:** `src/aidm` **−43** (budget −50) after the adversarial review pass, tests −16. The first
cut landed at +17; the review clawed back 59: the three action callable aliases and
`Offered`/`DeltaCheck` inlined, `Advancement` deleted (back to two plugin fields),
`labels` accepts a plain `frozenset` so the four constant lambdas died, a `Resolved` alias
collapsed seven 3-line resolver headers to one line, `engine` dropped from the unused check
signature, and every `del`-of-unused-parameter line deleted (neither ruff's rule set nor
basedpyright strict flags them). The remaining −8 to budget is the registry's floor: `_plan_model`
+ `_action` + `_spec` + `ActionSpec` cost ~32 lines HEAD never paid.

The review also fixed one defect: `_action`'s `raise ValueError` sat outside `check_plan`'s try,
the one exception path that could kill a turn instead of retrying; it is an unreachable
invariant on a validated plan and is now an assert.

### Deviations from REFACTOR.md, deliberate

- `resolve` takes `(engine, draft, action, rng)`, **not** the plan. The doc keeps the plan for
  "branch inspection", but the only resolver that read it was the milestone path this phase
  deletes; `check` still takes the whole plan, which is where `_double_spend` needs it. Widening
  it back is a one-line signature change if a resolver ever needs the plan.
- `check` takes `(state, plan, action)` — no engine: no check uses it today, and widening back
  is one signature change.
- No `Advancement` bundle and no `advancement=` keyword: `offered`/`check_delta` remain the two
  plugin fields they were at HEAD. The bundle held no behavior, and its `| None` optionality had
  no engine behind it.
- Story's `check_plan` now trial-resolves like every engine (kernelized): the refusal for a
  missing actor is the same `require_actor_here` string `_refused` returned at HEAD, so the
  model-facing messages did not move.
- `EnginePlugin.actions` is typed `tuple[ActionSpec[Any], ...]`: the spec is invariant in `A`
  (`type[A]` and `Callable[..., A]` in the same dataclass), so no non-`Any` element type accepts a
  heterogeneous tuple. The `Any` stops at that field — every call the kernel makes goes through
  `Frozen`.

### Evals — done 2026-08-07, gpt-oss-120b, full suite, n=69 per run

Measured against HEAD (645d930) run the same hour from a worktree, because `baseline.md`'s last
full suite predates the two `perf(ai)` prompt commits and is not a like-for-like:

| suite | overall | conditions | rest | spells | combat | story |
| --- | --- | --- | --- | --- | --- | --- |
| HEAD 645d930 | 96% | 83% | 67% | 100% | 100% | 100% |
| phase 2, first cut | 91% | 67% | 50% | 89% | 98% | 89% |
| phase 2, shipped | **96%** | 83% | 67% | 94% | 100% | 100% |

The first cut sat 5 points under HEAD with every 5e tag dipping in the same direction. The one
gratuitous prompt-surface change was mine, not the phase's: the built model inherited
`TurnPlanBase.__doc__`, adding a schema `description` the engine subclasses never had. Dropped it
(one line, fixtures regenerated) and the suite came back to parity. Not proof it was the cause —
n=69 cannot separate 3 turns — but the only remaining director-schema delta is now structural
(the union inlined under `action`, title `TurnPlan`), and structural is what the phase owes.

`rest` was probed separately at n=16 on both trees: HEAD 62%, phase 2 44%, both consistent with
`baseline.md`'s standing 72% weakness and with each other. It is a pre-existing prompt problem
(the model resolves the prompt's first clause as an `improvise` and never sleeps), not a phase-2
regression.

The eval scripts needed no edit — they import `director_stage`/`PlanContext`, which did not move,
and no probe matched `milestone_earned`. Results in `scripts/evals/results/2026-08-07-645d930+*`.
