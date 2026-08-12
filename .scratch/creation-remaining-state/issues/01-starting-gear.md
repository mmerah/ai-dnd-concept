# 01 — Starting gear at creation

Status: done 2026-08-12 (see PROGRESS.md phase 12 §7)

A created character starts with `items: ()`. Kael shows the target shape: an `Entity` in
`profile.items` (id, name, brief, `known: true`, `parent_id: "player"`, optional traits) plus an
overlay entry reffing the gear/weapon/armor record.

## Scope to decide at triage

1. **Options source.** Class equipment prose lists alternatives; transcribe per class (the
   `_CLASS_SKILLS` pattern) or offer a curated flat list per class (smaller, less faithful)?
2. **Entity authoring.** Item id from the record index; name from the record; brief — from
   record text (truncated?) or a fixed template. Decide before building: this is player-visible
   fiction, not mechanics.
3. **Armor class.** `create()` derives `armor-class = 10 + DEX mod`. Armor records carry AC
   facts; wearing chain mail must win over the derivation, shields add. Either creation computes
   final AC from the picked armor (one more authored rule) or AC derivation moves somewhere that
   understands armor. Keep the rule in creation until play needs armor swapping.
4. Weapons already work through refs alone (see `armed()` in `fivee_test_support.py`) — the
   entity + one weapons ref is enough for `Attack`.

## Done when

A created fighter starts with its chosen armor and weapons as carried, known items; the AC the
sheet shows matches the armor worn; the round-trip test asserts one armored and one unarmored
pick set.
