# Progress — structured-plan redesign (PLAN.md)

## Phase 0 — harness prep — DONE

- `scripts/evals/run.py`: `RunRecord.duration_s` (default 0.0, ge 0.0), timed with
  `time.perf_counter()` around the `_turn` call in `run_case`; timed on the error path too.
- `CaseRecord.mean_duration_s` and `SuiteRecord.mean_duration_s`, both from one `_mean_duration`
  helper over all runs (failed runs included).
- `summarise` prints `mean duration/turn: <x>s` under the interpretation line.
- Gate green: pytest 89 passed, ruff check, ruff format --check, basedpyright 0 errors.
- Staged, not committed. Suggested message: `feat(evals): time each run`.

## Phase 1 — baseline — NOT STARTED

Needs `OPENROUTER` credentials and ~1–2 h wall clock: run
`uv run python scripts/evals/run.py` twice, then write `baseline.md`.

## Phases 2–7 — NOT STARTED
