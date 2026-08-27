# L6 — Cairn Barebones engine

Scope: ~330 lines `rules.py`, ~150 `engine.py`, ~70 `director.md`, ~700 JSON pack — not the 4,100–5,600
that `docs/CAIRN-BAREBONES.md` §"Planned engine package" estimated (L0 has already deleted it). The
2026-08-17 deletion (`848d371`) killed a 708-line `actions.py`: scar mending, a day counter, `pass-time`,
per-item `ItemRules`, blast/joined attacks. None of it comes back.

## What the contract already carries, free

- **Saves are the engine.** One `roll_save` covers skill checks, morale, retreat, the first-round DEX
  gate, spell risk, panic, downtime cost-abatement. No separate tables.
- **Deprivation** is a core `add_trait` `deprived`; the only guard is one `if` in the rest resolver.
- **Casting a spell** = `add_fatigue` + a WIL `roll_save`. Zero engine code; spellbooks are content.
- **Conditions** (paralysed at 0 DEX, delirious at 0 WIL, critical damage, mortal wound) are traits;
  `kill` already exists for 0 STR, with corpse-drops and party removal.
- **Advancement fits unchanged.** Cairn Training is one mechanical ability per return to safety:
  `SheetAdvancement` + `complete_chapter`. `Engine.advancement` does **not** need `| None`. Note the SRD
  gates Training behind a Master, Costs and Milestones, which this plan cuts — steps 5 and 7 must say so
  and record the ungated grant as a deviation.
- **Item mechanics ride traits**, as 24XX already does with `bulky`/`broken`. One slug convention,
  `MARK = ^(petty|bulky|d(4|6|8|10|12)|armor-[1-3])$`, read off `Entity.traits` — so scenario canon,
  starting kit, and improvised items all get weapon dice, armor and slot size with **no new channel**.
  Trait text renders into the Director prompt already (`turn/context.py:319`). **Guard it:** core
  `add_trait` (`state/actions.py:166`) is in the Director's vocabulary, so the model can write `d12` onto a
  dagger — step 6's `validate` refuses more than one die-mark per item, and step 10's `director.md`
  reserves the mark slugs. Approved by the maintainer over the `Mechanics.items` alternative.

## Steps

1. `src/aidm/engines/cairn/rules.py` — `RULES` dataclass (`max_slots=10`, `max_armor=3`, `unarmed=4`,
   `impaired=4`, `enhanced=12`); `class Sheet(SheetBase)` with `pack: Slug = SRD_PACK` (**it needs a
   default**: `SheetEngine.seed` (`engines/sheets.py`) and `opening_mechanics` build
   `self.sheet_type()` for every non-player actor, and `Slug` rejects `""` — cf.
   `loner3e/rules.py: pack: Slug = SRD_PACK`), `background: str`,
   `strength/dexterity/willpower` (`Counter`, bounded), `hp`, `gold`, `fatigue`, `trainings` ledger,
   `rows()`; `class Mechanics(SheetMechanics[Sheet])` (empty body).
2. Same file, helpers: `saved(rolled: int, score: int) -> bool` (1 passes, 20 fails, else ≤ score);
   `marks(entity: Entity) -> tuple[Slug, ...]`; `item_die(item: Entity) -> int | None`;
   `armor_of(state: Game, actor: Entity) -> int` (own marks + carried items, capped 3);
   `slots_used(state: Game, actor: Entity, sheet: Sheet) -> int` (petty 0, bulky 2, else 1, plus fatigue);
   `mechanical_trait(mark: Slug) -> Trait` (name and text derived from the mark, not a lookup table).
