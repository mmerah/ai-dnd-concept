# Cairn Second Edition — core rules extraction

## Attribution & license

Cairn is designed by **Yochai Gal**. This document is a mechanics extraction of the Cairn
Second Edition **Player's Guide** (plus the Warden's Guide *Growth* chapter), taken from the
official free web edition.

The site states, on every page reproduced here:

> The text on this page is licensed under CC-BY-SA 4.0.

This file is therefore a derivative of CC BY-SA 4.0 material and is itself licensed
**CC BY-SA 4.0**, attributed to Yochai Gal, cairnrpg.com.

Sources (fetched 2026-08-13):

- https://cairnrpg.com/second-edition/
- https://cairnrpg.com/second-edition/players-guide/
- https://cairnrpg.com/second-edition/players-guide/overview-and-principles/
- https://cairnrpg.com/second-edition/players-guide/character-creation/
- https://cairnrpg.com/second-edition/players-guide/core-rules/
- https://cairnrpg.com/second-edition/players-guide/procedures/
- https://cairnrpg.com/second-edition/players-guide/marketplace/
- https://cairnrpg.com/second-edition/backgrounds/aurifex/ (sampled for background structure)
- https://cairnrpg.com/second-edition/wardens-guide/ and .../wardens-guide/growth/

**Scope note.** This is a rules extraction for judging engine implementability. Numbers, dice,
thresholds and procedure order are exact. Long flavor tables (Bonds, Omens, the eight Character
Trait tables, the 20 background pages) are represented by their *structure* plus a couple of
example rows; every elision is flagged inline. Prose advice, examples of play, and the setting
(Vald) are summarized or omitted.

---

## 1. Overview

Cairn is a classless, roll-under-d20 adventure game about exploring a dark Wood. Character
generation is quick and random; combat is deadly.

Six stated design pillars:

- **Neutrality** — the Warden (GM) is a neutral arbiter of rules, situations, NPCs, narrative.
- **Classless** — no classes; equipment carried and experiences had define a character's specialty.
- **Death** — always around the corner, but "never random or without warning."
- **Fiction First** — dice do not always reflect difficulty or outcome; success and failure are
  arbitrated from in-world elements, in dialogue with players.
- **Growth** — advancement is in-world: new skills and abilities come from surviving dangerous
  events and overcoming obstacles. There is no XP and no levels.
- **Player Choice** — risk information is provided freely and frequently.

Player principles cover Agency, Teamwork, Exploration, Talking, Caution, Planning, Ambition.
Warden principles cover Information, Difficulty, Preparation, Narrative Focus, Danger, Treasure,
Choice, Die of Fate. These are guidance, not mechanics; not reproduced here in full.

---

## 2. Character creation

Order of operations:

1. Roll or choose a **Background** (d20, 20 entries — see table below).
2. Take a **name** from that background's name list; record its **starting items**.
3. Roll on **each table inside the background** (typically two d6 tables); record the resulting
   items, skills or abilities. Some backgrounds send you to the Marketplace tables.
4. Roll **Attributes**: 3d6 for each of STR, DEX, WIL, in order. You may then swap any two results.
5. Roll **Hit Protection**: 1d6.
6. Roll the rest of the **Character Traits** (eight d10 tables), then the **Bonds** table (d20).
7. Roll **Age**: `2d20+10`.
8. The **youngest character** rolls on the **Omens** table (d20) and reads the result aloud; the
   Warden folds the omen into the setting.

### Attributes

Three attributes only:

- **Strength (STR)** — physical power: lifting gates, bending bars, resisting poison.
- **Dexterity (DEX)** — poise, speed, reflexes, dodging, climbing, sneaking, balancing.
- **Willpower (WIL)** — persuade, deceive, interrogate, intimidate, charm, provoke, and
  *manipulating spells*.

Attributes are explicitly not universal descriptors: a low-STR character may still attempt any
feat; "their risk is simply higher."

### Hit Protection (HP)

1d6 at creation. HP "reflects their ability to avoid damage in combat. It does not indicate a
character's health or fortitude." It is regained quickly (see Rest & Recovery).

If an attack takes a PC's HP **exactly to 0**, roll on the Scars table.

### Backgrounds (d20)

| d20 | Background | d20 | Background |
| --- | --- | --- | --- |
| 1 | Aurifex | 11 | Half-Witch |
| 2 | Barber-Surgeon | 12 | Hexenbane |
| 3 | Beast Handler | 13 | Jongleur |
| 4 | Bonekeeper | 14 | Kettlewright |
| 5 | Cutpurse | 15 | Marchguard |
| 6 | Fieldwarden | 16 | Mountebank |
| 7 | Fletchwind | 17 | Outrider |
| 8 | Foundling | 18 | Prowler |
| 9 | Fungal Forager | 19 | Rill Runner |
| 10 | Greenwise | 20 | Scrivener |

**Background page structure** (each of the 20 has its own page; contents elided except the
sample below):

- One paragraph of flavor.
- A list of ~10 suggested **names**.
- **Starting Gear**: a gold roll (e.g. `3d6 Gold Pieces`), Rations (3 uses), a weapon with its
  damage die, and 2-4 themed items with slot qualities (`petty`, `bulky`, `N uses`).
