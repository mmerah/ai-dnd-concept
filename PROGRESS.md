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
- [x] 4.1–4.9 done: core.load_packs (broken file raises), build(user_packs) per engine, registry.build_engines,
  Game.packs (validate checks it once), SheetBase = chapters only, Engine.describe(state, entity),
  scenario-shipped packs/write_pack/brief select/worked_example/engine_ids/as_engine_id deleted,
  Runtime.engines built once, Harness.blank_authoring lists authoring tools. Data: packs left every rules.
  Golden diff: top-level packs on state/save, packs gone from rules. 9786 → 9547 src lines, 280 tests.
- [x] eval gate: covered by the phase5 run below (Phase 4 changed no Director prompt).
## Phase 5 — fewer Director fields (eval per item)
- [x] 5.1 name[id] labels + director.md sentence; 5.2 Thread.clock/AdvanceThread.tick gone; 5.3 Entity.detail
  flattened to description/when_reached (23 entities hand-edited, entity_detail.json schema golden gone);
  5.5 ThreadSummary/thread_summaries/_thread_line deleted, panels+journal read Thread; 5.6 Thread.stage gone,
  nine when_reached leads rewritten to "advance ... with a note that ...". 9547 → 9467 src lines, 278 tests.
  Golden diff (18 files) all explained: id syntax, detail flattening, clock/stage/tick leaving.
- [x] eval gate: evals/results/phase5.json = 98% vs phase3 97%, errors 0, calls 1.28, 15.0s. New baseline.
  Per-case moves are all ±11% single-repeat swings (swing-the-fire-axe 44→67); no case dropped by a step.
- [x] review pass (phases 4+5): whole_text tests restored as tests/core/test_documents.py (deleted with
  test_sources.py, but the parser stayed), Game.packs min_length dropped as the srd check covers it,
  _authoring_tools and the test-support engine() wrapper inlined, PackName→NamedPack, ui create.py
  names its engine, eval builds engines once under one name. 9467 → 9461 src lines, 281 tests.
## Phase 6 — dict-keyed world, creation via decision panel
- [x] 6.4 done: TraceEntryBase/WorldExtended/TraceEntry deleted, TurnTrace is one Frozen, growth logs a line,
  trace_panel shows turns only. Golden turn fixtures drift on field order only (regen at phase end).
- [x] 6.2 done: one CreationStep (options empty = written answer), Picks = Mapping[Slug, str], numbered_steps
  turns choose-N into N steps (later steps drop earlier picks), CreationOption→DecisionOption, decision_widget shared
  by game.py and create.py, eight create.py widget helpers deleted. Net −168. Succession "new character" not built.
- [x] 6.1 done: WorldState.entities/threads and ScenarioDraft.entities/threads are dicts keyed by id (validator
  checks key == id), _index/_upsert/_drop and the by_id rebuilds gone, three world.json hand-migrated (47/47 lines).
  CharacterProfile.items stays a tuple: nothing reads items by id.
- [x] 6.3 done: BaseScene folded into the two scenes, one `placement(scene, entity)`; VisibleScene.canon holds
  revealed entities only, so the narrator names nothing unrevealed by construction.
- [x] verification: ruff/format/basedpyright clean, 282 tests pass, goldens regenerated (diff = `[`→`{` keyed by id
  + TurnTrace field order only). Prompt goldens unchanged → no eval run. 9461 → 9199 src lines (−262 vs −275 est.).
- [x] adversarial review (opus) fixed: worked example + scenario_so_far now render the `write` patch shape
  (ScenarioDraft.as_patch; prompt line changed, no authoring eval exists); Breathless rated skills distinct by
  construction (check in create gone); option detail shown inline on the character page (detail_shown flag);
  click an answered row to rewind (Undo button + dead stale-pick loop gone); 100-char cap back in check_picks;
  taken→distinct_from; scene canon is a Mapping. Content `_read` refuses duplicate JSON keys
  (object_pairs_hook), so a doubled id in world.json screams. 283 tests, ~9215 src lines.
- [x] eval gate: evals/results/phase6.json = 98% vs phase5 98%, errors 0, calls 1.28 (seconds 15→20 is provider
  queueing). New baseline. Only per-case drop: swing-the-fire-axe 67→22; re-run at 18 repeats on the same backend: HEAD 17%, Phase 6
  28% — backend lottery, not code (prompt + tool schemas byte-identical).
- Phase 6 total staged, not committed. PLAN.md kept: Phase 7.3–7.5 are decided and still open.
## Phase 8 — close the eval gaps (added 2026-08-29), not started
- Baseline gaps at 9 repeats: swing-the-fire-axe (axe-rolled 2/9, axe-in-hand 6/9), mend-the-floodlight
  (think-rolled 6/9), no-improvised-brick (shoot-rolled 8/9). All Breathless.
## Phase 7 — needs maintainer say, not started
