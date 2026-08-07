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

## Current

REFACTOR.md (rewritten 2026-08-07) implements VISION.md in full. Next: its phase 0.