3. Resolvers, all `-> tuple[Fact, ...]`, all reusing `require_actor_here`, `roll_pool`, `adjust`,
   `entity_fact`, `pending_notes`:
   - `resolve_save(draft, action: Save, rng)` — `Save{actor_id, attribute: Literal["strength",
     "dexterity","willpower"], risk: str}`; d20 vs the current score; `MechanicEvent` outcome pass/fail.
   - `resolve_attack(draft, action: Attack, rng)` — `Attack{attacker_id, target_id, weapon_id: ... | None,
     second_weapon_id: ... | None, also_attacking: tuple[CheckedEntityId, ...] = (), modifier:
     Literal["normal","impaired","enhanced"]}`. **Damage is one keep-highest pool, not one die.** The SRD:
     "If multiple attackers target the same foe, roll all damage dice and keep the single highest result",
     and "If attacking with two weapons at the same time, roll both damage dice and keep the single highest
     result (d8+d8)". Resolving one attacker per call would make three attackers deal three separate hits and
     turn every Cairn fight far deadlier than the game. Collect faces from `item_die` for the attacker, the
     second weapon and every id in `also_attacking`, and pass them to `roll_pool`, which already keeps the
     highest of a mixed pool and already renders `d8+d8` through `_notation` (`state/actions.py:13-25`) —
     nearly free. Then: unarmed d4; impaired d4 and enhanced d12 override the pool; subtract
     `armor_of(target)`; the attack always hits; HP first, overflow to STR. **A STR save fires only when
     damage overflowed into STR**, against the *new* score; a fail is `critical-damage` for the player (who
     dies within the hour) and `kill()` for anyone else; 0 STR is `kill()` outright.
   - `resolve_hazard(draft, action: Hazard, rng)` — `Hazard{target_id, die: Literal[4,6,8,10,12],
     attribute: Literal["hp","strength","dexterity","willpower"], why: str}`; traps, falls, poison; armor
     does not apply. Damage outside combat hits an attribute (docs line 180).
   - `apply_fatigue(draft, action: AddFatigue) -> list[Fact]` — +1 fatigue; refused when it would pass
     ten slots, with the message telling the Director to drop something first.
   - `settle(draft, rng)` on the engine (L3's post-command hook) — **the encumbrance rule**: when a sheeted
     actor's `slots_used` reaches `max_slots`, set HP to 0. `CAIRN-BAREBONES.md:204` prints both halves,
     the cap *and* the 0-HP consequence; the hook exists because core `move`/`gain_improvised_item`/`kill`
     change slot load and `validate` may only refuse. Keep step 6's eleventh-slot refusal as well.
   - `resolve_rest(draft, action: Rest) -> list[Fact]` — `Rest{actor_id, scope: Literal["breather",
     "night","week"]}`: HP full / +fatigue cleared / +attributes restored. Refused while `deprived`.
4. `take_scar(draft, actor, sheet, hp_lost, rng, scars)` — fires only when a **player's** HP lands exactly
   on 0. Row = `scars[min(hp_lost, 12) - 1]` — **clamp it**: the table has twelve rows but scars raise max
   HP, so `hp_lost` is unbounded and a raw index can `IndexError`. Adds the row's trait (+ a d6 location
   where the row has one, + `deprived` where it says so) and pays out immediately. `class Scar(Frozen)`:
   `label: str`, `text: str`, `attribute: Literal["strength","dexterity","willpower","hp"] | None`,
   `effect: Literal["higher","add","set"] | None`, **`dice: tuple[int, ...] = ()`** (not one die: rows 4, 5
   and 11 roll 2d6 and rows 6, 7, 9 and 12 roll 3d6), `amount: int | None`, `save: bool = False`,
   `locates: bool = False`, **`locates_attribute: bool = False`** (row 6 randomises *which* attribute, not a
   body part), `deprives: bool = False`. Row 12 (Doomed) is a conditional on the *next* critical-damage
   save, which no field can hold — write it as a `doomed` trait that `resolve_attack` reads on a failed STR
   save.
   "Pays out immediately" means the printed *roll the die, take the result if it is higher than the
   current score* — `higher` compares, `add` increments, `set` assigns; `save` gates the payout behind a
   `roll_save` first. No `until_mended`/`mending` fields: v1 has no scar mending and no day counter.
5. `src/aidm/engines/cairn/engine.py` — `class CairnEngine(SheetEngine[Sheet])`: `id = EngineId("cairn")`,
   `badge = ("CAIRN", "green-8")`, `sheet_type`, `mechanics_type`, `decisions = ()`. `__init__` loads packs
   (`load_packs`/`pack_paths`), builds `CairnAdvancement`, `CairnCreation`, and `director_commands` =
   `rule("roll_save"…)`, `rule("attack"…)`, `rule("hazard"…)`, `action("add_fatigue"…)`,
   `action("rest"…)`, `chapter_command("Record that the expedition has ended and the party has returned to
   safety.", "the expedition has ended")`.