- **Two d6 tables** whose rows grant items, quirks, abilities, or drawbacks. Rows are mechanically
  live: they hand out items with damage dice and use counts, Fatigue costs, deprivation triggers,
  and even statted companions.

Sample — **Aurifex**: gear is 3d6 gp, Rations (3 uses), Lantern, Oil Can (6 uses), Needle-knife
(d6), Protective Gloves (petty). Table 1 "What went horribly wrong?" (1d6) includes e.g. `5:
prototype Blunderbuss (d12, blast, bulky) that takes one round to reload`. Table 2 "What
alchemical marvel…" (1d6) includes e.g. `3: Aqua Vita — purifies any liquid; drinking it cures
1d6 STR (1 use)` and `6: Homunculus — 3 HP, 4 STR, 13 DEX, 5 WIL; damage to it is also done to
you`. **The other 19 background pages are elided.**

### Character Traits (eight d10 tables)

Eight tables, each `1d10` with 10 entries, purely descriptive: **Physique, Skin, Hair, Face,
Speech, Clothing, Virtue, Vice**. Example rows: Physique 1 Athletic … 10 Towering; Vice 1
Aggressive … 10 Vengeful. **Remaining rows elided** (no mechanical effect).

### Bonds (d20)

20 entries. Each is a paragraph of backstory that also grants a concrete starting item and, in
some cases, a live mechanic. Examples:

- `2` — a distant cousin's inheritance: **20gp** and a Strange Compass (petty) pointing deep into
  the Wood.
- `10` — a Mischievous Spirit: **occupies one slot but absorbs one Fatigue each day**.
- `13` — a wounded beast follows you: **you cannot become panicked when acting alone**.
- `15` — a Stone Heart curse: **grows heavier by one slot each month**; until the debt is lifted
  you cannot truly die.

**The other 16 rows are elided.** Note for implementation: Bond rows carry item grants, slot
costs, Fatigue interactions, and condition immunities — they are not pure flavor.

### Omens (d20)

20 entries, each a paragraph describing a portent in the world (blackened rivers, early winter,
a bleeding mother tree, a crimson moon, etc.). Purely a setting seed for the Warden; **no
mechanical effect, all 20 rows elided.**

---

## 3. Core resolution

### Saves

A save is a roll to avoid a negative outcome from a risky choice.

- Roll **d20** against the relevant attribute. **Equal to or under = success**; over = failure.
- **1 is always a success; 20 is always a failure.**
- If two opponents each try to overcome the other, **whoever is most at risk saves**.
- If two characters act together, whoever is most at risk saves — usually the one with the
  *lowest* relevant attribute.

There is no attack roll, no skill list, no difficulty class. (The Warden's Guide adds advice on
when to call for a save and on variable difficulty adjudicated in the fiction, not by modifiers.)

### Die of Fate

Optional: roll **1d6** when an outcome is uncertain or randomness is wanted. **4+ generally
favors the PCs; 3 or under usually means bad luck.**

### Reactions (2d6)

Rolled when an NPC's reaction to the party is not obvious.

| 2 | 3-5 | 6-8 | 9-11 | 12 |
| --- | --- | --- | --- | --- |
| Hostile | Wary | Curious | Kind | Helpful |

### Morale

- Enemies must pass a **WIL save** to avoid fleeing when they take their **first casualty**, and
  again when they **lose half their number**.
- Some groups use their **leader's WIL** instead of their own.
- **Lone foes save when reduced to 0 HP.**
- **Morale does not affect PCs.**

### Panic

A character surrounded by enemies, enveloped in darkness, or facing their greatest fears may
panic; typically a **WIL save** to avoid becoming panicked. A panicked character:

- **has 0 HP**,
- **does not act in the first round of combat**,
- **all their attacks are impaired**,
- and must spend an **action** on their turn making a WIL save to shake it off.

---

## 4. Inventory, fatigue, deprivation

- Every character has **10 inventory slots** total, but can only carry **four or five items
  comfortably** without bags, backpacks, horses, carts, etc.
- Each PC starts with a **Backpack holding up to six slots** of items or Fatigue.
- **Most items take one slot.** **Petty** items take **no** slot. **Bulky** items take **two**.
- A bag of coins **worth less than 100gp is petty** and occupies no slot.
- **Anyone filling all 10 slots is reduced to 0 HP.** A character cannot fill more than ten slots.
- Inventory is abstract, adjudicated by the Warden.

### Fatigue

- Each **Fatigue occupies one slot** and lasts until the PC can recuperate (e.g. a full night's
  rest in a safe spot).
- Fatigue is added by **casting a spell**, by **deprivation**, and by events in the fiction
  (travel penalties, weather, skipped camp, some Wilderness/Dungeon Events).
- If Fatigue must be added and **there are no free slots, the PC must drop an item**.

### Deprivation

- A PC lacking a crucial need (food, rest) is **Deprived**.
- **Deprived for more than a day → add one Fatigue per day.**
- A **Deprived PC cannot recover HP, Attributes, or item slots from Fatigue.**

---

## 5. Rest, healing & recovery

- **Resting a few moments with a drink of water restores lost HP**, but may leave the party
  exposed. In a dungeon, spending a turn resting restores **all HP** and requires a light source
  and a safe location; present or oncoming danger makes rest impossible.
- **Resting in a dungeon does not restore Fatigue** — it is impossible to safely Make Camp there.
- **Bandages** can stabilize a character who has taken critical damage.
- **Attribute loss** (from Critical Damage) is usually restored with **a week's rest**, aided by a
  healer or comparable expertise.
- Some healing is free; magical or faster recovery costs (Marketplace: Medical Healing 50gp).
- **Make Camp** (wilderness) removes **all Fatigue** from the inventory of each party member who
  was able to rest.

---

## 6. Combat

### Rounds

- A **Round is roughly ten seconds**. Each round: **PCs act first, then their opponents**. The
  results of each side's actions **occur simultaneously**.
- **First round of combat: each PC must make a DEX save in order to act.** Failure = lose the turn
  for that round. Circumstances, abilities, items or skills may negate this requirement.
- Rounds repeat (PCs, then opponents) until one side is defeated or has fled.

### Actions

On their turn a character may **move up to 40ft and take up to one action** — cast a spell,
attack, move a second time, or another reasonable action. **All PCs declare before dice are
rolled.** Risky attempts prompt a save.

### Attacking & damage

- **Attacks in combat automatically hit.** The attacker rolls their **weapon die**, subtracts the
  target's **Armor**, and deals the remainder to the target's HP.
- **Multiple attackers on the same foe: roll all damage dice, keep the single highest result.**
  All actions are declared before resolution.
- HP reduced **exactly to 0** → roll on the **Scars** table.

### Attack modifiers

- **Impaired** (position of weakness — cover, bound hands): roll **1d4** damage regardless of the
  weapon's die. **Unarmed attacks always do d4.**
- **Enhanced** (position of advantage — helpless foe, daring maneuver): roll **1d12** instead of
  the normal die.
- **Blast**: affects all targets in the noted area, rolling **separately for each** affected
  character. If unsure how many targets are affected, roll the related damage die for a count.
- **Two weapons at once**: roll both damage dice, **keep the single highest** (notated `d8+d8`).

### Armor

- Subtract **Armor** from the damage roll **before** applying it to HP.
- Shields and similar give a bonus (**+1 Armor**) **only while held or worn**.
- **No PC, NPC or monster may have more than 3 Armor.**

### Critical Damage

- Damage that reduces a target **below zero HP** is subtracted from their **STR** by the amount
  remaining.
- The target must then **immediately make a STR save using the new STR score** to avoid Critical
  Damage. On a success they stay in the fight (with the lower STR) and keep making such saves on
  further damage.
- A **PC** suffering Critical Damage can do nothing but crawl weakly. Given aid (e.g. bandages)
  they **stabilize**; untreated they **die within the hour**.
- **NPCs and monsters that fail a Critical Damage save are dead**, at the Warden's discretion.
  Some enemies have abilities triggered when a target fails a critical damage save.

### Attribute loss

- Damage taken **outside combat** is applied to an **Attribute, typically STR**, not HP.
- **STR 0 = death. DEX 0 = paralyzed. WIL 0 = delirious.** Full DEX or WIL loss leaves the
  character unable to act until restored by extended rest or extraordinary means.

### Character death

The player creates a new character or takes control of a hireling, joining the party immediately
to reduce downtime.

### Detachments

- Large groups of similar combatants fighting together are one **Detachment**.
- A detachment taking **Critical Damage** is **routed or significantly weakened**; at **0 STR** it
  is **destroyed**.
- **Individual → detachment attacks are impaired** (blast damage excepted).
- **Detachment → individual attacks are enhanced and deal blast damage.**

### Retreat

Running away from a dire situation **always requires a successful DEX save**, plus a safe
destination to run to.

### Ranged attacks

Ranged weapons can target any enemy "near enough to see the whites of their eyes." Attacks at
especially distant targets are **Impaired**. **Ammunition is not tracked** unless specified.

### Scars table

Consulted when damage brings a PC's HP **exactly to 0**; the index is the **amount of HP lost in
that attack** (e.g. 3 HP → 0 HP reads entry 3). Every entry is a permanent-stat mechanic:

| HP lost | Result (mechanics) |
| --- | --- |
| 1 | **Lasting Scar** — 1d6 for location (1 Neck, 2 Hands, 3 Eye, 4 Chest, 5 Legs, 6 Ear). Roll 1d6; if higher than max HP, take the new result. |
| 2 | **Rattling Blow** — describe how you refocus. Roll 1d6; if higher than max HP, take it. |
| 3 | **Walloped** — deprived until you rest a few hours; then roll 1d6 and **add** it to max HP. |
| 4 | **Broken Limb** — 1d6 location (1-2 Leg, 3-4 Arm, 5 Rib, 6 Skull). Once mended roll 2d6; if higher than max HP, take it. |
| 5 | **Diseased** — when you recover, roll 2d6; if higher than max HP, take it. |
| 6 | **Reorienting Head Wound** — 1d6 (1-2 STR, 3-4 DEX, 5-6 WIL). Roll 3d6; if higher than that attribute, take it. |
| 7 | **Hamstrung** — barely mobile until serious help and rest. After recovery roll 3d6; if higher than max DEX, take it. |
| 8 | **Deafened** — cannot hear until extraordinary aid. Regardless, make a WIL save; on a pass **increase max WIL by 1d4**. |
| 9 | **Re-brained** — roll 3d6; if higher than max WIL, take it. |
| 10 | **Sundered** — an appendage is lost or useless (Warden chooses). Make a WIL save; on a pass **increase max WIL by 1d6**. |
| 11 | **Mortal Wound** — deprived and out of action; you die in one hour unless healed. On recovery roll 2d6 and **take it** as max HP. |
| 12 | **Doomed** — if your **next** critical damage save fails, you die horribly. If you pass, roll 3d6; if higher than max HP, take it. |

---

## 7. Magic

### Spellbooks

- A Spellbook contains **a single spell** and takes **one slot**.
- They **cannot be easily transcribed or created**; they are recovered from tombs, dungeons,
  manors.
- They often have unusual properties or limitations (a foul smell when opened, an innate
  intelligence, legibility only in moonlight).
- They attract those seeking arcane power; displaying them openly is dangerous.

### Casting

- **Anyone** can cast by **holding a Spellbook in both hands and reading it aloud**. They must
  then **add a Fatigue** to inventory.
- Given **time and safety**, a PC can enhance a spell's impact (multiple targets, more power)
  **at no additional cost**.
- If the PC is **deprived or in danger** (e.g. combat), the Warden may require a **WIL save** to
  avoid ill effects. Consequences are on par with the intended effect: added Fatigue, destruction
  of the Spellbook, injury, even death.

### Scrolls

Like Spellbooks, except: **petty** (no slot), **cause no Fatigue**, **disappear after one use**.

### Relics

Items imbued with a spell or power. **No Fatigue.** Usually **limited use** plus a **Recharge
condition**.

---

## 8. Procedures

### 8.1 Dungeon exploration

**Cycle** (repeats):

1. Warden describes surroundings and immediate dangers; players declare movement and actions.
2. Warden resolves all characters' actions **simultaneously**, along with actions already in
   progress (Die of Fate for doubt).
3. Players record resource loss and new conditions (item use, deprivation, …). If appropriate the
   Warden rolls on the **Dungeon Events** table, and the cycle restarts.

**Movement**: on their turn a character moves a distance equal to their **torchlight's perimeter
(about 40ft)** and performs one action. They may instead use the action to move **up to three
times that distance**, which increases the chance of a Dungeon Events roll.

The Warden gives obvious information about an area and its dangers **freely and at no cost**.
"Dungeon" means any dangerous locale.

**Dungeon Events (d6)** — rolled when the party spends more than one cycle in one room, moves
quickly or haphazardly, moves into a new area/level/zone, or creates a loud disturbance:

| d6 | Event | Effect |
| --- | --- | --- |
| 1 | Encounter | Roll on an encounter table. Possibly hostile (see Reactions). |
| 2 | Sign | A clue, spoor, track, abandoned lair, scent, victim, etc. |
| 3 | Environment | Surroundings shift or escalate (water rises, ceiling collapses, a ritual nears completion). |
| 4 | Loss | Torches blown out, an ongoing spell fizzles; must be resolved before moving on. |
| 5 | Exhaustion | The party must rest (triggering another roll on this table), add a Fatigue, or consume a ration. |
| 6 | Quiet | The party is left alone and safe for now. |

**Actions** are any non-passive activity: searching for traps, forcing a door, listening,
disarming, fighting, casting, dodging, fleeing, resting. Some take multiple turns; loud actions
may trigger an encounter.

- **Searching** — a turn spent on an exhaustive search of **one object or location** reveals
  relevant hidden treasure, traps, secret doors. Large or complex rooms take several turns.
  Safe, but costs time.
- **Resting** — a turn spent resting **restores all HP**; requires a light source and a safe
  location; **does not restore Fatigue**.

**Light**

- Torches and radial light sources illuminate **40ft**; beyond that, only dim outlines.
- Torches burn until put out by a character or the environment. A **torch can be lit 3 times**
  before permanently degrading. A **lantern can be relit 6 times per oil can** but needs more
  inventory slots.
- Characters without a light source may suffer **panic**.

**Doors** may be locked, stuck or blocked; they can be forced or wedged with resources (spikes,
glue) or raw ability. **Marching order** determines who is most impacted by what lies beyond.
Careful observation (listening, smelling) can detect life and hazards through doors and walls.

**Traps**

- A cautious character is given all information needed to avoid springing a trap. An unwitting
  character triggers it per the fiction, **or otherwise has a 2-in-6 chance**.
- Traps are usually found by carefully searching a room.
- **Trap damage is taken from Attributes (usually STR or DEX), not HP.** Armor reduces it only
  when applicable (a shield does not stop noxious gas).

### 8.2 Wilderness exploration

**Watches**: a day is three watches — **morning, afternoon, night** (three eight-hour segments).
**Each character chooses one Wilderness Action per watch.** Split parties are handled as
independent entities. Since most parties rest during the third watch, "days" works as shorthand
for travel time.

**Points**: potential destinations on the map. One or more watches are needed to journey between
two points, depending on path, terrain, weather and party status. The party has a rough idea of
the challenge, rarely specifics.

**Travel duration**: combine all penalties from the path, terrain and weather tables, accounting
for changes along the route. Waterways use the surrounding terrain's difficulty. Especially vast
terrain may add **up to +2 watches**. Weather, terrain, darkness and injuries can force added
Fatigue or expended resources to sustain a pace; mounts, guides and maps can speed travel or
negate penalties.

**Path Difficulty**

| Path | Penalty | Odds of getting lost |
| --- | --- | --- |
| Roads | None | None |
| Trails | +1 Watch | 2-in-6 |
| Wilderness | +2 Watches | 3-in-6 |

| Path distance | Penalty |
| --- | --- |
| Short | +1 Watch |
| Medium | +2 Watches |
| Long | +3 Watches |

**Terrain Difficulty**

| Difficulty | Terrain | Penalty |
| --- | --- | --- |
| Easy | Plains, plateaus, valleys | none |
| Tough | Forests, deserts, hills | +1 Watch |
| Perilous | Mountains, jungles, swamp | +2 Watches |

(Each row also lists example hazards — safe rest spots and good visibility; wild animals,
flooding, broken equipment, falling rocks, hunters' traps; quicksand, sucking mud, choking vines,
unclean water, poisonous plants and animals, poor navigation.)

**Weather** — the Warden rolls **1d6 each day** on the seasonal table. **If "Extreme" is rolled
twice in a row, the weather becomes "Catastrophic."**

| d6 | Spring | Summer | Fall | Winter |
| --- | --- | --- | --- | --- |
| 1 | Nice | Nice | Fair | Fair |
| 2 | Fair | Nice | Fair | Unpleasant |
| 3 | Fair | Fair | Unpleasant | Inclement |
| 4 | Unpleasant | Unpleasant | Inclement | Inclement |
| 5 | Inclement | Inclement | Inclement | Extreme |
| 6 | Extreme | Extreme | Extreme | Extreme |

| Weather | Effect |
| --- | --- |
| Nice | Favorable conditions for travel. |
| Fair | Favorable conditions for travel. |
| Unpleasant | Add a Fatigue **or** add one watch to the journey. |
| Inclement | Add a Fatigue **or** +1 watch. **Increase terrain Difficulty by a step.** |
| Extreme | Add a Fatigue **and** +1 watch. **Increase terrain Difficulty by a step.** |
| Catastrophic | Most parties cannot travel at all. |

**Wilderness exploration cycle**:

1. Warden describes the current point/region and how path, weather, terrain or party status affect
   travel speed; the party plots or adjusts its course.
2. Each party member chooses **one Wilderness Action**; the Warden narrates results, then rolls on
   **Wilderness Events**; the party responds.
3. Everyone records lost resources and new conditions (torch use, deprivation, …); repeat.

**Wilderness Events (d6)**

| d6 | Event | Effect |
| --- | --- | --- |
| 1 | Encounter | Roll on an encounter table for that terrain/location; roll NPC reactions if applicable. |
| 2 | Sign | A clue, spoor, or indication of a nearby encounter, locality, hidden feature, or information. |
| 3 | Environment | A shift in weather or terrain. |
| 4 | Loss | A choice that costs a resource (rations, tools), time, or effort. |
| 5 | Exhaustion | A barrier forcing effort, care or delay: spend extra time (an additional Wilderness Action) or add Fatigue. |
| 6 | Discovery | Food, treasure or other useful resources; or the Warden reveals the area's primary feature. |

**Night**: the party may travel by night and rest by day, but night travel is slower and more
treacherous — **the Warden rolls twice on the Wilderness Events table**. Some terrain/weather is
easier at night (desert).

**Sleep**: the last watch of the day is normally the **Make Camp** action. Anything beyond a minor
interruption negates the benefits of sleep. **Skipping Make Camp: each PC adds a Fatigue and is
deprived**, and traveling sleep-deprived **raises terrain Difficulty by a step**.

**Light (wilderness)**: 40ft ahead, dim outlines beyond. No light source may cause panic.
Environmental conditions easily blow out a torch. A **torch can be lit 3 times**; a **lantern can
be relit indefinitely but needs a separate oil can (6 uses)**.

**Wilderness Actions**

- **Travel** — begins travel; nearby locations, features and terrain are revealed by distance.
  Usually taken by the whole party at once. The party **rolls 1d6 to see if they get lost**,
  compared against the relevant path Difficulty (see the odds column); risk shifts with maps,
  party skills and guides. If lost, recovering the route may cost a Wilderness Action; otherwise
  the party reaches the next point. Travel is still required to leave an area even if fully
  explored.
- **Explore** — one or more members search a large area, scout ahead or tread carefully; a
  **Location** (shelter, village, cave) or **Feature** (geyser, underground river, beached ship)
  is discovered.
- **Supply** — hunt, fish or forage, collecting **1d4 Rations (3 uses each)**. Each additional
  participant **steps the die up** (1d4 → 1d6, **up to a maximum of 1d12**). Relevant experience
  or equipment can also increase the bounty. The party may also spend gold and a full watch
  resupplying at homes and villages.
- **Make Camp** — each party member **and their mounts consume a Ration**; a lookout rotation is
  set. **Party members able to rest remove all Fatigue from their inventory.**

### 8.3 Downtime

Between sessions, players may research, follow leads, improve skills, build relationships. **A PC
is limited to one Downtime Action at a time.** Downtime actions cannot be taken in unsafe
conditions, while in recovery, or if they would put the character's safety at risk.

**Milestones**: for multi-step activities the Warden assigns **1-5 Milestones**, each a
comprehensive, non-interactive task. Different strategies may carry distinct Milestones; the
Warden may add or discard Milestones as play unfolds.

**Costs**: a PC completes a Milestone by taking a Downtime Action and paying its Cost —

- **Gold** — direct payment from inventory.
- **Resources** — material goods, specific common items.
- **Reputation** — renown, personality, presence, social connections.
- **Loss** — something specific and unique: a finger, a soul, a Relic.

Costs may be reduced or waived by skills, connections, or force of will: the Warden states the
risk, the PC makes a **WIL save**, and on a success the cost is reduced or avoided entirely.

**Downtime Actions** (the Warden may add custom ones):

- **Research** — requires a clearly formulated question drawn from play plus a **Source** (person,
  place, faction, or entity holding part or all of the answer). Finding a Source may itself cost a
  Downtime Action, with no guarantee of success. The Warden then sets Milestones and Costs.
- **Training** — improve a skill with an item or ability, with clear narrative or mechanical
  results. Requires a precise description of the improvement plus a **Master** to train with, and
  the inspiration must come from play. Worked examples show what mechanical rewards look like:
  *The Two-Handed Parry* (fighting with one hand free temporarily increases HP by **1d4**);
  *Herbology* (as a Downtime Action, craft a Healing Salve restoring **4 STR**); *Troutmaster*
  (Rations gathered near cold freshwater step up one die, 1d4 → 1d6).
- **Strengthening Ties** — foster a connection with an NPC or Faction toward a specific intent
  (trust, mended friendship, membership, alliance). The Warden provides Milestones and Costs; each
  completed Milestone changes the relationship.

---

## 9. Advancement / Growth

Cairn 2e has **no XP, no levels, and no class progression**. The Warden's Guide *Growth* chapter
is explicit: characters are not rewarded for killing monsters, looting treasure, or exploring new
places. Growth is a Warden ruling attached to a specific fictional experience.

Mechanically, the only *codified* stat changes in the rules are:

1. **Scars** (§6) — the one systematic, table-driven source of permanent max-HP and max-attribute
   increases.
2. **Downtime Training** — Milestone-and-Cost driven, yielding a Warden-authored ability
   (the examples above show the shape and typical magnitude).
3. Ad-hoc Warden rulings triggered by play: a new ability, a re-rolled attribute (keep if higher),
   a waived save requirement, a permanent bodily change with an upside and a cost.

**Principles for Growth** (paraphrased): growth is never arbitrary and always tied to a specific
fictional experience; becoming *interesting* matters more than becoming *capable*; the experience
must have affected the character significantly; growth opportunities are placed everywhere; growth
happens in play as often as in Downtime; growth is not a reward but the logical result of actions;
it most often follows interaction with something the character does not understand; changes may be
unwanted or carry a cost.

**Triggers** — a framework: a good trigger requires the character to engage in **at least two of**

- a focused, consistent pattern of behavior around a single objective,
- taking an obvious risk with potentially serious consequences, especially with an unknown outcome,
- interacting with a unique item, creature, or entity.

Seven worked example categories are given (interacting with something not understood; long-term
exposure to a Spellbook or Relic; forging a relationship with a being of great power; overcoming a
long-time woe or foe; injury or contamination; learning through trial and error; success or
failure despite a natural talent). **The example narratives are elided**; they establish magnitude,
not rules.

---

## 10. Marketplace (prices in gold pieces)

**Armor** — Shield (+1) 10 · Helmet (+1) 10 · Gambeson (+1) 15 · Brigandine (1 Armor, bulky) 20 ·
Chainmail (2 Armor, bulky) 40 · Plate (3 Armor, bulky) 60.

**Weapons** — Dagger/Cudgel/Sickle/Staff etc. (**d6**) 5 · Spear/Sword/Mace/Axe/Flail etc.
(**d8**) 10 · Halberd/War Hammer/Long Sword etc. (**d10, bulky**) 20 · Sling (**d6**) 5 · Bow
(**d6, bulky**) 20 · Crossbow (**d8, bulky**) 30.

**Transport** — Cart (**+4 slots, bulky**) 30 · Wagon (**+8 slots, slow**) 200 · Horse (**+4
slots**) 75 · Mule (**+6 slots, slow**) 30 · Carriage Seat 5 · Ship's Passage 10.

**Upkeep & Recovery** — Room & Board (per night) 10 · Private Room & Board (fits 4) 35 · Stable &
Feed (per night) 5 · **Medical Healing 50** · **Rations (3 uses) 10** · Animal Feed (3 uses,
bulky) 5.

**Hirelings (per day)** — Alchemist 30 · Animal Handler 5 · Blacksmith 15 · Bodyguard 10 · Local
Guide 5 · Lockpick 10 · Navigator 10 · Sailor 5 · Scholar 20 · Tracker 5 · Trapper 5 · Veteran
Bodyguard 20.

**Gear** — 48 entries, each price plus slot/use qualities. Mechanically notable ones:
**Bandages (3 uses) 30** (stabilize critical damage), **Torch (3 uses) 5**, **Lantern 10**,
**Oil Can (6 uses) 10**, **Rope (25ft) 5**, **Chain (10ft) 10**, **Pole (10ft) 5**,
**Trap (d6 STR damage) 35**, Antitoxin 20, Sedative 30, Fire Oil 10, Caltrops 10, Net 10,
Grappling Hook 25, Spyglass 40, Compass 75, Tent (fits 2, bulky) 20, Thieving Tools 25,
Chalk (petty) 1, Gloves (petty) 20, Whistle (petty) 15, Smoking Pipe (petty) 15,
Wilderness Clothes (petty) 15, Book 50, Parchment (3 uses) 10. **Remaining gear rows are
ordinary equipment at 5-50gp and are elided.**

### Hirelings

To create a hireling: pick a role from the Hirelings table, **roll 3d6 for each attribute and 1d6
for HP**, give equipment appropriate to their station, then roll on the Character Traits tables.
Alternatively pick a background and name from Character Creation, roll (or choose) that
background's tables, then roll Rations, Gold Pieces, Attributes, HP and age.

---

## 11. Warden's Guide (out of scope — summary only)

The Warden's Guide is a 27-chapter GM toolkit, not player-facing rules. Part 1 (World Building)
covers Setting Seeds, Factions, Topography, Dungeon Seeds, Forest Seeds. Part 2 (Warden's Tools)
covers the Bestiary, Creating Monsters, Naming Procedures, **Growth** (extracted in §9 above
because it is the closest thing to an advancement system), Spellbooks, and the Reliquary. Part 3
(Advice & Examples) covers Creating Backgrounds, Pointcrawls, FAQ on the example party, and
worked-example chapters expanding Dungeon Exploration, Detachments, Wilderness Exploration, Bonds
and Omens, Knowledge and Perception, Saves, Variable Difficulty, and Combat — these add principles
and play examples, **not new mechanics**. It closes with the setting of Vald, NPC tables, and a
bibliography. Everything in Part 1 and the monster/spell/relic content of Part 2 is generative
content the engine would need as data, not as rules.

---

## Deviations in this repo

Every divergence between `src/aidm/engines/cairn2e/` and the rules above, with the reason it
stands. Nothing diverges silently: a rule not listed here is implemented as printed. Omens and
the eight Character Trait tables are published *content* with no mechanical effect; their absence
is scenario-authoring scope, not a deviation.

1. **The turn loop and the Director stand in for Cairn's procedural scaffolding.** The plan
   resolves at most one action — a `save` or an `attack` — and the dungeon, wilderness and
   downtime cycles are turn structure the app already provides. With them go every procedure
   they drive: watches, weather, path and terrain difficulty, getting lost, the two d6 event
   tables, Wilderness Actions, Downtime's Milestones and Costs, rest and Make Camp, ammunition,
   a torch's burn-down and the 40ft light radius, and the Marketplace as a shop. Rest, Make
   Camp, medical healing and a week's rest for attribute loss land as Director-written
   `counter-change` effects; torches, lanterns and rations carry `uses` the Director spends;
   prices inform authored gear and rulings; gold moves through `counter-change`; light is
   fiction.
2. **Reactions, the Die of Fate, morale and panic are the Director's rulings.** The 2d6 and 1d6
   tables are never rolled, and the engine counts no casualties and knows no group size, so
   morale and panic land as ordinary willpower saves the Director calls for.
3. **One attack, one target, one die pool.** Detachments, blast, and two weapons at once
   (`d8+d8`) are not modelled: a large group is one actor with one sheet, a blast is several
   attacks or fiction, and the `impaired`/`enhanced` modifiers plus `joined_by`'s
   roll-everything-keep-highest carry the rest when the Director sets them.
4. **Scars are rolled only for the player, and the stat change lands the moment the scar
   does**, where several SRD rows defer it to "once mended" or "when you recover". The engine
   has no downtime clock to defer to; every other actor is an NPC mechanically, and a companion
   who drops takes critical damage like any other.
5. **Growth triggers per resolved thread, not per Warden ruling, and is written as a `Trait`**
   rather than a sheet field — the same reasoning LONER-3E's deviation 1 gives. Cairn is
   classless: what a character has done and carries is what defines them, and a trait is read
   by the resolver and the Director alike.
6. **Creation is deterministic picks, not dice.** Attributes and Hit Protection come from
   pre-rolled spreads, starting gold is a fixed number per background, and a background's d6
   tables are chosen rather than rolled, their rows landing as descriptive traits that grant no
   item, companion or number — the published rows hand out statted homunculi and blunderbusses,
   and a menu of qualities is the ceiling of the creation form. `Creation.create` takes no rng,
   so the dice move into the pack as published content; newcomers created during play *are*
   rolled — `seed` gives every new actor 3d6 per attribute and 1d6 HP, Cairn's own hireling
   recipe. Six of the twenty backgrounds ship, and only Aurifex's gear is the published list:
   the other nineteen pages are elided from this extraction, and inventing their contents under
   their real names would misattribute them.
7. **Bonds are not implemented.** Their rows carry live mechanics — item grants, slot costs,
   Fatigue absorption, condition immunities — and are the one content elision with real rules
   in it.
8. **The Backpack is not a container of its own**: a character has ten flat slots, and the
   "four or five carried comfortably" guidance is fiction the Director weighs.
9. **Deprivation does not tick a Fatigue per day.** There is no calendar here; the engine
   enforces the half of the rule it can see — a deprived character recovers no HP, attribute or
   slot, and any effect that would is refused — and the daily Fatigue is the Director's to
   write.
10. **Armor a character carries is armor they are wearing.** The SRD counts a shield only while
    it is held, and nothing here distinguishes carried from readied.

## Engine package

How this SRD maps onto `src/aidm/engines/cairn2e/`:

- **Sheet and items** (`mechanics.py`): a `Sheet` carries `background`, `strength`/`dexterity`/
  `willpower` and `hp` as bounded Counters, `gold`, `fatigue`, a natural `armor` (capped at 3),
  and a `growths` ledger the advancement subsystem reads but the Director never sees. An
  `ItemRules` carries `slots` (0 petty, 1 ordinary, 2 bulky), a `damage` die, `armor`, and an
  optional `uses` Counter; both shapes validate through one discriminating `RULES` adapter since
  Cairn authors rules for items as well as actors. `slots_used` sums carried items plus Fatigue
  against the flat `MAX_SLOTS = 10`; `check_load` empties HP to 0 at exactly ten and refuses an
  eleventh; `collapsed` writes the `dead`/`paralysed`/`delirious` trait the instant an attribute
  hits 0; the `deprived` trait blocks any `counter-change` that would recover HP, an attribute or
  a slot.
- **Plan** (`actions.py`): `TurnPlan.action` is `Save | Attack | None`, discriminated on `act`. A
  `Save` names the actor, the attribute, and the risk in one line. An `Attack` names attacker,
  target, an optional carried `weapon_id` (null is an unarmed d4), a `modifier` (`impaired` d4 /
  `enhanced` d12), and `joined_by` for other attackers on the same target. `SAVE_LABELS` is
  `pass`/`fail`; `ATTACK_LABELS` is `blocked`/`hit`/`wounded`/`down`.
- **Resolver** (`actions.py`): `resolve_save` rolls d20 against the attribute through `saved()`
  (1 always passes, 20 always fails). `resolve_attack` builds the dice pool from the weapon (or
  modifier) faces of the attacker and everyone in `joined_by`, keeps the highest, and subtracts
  the target's armor. Zero damage is `blocked`; damage within HP is `hit`; damage that overflows
  HP moves into strength and forces a strength save with the new score (`wounded` on a pass,
  `down` on a fail, which marks the player `critical-damage` or an NPC `dead`); strength emptied
  by the overflow is death outright, with no save owed. Damage that takes the player's HP to
  exactly 0 additionally rolls the twelve-row Scars table (`SCARS`), indexed by the HP lost in
  that blow: some rows roll a d6 location, rows 8 and 10 gate their payout behind a save, and the
  recovery roll moves a counter's maximum by `higher`, `add` or `set`.
- **What the Director carries**: `director.md` teaches the sheet shape, the inventory rule, the
  `counter-change` effect (the engine's one effect beyond world ops), when to call a save —
  including morale, panic, retreat and a spell read while deprived or in danger — and that
  reactions, the Die of Fate, and every rest/Make Camp/healing effect are its own rulings to
  write, never the engine's to roll. `advancement.md` carries Growth's trigger framework and
  worked-example magnitude for the ability a `Growth` proposal writes.
- **Creation/advancement** (`create.py`, `advance.py`, `packs/srd.json`): `Cairn2eCreation` steps
  through pack, background, an optional trait pick sized to the background's `chooses`, and a
  pre-rolled attribute spread; `create()` turns the background's gear into item entities and its
  chosen traits into character traits, and writes gold and the spread's attributes onto the
  overlay. `Cairn2eAdvancement` is a `Subsystem` that offers one `Growth` per resolved thread to
  the player and each party member who hasn't taken one yet, and records it as a `Trait` plus a
  `growths` tick. `packs/srd.json` ships four attribute spreads and six backgrounds — Aurifex,
  Barber-Surgeon, Cutpurse, Fieldwarden, Hexenbane, Marchguard — each with its gold, gear and
  three-option quirk table.

Divergences live in **Deviations in this repo** above, not here.
