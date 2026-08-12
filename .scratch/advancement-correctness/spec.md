# Advancement: what a level-up must own

Creation shipped in phase 12 and closed its four deferred tickets (`.scratch/creation-remaining-state/`,
all DONE 2026-08-12). A completeness audit run straight afterwards asked the other half of the
question — can a created character be *played* to level 20 — and the answer is no. Creation survives
a full sweep: 324 combinations (12 classes × 9 races × 4 subraces × the one background × 3 ability
methods) all produce a legal character, 82 of them round-tripped through `begin_game`. Advancement
does not: two thirds of the classes stop working at level 2 or 3, and where it does work it takes
its numbers from the model instead of from the level row.

## The shape of the problem

Creation derives everything from content and writes it itself. Advancement derives almost nothing:
`advance` writes `level`, whatever `hit_points`/`proficiency_bonus`/`slots`/`abilities` the proposal
names, the row's `granted` refs (ticket 03), and the spell counts (ticket 02). Everything else the
level row carries — its own int facts, its feature pools, the slot set it moves to — is either
trusted to the model or lost.

That is the same gap phase 12's review closed for creation, one capability over, and it contradicts
this repo's own rule: the model proposes, engine code resolves and records. `advancement.md` even
instructs the model to name the new slot maximum, so the *correct* proposal is the one that gets
refused.

## Tickets

- **01 — a level-up cannot create a counter.** Blocks every caster past level 2. One function.
- **02 — the row's numbers and pools are not applied.** Per-level stats freeze at level 1.
- **03 — the proposal's numbers are never checked against the row.** `hit_points=99` commits.
- **04 — an offer repeats what the character already holds.** Opaque refusal deep in `add_ref`.
- **05 — subclasses do not exist.** 50 of 290 level rows and all 12 subclass records unreachable;
  cleric, sorcerer and warlock are supposed to choose one during *creation*, so this is a gap in
  both capabilities.

01 and 02 are the ones that make the game wrong at the table. 03 is the rule violation. 05 is the
largest and can wait, but it is the only one that also reopens creation.

## Found by the same audit, not advancement, still open

Not ticketed here — record them where they belong when they are triaged:

- A created 5e character has **no traits at all** (`create.py` passes no `traits`), where the story
  engine writes two and kael ships an edge and a burden. Every created character is flatter in every
  role prompt than the shipped one.
- **Racial traits never reach a sheet**: `_SUBRACE_TRAITS` links one record of the pack's 38, so no
  Darkvision, no Breath Weapon, no Lucky, no Relentless Endurance. `Race.traits` is structured
  upstream (see `.scratch/creation-remaining-state/issues/05`).
- **Saving-throw proficiency is modelled nowhere**, though the pack ships both halves: the class
  record's `saving-throws` fact and `proficiencies/saving-throw-*`. `resolve.py` computes a save as
  the bare ability modifier, so a fighter and a wizard resist a spell identically.
- **Background equipment and the background feature are not granted** — acolyte's holy symbol,
  clothes, pouch and 15 gp. Money is not modelled anywhere.
- **A long rest never restores hit points**: creation writes `hp` with no `recharge`, and `refill`
  skips it. Pre-existing — kael's authored `hp` and `ACTOR_COUNTERS` have the same hole — but
  creation is now the mass producer of these counters. One line, plus kael's json.

The last one is a one-line fix and could ride any of the tickets below.

## Found by the adversarial review of 01–04, and fixed after it, 2026-08-12

Both were outside those tickets, and both were made *worse* by them, because an ability score
improvement is now compulsory where it used to be skippable. They were written up here as open,
then closed the same day.

- **`armor-class` was derived once, at creation, and nothing recomputed it.** Every improvement
that raised DEX (or the ability behind Unarmored Defense) desynced it for good: driven to 20, the
monk held AC 13 where its own numbers said 16, the rogue 13, the barbarian 14 where they said 17 —
and `resolve.py` rolls every attack against that number. `advance` now re-derives it from the
armour the character carries, the way creation does; `equipment.armor_class` takes the refs rather
than creation's `Gear` bundle so both callers can reach it. **Still open**: a level-up is the only
moment that re-asks the question, so armour picked up or dropped mid-adventure is not felt until
the next level. That needs a resolver hook, and a model of *worn* versus merely carried.
- **A pool the pack does not spell as an int fact never grew.** `_apply_row` can only raise what a
row counts, so rage stayed at 2, lay on hands at 5, bardic inspiration at its level-1 uses and
long rest, and druid wild shape had no counter at all. `pools.py` now transcribes that class prose
the way `create._CLASS_SKILLS` transcribes the skill lists, and both creation and advancement read
it: a level-20 barbarian rages 6 times, a paladin lays on 100 hit points, a bard's inspiration
returns on a short rest from level 5, a druid holds `wild-shape` 2/short-rest. The counter key
`bardic-inspiration-d6` became `bardic-inspiration`, because the die is on the sheet as
`bardic-inspiration-die` and grows to 12 while the key claimed six. A pool whose size works out
below one is no longer granted at all, so a paladin with a Charisma penalty stops carrying a
`divine-sense` counter it can never spend, and gains one if the score ever rises. **Still open**:
the SRD's level-20 barbarian rages without limit, and a counter with a recharge must have a
maximum, so the ladder stops at 6.
