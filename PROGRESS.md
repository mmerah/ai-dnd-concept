# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Phase 1 — transaction kernel and engine-contract enablers (2026-08-14)

- Step 1: `src/aidm/engines/transact.py` owns the one mutation sequence — resolve, fire hooks,
  seed created entities, engine-validate, commit. `run_turn` calls it twice (action resolution,
  worldkeeper report); `resolve_plan`, `apply_hooks`, `seed_created` are gone from
  `turn/pipeline.py`. `Transacted` splits `resolved` from `fired`, which is what keeps the
  trace's `resolve`/`hooks` split.
- Step 2: subsystem changes run through the kernel too, so hooks now react to advancement facts
  and `preview` shows the hook consequences a confirm would write. The one deliberate behavior
  addition of the phase, covered by
  `test_a_hook_matching_an_advancement_fact_fires_on_confirm`.
- Step 3: the authored-overlay check is engine-owned. `Engine.check_overlay` is concrete and
  defaults to the engine's one `rules_type`; `Binding` carries the callable, not the model. An
  engine with per-kind payloads (Cairn items) overrides it instead of core growing a branch.
- Step 4: one branched-action lifecycle. `check_branched` / `resolve_branched` live in
  `state/plan.py`; both engines' `rules.py` collapse to a private `_resolver` plus one call each.
  Fact order is unchanged — `apply_all(plan.effects)` still runs last.
- Step 5: `docs/ROADMAP.md` corrected to the real three-role roster (Director, Narrator,
  Worldkeeper) and to what is actually still weak about hooks (`once` / no `fire_count`).

Facts worth keeping:

- `engine.validate` now runs once per transaction instead of once per turn — strictly earlier,
  and cheap. A batch that leaves an invalid draft fails before the next role runs.
- Seeding inside the action batch is a no-op today: only the Worldkeeper creates actors, and both
  engines' `seed` ignores non-actor entities. It is wired so a future subsystem cannot forget it.
- No golden fixture moved and `SAVE_VERSION` did not change: nothing persisted changed shape.

## Next

- PLAN.md Phase 2: Cairn 2e, built directly on the Phase 1 contracts (docs/CAIRN-2E.md holds the
  rules extraction). It needs its full-resolution write-up in PLAN.md first.