# Task: make the d20 honest, make death real, make gear matter

Three phases in dependency order. Each is a complete, shippable change; stop cleanly between them.
Do not start a later phase before the earlier one is green.

Read `CLAUDE.md` first; its engineering rules and architecture invariants govern this work.

## Ground rules for all three phases

- The pattern to mirror already exists twice and is correct both times: `ResourceState(remaining,
  maximum, recharge)` in `domain/models/progression.py` with `.spent` / `.refills(completed)`, the
  engine deciding in `engine/features.py` and `engine/spells.py`, the reducer applying and verifying
  in `domain/reducer.py::_spent` / `::_slot_spent` / `::_refilled`, and a consequence in
  `domain/models/consequences.py` dispatched in `engine/resolve.py`. Extend it; do not invent a
  third shape.
- Bump `SAVE_VERSION` in `src/aidm/domain/base.py` **once per phase** — each of
  the three changes the persisted shape. It is 16 today, and it is the constant
  `aidm/application/game.py` enforces; `aidm_5e/domain/models/base.py`'s 15 belongs to the retained
  legacy 5e domain and gates nothing.
- No phase needs a pack regeneration: every record these need already ships. If you find one that
  does not, `tests/dnd5e/test_content.py::test_a_loaded_pack_writes_back_byte_for_byte`
  is the regression check — the pack must stay a pure function of an external 5e-database checkout,
  which is not vendored.
- `Dnd5ePresentation` is the only path from typed 5e state and events into role prompts. The
  Narrator receives exact state for visible entities and is instructed to translate it into
  fiction rather than recite the numbers.
- Content the engine cannot resolve deterministically stays description-guided, the same way
  unclassified features and untyped spell effects already do. Do not fake a mechanic to make
  something "work". Where the SRD rule depends on a concept this codebase has no state for, say so
  and leave it to the description.
- Update `docs/ROADMAP.md` as each phase lands. Its "Structure and scale" list currently names these
  gaps as open.

---

# Phase 1 — the d20 tells the truth

Three defects, one subsystem: `engine/rules.py` rolls a bare die and reads no proficiency.

## What already exists

- `rules.roll_check(actor, ability, dc, rng)` uses `modifier(actor.stats.attributes, ability)` and
  nothing else. `rules.save_bonus` is the correct counterpart: it adds `progression.prof_bonus` when
  the ability is in `progression.saving_throws`. Checks have no equivalent.
- `rules._rolled` and `rules.roll_attack` each roll one `rng.randint(1, DIE)`. **There is no
  advantage or disadvantage concept anywhere in `aidm_5e`** — `grep -rn advantage
  src/aidm_5e` returns exactly one hit, `ArmorRecord.stealth_disadvantage`, which
  nothing reads.
- `DcRolled(actor_id, actor_name, kind, ability, dc, roll, total, success)` and
  `AttackRolled(actor_name, target_name, weapon, roll, total, ac, hit)` each carry a single `roll`,
  and their `summary` properties print it.
- The content for skills is complete and read by nothing: `skills.json` ships 18
  `SkillRecord(index, name, ability)` in `content/records/rules.py`; `proficiencies.json` ships 117
  records including `SkillProficiency(kind="skill", skill: Slug)` with indexes like `skill-stealth`.
  `Progression.proficiencies` holds exactly those slugs.
- `pack_ruleset.proficient(origin, held, equipment)` answers only equipment questions: `covers` is
  built from `EquipmentProficiency.equipment` and skill proficiencies never enter it. Its one caller
  is `engine/procedures.py::_proficiency_bonus`, for weapons.
- `RollCheck(DcRoll)` proposes `ability` and `dc`. There is no way for the Director to say *which*
  skill is being used, so nothing can decide whether the actor is proficient in it.
- Expertise is worse than missing. `content/records/character.py::ChoiceEffect` is
  `Literal["grant", "double"]`; `engine/progression.py::_proficiencies` validates that a `double`
  pick names a proficiency the character holds and then throws the pick away — its docstring says
  "doubling remains in decisions". A rogue with Stealth expertise rolls like anyone.

## Build

1. **An advantage/disadvantage primitive** in `engine/rules.py`. Roll two d20s and keep the higher
   or lower; per the SRD they never stack and any one of each cancels to a straight roll, so the
   input is a net state and not a count. The events are the Narrator's evidence, so a two-die roll
   must be visible as two dice — decide whether `roll` becomes a pair or a second field appears
   beside it, and keep both `summary` properties honest. `roll_check`, `roll_save` and `roll_attack`
   all go through it.
2. **Skill proficiency on checks.** `roll_check` must add `prof_bonus` when the actor holds the skill
   proficiency for the check. That needs the proposal to name a skill, and the `SkillRecord` then
   supplies the ability — which overlaps `DcRoll.ability`, shared with `RollSave`. Decide how the
   two relate (a skill on `RollCheck` only; the record's ability winning; the ability validated
   against it) and say which and why.
