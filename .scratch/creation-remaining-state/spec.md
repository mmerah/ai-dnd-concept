# Creation: the remaining character state

Phase 12 shipped in-app creation; its adversarial review closed the state gaps that were pure
transcription (skills, feature pools, racial bonuses, background languages). Three items remain
deferred because each one's cost lives outside `engines/dnd5e/create.py`, in a system the change
would reshape. This spec records what was traced so the tickets don't re-derive it.

## Why these are not more creation tables

- **Starting gear** is not a ref on a sheet: an owned item is a world `Entity` (id, name, brief,
  `parent_id: player`) authored in `profile.items` plus an overlay ref — see kael's lantern.
  Class equipment is prose with alternatives ("(a) chain mail or (b) leather armor, longbow…"),
  and armor invalidates the current derivation `armor-class = 10 + DEX mod` in `create()`.
  Equipment therefore needs: prose→options transcription per class, an Entity-authoring step
  (name/brief for each granted item), and an AC rule that reads armor records.
- **Spell choice** has no state to fill: `resolve_cast_spell` reads the class ref's
  `spellcasting` fact and `slot-N` counters only. A known-spells list would be *new* casting
  mechanics (state + resolver check + advancement growth), not a creation feature. PLAN.md's
  phase 12 wording — "a caster's castable list arrives with the class ref in the current content
  model" — is the standing design; change it deliberately or not at all.
- **`fighter-1` models "one fighting style + Second Wind" as `choose 2 of 7`**, so two styles and
  no Second Wind is a legal pick. `Record` has only `options`/`choose` — no mandatory-grants
  list — so the fix is in the SRD importer and the vendored pack's shape, and every consumer of
  level rows (`Dnd5eAdvancement.offered`, creation's level-1 expansion) reads the new shape.
  The importer needs the external SRD checkout (see memory/repo notes); pack round-trip bytes
  are the regression check.

## Order

Gear is the only one a player feels every session (weaponless Attack works but reads oddly for
a fighter). The pack-modeling fix unblocks nothing else and can ride any future importer pass.
Spell choice should wait for a casting-mechanics decision.
