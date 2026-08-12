# 02 — A level-up applies none of the row's own numbers or pools

Status: needs-triage

`create._level_one_numbers` writes every int fact of the level-1 row onto the sheet, and
`create._feature_pool` grants the counter behind each pool-bearing feature. `advance` does neither:
it writes `level`, the spell counts, and whatever the proposal names.

Confirmed: a barbarian driven to 20 still holds `rage-damage-bonus: 2` where `barbarian-20` says 4,
and never gains `brutal-critical-dice`; a level-20 wizard still holds `arcane-recovery-levels: 1`;
a monk at level 5 holds counters `['hp']` only, though `monk-2` carries `ki-points: 2` as a fact —
so `UseFeature` on ki dies at `counter_of`, the exact failure phase 12's review fixed for creation.

The fix is the one ticket 03 of the creation set already made for refs: the engine reads the row and
writes what it says, rather than the model volunteering it. `LevelUp.granted` (a `PoolGrant` the
model fills) should shrink to whatever the row genuinely cannot answer, or disappear.

## Done when

Levelling any class to 20 leaves every int fact of the reached row on the sheet, every pool the
reached row's features bring is a counter at its own maximum, and no pool arrives because the model
remembered to ask for it.
