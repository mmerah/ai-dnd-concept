# Progress — drastic simplification (PLAN.md)

Baseline 2026-08-28: 10108 src lines, 290 tests pass, eval baseline evals/results/breathless-v5.json (96/99).
Working on master, no commits (maintainer: stage only).

## Phase 1 — rules on the entity
- [x] done + extra cuts (Game.mechanics deleted, Advancement ABC collapsed, 24XX _check_skills gone,
  check_sheet folded into rules(), describe overrides folded). 10108 → 9960 src lines, 288 tests.
- [x] eval: evals/results/phase1-baseline.json = 96% (3 repeats), new baseline. Prompt/schema goldens unchanged.
- [x] PLAN.md re-measured: phases 1–6 ≈ −780 lines, steps 3.3 and 5.2 dropped.
- [x] 2026-08-28 audit folded in, then trimmed by gameplay: phases 2–6 ≈ −700, Phase 7 ≈ −265;
  refused: 7.1, 7.2, 7.7–7.9, card-as-string, per-scenario pack choice, 5.4, options-only stake.
- [x] Phase 1 follow-up: Loner refuses an actor with empty rules again; _sheeted is items-only; doc restored.
## Phase 2 — card helpers only
## Phase 3 — flat tool ladder, engine as value
## Phase 4 — one pack list per scenario
## Phase 5 — fewer Director fields (eval per item)
## Phase 6 — dict-keyed world, creation via decision panel
## Phase 7 — needs maintainer say, not started