6. Same file, four overrides: `validate(self, state: Game) -> None` — `super()`, the pack-installed check
   (copy `loner3e/engine.py:192`), a refusal when any sheeted actor exceeds ten slots, and a refusal when an
   item carries more than one die-mark; `settle(self, draft, rng) -> None` — the encumbrance rule from
   step 3;
   `describe(self, state, entity) -> str` and `sheet_rows(self, state) -> tuple[tuple[str, str], ...]` —
   `super()` plus `("Slots", "7/10")` and `("Armor", "2")`, which `Sheet.rows()` cannot see (no state).
7. `class CairnAdvancement(SheetAdvancement)`: `proposal_type = Training` (`{ability: str, text: str,
   why: str}`), `ledger_key = "trainings"`, `occasion = "has returned to safety from an expedition"` —
   **match the string to what is actually granted.** The SRD gates Training behind a named Master, a Cost
   and a Milestone; v1 grants one ability per completed expedition with none of the three, so the
   `occasion` must not claim "has trained between expeditions". Record the ungated grant as a deviation in
   `docs/CAIRN-BAREBONES.md`;
   `ledger()` returns `sheets[subject_id].trainings`; `grant()` calls `state.actions.add_trait` with
   `slug(ability, taken)`. ~12 lines. `text` class var carries the rule (one trained ability, named
   master, mechanical text) — a `GROWTH`-style constant in `rules.py`, not a separate file.
7b. **Roll NPC sheets** — override **both** `seed` (entities created mid-play; it already receives an `rng`
   it discards, `engines/sheets.py`) **and `opening_mechanics`** (scenario-authored NPCs, rolling with its
   own `Random()`). Overriding only `seed` gives every authored monster identical 10/10/10/HP 4 stats:
   `begin_game` calls `opening_mechanics(world, character.rules)` (`registry.py:64`), which builds a bare
   `self.sheet_type()` per actor (`core.py:300-307`), while `seed` fires only on `entity_created` facts
   (`core.py:424-427`). Both overrides stay inside the package — no core change.
   **Record this as a deviation, do not cite it as a printed rule:** the 3d6/1d6 line in the SRD is for
   *hirelings*, which v1 cuts, and Barebones ships no bestiary and no general NPC stat rule.
8. `class CairnCreation(PackCreation[Pack])` — `steps_for` returns background (d100 as a menu), armor (d6),
   weapon (d6); `create(self, name, brief, picks, rng: Random) -> CreatedCharacter` rolls 3d6 ×3, 1d6 HP,
   3d6 gold, writes `Sheet(...).model_dump(mode="json")` as `rules`, and builds `profile.items` from
   `starting_kit + background.gear + armor + weapon` as `Entity(kind="item", parent_id=PLAYER_ID,
   known=True, traits=[mechanical_trait(m) for m in entry.marks])`.
9. `packs/srd.json` — `Pack{name, source, license, starting_kit, backgrounds, armors, weapons, scars}`;
   `KitItem{id, label, detail, marks: tuple[Slug, ...]}` validated against `MARK`;
   `Background{id, label, detail, gear}`. Content: rations + torch, 100 backgrounds of three items, six
   armors, six weapons, twelve scar rows. Transcribe backgrounds, armor, weapons and the scars table from
   the official Barebones pages at <https://cairnrpg.com/barebones/rules/barebones-character-creation/> and
   <https://cairnrpg.com/barebones/rules/barebones-marketplace/> — **not from any repo document**. CC BY-SA
   4.0, Yochai Gal; copy the attribution string from the L0 pointer file.
10. `director.md` — fiction-first saves ("whoever is most at risk saves"), HP is not health, attacks always
    hit, armor is subtracted not rolled against, out-of-combat damage hits an attribute, fatigue costs a
    slot, deprivation blocks all recovery and is lifted with `remove_trait`, `complete_chapter` on return
    to safety, and: never invent a roll result. Also reserve the mark slugs — `petty`, `bulky`, `d4`–`d12`,
    `armor-1`–`armor-3` are mechanical and are never written as flavour traits.
