# Progress — drastic simplification (PLAN.md)

Baseline 2026-08-28: 10108 src lines, 290 tests pass, eval baseline evals/results/breathless-v5.json (96/99).
Working on master, no commits (maintainer: stage only).
Eval gate runs with `--concurrency 16` (default 4 is slow).

## Phase 1 — rules on the entity
- [x] done + extra cuts (Game.mechanics deleted, Advancement ABC collapsed, 24XX _check_skills gone,
  check_sheet folded into rules(), describe overrides folded). 10108 → 9960 src lines, 288 tests.
- [x] eval: evals/results/phase1-baseline.json = 96% (3 repeats), new baseline. Prompt/schema goldens unchanged.
- [x] PLAN.md re-measured: phases 1–6 ≈ −780 lines, steps 3.3 and 5.2 dropped.
- [x] 2026-08-28 audit folded in, then trimmed by gameplay: phases 2–6 ≈ −700, Phase 7 ≈ −265;
  refused: 7.1, 7.2, 7.7–7.9, card-as-string, per-scenario pack choice, 5.4, options-only stake.
- [x] Phase 1 follow-up: Loner refuses an actor with empty rules again; _sheeted is items-only; doc restored.
## Phase 2 — card helpers only
- [x] done: explained_fact folded; traced/told_traces are the two join helpers; NOTHING is the one constant;
  chapters/jobs/milestones are ints. Golden diff: breathless save `chapters: 0` only. 288 tests pass.
## Phase 3 — flat tool ladder, engine as value
- [ ] 3.7 + 3.12 skipped: `claude.py:41` — the SDK bridge drops `tools/list_changed`, so authoring tools
  listed only while a run is open would never reach the Claude driver after `begin_growth`. Needs a
  maintainer decision.
- [x] 3.1 3.2 3.4 3.9 3.10 3.11 done: allows_text on PendingDecision (defence/loot options-only), settle_defence
  deleted, one `director_tool` constructor, engines spread CORE_TOOLS, Turn.call owns the gate,
  creation never rolls, TurnResult tuple, PackEntry→CreationOption. 9949 → 9819 lines. Goldens regenerated.
- [x] 3.5 3.6 done: Engine is a frozen dataclass, each engine ends in `build(sources)`, registry maps folder
  name → build (engine_class gone); CreatedCharacter merged into Character. 9819 → 9813 lines (shape, not size).
  Behaviour change to confirm: create page no longer suffixes a duplicate name (fen-2); it now refuses
  "character already exists". 285 tests pass (2 ABC-only tests deleted).
- [x] 3.8 eval gate: evals/results/phase3.json = 97% vs phase1-baseline 96%, errors 0, calls 1.28. New baseline.
  (seconds 16→28 is concurrency 16 queueing at the provider, not code.)
- [x] review pass: `check_rules` folded into `Engine.validate` (engines pass `checks`, no per-engine
  closure over packs), `_resume` and `Turn._applied` share one `_apply`, registry `cast`/`_builder`
  and the `CHOOSE_ABOVE` constant inlined. 9813 → 9783 lines, 285 tests pass.
- Phase 3 total: 9949 → 9783 src lines (−166 vs −145 estimated, 3.7/3.12 skipped). Staged, not committed.
## Phase 4 — one pack list per scenario
## Phase 5 — fewer Director fields (eval per item)
## Phase 6 — dict-keyed world, creation via decision panel
## Phase 7 — needs maintainer say, not started
