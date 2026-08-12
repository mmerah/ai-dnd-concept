# 02 — Spell and cantrip choice (casting model change)

Status: done 2026-08-12 (see PROGRESS.md phase 12 §7)

Decision taken 2026-08-12: the known list ships end to end; prepared casters are one
seeded list, which trades away long-rest re-preparation.

Play-test observation (maintainer, 2026-08-12): "Choosing spells/cantrips is missing
completely." Confirmed as the intended gap this ticket owns — cantrips included: a created
wizard has `cantrips-known: 3` as a number but no step chooses which three, because no state
holds them and no resolver reads them. High-elf's "High Elf Cantrip" subrace trait is the same
gap and joins this ticket, not creation.

Today any spell of the class is castable: `resolve_cast_spell` checks the class ref's
`spellcasting` fact and spends `slot-N`. `cantrips-known`/`spells-known` already land as sheet
numbers but nothing reads them. A known-spells list means: new engine state (refs or a note),
a resolver check with a model-facing refusal, advancement growing the list at level-up, and a
creation step to seed it (options from the `spells` collection filtered by class + level — the
pack has the data; check whether spell records carry a class fact before assuming).

Do not build the creation step first: seeding state nothing reads reopens exactly the gap class
skills had before the phase-12 review.

## Done when

Either the maintainer records "any class spell is castable" as the permanent design in PLAN.md's
considered-and-decided list (then this closes wontfix), or the casting change ships end to end
and creation seeds it in the same phase.
