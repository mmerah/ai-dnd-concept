# 04 — Ability scores: the three real generation methods

Status: needs-triage

Play-test observation (maintainer, 2026-08-12): the ability step should be the three actual
rules — roll (4d6 drop lowest), point buy (27 points), or standard-array assignment — not the
three authored spreads that shipped as phase 12's stopgap.

## Why this is a framework change, not a table

`CreationStep` is deliberately pick-from-options (PLAN.md phase 12 names this the phase's
ceiling), and `create(name, brief, picks)` is pure. Each method breaks that differently:

- **Roll** needs an RNG at creation time plus accept/reroll semantics — a rolled result is not a
  pick, and a pure `create()` cannot roll it. Either the UI rolls and the result is transported
  as picks (six value-assignment picks whose legality `create` re-checks against "some legal
  4d6-drop-lowest outcome" — weak), or the framework grows a rolled-step type with a seed.
- **Point buy (27)** needs a numeric-allocation step type and a UI widget (six bounded number
  inputs with a live budget), plus a validator (8–15 before racial bonuses, cost ladder).
- **Free standard-array assignment** fits pick-from-options only as a chain of five dynamic
  steps ("which ability takes 15?" → options shrink each pick, last ability inferred). Honest
  but clunky; it is the one method buildable without new step types, and could ship first.

## Sketch to triage

One `ability-method` step (choose 1 of the three), then method-specific follow-up steps; the
allocation/rolled step types join `state/creation.py` only when a second engine or the point-buy
widget proves the shape. Racial-bonus application and the AC/hp derivation order in `create()`
are already method-agnostic (bonuses land on whatever `numbers` holds) and must stay the tested
invariant.

## Done when

All three methods produce a legal level-1 character through the same
`create → write → load → begin_game` round trip, the authored spreads are deleted, and an
illegal point-buy or tampered roll is refused with a readable reason.