3. **Expertise doubles.** The pick has to land somewhere the engine reads. `Progression.decisions` is
   a `FrozenMap[Slug, tuple[Slug, ...]]` of raw answers and is the wrong home; a typed field beside
   `proficiencies` is the shape `spell_slots` and `feature_resources` already use. Doubling applies
   to the proficiency bonus on that skill's checks, and nowhere else.
4. Bump `SAVE_VERSION`.

## Gotchas

- `save_bonus` short-circuits on `stats.saving_throws`, which monsters carry as absolute numbers.
  Skill checks have no monster equivalent, so a monster's check stays the bare ability modifier —
  that is correct, not an omission.
- `tests/dnd5e/test_rules.py` pins the current single-die behaviour; expect it to
  move.

## Done when

`uv run pytest`, `uv run ruff check` and `uv run basedpyright` are clean, and a rogue with Stealth
expertise rolls at ability + 2 × `prof_bonus`, under disadvantage, with both dice in the event.

---

# Phase 2 — an actor can die

`StatBlock.hp` floors at 0 and `wounds` reports `"down"`. An actor at 0 HP simply stops changing.
Rest recharges pools and restores no hit points. Needs phase 1's primitive for exhaustion.

## What already exists

- `StatBlock(attributes, max_hp≥1, hp≥0, ac≥0, conditions, saving_throws, condition_immunities)` in
  `domain/models/stats.py`. `with_hp_delta` clamps into `[0, max_hp]`; `_consistent_stats` rejects
  `hp > max_hp`; `wounds` returns `"down"` at 0 and gives event presentation a concise qualitative
  summary alongside the exact visible state.
- `engine/mechanics/health.py::hp_events` is the single HP path in the codebase. Four callers:
  `health.damage`, `health.heal`, `features.use` (self-heal) and `spells._effects` (damage and
  healing). Whatever decides dying decides it there, once.
- `Rest` in `consequences.py` carries only `rest: RestType`. `engine/resolve.py` builds
  `Rested(rest=rest, refilled=features.recharged(ctx, rest), slots=spells.recharged(ctx, rest))`.
  No hit points are touched and no hit-dice pool exists.
- `CharacterProfile.hit_die` and `LevelBenefits.hit_die` are compiled and used only to roll HP at
  level-up (`engine/progression.py::advance`).
- `ConditionName` in `content/vocabulary.py` includes `"exhaustion"` as a flat name with no level.
  `conditions.json` ships its prose. `StatBlock.with_condition(name, active=…)` is the only mutator.
- Monsters are snapshotted by `engine/bestiary.py::statted`; `ActorEntity.progression is None` is
  what distinguishes them from the player.

## Build

1. **A hit-dice pool** on `Progression` alongside `feature_resources` and `spell_slots`. Its maximum
   is the class level and its die size is `CharacterProfile.hit_die`. The SRD returns half your total
   dice on a long rest, rounded down, minimum one — decide whether to model that or the simpler full
   return, and say which.
2. **Short rest spends hit dice**, healing `1d{hit_die} + constitution modifier` each. `Rest` carries
   no amount today, so decide how many are spent: a field on the consequence, or spend up to full.
   **A long rest heals to full.** Extend `Rested` rather than adding a parallel event.
3. **Dying.** At 0 HP the player is unconscious and making death saves: a plain d20 against DC 10
   with no modifier and no proficiency; three successes stabilise, three failures kill; a natural 20
   revives at 1 HP and a natural 1 counts as two failures. Damage taken while at 0 HP is an
   automatic failure. Massive damage — leftover damage at or above `max_hp` — kills outright. Any
   healing above 0 clears the tally. Monsters do not make death saves; they drop.
4. **Temporary HP.** Absorbed before `hp`, never stacked (the higher of the two wins), lost on a long
   rest, and never raising `max_hp`. It has to sit inside `hp_events` or damage will route around it.
5. **Exhaustion 1-6.** Levels 1 and 3 are the disadvantage phase 1 built, on checks and on
   attacks/saves respectively. Level 4 halves the hit point maximum. Level 6 is death, which
   step 3 now has state for. Levels 2 and 5 reduce speed, and there is no speed concept in this
   codebase — leave those two to the description rather than inventing one.
6. Bump `SAVE_VERSION`.

## Gotchas

- Do not model negative hit points. `hp` is `ge=0` and dying is a state, not a number.
- `wounds` remains the concise event-level health summary. Dying, stable and dead must be
  distinguishable there even though the visible entity-state section also carries exact values.
- Whether an actor is dead is a fact the reducer owns; the engine proposes the events that get it
  there. A dead actor must stop being a legal target, and `_apply_one` is where that invariant holds.
