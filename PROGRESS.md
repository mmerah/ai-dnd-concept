# Progress — structured-plan redesign (PLAN.md)

## Phase 0 — harness prep — DONE

- `scripts/evals/run.py`: `RunRecord.duration_s` (default 0.0, ge 0.0), timed with
  `time.perf_counter()` around the `_turn` call in `run_case`; timed on the error path too.
- `CaseRecord.mean_duration_s` and `SuiteRecord.mean_duration_s`, both from one `_mean_duration`
  helper over all runs (failed runs included).
- `summarise` prints `mean duration/turn: <x>s` under the interpretation line.
- Gate green: pytest 89 passed, ruff check, ruff format --check, basedpyright 0 errors.
- Staged, not committed. Suggested message: `feat(evals): time each run`.

## Phase 1 — baseline — DONE

- Three suites on ba6455d (207 turns, ~5 min each, not the 1–2 h the plan guessed):
  overall 45% / 17% / 38%, pooled 33%; interpretation pooled 37%; mean 15.6s/turn.
- `baseline.md` written from all three, pooled column as the comparison number.
- Drift is the headline: 28 points overall, 38 on interpretation, up to 50 per tag, on an
  unchanged commit. Phase 6 must compare against pooled 37% over a 207-turn budget, and only
  `combat` (n=135) and `spells` (n=54) have enough turns to read per-tag.
- Run 2 anomaly: completion 99% but the director called no mutating tool at all. Provider
  routing suspected, unconfirmed — run 3 has run 1's latency and fails similarly.
- Result JSONs are gitignored (`scripts/evals/results/`), so only `baseline.md` is committed.

## Phases 2–7 — NOT STARTED

Phase 2 is next: `core/effects.py` + `core/plan.py` + `Engine` migration defaults, ~half a day.
