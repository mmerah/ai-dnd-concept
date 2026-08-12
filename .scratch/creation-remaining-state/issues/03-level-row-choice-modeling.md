# 03 — Level rows conflate grants with choices

Status: done (2026-08-12) — `Record.granted` beside the kept `options`/`choose` pair; the audit
found no record anywhere needing two choice groups, so 05's `choices` list was not built. Pack
re-imported from the checkout at the pinned commit; round trip byte-identical but for `levels.json`
and one line of `features.json`. See PROGRESS.md phase 12 §7.

`fighter-1` is `choose 2 of [6 fighting styles, second-wind]`: two styles and no Second Wind is
legal at creation and at advancement. Same flattening on `wizard-1` (`choose 2` of exactly its 2
mandatory features — a non-choice dressed as one).

The fix is upstream of creation: `Record` needs a mandatory-grants notion (e.g. a `granted:
tuple[ContentRef, ...]` field, or a convention like `choose` only over the genuinely optional
options), written by the SRD importer. Touches: the importer (needs the external SRD checkout;
byte-identical round-trip is the regression check), `packs.Record` + `validate_pack`,
`Dnd5eAdvancement.offered` (offers must show only real choices and auto-grant the rest),
creation's level-1 expansion, and the `advancement.md`/schema goldens if the offer shape moves.

Audit all 20 levels × 12 classes for the same pattern before designing — the right shape falls
out of the data, not from fighter-1 alone.

## Done when

A level row distinguishes what it grants from what it offers; fighter-1 creation and advancement
force Second Wind and offer one style; wizard-1 offers nothing; pack round-trip stays
byte-identical for untouched rows.
