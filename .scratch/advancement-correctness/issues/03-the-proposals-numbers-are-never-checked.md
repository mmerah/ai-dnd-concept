# 03 — Every number a level-up writes is taken from the model unchecked

Status: needs-triage

`violation` checks picks against the offer, spell counts against the pools, and abilities against
the cap of 20. It never compares `hit_points`, `proficiency_bonus`, `slots` or `abilities` to the
level row, which carries `hit-die`, `proficiency-bonus`, `ability-score-bonuses` and every `slot-N`.

Confirmed at fighter 4: `hit_points=99`, `proficiency_bonus=17` and STR raised to 20 all pass
`violation` and commit. Conversely a proposal that names *no* abilities at an ability-score-improvement
level is also accepted, so the improvement is silently skipped.

This is the rule in CLAUDE.md — "every roll and every ledger change happens in resolver code, never
in model output" — and creation already honours it: it derives hp, AC and every number from content.
Advancement should either check each field against the row or derive it and drop the field from the
proposal type. Dropping is the smaller surface: `hit_points` is the class hit die's average plus the
CON modifier, and the row already names the proficiency bonus and the slots.

Note the interaction with 02: if the engine writes the row's numbers, most of these fields have
nothing left to say. Settle 02's shape first.

## Done when

No number a level-up writes can disagree with the level row; an ability score improvement is either
made or refused, never skipped; and the proposal type carries only what the row cannot answer.
