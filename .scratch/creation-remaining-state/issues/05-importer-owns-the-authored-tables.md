# 05 — The importer owns the tables `create.py` hand-transcribes

Status: DONE (2026-08-12) — see PROGRESS phase 12 §9. Original triage: — scope is **maximal**: delete as much authored SRD
data from `src/` as the upstream data can answer, equipment included. Two maintainer decisions:
`scripts/` may be a type-free zone if strict typing gets in the way of that (it is under
basedpyright strict today via `pyproject.toml`'s `include`; loosen it there rather than fighting it),
and no table stays in production merely because moving it is awkward — only because nothing upstream
answers it. See the measured triage below and in PROGRESS phase 12 §7.

Blocked by: nothing. 03 shipped `Record.granted` and KEPT the single `options`/`choose` pair, having
audited that no record in the pack needs two independent choice groups. Class records still have
their pair free, so this ticket does not need `Record.choices` for skills — only equipment has
several groups at once, and the recommended shape for that is a sibling collection (see "The shape
question" note appended below), not a new `Record` field.

`create.py` (591) + `equipment.py` (478) = **1,069 lines, ~390 of them SRD data typed by hand**
because the projector renders class/race/background structure into record `text` and drops the
structure. The upstream models in `scripts/srd/upstream.py` already **parse** almost every field
these tables restate — `Class.proficiency_choices`, `Class.starting_equipment`,
`Class.starting_equipment_options`, `Background.starting_proficiencies`,
`Background.language_options`, `Race.languages`, `Subrace.racial_traits`. Nothing new needs
reading from 5e-database; it needs projecting instead of prose-rendering.

Each table is verified at engine build against the pack today (`Dnd5eCreation.__init__`,
`equipment.verify`), so a typo fails loudly — but a table that agrees with the pack is still a
second copy of it, and it only covers the twelve classes and nine races the SRD ships.

## The tables, and what upstream answers each

| Authored table | Lines | Upstream field | Verdict |
|---|---|---|---|
| `_CLASS_EQUIPMENT` (equipment.py:39–319) | 281 | `Class.starting_equipment` + `starting_equipment_options` | replaceable, hardest |
| `_CLASS_SKILLS` (create.py:69–139) | 71 | `Class.proficiency_choices` (type `proficiencies`, `skill-*` options) | replaceable |
| `_SKILLS` (create.py:49–68) | 20 | the `skills` collection already in the pack | falls out with the above |
| `_RACE_LANGUAGES` (create.py:150–162) | 13 | `Race.languages` | replaceable |
| `_BACKGROUND_SKILLS` / `_BACKGROUND_LANGUAGES` | 2 | `Background.starting_proficiencies` / `language_options.choose` | replaceable |
| `_SUBRACE_TRAITS` (create.py:143) | 1 | `Subrace.racial_traits` | replaceable |
| `_feature_pool` (create.py:578) | 14 | **partial** — `rage-count`, `bardic-inspiration-die`, ki are already level-row facts; second-wind, divine-sense, lay-on-hands, arcane-recovery are prose in the feature's `desc` | see decision 3 |
| `_ITEM_BRIEFS` (equipment.py:320–369) | 50 | none — authored fiction the Narrator reads | **keeps** |
| `_UNARMORED_DEFENSE` (equipment.py:28–38) | 11 | none — prose in the feature record | keeps (or joins decision 3) |
| `_ARRAY` / `_MIGHT` / `_GRACE` / `_FOCUS_REST` | 6 | none — this project's design, not SRD | keeps |

Realistic deletion: **~390 lines** out of 1,069, against ~100–150 added to
`scripts/srd/project.py`. The point is not the net (~−250): it is that the surviving data is
either verified upstream or authored fiction, with nothing in between.

## The blocker, shared with ticket 03 — RESOLVED, and not the way this ticket guessed

03 shipped `Record.granted` and kept the single `options`/`choose` pair; the audit behind that
decision found no record in the pack needing two independent choice groups. Class, subrace and
background records each still have their pair free, so skills and languages need no new field at
all. Equipment is the only data with several groups at once, and the shape recommended for it is a
sibling collection of group records — no `Record.choices`, no `AdvancementOffer` change. See the
triage findings at the bottom of this file, which supersede the four decisions below (1: project
all three shapes, maximal scope; 2: moot, `_skill_ref` already writes the upstream shape; 3: no,
`_feature_pool` stays; 4: the checkout exists and the round trip is the scoping check).

## Sequencing

02, 03 and 04 are all DONE and staged. 05 is a data-and-projector phase with no model-facing text
change — but every record's `text` moves (prose the projector stops writing), so the pack bytes,
the content goldens, and any prompt that renders a class or race record all move with it.

## Done when

`_CLASS_EQUIPMENT`, `_CLASS_SKILLS`, `_SKILLS`, `_RACE_LANGUAGES`, `_BACKGROUND_SKILLS`,
`_BACKGROUND_LANGUAGES`, and `_SUBRACE_TRAITS` are deleted; `Dnd5eCreation.steps` builds every
skill, language, and equipment step from what the records themselves carry; the fighter and wizard round
trips assert the same sheet they assert today (AC 18 chain mail + shield, elf DEX 15 → AC 12);
and the only authored data left in the 5e package is `_ITEM_BRIEFS`, `_UNARMORED_DEFENSE`, the
ability generation constants, `_feature_pool` and `_PREPARED_*` — each with a one-line note saying
why upstream cannot answer it — plus the ~30 new `_ITEM_BRIEFS` entries full category expansion
makes reachable.

## Triage findings, 2026-08-12 (measured, not estimated)

Every upstream field below was checked against `../5e-database` at the manifest's pinned
`source_commit`, not taken from the table above, which predates tickets 01–04.

| Block | Lines | Upstream answer | Verdict |
|---|---|---|---|
| `_CLASS_EQUIPMENT` (equipment.py) | 281 | `Class.starting_equipment_options`, but `upstream.Option` parses **none** of its payload (`count`, `of`, `items`, `choice` dropped by `extra="ignore"`); category expansion also needs `5e-SRD-Equipment-Categories.json`, which `build.py` does not read | replaceable, hardest — see below |
| `_CLASS_SKILLS` + `_SKILLS` | 94 | `Class.proficiency_choices` — **byte-for-byte identical** to the table for all 12 classes | replaceable |
| `_RACE_LANGUAGES` | 13 | `Race.languages` — exact for all 9 races (`list[Label]` → `Named`) | replaceable |
| `_SUBRACE_TRAITS` | 5 | `Subrace.racial_traits` — 7 refs across 4 subraces, not 1 | replaceable, adds behaviour |
| `_BACKGROUND_SKILLS` / `_BACKGROUND_LANGUAGES` | 3 | `starting_proficiencies` / `language_options.choose`; the language list must come from the languages file, `from` is a `resource_list` URL | replaceable |
| `_ITEM_BRIEFS` | 51 | none — upstream `Equipment.desc` is **null** for leather-armor, longsword, explorers-pack | authored fiction, stays |
| `_UNARMORED_DEFENSE` | 10 | none — `feature_specific` is None for both records | stays |
| `_feature_pool` | 14 | none — `feature_specific` is None for all six; every number is `desc` prose | stays |
| `_ARRAY`/`_POINT_COST` | 6 | none — no point-buy table exists in 5e-database | stays |
| `_PREPARED_AT_LEVEL_ONE`/`_PREPARED_GROWTH` | 9 | none — the recorded deviation | stays |

486 lines of authored data. **90 must stay** (nothing upstream answers them). Decision 2 above is
moot: `create._skill_ref` already writes `proficiencies/skill-*`, the upstream shape, and nothing
computes off it — `Check.bonus` is model-supplied and `resolve.py` reads only `proficiency-bonus`.
Decision 3 is **no**: moving `_feature_pool` into the projector relocates 14 lines, deletes nothing,
and trades an engine-build check for an untested script gated on a checkout.

## What the maximal scope has to solve

Equipment is 281 of the 486 lines and the reason this ticket exists. The data: **39 groups across
12 classes** — 35 `options_array`, 4 top-level `equipment_category`; inside them 48
`counted_reference`, 8 `multiple`, 17 nested `choice`. **21 of 39 groups pick from an open
category**, and 2 nest a category choice inside a `multiple` (fighter, paladin: "a martial weapon
and a shield"). Only the rogue is fully concrete.

The triage concluded that this needs a recursive step model in `state/creation.py`, `check_picks`
and `ui/create.py`, and recommended not moving it. **Test that conclusion first — there is reason to
think it is wrong.** With a sibling collection rather than an inline field, each equipment group is
one record (`options`/`choose`) whose options are option-records, and an option-record carries
`granted` for the items it hands over and its own `options`/`choose` for a category it leaves open.
`create._chosen_records` already yields a picked record so that the generic rule — "a picked record
carrying options becomes one more step" — spawns the follow-up; that is exactly how a class reaches
its level-1 row and a subrace its trait records. If a picked option-record is yielded the same way,
nesting falls out of machinery that already ships and the framework does not move at all.

Two costs that are real either way, and are not reasons to stop:

- Full category expansion makes **75 items reachable** against `_ITEM_BRIEFS`' 46, so **~30 new
  authored briefs come back** into production. Authored fiction the Narrator reads; nothing upstream
  can supply it.
- Deleting an engine table deletes its `__init__`/`verify` check. Nothing validates that a
  `Record.options` or `granted` ref resolves — `validate_pack` checks facts only. The shipped pack
  has **0 dangling refs** today. Add the check to `packs.loaded()` (refs cross packs, so not
  `validate_pack`) **before** deleting the first table.

## One bug found in passing, no pack change

`Class.starting_equipment` — the unconditional grants — is ignored, and the bundles contradict it:
the SRD gives *every* ranger a longbow and 20 arrows and *every* cleric a shield, where the bundles
make both a choice. ~12 lines in `equipment.py`. Watch `equipment.verify`'s "two armours in one
bundle" rule when folding the paladin's chain mail in.
