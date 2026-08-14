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

## Phase 2 — Cairn 2e (2026-08-14)

The third engine, and the acceptance test for the Phase 1 contracts: it landed entirely in
`src/aidm/engines/cairn2e/**` plus its two content overlays, with no `if engine == "cairn2e"`
anywhere. Its file set is identical to the other two engines'. docs/CAIRN-2E.md now carries the
deviations list and the package map.

- `state/dice.py` grew `roll_sum` beside `roll_pool` (Cairn totals 3d6 and its scar recoveries).
  One shared private body, so `roll_pool`'s fact is byte-identical and no fixture moved.
- Two plan actions: `save` (d20 roll-under, 1 always passes and 20 always fails) and `attack`
  (auto-hit, weapon die less armor). Labels are per action — Cairn is the first engine whose
  outcome set depends on which action was chosen, so `_labels(plan)` is a method, not a constant.
- The damage pipeline is armor, then HP, then overflow into strength, then the critical-damage
  strength save, then the twelve-row Scars table when a blow takes the player to exactly 0 HP.
- Creation: pack → background → the background's quirk table → a pre-rolled attribute spread.
  `Creation.create` takes no rng, so the 3d6 dice moved into the pack as published spreads; `seed`
  does roll, giving every newcomer Cairn's hireling recipe (3d6 per attribute, 1d6 HP).
- Advancement is `id = "advancement"` like the other two, and a growth writes a core `Trait`.

Facts worth keeping:

- **The engine-owned overlay carried items without any core change.** `check_overlay` is
  overridden with a `Sheet | ItemRules` union; both forbid extra keys, so the payload's own keys
  decide which it is. An item with no authored payload is one ordinary slot. Phase 1 step 3 paid
  off exactly as designed.
- **No pending-player-choice was needed after all.** Encumbrance refuses an over-ten-slot load
  inside the engine's `apply`, which the Director's plan check already runs on a trial draft — so
  "drop something first" comes back as a retry message rather than a turn that stops to ask. The
  same seam refuses recovery while `deprived`, which is a core trait the engine reads rather than
  new state.
- Nothing else on the deliberately-not-pre-built list was needed either: no planner seam, no
  `PartyState`, no multi-pack manifests, no `fire_count`. Combat needed no state machine — a Cairn
  round is one attack.
- `SAVE_VERSION` did not move: nothing persisted changed shape, and the regeneration diff held
  only new `cairn2e` fixture files.

## Next

- PLAN.md Phase 3: the scenario creator. Its full-resolution write-up is already in PLAN.md.
- Then close the Loner 3e and 24XX fidelity deviations, per their docs' "Deviations in this repo"
  sections. Cairn forced nothing new into core, so nothing there is waiting on it.