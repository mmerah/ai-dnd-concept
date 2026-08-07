# Progress

## Shipped

- **Kernel phase 1 — Worldkeeper + generic steps and trace** (645d930). One worldkeeper
  role replaces maintainer+creator (1 model call, screening in code); `Turn` persists
  generic `StepTrace`s; the trace panel and `run_turn` know no role names; a role is an
  inserted `(name, StepFn)` pair from `default_workflow`. `SAVE_VERSION` 39. Config note:
  role settings key is `worldkeeper`; `ROLES__MAINTAINER__*` / `ROLES__CREATOR__*` env
  entries silently stopped applying.
- **Kernel phase 2 — Action registry, one TurnPlan** (633e107, built after VISION.md was
  written and consistent with it). Engines register `ActionSpec`s (model + labels +
  resolve + optional check); the loader builds the Director's plan model per engine;
  `check_plan` is kernelized (trial resolve, `Random(0)`, refusals as strings); no plan
  subclasses, no isinstance downcasts; `milestone_earned` deleted. Evals at parity with
  pre-phase HEAD: 96% overall, measured same-hour from a worktree (n=69,
  `scripts/evals/results/2026-08-07-645d930+*`). Standing weakness: `rest` ~60-70%
  (prompt problem, pre-existing).

- **Vision phase 0 — Eval debt, harness half** (2026-08-07). `EvalCase` gained a `role`
  dimension (`director` | `advisor` | `worldkeeper`) and `run.py` dispatches to one turn
  function per role; `--only <role>` selects a suite. Advisor runs `render_proposal` +
  the `advisor` stage (whose output validator *is* `Engine.violation`, so a proposal that
  lands is legal by construction); worldkeeper runs the pipeline's own `worldkeeper_step`
  against an authored `narration`, so admission code is what is measured. New probes:
  setup `set_note`; checks `number_value`, `has_ref`, `note_value`, `rolled_with_mode`,
  `created`. 7 new cases (23 → 30): 2 advisor, 2 worldkeeper, and the three owed director
  cases (`advantage-attack`, `concentration-replaced`, `story-check-both-directions`).
  `concentration-replaced` needed a concentration spell, so eval-only `elowen` gained
  `hideous-laughter`.
- **Vision phase 1 — One change language** (2026-08-07). `DeltaChange` is deleted; one
  `Effect` union in `state/effects.py` (12 ops), published per surface as `TurnEffect`
  (10, the Director's) and `SheetEffect` (8, the advisor's) — a model is never shown an op
  its surface always refuses. New ops `grant-counter` and `add-ref`; `change-counter`
  folded into `adjust-counter` as an optional advancing-only `maximum`;
  `adjust-counter.reason` became the `why: str = ""` every sheet write now carries, and
  `entity_id` too. `apply_effect(..., advancing=)` is the one context switch: advancing
  refuses non-sheet ops and any entity but `player`, and grows the sheet; a turn refuses
  `grant-counter`, `add-ref`, and a raised `maximum`. `apply_delta` died into
  `Engine.advance`; `EnginePlugin.check_delta` now judges the resulting `Sheet` the kernel
  already applied, instead of re-applying the delta itself. `Engine.violation` requires a
  non-empty `why` per change, keeping the confirmation panel's per-change reasons.
  `SAVE_VERSION` 40. Regenerated: both `turn_plan.json`, `sheet_delta.json`,
  `instructions/*`, `save/*`, `state/*`, `turn/*`.

**Phase 0+1 baseline, measured** (`results/2026-08-07-0d6deec+61ccea8{,-2}.json`, gpt-oss-120b,
2 suites × 30 cases × 3 runs): overall 90% / 89%.

- **Gate: passed.** The 23 pre-phase cases score **133/138 = 96%**, exactly the parity figure
  phase 2 of the kernel plan recorded. Phase 1 regressed nothing; every 0% case is new.
- The advisor and worldkeeper dimensions both work end to end: `advisor-story-growth`,
  `advisor-5e-level-up`, `concentration-replaced` and `worldkeeper-creates-nothing` are all
  100%. The advisor's grown `NativeOutput(SheetDelta)` therefore *is* now probed live on
  gpt-oss at 6/6 — that phase-0 debt is closed, and the IDEAS.md entry with it.
- `worldkeeper-creates-npc` was 0/6 against a mis-authored check, not a model fault: its
  narration named a crypt that is not in canon, so the worldkeeper correctly created two
  entities where the check demanded one. Narration now points at the authored bell tower,
  and the case is **6/6** (`results/2026-08-07-0d6deec+634d471{,-2}.json`).
- The remaining weaknesses are recorded in REFACTOR.md under "Eval findings owed a cleanup
  pass" — advantage never fires, discipline sits at 67%, and `condition-lifted` is flaky.
  None blocks phase 2.

## Current

Next: REFACTOR.md phase 2 (relations).

- Phase-1 line delta: `src/aidm` +11 (budget said −100). The budget was wrong, not the
  work: REFACTOR.md's own bail-out note prices the true duplication at ~60 lines, and the
  merge paid that back while adding two ops, the surface gate, and the shared fact helper.
