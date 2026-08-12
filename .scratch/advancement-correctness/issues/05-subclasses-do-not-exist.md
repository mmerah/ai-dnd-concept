# 05 — Subclasses do not exist in the game

Status: needs-triage

`level_ref` addresses `<class>-<level>` only, and nothing in `src/` ever reads the `subclasses`
collection. So 12 subclass records and 50 of the pack's 290 level rows — `champion-3`, `life-1`,
`draconic-1`, `hunter-3`, every subclass row — are unreachable, and a character never receives a
subclass feature at any level.

The pack does not hide this: `fighter-3` simply *grants* the feature record `martial-archetype`,
whose text says "choose an archetype". The choice has nowhere to land.

**It is a creation gap too.** Cleric, sorcerer and warlock choose at level 1, so a created cleric
holds `divine-domain` and no domain, a sorcerer no origin, a warlock no patron — and the domain
spell rows (`life-1`'s `domain-spells-1`) never reach the sheet.

Design notes before implementing:

- The subclass record carries `class` as a fact, the way `subraces` carry `race` — creation already
  groups on exactly that shape (`create.py`'s `_subraces`).
- A character with a subclass needs a second level ref (`<subclass>-<level>`), and `offered` has to
  merge the two rows: the class row's own grants and choices plus the subclass row's. Both are
  `Record`s of the same collection, so this may be a merge rather than a new shape.
- Creation's `_chosen_records` already yields a picked record's level-1 sibling; a picked subclass
  would yield its own.

## Done when

A class that chooses its subclass at level 1 offers the choice at creation and lands the subclass
row's grants; a class that chooses later is offered it at that level; and levelling to 20 with a
subclass leaves both rows' features, numbers and pools on the sheet.