- Changing the `hp_events` contract touches every damage and healing path, including the four spell
  outcomes just built in `engine/spells.py`.

## Done when

The three commands are clean, and: a player at 0 HP makes death saves and either stabilises or dies;
massive damage kills outright; a short rest spends hit dice to heal and a long rest heals to full;
temporary HP absorbs a hit before hit points do; exhaustion 4 halves the maximum and 6 kills.

---

# Phase 3 — armour and items reach the table

`StatBlock.ac` defaults to 10 and the player's never changes. 13 armours and 362 magic items are
registered and read by nothing.

## What already exists

- `StatBlock.ac: int = Field(default=10, ge=0)`. It has exactly two writers in `aidm_5e`:
  `pack_ruleset._stats` sets `ac=monster.armor_class` from the snapshot, and nothing sets the
  player's — `domain/models/state.py::GameState.from_scenario`, reached from
  `Dnd5eLifecycle.initialise` via `engine/campaign.py::begin`, builds
  `StatBlock(attributes=…, max_hp=…, hp=…)` and takes the default. `rules.roll_attack` reads
  `target.stats.ac`. A level 20 fighter in full plate has AC 10.
- `ArmorRecord(category: Light|Medium|Heavy|Shield, base_ac, dex_bonus, max_dex_bonus, str_minimum,
  stealth_disadvantage)` — 13 records in `armor.json`, registered in `content/registry.py` under an
  `"item"` entity kind, read by nothing.
- **There is no equipped or worn concept.** `ItemEntity` carries `kind` and `container_id` and
  nothing else. `procedures._held_weapon` finds a weapon by scanning `world.carried_by(actor_id)`
  and matching the name — carrying is wielding.
- `MagicItemRecord(category, rarity, desc, variant, variants)` — 362 records. It carries prose and no
  mechanics, so a magic item is description-guided by construction; the gap is reachability, not
  effects.
- **Nothing created during play can name a pack record.** `aidm/pipeline.py::_created_entity` builds
  an entity with no `ref` at all. Refs enter the world only through a scenario's authored `entities`
  and a character sheet's `starting_items`. `engine/bestiary.py::statted_world` then verifies every
  ref the world holds, and `COLLECTION_SPECS[…].entity` already declares which collections may back
  an item.
- `pack_ruleset.proficient()` and its `covers` index already answer "may this actor use this armour".

## Build

1. **A worn state**, on the item rather than the actor, so `world` stays the single index of what is
   where. One body of armour and one shield at a time; that invariant must fail fast in the reducer,
   not be checked in the UI. A consequence for donning and doffing, dispatched in `resolve.py`.
2. **Derive the player's AC** from what they wear: `base_ac`, plus the dexterity modifier capped by
   `max_dex_bonus` when `dex_bonus` is set, plus a shield's `base_ac`; unarmoured is 10 + dexterity.
   Decide whether the player's AC becomes a rule computed on read — like `save_bonus` — or stays
  stored on `StatBlock` and recomputed on change, and say which. A snapshotted monster's AC is an
  absolute number and must keep working either way.
3. `str_minimum` unmet costs speed in the SRD, and there is no speed here — record the constraint,
   do not invent a substitute. `stealth_disadvantage` feeds phase 1's primitive on Stealth checks,
   which is a real mechanic and should land.
4. **Make catalogue items reachable in play.** Today the only path is authoring them into a
   scenario. Decide the channel — the Creator naming a ref, a consequence that grants a catalogue
   item, or a loot table — and say which and why. Whatever it is, `bestiary.statted_world` must still
   reject a ref nothing provides, and an item may only name a collection whose spec declares the
   `"item"` kind.
5. Bump `SAVE_VERSION`.

## Gotchas

- `_held_weapon` treats carried as wielded. Introducing worn state without touching it leaves two
  competing notions of "in use"; decide whether wielding joins the same mechanism now or stays as it
  is, and be explicit either way.
- AC is a number the Narrator must not see for a non-player actor, the same as HP.
- `bestiary.statted` refuses a record-backed actor whose stats are not the default `StatBlock()`, so
  anything that pre-sets AC on a monster-backed entity will trip it.

## Done when

The three commands are clean, a character in chain mail with a shield has AC 18 and not 10, doffing
it drops them to 10 + dexterity, and a magic item can enter play through the channel you chose.

---

# Out of scope — later prompts, not these

- **Concentration.** `SpellRecord.concentration` is parsed and nothing tracks an active
  concentration or breaks it on damage. Wants phase 2's damage path to exist first.
- **Spell preparation.** A prepared caster's whole class list is castable, because there is no
  per-rest decision channel. Deliberate and recorded in `docs/ROADMAP.md`; revisit only with a real
  preparation step.
- **Reliability and canon quality.** A dropped consequence is silent; the Maintainer only grows
  canon and never deepens it; locations and inventory are free strings. See `docs/ROADMAP.md`.
