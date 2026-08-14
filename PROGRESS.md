# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 Part A — one live mechanics per transaction (2026-08-14)

- `GameState` caches the parsed mechanics in `_live_mechanics` (a `PrivateAttr`, so no persisted
  byte moved and `SAVE_VERSION` stayed at 61): `mechanics_as(Model)` parses once and returns the
  same instance for the rest of the transaction, `set_mechanics` installs a freshly built one.
- `committed()` flushes (dump + revalidate, the gate `write_mechanics` used to be, now once per
  transaction rather than ~10 times per turn); `draft()` clears the copy's cache so a draft always
  re-parses from the last committed JSON.
- `read_mechanics`/`write_mechanics` deleted from `engines/counters.py`; all 62 src and 53 test
  call sites rewritten. Every write-back line vanished; the three `begin` builders use
  `set_mechanics`.
- **Trap for later phases:** Pydantic's `__eq__` compares private attributes, so a state whose
  cache has been primed never equals a freshly parsed one. Two tests comparing a save to a live
  state now compare dumps instead. Overriding `__eq__` was tried and reverted: ignoring the cache
  would make a dirty draft compare *equal* to its pristine origin.
- Three cases in `tests/core/test_integrity_boundaries.py`: two reads in one draft share one
  object; a mutation with no write-back survives the commit; a mutation against a *committed* state
  reaches no save and no draft.
- No golden fixture moved. 158 tests green on all four commands.

## Next

- PLAN.md Phase 1 Part B (steps 3–6): `SheetEngine` base class, the action registry,
  `ThreadAdvancement`. Then Part C, the Director's loop.
- Then PLAN.md Phase 2: the scenario creator.
- Close the Cairn 2e, Loner 3e, 24XX fidelity deviations, per their docs' "Deviations in this repo" sections — Phase 1 Part C unblocks the ones that blame the one-action turn.