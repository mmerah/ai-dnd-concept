# PROGRESS

Tracks `PLAN.md`. One section per phase; closed phases are recorded in git history, not here.

## Phase 2.9 — simplification pass — in progress (Step 1 done)

`SIMPLIFICATION_PLAN.md`, six steps, decided 2026-08-27 with every candidate verified against the
code. Ships: launch loses `engine`, `SavedGame` folded into `Game`, `pack_type` required, Advisor
role deleted, one turn lifecycle, MCP wrapper types, note-only thread bug, authored JSON without
defaults, two file moves, housekeeping. Scratched with numbers recorded there: entity split by
kind, typed authoring tools, one tool type, stateful MCP surface, engine-as-composition.

### Step 1 — bug, docs, housekeeping — DONE

- `src/aidm/state/model.py`: `AdvanceThread._moves_something` accepts a note-only patch (added
  `and self.note is None` to the guard, reworded the error to name "its note").
- `tests/core/test_actions.py`: added a note-only `AdvanceThread` round-trip test;
  `tests/core/test_pipeline.py` updated the one assertion that matched the old error text.
- `evals/turn_eval.py`: one-line header noting the 1000-line file cap is waived for this eval
  script.
- `README.md` and `docs/MEMORY-SYSTEM.md`: qualified the Narrator's "no unrevealed canon" claim as
  builtin-mode only — code mode holds it by prompt, not by type.
- `docs/ROADMAP.md`: dropped the stale "UI growth" bullet (character sheet, journal and
  known-world panel all ship in `ui/panels.py`); the Trace/State weaknesses now say they are
  expansions inside the `dev` tab, matching `ui/game.py`.
- `PROGRESS.md`: deleted the DONE phase sections (Phase 0, Phase 1, Phase 2, Single-engine
  scenarios, Phase 2.5, Tightening round); git history is the record.
- `src/aidm/harness/codemode.py`: reworded the `Harness` docstring off "composition root" (that's
  `Runtime`, `app/runtime.py:338`) to what it is: one game, one lock, one turn in flight.
- Verified: 277 passing, `ruff check`, `ruff format --check`, `basedpyright` clean.

## Phase 3 — L6 Cairn Barebones — not started (after Phase 2.9)
## Phase 4 — L5 Fate Condensed — not started
