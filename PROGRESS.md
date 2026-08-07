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

## Phase 2 — Action registry, one TurnPlan — not started
