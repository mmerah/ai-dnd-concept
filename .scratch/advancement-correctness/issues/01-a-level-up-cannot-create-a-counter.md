# 01 — A level-up cannot create a counter, so no caster plays past level 2

Status: needs-triage

`_raise_pool` (`advance.py`) reads `counter_of(sheet, player, key)`, which raises when the sheet
holds no such counter. Creation grants `slot-1` at level 1 and nothing else, so the first level that
adds a new slot level refuses the only correct proposal:

```
created wizard, counters: arcane-recovery, hp, slot-1
level 3, slots={'slot-1': 4, 'slot-2': 2} -> "Nym has no counter 'slot-2'.
                                              Their counters are: arcane-recovery, hp, slot-1"
level 3, omitting the slot                -> None   (accepted)
   -> counters: arcane-recovery 1/1, hp 16/16, slot-1 3/3
```

The accepted proposal is the wrong one: the caster can never cast above 1st level, and slot-1 does
not grow either. Paladin and ranger hit this at level 2; bard, cleric, druid, sorcerer, warlock and
wizard at level 3. `advancement.md` tells the model to name the new maximum, so the instruction and
the engine disagree.

**The warlock rides on this.** Pact slots migrate key rather than accumulate: `warlock-1/2` carry
`slot-1`, `warlock-3` carries `slot-2` only, `warlock-5` `slot-3`. Granting a missing counter
without also dropping the keys the row no longer names would leave a level-5 warlock with
slot-1 + slot-2 + slot-3 and six casts per short rest instead of two.

## Done when

A created caster of every class reaches level 20 with exactly the slot counters its level-20 row
names, at the row's maxima; the warlock holds one pact slot key at every level; and the recharge of
a newly granted slot follows the class the way `create._slot_counters` already decides it
(short rest for the warlock, long for everyone else).
