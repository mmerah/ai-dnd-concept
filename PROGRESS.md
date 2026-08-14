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

### Phase 1 Part B — engines declare, they do not re-implement (2026-08-14)

- `SheetEngine[S: SheetBase, A: Action]` (`engines/sheet_engine.py`) owns `check_overlay`, `begin`,
  `validate`, `seed`, `parse_effect`, `apply_effect`, `apply`, `renderer`, `check_plan` and
  `resolve_action`. An engine declares `sheet_type`, `mechanics_type`, `effects`, `plan_type` and
  writes `new_sheet` + `describe`. `rules.py` is now 44–75 lines; `Engine.rules_type` is gone
  (`sheet_type` is the overlay shape) and `check_overlay` is abstract on `Engine`.
- Mechanics shapes are shared: `SheetBase` (abstract `counters`) and `SheetMechanics[S]` in
  `engines/sheets.py`; each engine's `Mechanics` subclasses it and adds only what it also tracks.
- `Action` (`engines/actions.py`) carries `outcomes` and `resolve(engine, draft, rng)`; the plan is
  `Branched[E, A]` and `plan.action.resolve` replaced every `_resolver`/`_labels` match and six of
  the seven `assert isinstance` narrowings. The seventh is loner3e's `twist_table_of`, which
  refuses an engine that cannot hand it a twist table.
- `Resolution(facts, outcome, flow)` replaced the resolvers' `(facts, outcome)` tuple and is what
  `transact` takes; `Transacted.flow` is plumbed and unread until Part C's loop. Cairn yields on
  the player's own scar/critical damage/death, 24XX on a player disaster or landed bad luck,
  loner3e never.
- `ThreadAdvancement` (`engines/advancement.py`) owns `offers`, `resolve` and `violation`; an
  engine writes `ledger` and `grant` plus four class vars.
- **Each action now lives with its own resolver**: `resolve.py` merged into `actions.py` per
  engine, because an action that resolves itself and a resolver that reads the action would
  otherwise import each other.
- **Deviations from the plan, deliberate:** `pack_type`/`creation_type`/`subsystem_types` were not
  hoisted — each engine keeps its five-line `__init__`, since abstracting it costs a fourth type
  parameter and a creation-factory protocol to save fifteen lines. `check_mechanics(state)` takes
  no mechanics argument (an override cannot narrow a parameter), and Cairn's `apply` override does
  not call `super()` — its deprivation refusal, item pools and load check leave nothing to reuse.
- **Typing:** two type parameters, no `Any`. `isinstance` against `self.plan_type` drops the type
  arguments, so `SheetEngine._typed` is the one cast in the tree; `plan_type` narrows `Engine`'s
  declaration under a scoped `reportIncompatibleVariableOverride` ignore. `SheetEngine.__init__`
  reads its three declarations once, so a missing one fails the build rather than the turn.
- **Known limit for Part C:** `flow` is decided from the action's own facts, so a death caused by
  a *branch effect* rather than by the action does not yield.
- No golden fixture moved (`turn_plan.json` byte-identical for all three engines), `SAVE_VERSION`
  unchanged at 61. 160 tests green on all four commands. Production lines 6,803 → 6,856: the
  duplication went, but Part B also added the `Resolution`/`flow` machinery Part C consumes and an
  `outcomes`/`resolve` pair on six action classes. A shared effect alias would have saved ~10 more
  and was refused: it renames the `$defs` key the Director's schema shows.

## Next

- PLAN.md Phase 1 Part C (steps 7–9): the Director's beat loop. `Transacted.flow` is already
  carried; the loop is what reads it.
- Then PLAN.md Phase 2: the scenario creator.
- Close the Cairn 2e, Loner 3e, 24XX fidelity deviations, per their docs' "Deviations in this repo" sections — Phase 1 Part C unblocks the ones that blame the one-action turn.