11. Content: write `characters/kael/cairn.json` — mandatory, because `settings.authoring.starter_character`
    is `"kael"` (`config.py:70-71`), so every future authoring run needs it, not just play. Do **not** add
    `"cairn"` to the two existing multi-engine `world.json`s: once the trait-mark convention lands, a
    scenario carrying `d8` / `armor-2` / `petty` leaks meaningless mechanical traits into every other
    engine's prompt (`turn/context.py` renders traits per entity). Cairn gets its own single-engine scenario,
    authored with the `authoring-aidm` skill after this phase ships — see PLAN.md § "Scenarios".
    The registry auto-discovers `cairn/engine.py` — no list anywhere to edit. Also add Cairn's "make a new
    character on death" gap as a deviation, the same entry L4 step 7 gives 24XX, and add a
    `src/aidm/engines/cairn/` row (CC BY-SA 4.0, Yochai Gal) to the README licensing table
    (`README.md:129-131`), dropping "planned" at `README.md:14-17`.

## Cut from v1 (add when …)

- Die of Fate — the Director already adjudicates the uncertain. Add when play shows it hedging.
- Reaction table, morale table, detachments, blast — reaction is Director judgment, morale is a WIL
  `roll_save`. Add when a scenario needs mass combat. (Multi-attacker and dual-wield keep-highest are
  **not** cut — they are printed core combat and ship in step 3.)
- Dungeon/wilderness procedures, watches, light and ration clocks, weather, panic, travel — add when a
  scenario is authored around exploration turns rather than locations. Downtime milestones, research and
  strengthening ties go with them; Training already covers growth.
- Spellbook/scroll/relic tables and the 100 spells — casting already works; add as a content pack.
- Item `uses` counters — a spent torch is `add_trait spent`. Scar mending and the day counter — v1 pays
  every scar out immediately.
- d100 names, 2d20+10 age, the eight d10 trait tables, additional-gear d100, marketplace, hirelings — the
  player writes name and brief. Add when in-app rolling is worth the pack lines.
- Pending decisions (stake a save before rolling, à la 24XX) — add when a save's cost surprises players.
(Not cut, contrary to an earlier draft: "all ten slots filled reduces you to 0 HP" is a printed rule and
ships in step 3 via L3's `settle` hook.)

## Requires from L3

1. `CharacterCreation.create(self, name, brief, picks, rng: Random) -> CreatedCharacter`, plus a
   page-held seed and a Reroll button in `ui/create.py`. Non-negotiable: attributes, HP and gold are
   rolled in Cairn, and `create()` is called on every preview refresh (`ui/create.py:109`), so an
   unseeded `Random()` would reshuffle the preview and write something else. Both existing engines
   ignore the new parameter.
2. **The `settle` hook** — L3 step 2, a no-op `Engine.settle(draft, rng)` called just before
   `engine.validate` in `apply_to_draft` (`engines/core.py:388`). Core `move`, `gain_improvised_item` and
   `kill` all shift slot load and `Engine.validate` may only refuse, never write, so without it the printed
   "all ten slots filled reduces you to 0 HP" cannot be implemented at all.
3. Keep registry auto-discovery when the hand-maintained lists go. Cairn must add zero entries outside
   its own package.

Not required: **optional advancement** — Training makes `Engine.advancement` fit as it stands, and L3 has
dropped the `| None` change on that finding. Not required either: a scenario-level engine overlay, or
per-item mechanics state — the maintainer has approved the trait-mark convention, so the
`Mechanics.items: dict[EntityId, ItemRules]` fallback (the plumbing the 2026-08-17 deletion removed) is not
built.

**Proof L3 worked:** Cairn ships as five files under `src/aidm/engines/cairn/`, with no edit anywhere else
except the `create(..., rng)` signature, `characters/kael/cairn.json`, the deviation entries in
`docs/CAIRN-BAREBONES.md`, and one README licensing row.
