# 04 — An offer lists options the character already holds

Status: needs-triage

`offered` passes `record.options` through untouched. `_spell_pools` already filters a spell that is
on the sheet, precisely so a stale pick meets the offer's own refusal instead of the opaque one
`add_ref` raises deeper in; the feature options never got the same treatment.

Confirmed: a sorcerer at level 10 is offered all eight metamagic options including the two taken at
level 3, and picking one is refused as
`"Hero already holds content srd-2014/features/metamagic-careful-spell"`. Recoverable — six fresh
options remain — but the offer is wrong and the reason is unreadable.

One line, beside the `_spell_pools` filter it should mirror.

## Done when

An offer lists only what the character can still take, and the level-10 and level-17 metamagic
offers shrink by what level 3 took.
