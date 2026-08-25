# Cairn: Barebones Edition

## License and source

This file reproduces the complete official Cairn: Barebones Edition rules corpus in Markdown for
engine reference. The official site presents Barebones as an edition rather than as a separately
versioned SRD; “SRD” in this repository means the complete open rules reference reproduced below.

Sources:

- the [official Barebones rules](https://cairnrpg.com/barebones/rules/introduction-to-cairn-barebones-edition/)
  and their seven sibling pages;
- the [official Markdown source directory](https://github.com/yochaigal/cairn/tree/009578e8e98f7d235daf3f884da2ea3c14e758c4/barebones/rules)
  at commit `009578e8e98f7d235daf3f884da2ea3c14e758c4` (2026-08-18);
- the [official release page](https://yochaigal.itch.io/cairn-barebones-edition).

The rules wording and tables are unchanged. Jekyll front matter was removed, heading levels were
nested under this document title, links between the original web pages were changed to local
section links, and trailing whitespace was normalized. The source's emphasis, capitalization,
punctuation, and occasional editorial quirks are preserved.

Cairn was written by [Yochai Gal](https://newschoolrevolution.com/). The
[official Cairn repository](https://github.com/yochaigal/cairn) and site state that the full text is
licensed under the [Creative Commons Attribution-ShareAlike 4.0 International
license](https://creativecommons.org/licenses/by-sa/4.0/). This repository copy is a derivative
work distributed under the same license.

---

## Introduction to Cairn Barebones Edition

Cairn Barebones Edition is an adventure game about traversing underground tunnels, decrepit castles, dark forests, and other dreadful places. Character creation is entirely random and fast, exploration is tense and rewarding, and combat is chaotic and lethal. The rules and procedures match those in the _Cairn Second Edition Player’s Guide_, but this version removes the implied setting and structured creation process. It assumes a generic fantasy world, embracing full randomness, much like the original _Cairn_. It retains full compatibility with _Cairn Second Edition_ adventures but offers an even more minimal, flexible framework for old-school play.

---

## Barebones Edition Overview & Principles

### Overview

#### Neutrality

The Warden's role is to act as a neutral arbiter and portray the rules, situations, non-player characters (NPCs), and narrative clearly.

#### Classless

A character's role or skills are not limited by a single class. Instead, the equipment they carry and their experiences define their specialty.

#### Death

Characters may be powerful, but they are also vulnerable to harm in its many forms. Death is always around the corner, but it is never random or without warning.

#### Fiction First

Dice do not always reflect an obstacle's difficulty or its outcome. Instead, success and failure are based on in-world elements and arbitrated by the Warden in dialogue with the players.

#### Growth

Characters are changed through in-world advancement, gaining new skills and abilities by surviving dangerous events and overcoming obstacles.

#### Player Choice

Players should always understand the reasons behind the choices they've made, and information about potential risks should be provided freely and frequently.

#### Principles

The Warden and the players each have guidelines that help foster a specific play experience defined by critical thinking, exploration, and an emergent narrative.

#### Shared Objectives

Players trust one another to engage with the shared setting, character goals, and party challenges. Therefore the party is typically working together towards a common goal, as a team.

### Principles for Players

#### Agency

- Attributes and related saves do not define your character. They are tools.
- Don't ask only what your character would do; ask what you would do, too.
- Be creative with your intuition, items, and connections.

#### Teamwork

- Seek consensus from the other players before barreling forward.
- Stay on the same page about goals and limits, respecting each other and accomplishing more as a group than alone.

#### Exploration

- Asking questions and listening to detail is more useful than any stats, items, or skills you have.
- Take the Warden's description without suspicion, but don't shy away from seeking more information.
- There is no single correct way forward.

#### Talking

- Treat NPCs as if they were real people, and rely on your curiosity to safely gain information and solve problems.
- You'll find that most people are interesting and will want to talk things through before getting violent.

#### Caution

- Fighting is a choice and rarely a wise one; consider whether violence is the best way to achieve your goals.
- Try to stack the odds in your favor, and retreat when things seem unfavorable.

#### Planning

- Think of ways to avoid your obstacles through reconnaissance, subtlety, and fact-finding.
- Do some research, and ask around about your objectives.

#### Ambition

- Set goals, and use your meager means to take steps forward.
- Expect nothing. Earn your reputation.
- Keep things moving forward, and play to see what happens.

### Principles for Wardens

#### Information

- Provide useful information about the game world as the characters explore it.
- Players do not need to roll dice to learn about their circumstances.
- Be helpful and direct with your answers to their questions.
- Respond honestly, describe consistently, and always let them know they can keep asking questions.

#### Difficulty

- Default to context and realism rather than numbers and mechanics.
- If something the players want to do is sincerely impossible, no roll will allow them to do it.
- Is what the player describes and how they leverage the situation sensible? Let it happen.
- Saves cover a great deal of uncertain situations and are often all that is necessary for risky actions.

#### Preparation

- The game world is organic, malleable and random. It intuits and makes sharp turns.
- Use random tables and generators to develop situations, not stories or plots.
- NPCs remember what the PCs say and do, and how they affect the world.
- NPCs don't want to die. Infuse their own self-interest and will to live into every personality.

#### Narrative Focus

- Emergent experience of play is what matters, not math or character abilities. Give the players weapon trainers and personal quests to facilitate improvement and specialization.
- Pay attention to the needs and wants of the players, then put realistic opportunities in their path.
- A dagger to your throat will kill you, regardless of your expensive armor and impressive training.

#### Danger

- The game world produces real risk of pain and death for the player characters.
- Telegraph serious danger to players when it is present. The more dangerous, the more obvious.
- Put traps in plain sight and let the players take time to figure out a solution.
- Give players opportunities to solve problems and interact with the world.

#### Treasure

- A Treasure is specific to the environment from where it is recovered. It tells a story.
- Treasure is highly valuable, almost always bulky, and rarely useful beyond its worth and prestige.
- Relics are not Treasure, though they are useful and interesting.
- Use Treasure as a lure to exotic locations under the protection of intimidating foes.

#### Choice

- Give players a solid choice to force outcomes when the situation lulls.
- Use binary "so, A or B?" responses when their intentions are vague.
- Work together using this conversational method to keep the game moving.
- Ensure that the player character's actions leave their mark on the game world.

---

## Barebones Core Rules

### Player Characters

#### Attributes

Player Characters (PCs) have three **Attributes**:

- **Strength (STR)**: Used for saves requiring physical power, like lifting gates, bending bars, resisting poison, etc.
- **Dexterity (DEX)**: Used for saves requiring poise, speed, reflexes, dodging, climbing, sneaking, balancing, etc.
- **Willpower (WIL)**: Used for saves to persuade, deceive, interrogate, intimidate, charm, provoke, manipulate spells, etc.

> Attributes are not universal descriptors. A character with a low STR is not necessarily hopelessly weak; they can still attempt to lift a heavy door or survive a deadly fight! Their risk is simply higher.

##### Attribute Loss

- If a PC takes damage outside of combat, they should instead receive damage to an Attribute, typically STR.
- If a PC's STR is reduced to 0, they die. If their DEX is reduced to 0, they are paralyzed. If their WIL is reduced to 0, they are delirious. Complete DEX and WIL loss renders the character unable to act until they are restored through extended rest or by extraordinary means.

#### Hit Protection

- Hit Protection (HP) reflects a character's ability to avoid damage in combat.
- This measurement does _not_ indicate a character’s health or fortitude, nor do they lose it for very long. See [Healing & Recovery](#healing--recovery).

##### Healing & Recovery

- Resting for a few moments and having a drink of water restores lost HP but may leave the party exposed. Bandages can stabilize a character that has taken critical damage.
- Attribute loss (see **Critical Damage**) can usually be restored with a week's rest, facilitated by a healer or other appropriate source of expertise.
- Some healing services are free, while magical or more expedient means of recovery may come at a cost.

### Armor

- Before calculating damage to HP, subtract the target's **Armor** value from the result of damage rolls.
- Shields and similar armor provide a bonus defense (e.g. +1 Armor), but only while the item is held or worn. Some may also provide additional benefits, depending on the fiction.
- A PC, NPC, or monster cannot have more than 3 Armor.

### Inventory

- Characters have a total of ten inventory slots but can only carry four or five items comfortably without the help of bags, backpacks, horses, carts, etc.
- Each PC starts with a **Backpack** that can hold up to six slots of items or **Fatigue**. Carts (which must be pulled with both hands), horses, or mules can make a huge difference in how much a PC can bring with them on an adventure. **Hirelings** can also be paid to carry equipment.
- Inventory is abstract, dependent only on the fiction as adjudicated by the Warden. Anyone carrying a full inventory (i.e. filling all 10 slots) is reduced to 0 HP. A character cannot fill more than ten slots.

#### Inventory Slots

- Most items take up one slot unless otherwise indicated.
- _Petty_ items do not take up any slots. _Bulky_ items take up **two** slots.
- A bag of coins worth less than 100gp is _petty_ and does not occupy a slot.

### Deprivation & Fatigue

- A PC that lacks a crucial need (such as food or rest) is **Deprived**. Anyone **Deprived** for more than a day adds **Fatigue** to their inventory, one for each day. A **Deprived** PC cannot recover HP, Attributes, or item slots from **Fatigue**.
- A PC may also be forced to add **Fatigue** after casting spells or due to events occurring in the fiction. Each Fatigue occupies one slot and lasts until the PC is able to recuperate (such as with a full night’s rest in a safe spot).
- If a character is forced to add **Fatigue** to their inventory but they have no free slots, they must drop an item from their inventory.

### Saves & Risk

### Saves

- A save is a roll to avoid negative outcomes from risky choices. Characters roll a d20 and compare the results to the appropriate attribute. If they roll equal to or under that attribute, they succeed. Otherwise, they fail. A 1 is always a success, and a 20 is always a failure.
- If two opponents are each trying to overcome the other, whoever is most at risk should save.
- If two characters need to take an action together, whoever is most at risk should save (usually the character with the lowest relevant Attribute).

#### Die of Fate

- Optionally, roll 1d6 whenever the outcome of an event is uncertain or to simulate an element of randomness and chance.
- A roll of 4 or more generally favors the PCs, while a roll of 3 or under usually means bad luck for the PCs.

### Magic

#### Spellbooks

- **Spellbooks** contain a single spell and take up one slot. They cannot be easily transcribed or created; instead they are recovered from places like tombs, dungeons, and manors.
- Spellbooks sometimes display unusual properties or limitations, such as producing a foul or unearthly smell when opened, possessing an innate intelligence, or being legible only when held in moonlight.
- Spellbooks will attract the attention of those who seek the arcane power within, and it is considered dangerous to display them openly.

#### Casting Spells

- Anyone can cast a spell by holding a Spellbook in both hands and reading its contents aloud. They must then add a **Fatigue** to inventory.
- Given time and safety, PCs can _enhance_ a spell's impact (e.g., affecting multiple targets, increasing its power, etc.) without any additional cost.
- If the PC is _deprived_ or in danger (such as during combat), the Warden may require a PC to make a WIL save to avoid any ill-effects from casting the spell. Consequences of failure are on par with the intended effect and may result in added **Fatigue**, the destruction of the Spellbook, injury, and even death.

#### Scrolls

**Scrolls** are similar to Spellbooks, however:

- They are _petty_.
- They do not cause **Fatigue**.
- They disappear after one use.

#### Relics

**Relics** are items imbued with a magical spell or power. They do not cause Fatigue. Relics usually have limited use, as well as a **Recharge** condition.

### Non-Player Characters

#### Hirelings

- Adventuring parties can recruit hirelings, relying on their unique skills, knowledge, and training to aid in expeditions.
- To create a hireling, choose an appropriate role from the [Hirelings](#hirelings-per-day) table in the Marketplace. Roll 3d6 for each attribute and 1d6 for their HP. Give them **equipment** appropriate to their station, then roll on the Character Traits tables to further flesh them out.
- Alternatively, follow the [**Character Creation**](#barebones-edition-character-creation) process but select the appropriate background, name, and gear for the character.

#### Reactions

When the PCs encounter an NPC whose reaction to the party is not obvious, the Warden may roll 2d6 and consult the following table:

|         |      |         |      |         |
| :-----: | :--: | :-----: | :--: | :-----: |
|    2    | 3-5  |   6-8   | 9-11 |   12    |
| Hostile | Wary | Curious | Kind | Helpful |

### Combat

#### Rounds

- A **Round** is roughly ten seconds of in-game time and proceeds with each side taking turns. Each round starts with any PC that is able to act, followed by their opponents. _The result of each side's actions occur simultaneously_.
- During the _first round of combat_, each PC must make a DEX save in order to act. Special circumstances, abilities, items, or skills may negate this requirement. PCs that fail their save _lose their turn_ for this round.
- Their opponents then take their turn, and the first round ends. The next round begins with the PCs taking their turn, followed by their opponents, and so on until combat has ended with one side defeated or fled.

#### Actions

On their turn, a character may move up to 40ft and take up to one action. This may be casting a spell, attacking, moving for a second time, or some other reasonable action. Each round, the PCs declare what they are doing before dice are rolled. If a character attempts something risky, the Warden calls for a save for appropriate players or NPCs.

#### Attacking & Damage

- The attacker rolls their weapon die and subtracts the target's armor, then deals the remaining total to their opponent's HP. Attacks in combat automatically hit.
- If multiple attackers target the same foe, roll all damage dice and keep the single highest result. All actions are declared before being resolved.
- If an attack would take a PC's HP exactly to 0, refer to the [Scars](#scars-table) table to see how they are uniquely impacted.

#### Attack Modifiers

- If fighting from a position of weakness (such as through cover or with bound hands), the attack is _Impaired_, and the attacker must roll 1d4 damage regardless of the attacks damage die. Unarmed attacks always do d4 damage.
- If fighting from a position of advantage (such as against a helpless foe or through a daring maneuver), the attack is _Enhanced_, allowing the attacker to roll 1d12 damage instead of their normal die.
- Attacks with the _Blast_ quality affect all targets in the noted area, rolling separately for each affected character. This can be anything from explosions to a dragon’s breath or the impact of a meteorite. If unsure how many targets can be affected, _roll the related damage die for a result_.
- If attacking with two weapons at the same time, roll both damage dice and keep the single highest result (denoted with a plus symbol, e.g. d8+d8).

#### Critical Damage

- Damage that reduces a target's HP below zero is subtracted _from their STR_ by the amount of damage remaining. The target must then immediately make a STR save to avoid taking **Critical Damage**, using their _new STR score_. On a success, the target is still in the fight (albeit with a lower STR score) and must continue to make critical damage saves when incurring damage.
- Any PC that suffers Critical Damage cannot do anything but crawl weakly, grasping for life. If given aid (such as bandages), they will stabilize. If left untreated, they die within the hour. NPCs and monsters that fail a Critical Damage save are considered dead, per the **Warden's** discretion. Additionally, some enemies will have special abilities or effects that are triggered when their target fails a critical damage save.

#### Character Death

- When a character dies, the player should create a new character or take control of a hireling. They immediately join the party in order to reduce downtime.

#### Detachments

- Large groups of similar combatants fighting together are treated as a single _Detachment_. When a _detachment_ takes **Critical Damage**, it is routed or significantly weakened. When it reaches 0 STR, it is destroyed.
- Attacks against detachments by individuals are _impaired_ (excluding _blast_ damage). Attacks against individuals by detachments are _enhanced_ and deal _blast_ damage.

#### Retreat

- Running away from a dire situation always requires a successful DEX save, as well as a safe destination to run to.

#### Morale

- Enemies must pass a WIL save to avoid fleeing when they take their first casualty and again when they lose half their number.
- Some groups may use their leader's WIL in place of their own. Lone foes must save when they're reduced to 0 HP.
- Morale does not affect PCs.

#### Ranged Attacks

- Ranged weapons can target any enemy near enough to see the whites of their eyes. Attacks against especially distant targets are _Impaired_.
- Ammunition is not tracked unless otherwise specified.

#### Scars

If damage to a PC would reduce their HP to exactly 0, look up the result on the table below based on the _amount of HP lost in the attack_. For example, if a PC went from 3 HP to 0 HP, they would look at entry #3 (Walloped).

##### Scars Table

|             |                                                                                                                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **HP Lost** | **Result**                                                                                                                                                                                                                |
| 1           | Lasting Scar: Roll 1d6. 1: Neck, 2: Hands, 3: Eye, 4: Chest, 5: Legs, 6: Ear. Roll 1d6. If the total is higher than your max HP, take the new result.                                                                     |
| 2           | Rattling Blow: You’re disoriented and shaken. Describe how you refocus. Roll 1d6. If the total is higher than your max HP, take the new result.                                                                           |
| 3           | Walloped: You’re sent flying and land flat on your face, winded. You are deprived until you rest for a few hours. Then, roll 1d6. Add that amount to your max HP.                                                         |
| 4           | Broken Limb: Roll 1d6. 1-2: Leg, 3-4: Arm, 5: Rib, 6: Skull. Once mended, roll 2d6. If the total is higher than your max HP, take the new result.                                                                         |
| 5           | Diseased: You’re afflicted with a gross, uncomfortable infection. When you get over it, roll 2d6. If the total is higher than your max HP, take the new result.                                                           |
| 6           | Reorienting Head Wound: Roll 1d6. 1-2: STR, 3-4: DEX, 5-6: WIL. Roll 3d6. If the total is higher than your current attribute, take the new result.                                                                        |
| 7           | Hamstrung: You can barely move until you get serious help and rest. After recovery, roll 3d6. If the total is higher than your max DEX, take the new result.                                                              |
| 8           | Deafened: You cannot hear anything until you find extraordinary aid. Regardless, make a WIL save. If you pass, increase your max WIL by 1d4.                                                                              |
| 9           | Re-brained: Some hidden part of your psyche is knocked loose. Roll 3d6. If the total is higher than your max WIL, take the new result.                                                                                    |
| 10          | Sundered: An appendage is torn off, crippled, or useless. (The Warden will tell you which.) Then make a WIL save. If you pass, increase your max WIL by 1d6.                                                              |
| 11          | Mortal Wound: You are deprived and out of action. You die in one hour unless healed. Upon recovery, roll 2d6. Take the new result as your max HP.                                                                         |
| 12          | Doomed: Death seemed ever so close, but somehow you survived. If your next save against critical damage is a fail, you die horribly. If you pass, roll 3d6. If the total is higher than your max HP, take the new result. |

---

## Barebones Edition Procedures

### Dungeon Exploration

#### The Basics

- The dungeon exploration cycle (see below) is divided into a series of **Turns**, **Actions**, and their consequences.
- On their **turn**, a character can move a distance equal to their torchlight's perimeter (about 40ft), and perform one **action**. Players can use their **action** to move up to three times that distance though that will increase the chance of triggering a roll on the [**Dungeon Events**](#dungeon-events) table.
- The **Warden** should present obvious information about an area and its dangers freely and at no cost. Moving quickly or without caution may increase the chance of encountering a wandering monster, springing a trap, or triggering a roll on the [**Dungeon Events**](#dungeon-events) table.

> Although the term "dungeon" is used here, it can mean any dangerous locale (mansions, farmhouses, adventure site, etc).

#### Dungeon Exploration Cycle

1. The **Warden** describes the party's surroundings and any immediate dangers (combat, traps, surprises, etc.). The players then declare their character's intended movements and **actions**.
2. The Warden resolves the **actions** of each character simultaneously, along with any **actions** that are already in progress. Remember, the Die of Fate can be a useful tool whenever the Warden is in doubt!
3. The players record any loss of resources and any new conditions (i.e. item use, _deprivation_, etc). The cycle then begins again. If appropriate, the **Warden** should roll on the [**Dungeon Events**](#dungeon-events) table. Keep common sense in mind when interpreting the results!

#### Dungeon Events

Exploring a dungeon is always dangerous, and time must always be weighed against the risk of awakening the location's denizens, natural hazards, and worse.
When the party:

- Spends more than one dungeon cycle in a single room or location
- Moves quickly or haphazardly through a room
- Moves into a new area, level, or zone
- Creates a loud disturbance

**Roll on the table below.**

|       |                 |                                                                                                           |
| :---: | :-------------: | :-------------------------------------------------------------------------------------------------------: |
| **1** |  **Encounter**  |    Roll on an encounter table. Possibly **hostile**. (See [Reactions](#reactions).)    |
| **2** |    **Sign**     |                  A clue, spoor, track, abandoned lair, scent, victim, etc is discovered.                  |
| **3** | **Environment** |      Surroundings shift or escalate. Water rises, ceilings collapse, a ritual nears completion, etc.      |
| **4** |    **Loss**     | Torches are blown out, an ongoing spell fizzles, etc. The party must resolve the effect before moving on. |
| **5** | **Exhaustion**  |   The party must rest (triggering another roll on this table), add a **Fatigue**, or consume a ration.    |
| **6** |    **Quiet**    |                          The party is left alone (and safe) for the time being.                           |

#### Actions

- **Actions** are any non-passive activities, such as _searching for traps_, _forcing open a door_, _listening for danger_, _disarming a trap_, _engaging an enemy in combat_, _casting a spell_, _dodging a trap_, _running away_, _resting_, etc.
- Some **actions** have special rules (see below), while others may take multiple **turns** to complete.
- Loud or noticeable **actions** may also trigger an **encounter** with the dungeon's denizens.

##### Searching

- A character can spend a **turn** performing an _exhaustive_ search of **one** object or location in an area, revealing any relevant hidden treasure, traps, secret doors, etc.
- Larger rooms and difficult or complex dungeon terrain may take a few **turns** to properly search.
- Searching a room _first_ is a safer way to explore the dungeon, but it has a steep cost: time.

##### Resting

- A character can spend a turn **resting** to restore all **HP**.
- A light source and a _safe location_ are required to **rest**. Present or oncoming danger makes **rest** impossible.
- **Resting** does not restore **Fatigue**, as it is impossible to safely **Make Camp** in a dungeon.

### Panic

- A character that is surrounded by enemies, enveloped by darkness, or facing their greatest fears may experience _panic_. A **WIL** **save** is typically required to avoid losing control and becoming _panicked_.
- A _panicked_ character must make a **WIL** **save** to overcome their condition as an **action** on their **turn**.
- A _panicked_ character has 0 **HP**, does not act in the first round of combat, and all of their attacks are _impaired_.

#### Dungeon Elements

##### Light
- Torches and other radial sources of light illuminate 40ft of dungeon and beyond that only a dim outline of objects. Torches last until they are put out by a character or their environment.
- A torch can be lit 3 times before permanently degrading. A lantern can be relit 6 times per oil can, but requires more inventory slots.
- Characters without a light source may suffer from _panic_ until their situation is remedied.

##### Doors

- Doors and entryways may be locked, stuck, or blocked entirely. Characters can try to force a door open (or wedge it shut) using available resources (spikes, glue) or through raw ability.
- The party's marching order determines who is most impacted by whatever lies beyond a door.
- A character can detect, through careful observation (listening, smelling, etc.), signs of life and other hazards through nearby doors and walls.

##### Traps

- A cautious character should be presented with any and all information that would allow them the opportunity to _avoid_ springing a trap. An unwitting character will trigger a trap according to the fiction, or otherwise will have a 2-in-6 chance.
- **Traps** can usually be detected by carefully **searching** a room.
- Damage from traps is taken from Attributes (usually **STR** or **DEX**) and _not_ from **HP**. Armor can reduce damage, but only if applicable (e.g. a shield would not reduce damage from noxious gas).

### Wilderness Exploration

#### Watches

- A day is divided into three **watches**, called _morning_, _afternoon_, and _night_.
- Each character can choose _one_ [**Wilderness Action**](#wilderness-actions) per **watch**.
- If the characters split up, each group is treated as an independent entity.

#### Points

- Potential destinations on a map are called **points**.
- One or more **watches** may be required to journey between two **points** on a map, depending on the path, terrain, weather, and party status.
- The party has a rough idea of the challenges involved to get to their destination, but rarely any specifics.

#### Travel Duration

Travel time in Cairn is counted in watches, divided into three eight-hour segments per day. However, as most parties elect to spend the third watch of the day resting, one can use "days" as a shorthand for travel time.

To determine the distance between two points, combine all penalties from the path, terrain, and weather difficulty tables, taking into account any changes to those elements along the route. For travel via waterways, refer to the surrounding terrain difficulty. For especially vast terrain, assign a penalty of up to +2 watches to the journey.

The weather, terrain, darkness, injured party members, and other obstacles can impact travel or even make it impossible! In some cases, the party may need to add **Fatigue** or expend resources in order to sustain their pace. Mounts, guides, and maps can increase the party’s travel speed or even negate certain penalties.

#### Path Difficulty

|            |             |                          |
| ---------- | ----------- | ------------------------ |
| **Path**   | **Penalty** | **Odds of Getting Lost** |
| Roads      | None        | None                     |
| Trails     | +1 Watch    | 2-in-6                   |
| Wilderness | +2 Watches  | 3-in-6                   |

|                   |             |
| ----------------- | ----------- |
| **Path Distance** | **Penalty** |
| Short             | +1 Watch    |
| Medium            | +2 Watches  |
| Long              | +3 Watches  |

### Terrain Difficulty

|                |                               |             |                                                                                                       |
| -------------- | ----------------------------- | ----------- | ----------------------------------------------------------------------------------------------------- |
| **Difficulty** | **Terrain**                   | **Penalty** | **Factors**                                                                                           |
| **Easy**       | **Plains, plateaus, valleys** | none        | _Safe areas for rest, fellow travelers, good visibility_                                              |
| **Tough**      | **Forests, deserts, hills**   | +1 Watch    | _Wild animals, flooding, broken equipment, falling rocks, unsafe shelters, hunter's traps_            |
| **Perilous**   | **Mountains, jungles, swamp** | +2 Watches  | _Quicksand, sucking mud, choking vines, unclean water, poisonous plants and animals, poor navigation_ |

#### Weather

Each day, the Warden should roll on the weather table for the appropriate season. If the "**Extreme**" weather result is rolled twice in a row, the weather turns to "**Catastrophic**". A squall becomes a hurricane, a storm floods the valley, etc.

##### Weather Type

|        |            |            |            |            |
| :----: | :--------: | :--------: | :--------: | :--------: |
| **d6** | **Spring** | **Summer** |  **Fall**  | **Winter** |
| **1**  |    Nice    |    Nice    |    Fair    |    Fair    |
| **2**  |    Fair    |    Nice    |    Fair    | Unpleasant |
| **3**  |    Fair    |    Fair    | Unpleasant | Inclement  |
| **4**  | Unpleasant | Unpleasant | Inclement  | Inclement  |
| **5**  | Inclement  | Inclement  | Inclement  |  Extreme   |
| **6**  |  Extreme   |  Extreme   |  Extreme   |  Extreme   |

##### Weather Difficulty

|                  |                                                                                                         |                                                           |
| :--------------: | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
|   **Weather**    | **Effect**                                                                                              | **Examples**                                              |
|     **Nice**     | Favorable conditions for travel.                                                                        | _Clear skies, sunny_                                      |
|     **Fair**     | Favorable conditions for travel.                                                                        | _Overcast, breezy_                                        |
|  **Unpleasant**  | Add a **Fatigue** _or_ add one **watch** to the journey.                                                | _Gusting winds, rain showers, sweltering heat, chill air_ |
|  **Inclement**   | Add a **Fatigue** _or_ add **+1 watch**. Increase terrain **Difficulty** by a step.  | _Thunderstorms, lightning, rain, muddy ground_           |
|   **Extreme**    | Add a **Fatigue** _and_ add **+1 watch**. Increase terrain **Difficulty** by a step. | _Blizzards, freezing winds, flooding, mud slides_         |
| **Catastrophic** | Most parties cannot travel under these conditions.                                                      | _Tornados, tidal waves, hurricane, volcanic eruption_     |

#### Wilderness Exploration Cycle

1. The **Warden** describes the current **point** or **region** on the map and how the path, weather, terrain, or party status might affect **travel speed**. The party plots or adjusts a given course towards their destination.
2. Each party member chooses a single **Wilderness Action**. The **Warden** narrates the results and then rolls on the [**Wilderness Events**](#wilderness-events) table. The party responds to the results.
3. The **players** and the **Warden** record any loss of resources and new conditions (i.e. torch use, _deprivation_, etc), and the cycle repeats.

#### Wilderness Events

|       |                 |                                                                                                                                                                                                                            |
| ----- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1** | **Encounter**   | Roll on an encounter table for that terrain type or location. Don’t forget to roll for NPC [reactions](#reactions) if applicable.                                                                               |
| **2** | **Sign**        | The party discovers a clue, spoor, or indication of a nearby encounter, locality, hidden feature, or information about a nearby area.                                                                                      |
| **3** | **Environment** | A shift in weather or terrain.                                                                                                                                                                                             |
| **4** | **Loss**        | The party is faced with a choice that costs them a resource (rations, tools, etc), time, or effort.                                                                                                                        |
| **5** | **Exhaustion**  | The party encounters a barrier, forcing effort, care or delays. This might mean spending extra time (and an additional **Wilderness Action**) or adding **Fatigue** to the PC's inventory to represent their difficulties. |
| **6** | **Discovery**   | The party finds food, treasure, or other useful resources. The **Warden** can instead choose to reveal the primary feature of the area.                                                                                    |

#### Wilderness Elements

##### Night

- The party can choose to travel during the night and rest during the day, but night travel is far slower and more treacherous!
- Traveling at night is always more dangerous! The **Warden** should roll _twice_ on the [**Wilderness Events**](#wilderness-events) table.
- Some terrain and weather may be easier to traverse at night (desert, for example). The **Warden** should balance these challenges along with any other.

##### Sleep

- The last **watch** of the day is typically reserved for the [**Make Camp**](#make-camp) action.
- Characters typically need to sleep each day. Anything beyond a minor interruption can negate or cancel the benefits of sleep.
- If the party skips the **Make Camp** action, they each add a **Fatigue** to their inventory and are _deprived_. Additionally, traveling when sleep-deprived raises the terrain **Difficulty** by a step (i.e. _Easy_ becomes _Tough_).

##### Light

- Torches and other radial sources of light illuminate 40ft ahead of the party, but beyond that only provides a dim outline of objects.
- Characters without a light source may suffer from _panic_ until their situation is remedied.
- Environmental conditions (sudden gusts of wind, dust, water, etc.) can easily blow out a torch.

###### Light Sources

- A torch can be lit 3 times before degrading.
- A lantern can be relit indefinitely but requires a separate oil can (6 uses).

#### Wilderness Actions

##### Travel

- Travel begins. Obvious locations, features, and terrain of nearby areas are revealed according to their distance. This action is typically taken by the entire party as one.
- The party rolls 1d6 to see if they get lost along the way. This risk can increase or decrease, depending on path **Difficulty**, maps, party skills, and guides.
- If lost, the party may need to spend a **Wilderness Action** to recover their way. Otherwise, the party reaches the next **point** along their route.

> Remember to compare the results of getting lost to the relevant path **Difficulty**.

##### Explore

- One or more party members search a large area, searching for hidden features, scouting ahead, or treading carefully.
- A Location (shelter, village, cave, etc.) or Feature (geyser, underground river, beached ship, etc.) is discovered.
- The **Travel** action is still required to _leave_ the current area, even if it has been completely explored.

##### Supply

- One or more party members may hunt, fish, or forage for food, collecting 1d4 **Rations** (3 uses each). The chance of a greater bounty increases with each additional participant (e.g. 1d4 becomes 1d6, up to a maximum of 1d12).
- Relevant experience or equipment may also increase the bounty collected.
- The party may encounter homes and small villages, spending gold and a full **watch** to resupply.

##### Make Camp

- The party stops to set up camp in the wilds. Each party member (and their mounts) consumes a **Ration**.
- A **lookout rotation** is set so that the party can sleep unmolested. A smaller party may need to risk sleeping unguarded or switch off sleeping over multiple days.
- Party members that were able to rest remove all of **Fatigue** from their inventory.

### Downtime

Between game sessions, players can engage in a variety of activities such as research, following up on leads, improving skills, or building relationships. A PC is limited to one **Downtime Action** at a time. These actions cannot be undertaken in unsafe conditions or while a character is in recovery. A character cannot perform an action if it would put their safety at risk.

#### Milestones

For activities requiring multiple steps, the **Warden** assigns 1-5 **Milestones** for players to track progress. Each **Milestone** represents a comprehensive, non-interactive task. The **Warden** may present different strategies to achieve these goals, each with distinct **Milestones**. Depending on the unfolding events in the game, the **Warden** is also empowered to introduce new **Milestones** or discard existing ones.

#### Costs

PCs can complete individual **Milestones** by taking a **Downtime Action** and paying its respective **Cost**. If a character is unable to pay the **Cost**, they may have to find some other way to achieve their goal. A few examples of **Cost**:
- **Gold**: Direct payment of gold from a character's inventory.
- **Resources**: Non-monetary costs such as material goods, specific common items, and so on.
- **Reputation**: Betting on a character's renown, personality, presence, social connections, etc.
- **Loss**: Offering something specific and unique. A finger, a soul, a **Relic**, etc.

Some **Costs** can be reduced or disregarded through character skills, connections, or force of will. For example, a PC may have already acquired the necessary reputation to gain access to a renowned institution, and thus the **cost** is abated. On the other hand, another character may not be so lucky and must rely on their force of personality instead. In this case, the Warden should state the risk (a permanent ban on entry, a loss of reputation, etc.). The PC then makes a **WIL** save; on a success, the cost is either reduced or avoided entirely.

### Downtime Actions

The following activities represent some of the most common **Downtime Actions** a player can choose. The **Warden** can also create custom actions based on the needs of play.

#### Research

A PC investigates a question about a bit of lost or forgotten lore, the location of a lost item, the whereabouts of an important NPC, and so on. To take this action, the player must have a clearly formulated question they'd like to answer and a **Source** of knowledge in the game world that their character can interact with. If the PC does not have a **Source**, then they can spend a **Downtime Action** trying to find one. There is no guarantee that they will be successful. Once a question is posed and an appropriate **Source** has been identified, the **Warden** should provide any **Milestones** and associated **Costs**.

##### Questions

As always, the question must come from an experience that occurred during play.

**Examples:**

- "Where is the **Lost Temple of East Nipoor**?"
- "Who in **Fortune City** might know how to crack an ancient vault?"
- "Where can I find the cure to **curly sickness**?"

##### Sources

A **Source** is a person, place, faction, or entity that holds either a part or whole answer that the character seeks. They can be NPCs, Factions, spirits, or even other PCs.

###### Examples:

- **Kewr the Mouth**, a frequent contact for the **Conclave of Merchants**. Despite their excellent relationship with this faction, asking for help in an illicit activity might come at a high cost.
- A **Woodwose** who makes his home deep in the **Forest of Knives**. The party encountered him in an earlier expedition and the meeting did not end well. Still, he is said to know the nature of every herb and their healing properties.
- The **Temple of Puppets**, a nomadic circus troupe who have travelled the known and unknown lands. The party assisted one of their members during the **Rain of Fire**, when even the creatures of the Wood were preparing to flee their homes. If anyone has heard of forgotten places, it's them.

#### Training

A character can improve their skills with an item or ability, with clear narrative or mechanical results. They might be interested in dealing greater damage with a particular weapon, decreasing their chances of getting lost in rough weather, or learning to read the languages of the ancients. A PC might spend multiple **Downtime Actions** sparring with a particular weapon, improving their skills week by week. Or they may need to travel to the home of a distant sage, improving themselves through short but intense study.

The player must describe precisely what they'd like to improve and a **Master** whom they might train with. And of course, the character's inspiration to improve should come from an experience in play. The **Warden** should provide any **Milestones** and associated **Costs**.

**Examples:**

- **The Two-Handed Parry**: When fighting with one hand free, a PC's HP temporarily increases by 1d4. The party took on a hireling from the **Cratered Lands**, whose fighters emphasize avoiding enemy attacks. She has agreed to train anyone who can best her in hand to hand combat.
- **Herbology**: Given proper ingredients, a PC can create a **Healing Salve** (restores 4 STR) as a **Downtime Action**. After receiving care from an elderly herbalist in the **Verdant Glades**, the wounded PC asked to be trained in the healing arts. The **Master** has agreed, but asked that they collect three rare herbs before training can begin.
- **Troutmaster**: When taking the Supply **Action**, **Rations** gathered near cold freshwater sources increase by one step (e.g. 1d4 becomes 1d6). The party escorted a stranded naturalist from the famously dreadful **Silver Wastes** safely back to the city. As thanks, she has offered to train a PC to identify and capture a common lakefish that frequents colder waters.

#### Strengthening Ties

A character fosters a connection with an NPC or Faction in the game world. First, they must identify the entity with whom they wish to strengthen ties, as well as a specific **intent** (e.g., building trust, mending a friendship, seeking membership in a Faction, forming an alliance, and so on). The **Warden** then provides concrete measures (described as **Milestones** and **Costs**) that the PC can undertake to advance the relationship. With each completed **Milestone**, the **Warden** describes how the PC's relationship has grown or changed.

**Examples:**

- After returning from an unsuccessful delve into the **Roots**, a PC discovers that they'd unknowingly brought along a stowaway: an eyeless devourer, barely hatched. They decide to keep the creature and train it in secret.
- During a play session, a PC becomes friendly with an agent of the **Order of the Helm**. Impressed by the Order's values, the PC asks what the requirements are to join.
- An agent for a powerful faction dies during the **Battle of Frogs** while under the party's care. Now those responsible wish to provide redress, so that the party can once again perform tasks for that faction.

---

## Barebones Edition Character Creation

### Overview

1. Roll for your character’s first and last [Name](#names-d100) as well as **Age** (2d20+10).
2. Roll for your characters’ [Attributes](#attributes-1) and [Hit Protection](#hit-protection-1).
3. Roll for your character’s [Traits](#traits-d10).
4. Roll for your character's [Background](#background) and related items.
5. Roll for your character's [Armor & Weapon](#armor--weapon).
6. Roll for an [Additional Gear](#additional-gear) to complete your character's starting equipment.
7. Purchase any additional items your character can afford from the [Marketplace](#barebones-marketplace).

#### Names (d100)

|       |             |        |
| ----- | ----------- | ------ |
| d100 | Name     | Surname     |
| 1    | Adair    | Abbot       |
| 2    | Alaric   | Addyman     |
| 3    | Alder    | Ashwell     |
| 4    | Amaris   | Balfe       |
| 5    | Anwen    | Baxter      |
| 6    | Arlo     | Bevan       |
| 7    | Ash      | Beran       |
| 8    | Aster    | Blackwood   |
| 9    | Ballad   | Bowen       |
| 10   | Barley   | Brewer      |
| 11   | Basil    | Broder      |
| 12   | Beatrix  | Bukharin    |
| 13   | Birch    | Cadwallan   |
| 14   | Bram     | Carter      |
| 15   | Briar    | Cobb        |
| 16   | Brook    | Collier     |
| 17   | Bryn     | Cooper      |
| 18   | Cai      | Crowther    |
| 19   | Callan   | Dempsey     |
| 20   | Carver   | Dermody     |
| 21   | Cedric   | Domański    |
| 22   | Cinder   | Dymov       |
| 23   | Cliff    | Fairweather |
| 24   | Corin    | Fedorov     |
| 25   | Crow     | Fletcher    |
| 26   | Dain     | Fuller      |
| 27   | Darnel   | Galen       |
| 28   | Dax      | Glinka      |
| 29   | Dorian   | Glover      |
| 30   | Eira     | Golubov     |
| 31   | Elowen   | Gradnik     |
| 32   | Ember    | Granger     |
| 33   | Eon      | Grobar      |
| 34   | Evander  | Halberg     |
| 35   | Falcon   | Harkin      |
| 36   | Faris    | Hlebar      |
| 37   | Fern     | Hromada     |
| 38   | Finch    | Horgan      |
| 39   | Flint    | Iliev       |
| 40   | Freya    | Ivanec      |
| 41   | Gale     | Joryn       |
| 42   | Garen    | Kamensk     |
| 43   | Hazel    | Kavanagh    |
| 44   | Hemlock  | Kovac       |
| 45   | Idris    | Kovalenko   |
| 46   | Ivy      | Kravec      |
| 47   | Juniper  | Krznar      |
| 48   | Kael     | Kuchar      |
| 49   | Kavi     | Kvasnikov   |
| 50   | Keir     | Lethbridge  |
| 51   | Leif     | Llewellyn   |
| 52   | Liora    | Locke       |
| 53   | Lucan    | Lovett      |
| 54   | Lyra     | Lukanov     |
| 55   | Lysander | Maddox      |
| 56   | Marius   | Malinov     |
| 57   | Marlowe  | Marinov     |
| 58   | Milo     | Markov      |
| 59   | Moss     | Mason       |
| 60   | Nazira   | Melnik      |
| 61   | Neria    | Mercer      |
| 62   | Noa      | Milner      |
| 63   | Nyx      | Morozov     |
| 64   | Onyx     | Novak       |
| 65   | Orla     | Obradov     |
| 66   | Pan      | O’Callaghan |
| 67   | Patch    | O’Farrell   |
| 68   | Perran   | O’Leary     |
| 69   | Quill    | Osipov      |
| 70   | Rain     | Pavlenko    |
| 71   | Reed     | Pekar       |
| 72   | River    | Petrov      |
| 73   | Robin    | Pisarev     |
| 74   | Rowan    | Powell      |
| 75   | Rune     | Price       |
| 76   | Rush     | Radoslav    |
| 77   | Rye      | Reeve       |
| 78   | Sable    | Rogov       |
| 79   | Sage     | Romanov     |
| 80   | Selene   | Rowanfield  |
| 81   | Shade    | Rybak       |
| 82   | Silas    | Sawyer      |
| 83   | Sky      | Shepherd    |
| 84   | Soren    | Shevchenko  |
| 85   | Sparrow  | Slater      |
| 86   | Stellan  | Smirnov     |
| 87   | Stone    | Sokolov     |
| 88   | Storm    | Tanner      |
| 89   | Talon    | Thatcher    |
| 90   | Thistle  | Tallow      |
| 91   | Thorn    | Vukovic     |
| 92   | Thresh   | Webb        |
| 93   | Valen    | Whitlock    |
| 94   | Vesper   | Wicklowe    |
| 95   | Vex      | Wightman    |
| 96   | Willow   | Wilkin      |
| 97   | Winslow  | Wright      |
| 98   | Wisp     | Wynne       |
| 99   | Wren     | Yarrow      |
| 100  | Yarrow   | Zidar       |

#### Attributes

- Roll **3d6** for each of your character’s Attributes (**Strength (STR)**, **Dexterity (DEX)**, and **Willpower (WIL)**), in order. You may then swap any two results.

#### Hit Protection

- Roll **1d6** to determine your PC’s starting **Hit Protection** (HP).

### Traits (d10)

 Roll on the following tables for your character’s Traits.

##### Physique

|       |          |        |            |
| ----- | -------- | ------ | ---------- |
| **1** | Athletic | **6**  | Scrawny    |
| **2** | Brawny   | **7**  | Short      |
| **3** | Flabby   | **8**  | Statuesque |
| **4** | Lanky    | **9**  | Stout      |
| **5** | Rugged   | **10** | Towering   |

##### Skin

|       |             |        |           |
| ----- | ----------- | ------ | --------- |
| **1** | Birthmarked | **6**  | Soft      |
| **2** | Marked      | **7**  | Tanned    |
| **3** | Oily        | **8**  | Tattooed  |
| **4** | Rosy        | **9**  | Weathered |
| **5** | Scarred     | **10** | Webbed    |

##### Hair

|       |         |        |           |
| ----- | ------- | ------ | --------- |
| **1** | Bald    | **6**  | Long      |
| **2** | Braided | **7**  | Luxurious |
| **3** | Curly   | **8**  | Oily      |
| **4** | Filthy  | **9**  | Wavy      |
| **5** | Frizzy  | **10** | Wispy     |

##### Face

|       |           |        |         |
| ----- | --------- | ------ | ------- |
| **1** | Bony      | **6**  | Perfect |
| **2** | Broken    | **7**  | Rakish  |
| **3** | Chiseled  | **8**  | Sharp   |
| **4** | Elongated | **9**  | Square  |
| **5** | Pale      | **10** | Sunken  |

##### Speech

|       |         |        |            |
| ----- | ------- | ------ | ---------- |
| **1** | Blunt   | **6**  | Gravelly   |
| **2** | Booming | **7**  | Precise    |
| **3** | Cryptic | **8**  | Squeaky    |
| **4** | Droning | **9**  | Stuttering |
| **5** | Formal  | **10** | Whispery   |

##### Clothing

|       |         |        |        |
| ----- | ------- | ------ | ------ |
| **1** | Antique | **6**  | Frayed |
| **2** | Bloody  | **7**  | Frumpy |
| **3** | Elegant | **8**  | Livery |
| **4** | Filthy  | **9**  | Rancid |
| **5** | Foreign | **10** | Soiled |

##### Virtue

|       |             |        |           |
| ----- | ----------- | ------ | --------- |
| **1** | Ambitious   | **6**  | Honorable |
| **2** | Cautious    | **7**  | Humble    |
| **3** | Courageous  | **8**  | Merciful  |
| **4** | Disciplined | **9**  | Serene    |
| **5** | Gregarious  | **10** | Tolerant  |

##### Vice

|       |            |        |          |
| ----- | ---------- | ------ | -------- |
| **1** | Aggressive | **6**  | Lazy     |
| **2** | Bitter     | **7**  | Nervous  |
| **3** | Craven     | **8**  | Rude     |
| **4** | Deceitful  | **9**  | Vain     |
| **5** | Greedy     | **10** | Vengeful |

### Background

Roll on the following table to determine your character's background and starting equipment:

|       |             |
| ----- | ----------- |
| d100 | Background & Starting Gear                                                                                                             |
|  1   | **Acolyte**: Incense, Parchment & Ink (3 uses), [Spellbook](#barebones-edition-spellbooks)                                           |
|  2   | **Acrobat**: Pole (10ft), Rope (25ft), Smokebomb                                                                                       |
|  3   | **Alchemist**: Acid, Lens, Oilskin Bag                                                                                                 |
|  4   | **Apothecary**: Antitoxin, Bandages (3 uses), Sealable Bottle                                                                          |
|  5   | **Assassin**: Garrotte, Mask, Poison                                                                                                   |
|  6   | **Astrologer**: Candle (3 uses, dim), Marbles, Spyglass                                                                                |
|  7   | **Baker**: Flour, Honey, Sealable Bottle                                                                                               |
|  8   | **Barber-Surgeon**: Bandages (3 uses), Scissors, Sedative                                                                              |
|  9   | **Barkeep**: Alcohol, Sealable Bottle, Sedative                                                                                        |
|  10  | **Beadle**: Bell, Gloves (_petty_), Whistle (_petty_)                                                                                  |
|  11  | **Beekeeper**: Fire Oil, Gloves (_petty_), Honey                                                                                       |
|  12  | **Bell Ringer**: Gloves (_petty_), Rope (25 ft), Whistle (_petty_)                                                                     |
|  13  | **Bird Keeper**: Cage, Net, Whistle (_petty_)                                                                                          |
|  14  | **Blacksmith**: Bellows, Hammer, Iron Tongs                                                                                            |
|  15  | **Bookbinder**: Glue, Parchment & Ink (3 uses), Sewing Kit                                                                             |
|  16  | **Bounty Hunter**: Flash Powder, Manacles, Rope (25 ft)                                                                                |
|  17  | **Butcher**:  Pail, Saw, Whetstone                                                                                                     |
|  18  | **Carpenter**: Hammer, Metal File, Saw                                                                                                 |
|  19  | **Cartographer**: Compass, Parchment & Ink (3 uses), Sextant                                                                           |
|  20  | **Cartwright**: Hand Drill, Pulley, Saw                                                                                                |
|  21  | **Chandler**: Candle (3 uses, dim), Honey, Perfume                                                                                     |
|  22  | **Charlatan**: Cards, Paint, Perfume                                                                                                   |
|  23  | **Chimney Sweep**: Bellows, Climbing Spikes, Rope (25 ft)                                                                              |
|  24  | **Clockmaker**: Magnifying Glass, Metal File, Pliers                                                                                   |
|  25  | **Cobbler**: Pliers, Sack, Sewing Kit                                                                                                  |
|  26  | **Cook**: Flour, Pail, Smoking Herbs (3 uses)                                                                                          |
|  27  | **Cooper**: Hammer, Hand Drill, Saw                                                                                                    |
|  28  | **Courier**: Bell, Compass, Parchment & Ink (3 uses)                                                                                   |
|  29  | **Crypt Custodian**: Incense, Lantern, Oil Can (6 uses)                                                                                |
|  30  | **Cultist**: Incense, Mask, Scroll of Random [Spellbook](#barebones-edition-spellbooks) (_petty_)                                    |
|  31  | **Demolitionist**: Explosive, Goggles, Grease                                                                                          |
|  32  | **Dowser**: Dowsing Rod, Sealable Bottle, Shovel                                                                                       |
|  33  | **Duelist**: Cloak (_petty_), Gloves (_petty_), Whetstone                                                                              |
|  34  | **Entertainer**: Dice, Songbook, Wig                                                                                                   |
|  35  | **Executioner**: Mask, Rope (25 ft), Whetstone                                                                                         |
|  36  | **Falconer**: Cage, Gloves (_petty_), Whistle (_petty_)                                                                                |
|  37  | **Farmer**: Rope (25 ft), Sack, Shovel                                                                                                 |
|  38  | **Fence**: Bolt Cutters, Random Additional Gear, Sack                                                                                  |
|  39  | **Fisher**: Air Bladder, Fishing Rod, Net                                                                                              |
|  40  | **Fletcher**: Sack, Trap, Whetstone                                                                                                    |
|  41  | **Gambler**: Alcohol, Cards, Dice                                                                                                      |
|  42  | **Gardener**: Gloves (_petty_), Sack, Shovel                                                                                           |
|  43  | **Glassblower**: Goggles, Lens, Pliers                                                                                                 |
|  44  | **Gong Farmer**: Gloves (_petty_), Sack, Shovel                                                                                        |
|  45  | **Gravedigger**: Alcohol, Ladder, Shovel                                                                                               |
|  46  | **Guard**: Lantern, Manacles, Whistle (_petty_)                                                                                        |
|  47  | **Herald**: Mask, Signal Flag, Whistle (_petty_)                                                                                       |
|  48  | **Herbalist**: Antitoxin, Mugwort, Sack                                                                                                |
|  49  | **Hermit**: Blanket, Pole (10 ft), Smoking Herbs (3 uses)                                                                              |
|  50  | **Highway Robber**: Grappling Hook, Rope (25 ft), Signal Flag                                                                          |
|  51  | **Hunter**: Trap, Rope (25 ft), Smoking Herbs (3 uses)                                                                                 |
|  52  | **Illusionist**: Candle (3 uses, dim), Flash Powder, Mirror                                                                            |
|  53  | **Innkeeper**: Alcohol, Bandages (3 uses), Parchment & Ink (3 uses)                                                                    |
|  54  | **Jailer**: Chain (10ft), Manacles, Whistle (_petty_)                                                                                  |
|  55  | **Jester**: Cards, Lute, Perfume                                                                                                       |
|  56  | **Jeweler**: Magnifying Glass, Pliers, Tongs                                                                                           |
|  57  | **Knight**: Gloves (_petty_), Signal Flag, Whetstone                                                                                   |
|  58  | **Lamplighter**: Ladder (10ft, _bulky_), Oil Can (6 uses), Whistle (_petty_)                                                           |
|  59  | **Leech Collector**: Gloves (_petty_), Leech (restores 1 STR, 3 uses), Net                                                             |
|  60  | **Librarian**: Candle (3 uses, dim), Parchment & Ink (3 uses), Scroll of Random [Spellbook](#barebones-edition-spellbooks) (_petty_) |
|  61  | **Locksmith**: Lock & Key, Metal File, Pliers                                                                                          |
|  62  | **Lumberjack**: Rope (25 ft), Saw, Whetstone                                                                                           |
|  63  | **Mason**: Chisel, Fan, Hammer                                                                                                         |
|  64  | **Merchant**: Random Additional Gear, Stylus, Wagon (+8 slots, slow)                                                                   |
|  65  | **Miller**: Bowl, Flour, Rope (25 ft)                                                                                                  |
|  66  | **Miner**: Lantern, Lodestone, Pickaxe                                                                                                 |
|  67  | **Monk**: Candle (3 uses, dim), Cloak (_petty_), Songbook                                                                              |
|  68  | **Musician**: Bowl, Fiddle, Songbook                                                                                                   |
|  69  | **Naturalist**: Hammock, Rope (25ft), Spyglass                                                                                         |
|  70  | **Navigator**: Compass, Poncho (_petty_), Spyglass                                                                                     |
|  71  | **Oil Collector**: Lantern, Oil Can (6 uses), Sealable Bottle                                                                          |
|  72  | **Painter**: Paint, Parchment & Ink (3 uses), Stylus                                                                                   |
|  73  | **Peddler**: Cart (+4 slots, _bulky_), Random Additional Gear, Sack                                                                    |
|  74  | **Philosopher**: Chalk (_petty_), Parchment & Ink, Pipe                                                                                |
|  75  | **Physician**: Antitoxin, Bandages (3 uses), Crowbar                                                                                   |
|  76  | **Pilgrim**: Blanket, Pole (10 ft), Poncho (_petty_)                                                                                   |
|  77  | **Potter**: Chisel, Pail, Tongs                                                                                                        |
|  78  | **Priest**: Bandages (3 uses), Candle (3 uses, dim), Incense                                                                           |
|  79  | **Prospector**: Lantern, Lodestone, Pickaxe                                                                                            |
|  80  | **Rat Catcher**: Sack, Trap, Whistle (_petty_)                                                                                         |
|  81  | **Sailor**: Hammock, Rope (50 ft), Spyglass                                                                                            |
|  82  | **Scribe**: Candle (3 uses, dim), Parchment & Ink (3 uses), Stylus                                                                     |
|  83  | **Shepherd**: Cloak (_petty_), Rope (25 ft), Whistle (_petty_)                                                                         |
|  84  | **Smuggler**: Lock & Key, Oilskin Bag, Rope (25 ft)                                                                                    |
|  85  | **Soldier**: Spiked Boots, Tent (fits 2, _bulky_), Whetstone                                                                           |
|  86  | **Spy**: Disguise Kit, Garrotte, Mirror                                                                                                |
|  87  | **Stablehand**: Blanket, Rope (25ft), Shovel                                                                                           |
|  88  | **Street Preacher**: Bell, Parchment & Ink, Scroll of Random [Spellbook](#barebones-edition-spellbooks) (_petty_)                    |
|  89  | **Tailor**: Cloak (_petty_), Scissors, Sewing Kit                                                                                      |
|  90  | **Tanner**: Gloves (_petty_), Pliers, Tar                                                                                              |
|  91  | **Tax Collector**: Parchment & Ink (3 uses), Sealable Bottle, Whistle (_petty_)                                                        |
|  92  | **Thief**: Caltrops, Grappling Hook, Lockpick                                                                                          |
|  93  | **Tinker**: Grease, Hammer, Pliers                                                                                                     |
|  94  | **Toll Keeper**: Bell, Lock & Key, Waterproof Bag                                                                                      |
|  95  | **Toymaker**: Glue, Pliers, Scissors                                                                                                   |
|  96  | **Vagabond**: Blanket, Poncho (_petty_), Rope (25 ft)                                                                                  |
|  97  | **Vintner**: Alcohol, Rope (25 ft), Sealable Bottle                                                                                    |
|  98  | **Weaver**: Perfume, Rope (25 ft), Scissors                                                                                            |
|  99  | **Witch**: Candle (3 uses, dim), [Spellbook](#barebones-edition-spellbooks), Wolfsbane                                               |
| 100  | **Witchfinder**: Rope (25 ft), Scroll of Random [Spellbook](#barebones-edition-spellbooks)(_petty_), Spyglass                        |
|      |                                                                                                                                        |

#### Armor & Weapon

All PCs start with the following gear:
- 3d6 Gold Pieces
- Rations (3 uses)
- Torch (3 uses)

Additionally, roll on the following tables for your character's armor, weapons, and additional gear:

##### Armor (d6)

|  d6   | Armor                                              |
| :---: | :------------------------------------------------- |
| **1** | None. Roll for [Additional Gear](#additional-gear) |
| **2** | Shield (+1 Armor)                                  |
| **3** | Helmet (+1 Armor)                                  |
| **4** | Gambeson (+1 Armor)                                |
| **5** | Chainmail (2 Armor, _bulky_)                       |
| **6** | Plate (3 Armor, _bulky_)                           |


##### Weapons (d6)

|  d6   | Weapons                                                     |
| :---: | :---------------------------------------------------------- |
| **1** | Dagger, Cudgel, Sickle, Staff, etc. (d6 damage)             |
| **2** | Spear, Sword, Mace, Axe, Flail, etc. (d8 damage)            |
| **3** | Halberd, War Hammer, Long Sword, etc. (d10 damage, _bulky_) |
| **4** | Sling (d6 damage)                                           |
| **5** | Bow (d6 damage, _bulky_)                                    |
| **6** | Crossbow (d8 damage, _bulky_)                               |

##### Additional Gear

| d100 | Gear                                                          |
| ---- | ------------------------------------------------------------- |
| 1    | Acid                                                          |
| 2    | Air Bladder                                                   |
| 3    | Alcohol                                                       |
| 4    | Antitoxin                                                     |
| 5    | Bandages (3 uses)                                             |
| 6    | Bell                                                          |
| 7    | Bellows                                                       |
| 8    | Blanket                                                       |
| 9    | Boltcutters                                                   |
| 10   | Bowl                                                          |
| 11   | Cage                                                          |
| 12   | Caltrops                                                      |
| 13   | Candle (3 uses, dim)                                          |
| 14   | Cards                                                         |
| 15   | Cart (+4 slots, _bulky_)                                      |
| 16   | Chain (10ft)                                                  |
| 17   | Chalk (_petty_)                                               |
| 18   | Chisel                                                        |
| 19   | Climbing Spikes                                               |
| 20   | Cloak (_petty_)                                               |
| 21   | Compass                                                       |
| 22   | Crowbar                                                       |
| 23   | Dice                                                          |
| 24   | Dowsing Rod                                                   |
| 25   | Explosive                                                     |
| 26   | Fan                                                           |
| 27   | Fiddle                                                        |
| 28   | Fire Oil                                                      |
| 29   | Fishing Rod                                                   |
| 30   | Flash Powder                                                  |
| 31   | Flour                                                         |
| 32   | Garrotte                                                      |
| 33   | Gloves (_petty_)                                              |
| 34   | Glue                                                          |
| 35   | Goggles                                                       |
| 36   | Grappling Hook                                                |
| 37   | Grease                                                        |
| 38   | Hammer                                                        |
| 39   | Hammock                                                       |
| 40   | Hand Drill                                                    |
| 41   | Honey                                                         |
| 42   | Hourglass                                                     |
| 43   | Incense                                                       |
| 44   | Ladder (10 ft, _bulky_)                                       |
| 45   | Lantern                                                       |
| 46   | Leech (restores 1 STR, 3 uses)                                |
| 47   | Lens                                                          |
| 48   | Lock & Key                                                    |
| 49   | Lockpick                                                      |
| 50   | Lodestone                                                     |
| 51   | Lute                                                          |
| 52   | Magnifying Glass                                              |
| 53   | Manacles                                                      |
| 54   | Marbles                                                       |
| 55   | Mask                                                          |
| 56   | Metal File                                                    |
| 57   | Mirror                                                        |
| 58   | Mugwort                                                       |
| 59   | Net                                                           |
| 60   | Oil Can (6 uses)                                              |
| 61   | Oilskin Bag                                                   |
| 62   | Pail                                                          |
| 63   | Paint                                                         |
| 64   | Parchment & Ink (3 uses)                                      |
| 65   | Perfume                                                       |
| 66   | Pickaxe                                                       |
| 67   | Pipe                                                          |
| 68   | Pliers                                                        |
| 69   | Poison                                                        |
| 70   | Pole (10ft)                                                   |
| 71   | Poncho (_petty_)                                              |
| 72   | Pulley                                                        |
| 73   | Random [Spellbook](#barebones-edition-spellbooks)           |
| 74   | Rope (25ft)                                                   |
| 75   | Sack                                                          |
| 76   | Saw                                                           |
| 77   | Scissors                                                      |
| 78   | Scroll of Random [Spellbook](#barebones-edition-spellbooks) (_petty_) |
| 79   | Sealable Bottle                                               |
| 80   | Sedative                                                      |
| 81   | Sewing Kit                                                    |
| 82   | Sextant                                                       |
| 83   | Shovel                                                        |
| 84   | Signal Flag                                                   |
| 85   | Smokebomb                                                     |
| 86   | Smoking Herbs (3 uses)                                        |
| 87   | Songbook                                                      |
| 88   | Spiked Boots                                                  |
| 89   | Spyglass                                                      |
| 90   | Stylus                                                        |
| 91   | Tar                                                           |
| 92   | Tent (fits 2, _bulky_)                                        |
| 93   | Tongs                                                         |
| 94   | Trap (d6 STR damage)                                          |
| 95   | Wagon (+8 slots, slow)                                        |
| 96   | Waterproof Bag                                                |
| 97   | Whetstone                                                     |
| 98   | Whistle (_petty_)                                             |
| 99   | Wig                                                           |
| 100  | Wolfsbane                                                     |

> You may reroll any duplicate gear.

---

## Barebones Gear Packages

### Fighter

* 3d6 Gold Pieces
* Jerky (3 uses, _petty_)
* Torches (3 uses)
* Bandages (3 uses)
* Rope (25ft)
* Shield (+1 Armor)
* Gambeson (+1 Armor)
* Sword (d8)
* Throwing Dagger (d6)
* Dog Tags (_petty_)

### Thief

* 3d6 Gold Pieces
* Rations (3 uses)
* Twin Folding Daggers (d6+d6, _bulky_)
* Bullseye Lantern
* Oil Can (6 uses)
* Caltrops
* Small Mirror
* Lockpick
* Grappling Hook
* Dark Hood (_petty_)
* Chalk (_petty_)

### Magic-User

* 3d6 Gold Pieces
* Rations (3 uses)
* Staff (d6)
* Knife (d6)
* Spellbook: _Illuminate_
* Spellbook: _Sleep_
* Scroll of _Detect Magic_
* Parchment & Ink (3 uses)
* Robes (_petty_)

### Cleric

* 3d6 Gold Pieces
* Rations (3 uses)
* Torches (3 uses)
* War Hammer (d10, _bulky_)
* Helmet (+1 Armor)
* Spellbook: _Cure Wounds_
* Bandages (3 uses)
* Bone Charm (_petty_, casts _Ward_ once per day)

---

## Barebones Marketplace

> All prices are in gold pieces

### Armor

|                               |     |
| ----------------------------- | --- |
| Shield (+1 Armor)             | 10  |
| Helmet (+1 Armor)             | 10  |
| Gambeson (+1 Armor)           | 15  |
| Brigandine (1 Armor, _bulky_) | 20  |
| Chainmail (2 Armor, _bulky_)  | 40  |
| Plate (3 Armor, _bulky_)      | 60  |

### Weapons

|                                                             |     |
| ----------------------------------------------------------- | --- |
| Dagger, Cudgel, Sickle, Staff, etc. (d6 damage)             | 5   |
| Spear, Sword, Mace, Axe, Flail, etc. (d8 damage)            | 10  |
| Halberd, War Hammer, Long Sword, etc. (d10 damage, _bulky_) | 20  |
| Sling (d6 damage)                                           | 5   |
| Bow (d6 damage, _bulky_)                                    | 20  |
| Crossbow (d8 damage, _bulky_)                               | 30  |

### Transport

|                          |     |
| ------------------------ | --- |
| Cart (+4 slots, _bulky_) | 30  |
| Wagon (+8 slots, slow)   | 200 |
| Horse (+4 slots)         | 75  |
| Mule (+6 slots, slow)    | 30  |
| Carriage Seat            | 5   |
| Ship's Passage           | 10  |

### Upkeep & Recovery

|                               |     |
| ----------------------------- | --- |
| Room & Board (per night)      | 10  |
| Private Room & Board (fits 4) | 35  |
| Stable & Feed (per night)     | 5   |
| Medical Healing               | 50  |
| Rations (3 uses)              | 10  |
| Animal Feed (3 uses, bulky)   | 5   |

### Hirelings (per day)

|                   |     |
| ----------------- | --- |
| Alchemist         | 30  |
| Animal Handler    | 5   |
| Blacksmith        | 15  |
| Bodyguard         | 10  |
| Local Guide       | 5   |
| Lockpick          | 10  |
| Navigator         | 10  |
| Sailor            | 5   |
| Scholar           | 20  |
| Tracker           | 5   |
| Trapper           | 5   |
| Veteran Bodyguard | 20  |


### Gear

|                                                    |     |
| -------------------------------------------------- | --- |
| Air Bladder                                        | 5   |
| Antitoxin                                          | 20  |
| Bandages (3 uses)                                  | 30  |
| Bathing Goods (Soap, Perfume, etc.)                | 5   |
| Book                                               | 50  |
| Caltrops                                           | 10  |
| Card Deck                                          | 5   |
| Chain (10ft)                                       | 10  |
| Chalk (_petty_)                                    | 1   |
| Chest                                              | 25  |
| Chisel                                             | 5   |
| Common Agents (Glue, Grease, etc.)                 | 10  |
| Common Tools (Hammer, Shovel, etc.)                | 10  |
| Compass                                            | 75  |
| Complex Instruments (Bagpipes, Fiddle, etc.)       | 50  |
| Containers (Sack, Waterskin, etc.)                 | 10  |
| Cooking Gear (Pots, Utensils, etc.)                | 10  |
| Costume Gear (Face Paint, Disguise)                | 15  |
| Dowsing Rod                                        | 15  |
| Expeditionary Gear (Climbing Spikes, Pulley, etc.) | 10  |
| Fire Oil                                           | 10  |
| Fishing Rod                                        | 10  |
| Games (Cards, Dice, etc.)                          | 10  |
| Gloves (_petty_)                                   | 20  |
| Grappling Hook                                     | 25  |
| Lantern                                            | 10  |
| Mirror                                             | 5   |
| Net                                                | 10  |
| Oil Can (6 uses)                                   | 10  |
| Outdoor Comfort (Blanket, Hammock, etc.)           | 10  |
| Parchment (3 uses)                                 | 10  |
| Pole (10ft)                                        | 5   |
| Repellent (Wolfsbane, Mugwort, etc.)               | 10  |
| Rope (25ft)                                        | 5   |
| Sedative                                           | 30  |
| Sewing Kit                                         | 20  |
| Simple Instruments (Pipes, Lute, etc.)             | 10  |
| Smoking Pipe (_petty_)                             | 15  |
| Specialized Tools (Ink, etc.)                      | 20  |
| Spiked Boots                                       | 15  |
| Spyglass                                           | 40  |
| Tent (fits 2, _bulky_)                             | 20  |
| Thieving Tools (Lockpick, Metal File, etc.)        | 25  |
| Torch (3 uses)                                     | 5   |
| Trap (d6 STR damage)                               | 35  |
| Whistle (_petty_)                                  | 15  |
| Wilderness Clothes (Poncho, Cloak, etc.) (_petty_) | 15  |

---

## Barebones Edition Spellbooks

|         |                       |                                                                                                                                                                                                                                                                                              |
| ------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**   | **Adhere**            | An object is covered in extremely sticky slime. _Adjacent objects stick to the book with great force._                                                                                                                                                                                       |
| **2**   | **Anchor**            | A strong wire sprouts from your arms, affixing itself to two points within 50ft on each side. _If a rope is pulled through the iron loop on its spine, it becomes as heavy as an elephant._                                                                                                  |
| **3**   | **Animate Object**    | An object obeys your commands as best it can. _Moldable like clay. Childish laughter sprouts from its pages._                                                                                                                                                                                |
| **4**   | **Anthropomorphize**  | An animal either gains human intelligence or human appearance for one day. _Whimpers, purrs and growls depending on its treatment._                                                                                                                                                          |
| **5**   | **Arcane Eye**        | You can see through a magical floating eyeball that flies around at your command. _Needs a spritz of water to open._                                                                                                                                                                         |
| **6**   | **Astral Prison**     | An object is frozen in time and space within an invulnerable crystal shell. _Silent, abstract, faces scream in anguish within._                                                                                                                                                              |
| **7**   | **Attract**           | Two objects are strongly magnetically attracted to each other if they come within 10 feet. _Nearby compasses spin uselessly._                                                                                                                                                                |
| **8**   | **Auditory Illusion** | You create illusory sounds that seem to come from a direction of your choice. _Produces random and occasionally inopportune sounds throughout the day_.                                                                                                                                      |
| **9**   | **Babble**            | A creature must loudly and clearly repeat everything you think. It is otherwise mute. _When the text is read aloud, the words of others become unintelligible._                                                                                                                              |
| **10**  | **Bait Flower**       | A plant sprouts from the ground that emanates the smell of decaying flesh. _Attracts flies._                                                                                                                                                                                                 |
| **11**  | **Beast Form**        | You and your possessions transform into a mundane animal. _Covered in thick fur, its edges lined with small teeth._                                                                                                                                                                          |
| **12**  | **Befuddle**          | A creature of your choice is unable to form new short-term memories for the duration of the spell. _Its contents shift and change each time it is opened._                                                                                                                                   |
| **13**  | **Body Swap**         | You switch bodies with a creature you touch. If one body dies, the other dies as well. _The front cover shows an image of the last creature to read it._                                                                                                                                     |
| **14**  | **Charm**             | A creature you can see treats you as a friend. _Warm to the touch, and smells of roses._                                                                                                                                                                                                     |
| **15**  | **Command**           | A target obeys a single three-word command that does not cause it harm. _Grows thinner over time, until finally disappearing forever._                                                                                                                                                       |
| **16**  | **Comprehend**        | You become fluent in all languages for a short while. _Drips letters, staining whatever it touches._                                                                                                                                                                                         |
| **17**  | **Cone of Foam**      | Dense foam sprays from your hand, coating the target. _Spongy and moist with a soapy residue._                                                                                                                                                                                               |
| **18**  | **Control Plants**    | Nearby plants and trees obey you and gain the ability to move at a slow pace. _Leaves grow along the spine, and it smells faintly of decay._                                                                                                                                                 |
| **19**  | **Control Weather**   | You may alter the type of weather at will, but you do not otherwise control it. _Highly resistant to fire and water damage._                                                                                                                                                                 |
| **20**  | **Cure Wounds**       | Restore 1d4 STR per day to a creature you can touch. _Smells of vinegar and thyme. Turns red after use._                                                                                                                                                                                     |
| **21**  | **Deafen**            | All nearby creatures are deafened. _Nearby instruments occasionally sound off, as if in protest._                                                                                                                                                                                            |
| **22**  | **Detect Magic**      | You can see or hear nearby magical auras. _Becomes warm to the touch if magic is used nearby._                                                                                                                                                                                               |
| **23**  | **Disassemble**       | Any of your body parts may be detached and reattached at will, without causing pain or damage. You can still control them. _Regenerates any torn or defaced pages._                                                                                                                          |
| **24**  | **Disguise**          | You may alter the appearance of one character at will as long as they remain humanoid. Attempts to duplicate other characters will seem uncanny. _The surface makes a perfect mirror._                                                                                                       |
| **25**  | **Displace**          | An object appears to be up to 15ft from its actual position. _Bits of string, clothing, and leaves are sometimes stuffed inside._                                                                                                                                                            |
| **26**  | **Earthquake**        | The ground begins shaking violently. Structures may be damaged or collapse. _Sand dribbles from the corners, seemingly without stop._                                                                                                                                                        |
| **27**  | **Elasticity**        | Your body can stretch up to 10ft. _Smells of taffy, and is very flexible._                                                                                                                                                                                                                   |
| **28**  | **Elemental Wall**    | A straight wall of ice or fire 50ft long and 10ft high rises from the ground. _Skin and warmer substances stick to it after use._                                                                                                                                                            |
| **29**  | **Filch**             | A visible item teleports to your hands. _An ally's prized possession may occasionally be found tucked between its covers_.                                                                                                                                                                   |
| **30**  | **Fish Lung**         | A target can breathe underwater until they surface again. _Smells strongly of the sea. Attracts wild animals._                                                                                                                                                                               |
| **31**  | **Flare**             | A bright ball of energy fires a trail of light into the sky, revealing your location to friend or foe. _Faintly glows in complete darkness_.                                                                                                                                                 |
| **32**  | **Fog Cloud**         | A dense fog spreads out from you. _When submersed in water, the book eventually turns all the liquid to vapor._                                                                                                                                                                              |
| **33**  | **Frenzy**            | A nearby creature erupts in a frenzy of violence. _Rough, sandpaper cover that destroys any book it touches._                                                                                                                                                                                |
| **34**  | **Gate**              | A portal to a random plane opens. _A large hole is carved into the center, ending in a void. Items dropped within are never seen again_.                                                                                                                                                     |
| **35**  | **Gravity Shift**     | You can change the direction of gravity, but only for yourself. _Attaches itself to the largest object nearby._                                                                                                                                                                              |
| **36**  | **Greed**             | A creature develops the overwhelming urge to possess a visible item of your choice. _The cover changes depending on the owner, subtly hinting at their deepest desires._                                                                                                                     |
| **37**  | **Haste**             | Your movement speed is tripled. _Pages flip wildly while open. Can cause paper cuts._                                                                                                                                                                                                        |
| **38**  | **Hatred**            | A creature develops a deep hatred of another creature or group and wishes to destroy them. _Long term exposure to the book can cause suspicion, paranoia and distrust of others._                                                                                                            |
| **39**  | **Hear Whispers**     | You can hear faint sounds clearly. _The reader's voice is amplified for a short period of time afterwards._                                                                                                                                             |
| **40**  | **Hover**             | An object hovers, frictionless, 2ft above the ground. It can hold up to one humanoid. _Floats if dropped._                                                                                                                                                                                   |
| **41**  | **Hypnotize**         | A creature enters a trance and will truthfully answer one yes or no question you ask it. _Eye-catching, swirling spirals don its covers._                                                                                                                                                    |
| **42**  | **Icy Touch**         | A thick ice layer spreads across a touched surface, up to 10ft in radius. _Gloves required. Nonflammable_.                                                                                                                                                                                   |
| **43**  | **Identify Owner**    | Letters appear over the object you touch, spelling out the name of the object’s owners, if there are any. _The book's interior lists the name of its previous owner._                                                                                                                        |
| **44**  | **Illuminate**        | A floating light moves as you command. _When held in light, the pages become a prism of vibrant rainbows._                                                                                                                                                                                   |
| **45**  | **Invisible Tether**  | Two objects within 10ft of each other cannot be moved more than 10ft apart. _Its pages are not attached by glue or thread, yet stay together nonetheless._                                                                                                                                   |
| **46**  | **Knock**             | A nearby mundane or magical lock unlocks loudly. _Locked. A new owner "produces" the key after their next meal._                                                                                                                                                                             |
| **47**  | **Leap**              | You jump up to 10ft high, once. _When thrown, it just keeps going._                                                                                                                                                                                                                          |
| **48**  | **Liquid Air**        | The air around you becomes swimmable. _Floats of its own volition, bouncing off of whatever it touches._                                                                                                                                                                                     |
| **49**  | **Magic Dampener**    | All nearby magical effects have their effectiveness halved. _Relics within 100ft of the spellbook cannot be recharged._                                                                                                                                                                      |
| **50**  | **Manse**             | A sturdy, furnished cottage appears for hours. You can permit and forbid entry to it at will. _If left inside, both the book and the cottage vanish forever._                                                                                                                                |
| **51**  | **Marble Craze**      | Your pockets are full of marbles and will refill every 30 seconds. _When jostled, makes a playful rattling sound._                                                                                                                                                                           |
| **52**  | **Masquerade**        | A character's appearance and voice becomes identical to those of a character you touch. _Extended use causes the owner to develop unconscious yet noticeable tics._                                                                                                                          |
| **53**  | **Miniaturize**       | A creature you touch is shrunk down to the size of a mouse. _The text is ludicrously, comically large._                                                                                                                                                                                      |
| **54**  | **Mirror Image**      | An illusory duplicate of yourself appears and is under your control. _Over time, the owner begins to question who is the original, and who is the duplicate._                                                                                                                                |
| **55**  | **Mirrorwalk**        | A mirror becomes a gateway to another mirror that you looked into today. _Will not open unless the owner politely knocks on the cover._                                                                                                                                                      |
| **56**  | **Multiarm**          | You temporarily gain an extra arm. _After use, the caster is wracked with phantom limb syndrome for a day._                                                                                                                                                                                  |
| **57**  | **Night Sphere**      | A 50ft-wide sphere of darkness displaying the night sky appears before you. _Displays a prominent constellation on its cover_.                                                                                                                                                               |
| **58**  | **Objectify**         | You become any inanimate object between the size of a grand piano and an apple. _The owner experiences intense pareidolia for days after use._                                                                                                                                               |
| **59**  | **Ooze Form**         | You become a living jelly. _Slowly drips an acid that eventually eats away anything it touches._                                                                                                                                                                                             |
| **60**  | **Pacify**            | A creature near you has an aversion to violence. _Smells of jasmine and incense. Attracts children._                                                                                                                                                                                         |
| **61**  | **Passage**           | Creates a temporary path through wood, stone or brick. _An object dropped on top of the book inevitably falls through the other side._                                                                                                                                                       |
| **62**  | **Phobia**            | A nearby creature becomes terrified of an object of your choice. _Over time, haunting, abstract art begins to fill its pages._                                                                                                                                                               |
| **63**  | **Pit**               | A pit 10ft wide and 10ft deep opens in the ground. _A standard piton can be safely stored in its spine_.                                                                                                                                                                                     |
| **64**  | **Primal Surge**      | A creature rapidly evolves into a future version of its species. _The owner is haunted by strange visions of their own ancestors._                                                                                                                                                           |
| **65**  | **Push/Pull**         | An object of any size is pulled directly towards you or pushed directly away from you with the strength of one man. _Any force against the book is comically amplified._                                                                                                                     |
| **66**  | **Raise Dead**        | A skeleton rises from the ground to serve you. They are incredibly stupid and can only obey simple orders. _The owner becomes more and more fascinated with bones after each use._                                                                                                           |
| **67**  | **Raise Spirit**      | The spirit of a nearby corpse manifests and will answer 1 question. _The answers (but not their questions) are forever inscribed in its pages._                                                                                                                                              |
| **68**  | **Read Mind**         | You can hear the surface thoughts of nearby creatures. _Long-term possession can cause the reader to mistake the thoughts of others as their own._                                                                                                                                           |
| **69**  | **Repel**             | Two objects are strongly magnetically repelled from each other within 10 feet. _Closed by two powerful straps that spring open at inopportune times._                                                                                                                                        |
| **70**  | **Scry**              | You can see through the eyes of a creature you touched earlier today. _The owner's eyes turn milky-white for an hour after use._                                                                                                                                                             |
| **71**  | **Sculpt Elements**   | Inanimate material behaves like clay in your hands. _Slowly decays on contact with wood or cloth. Bury in dirt or submerge in water to refresh._                                                                                                                                             |
| **72**  | **Sense**             | Choose one kind of object (key, gold, arrow, jug, etc). You can sense the nearest example. _The book's previous owner is always aware of the book's current location._                                                                                                                       |
| **73**  | **Shield**            | A creature you touch is protected from mundane attacks for one minute. _Bound in rusty ring-mail and is quite heavy. If held, provides +1 Armor._                                                                                                                                            |
| **74**  | **Shroud**            | A creature you touch is invisible until they move. _Invisible to any but the book's current owner._                                                                                                                                                                                          |
| **75**  | **Shuffle**           | Two creatures you can see instantly switch places. _If stolen but not yet read, it reappears wherever its owner last left it._                                                                                                                                                             |
| **76**  | **Skillful Repair**   | You make minor repairs to a nonliving object. _Sewn from the vellum of one hundred books, no two pages are alike._                                                                                                                                                                           |
| **77**  | **Sleep**             | A creature you can see falls into a light sleep. _Soft as a pillow, but yields only fitful sleep._                                                                                                                                                                                           |
| **78**  | **Slick**             | Every surface in a 30ft radius becomes extremely slippery. _Gloves are required for handling, lest the book is dropped in a most comical fashion._                                                                                                                                           |
| **79**  | **Smoke Form**        | Your body becomes a living smoke that you can control. _Smells of campfire. The pages cannot be burnt, but are very sensitive to moisture._                                                                                                                                                  |
| **80**  | **Sniff**             | You can smell even the faintest traces of scents. _Expresses a strong odor detectable only by its owner._                                                                                                                                                                                    |
| **81**  | **Snuff**             | The source of any mundane light you can see is instantly snuffed out. _If left in one place for long periods, nearby light sources eventually dim, then finally go out._                                                                                                                     |
| **82**  | **Sort**              | Inanimate items sort themselves according to categories you set. _Rights itself when dropped or thrown._                                                                                                                                                                                     |
| **83**  | **Spellsaw**          | A whirling blade flies from your chest, clearing any plant material in its way. It is otherwise harmless. _Wrapped in stained leather, it should be oiled at least once a month_.                                                                                                            |
| **84**  | **Spider Climb**      | You can climb surfaces like a spider. _New cobwebs must be pushed aside prior to each use. They are hard to remove._                                                                                                                                                                        |
| **85**  | **Swarm**             | You become a swarm of crows, rats, or piranhas. You can only be harmed by _blast_ attacks. _Easily broken into a dozen distinct parts that slowly move towards one another over time._                                                                                                       |
| **86**  | **Target Lure**       | An object you touch becomes the target of any nearby spell. _Attracts all manner of magical creatures, spell leaks, and scrying._                                                                                                                                                            |
| **87**  | **Telekinesis**       | You may mentally 1 move item under 60lbs. _The owner can summon the book through mental command alone (WIL save or become deprived afterwards)._                                                                                                                                             |
| **88**  | **Telepathy**         | Two creatures can hear each other’s thoughts, no matter how far apart. _The holder can hear (but not respond) to the thoughts of whoever last possessed it, and vice versa._                                                                                                                 |
| **89**  | **Teleport**          | An object or person you can see is transported from one place to another in a 50ft radius. _Can be destroyed to create a portal to another dimension._                                                                                                                                       |
| **90**  | **Thicket**           | A thicket of trees and dense brush up to 50ft wide suddenly sprouts up. _Wrapped in vines that must be destroyed again with each use._                                                                                                                                                       |
| **91**  | **Time Control**      | Time in a 50ft bubble slows down or increases by 10% for 30 seconds. _Alternates its appearance as either impossibly old or freshly written._                                                                                                                                              |
| **92**  | **True Sight**        | You see through all nearby illusions. _Cannot be concealed by magic, and sticks out like a sore thumb._                                                                                                                                                                      |
| **93**  | **Upwell**            | A spring of seawater appears. _Hardened leather bindings caked in salt and living barnacles._                                                                                                                                                                                               |
| **94**  | **Vision**            | You completely control what a creature sees. _An unnerving, lidless eye graces the front cover._                                                                                                                                                                                             |
| **95**  | **Visual Illusion**   | A silent, immobile, room-sized illusion of your choice appears. _Filled with rich, colorful pages very much like a children's bedtime story._                                                                                                                                                |
| **96**  | **Ward**              | A silver circle 50ft across appears on the ground. Choose one species that cannot cross it. _The covers are decorated with bizarre, otherworldly creatures with thousands of eyes._                                                                                                          |
| **97**  | **Web**               | Your wrists shoot thick webbing. _The text is alien, yet somehow intelligible, for it is the language of dreams._                                                                                                                                                                            |
| **98**  | **Widget**            | A primitive version of a drawn tool or item appears before you and disappears after a short time. _Smells of iron and rust, sweat and effort. Faint sounds of harsh labor emanate from deep within its pages._                                                                               |
| **99**  | **Wizard Mark**       | Your finger can shoot a stream of ulfire-colored paint. This paint is only visible to you and can be seen at any distance, even through solid objects. _Inside the front cover is a small pocket containing a thin pad of paper, listing the name and date of death of all previous owners._ |
| **100** | **X-Ray Vision**      | You can see through walls, dirt, clothing, etc. _Long-term exposure can cause hair loss, blurry vision, and fatigue._                                                                                                                                                                        |

---

## Planned engine package

This is a scope report, not an implemented engine. The estimate assumes the same standard as the
existing Loner 3e and 24XX packages and the Fate Condensed plan: typed proposals, resolver-owned
rolls and state changes, strict save validation, faithful in-app character creation, player
decisions, prompt guidance, offline tests, and no rule parsing at run time. The package would live
at `src/aidm/engines/cairn_barebones/` and declare the engine ID `cairn-barebones`.

### Contract prerequisites

- **Optional advancement:** `Engine.advancement` must accept `None`, and runtime, UI, and harness
  callers must omit advancement offers and tools for this engine. Barebones has in-world growth and
  downtime training, but no XP, levels, or automatic end-of-adventure award; training is a play
  procedure, not an advancement advisor.
- **Resolver-owned random creation:** character creation must receive a seeded RNG (including its
  preview/test path) so names, age, attributes, HP, traits, background, armor, weapon, extra gear,
  gold, and random spellbooks are rolled rather than presented as elective menus. The UI may expose
  a reroll of the whole generated character, but not silently convert random tables into choices.
- **Engine-owned item state:** Cairn needs validated per-item slot size, uses, armor, damage dice,
  blast, spell/scroll/relic behavior, and recovery state keyed by world item ID. Ordinary improvised
  items default to one slot; catalog items are seeded from the selected content pack.

### Engine shape

- **Sheet and mechanics:** every actor has current and maximum STR, DEX, WIL, and HP; gold; deprived,
  panicked, critical, and scar state; and a pack ID. Mechanics also own typed item state, Fatigue
  slots, combat round/side state, exploration mode and elapsed turns or watches, season/weather,
  and active downtime projects. Inventory capacity is derived from carried world items and Fatigue,
  with petty/bulky sizing and the full-inventory 0 HP rule enforced at every item boundary.
- **Action proposals:** a staked `save` names the actor, STR/DEX/WIL, risky intent, and exact failure
  consequence; `attack-side` batches all declared attackers, targets, weapons, modifiers, and
  blast areas for one side; `cast-spell` names the held book or scroll and any enhancement; typed
  utility rolls cover the Die of Fate, reactions, morale, dungeon/wilderness events, weather,
  getting lost, supply, and other procedure tables. The Director decides when a rule applies, while
  every die and resulting state change belongs to a resolver.
- **Combat resolver:** first-round DEX saves gate each PC, then side actions resolve simultaneously
  from one pre-resolution snapshot. Attacks hit automatically; the resolver applies impaired d4,
  enhanced d12, dual-weapon and focus-fire keep-highest rules, blast, Armor 0–3, HP loss, overflow
  to STR, the immediate critical-damage save, exact-zero scars, morale, retreat, detachments, and
  death. Batching is required so an earlier result cannot erase an action already declared for the
  same side.
- **Exploration and downtime:** dungeon turns and wilderness watches consume light, rations, item
  uses, Fatigue, travel time, and weather effects through explicit commands. Rest and camp enforce
  their different safety and recovery rules. Research, training, and strengthening ties use typed
  1–5-milestone projects with explicit costs; completed training grants a validated trait or
  mechanical ability directly, without creating a generic XP subsystem.
- **Player decisions and guidance:** the player accepts or revises a save after seeing its risk but
  before rolling, declares their side's combat actions, chooses what to drop when forced Fatigue
  meets a full inventory, and chooses costs or routes for downtime milestones. Director guidance
  carries fiction-first adjudication, danger telegraphing, information, reaction/morale timing,
  spell risk, procedure cadence, and the rule that the model never invents a roll result.

### Size estimate

| Deliverable | Estimated size | Why |
| --- | ---: | --- |
| Engine and rules Python | 1,300–1,700 lines | More state than 24XX: simultaneous combat batches, actor/item mechanics, scars, recovery, exploration clocks, and downtime projects. |
| Director prompt | 150–220 lines | Fiction-first saves, danger telegraphing, combat declaration, spell risk, and dungeon/wilderness procedure cadence. |
| Shipped content pack | 2,000–2,800 JSON lines | Two d100 name columns, eight trait tables, 100 backgrounds, gear and price catalogs, four packages, and 100 spellbooks. |
| **Expected initial diff** | **4,100–5,600 lines** | Includes optional-advancement/random-creation plumbing, registration, offline behavior tests, and golden fixtures, but not this SRD document. |

For comparison, the current 24XX engine and rules Python total about 775 lines. Cairn's individual
roll-under save is simpler, but faithful simultaneous combat and the exploration/downtime procedures
make the whole engine larger; its shipped pack is much larger because Barebones makes its random
creation and spell tables part of the game.

### Content pack

The first and only required shipped pack should be `packs/srd.json`, named **Cairn: Barebones
Edition**. It is distributed under CC BY-SA 4.0 with the attribution at the top of this document and
should contain:

- the d100 given names and surnames, age formula, 3d6 attributes, d6 HP, eight d10 trait tables, 100
  backgrounds, armor/weapon rolls, additional gear, duplicate-reroll rule, and four optional gear
  packages;
- normalized equipment records for price, petty/one-slot/bulky size, uses, Armor, damage dice,
  blast, capacity bonuses, slow transport, healing, light, and other printed mechanical effects;
- all 100 spellbooks as separate spell and book-property fields, plus scroll and relic defaults;
- resolver tables and constants for reactions, scars, dungeon/wilderness events, path/terrain,
  seasonal weather, travel, hirelings, recovery, and marketplace services;
- no bestiary or implied setting. Barebones does not include either in this corpus; opponents and
  locations remain scenario canon, while later ShareAlike-compatible packs may add catalogs without
  changing resolver code.

A pack may replace creation tables, equipment, prices, spells, or procedure tables, but it cannot
alter the core save, inventory, combat, damage, recovery, or spellcasting invariants. Scenario
canon remains in the existing scenario format rather than in the engine pack.
