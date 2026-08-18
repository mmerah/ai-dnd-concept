# Plan

The phased plan for what is built next, in order. Phases 1-6 have all shipped and moved to
PROGRESS.md: the scenario creator, progressive world expansion, the source system (PDF ingestion,
grounded expansion, fused authoring), scene illustrations, the player-facing UI, and the authoring
page. Nothing is planned next; what stands is the working rules a future phase inherits and the
deferred items below. Each phase carries enough detail to implement without prior context; only
the next unshipped phase needs full resolution. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted. `tests/core/test_golden_state.py` pins `FIXTURE_SAVE_VERSION` —
   bump both or the suite catches you.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Deferred, with their trigger

- Player-agency eval: when live eval gates come back (working rule 3).
- Provider/cost UX (connection checks, per-turn latency, token counts): shell polish after the
  play surface exists.
