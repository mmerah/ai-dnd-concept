# Maze Rats

Maze Rats is a fantasy game of exploration, problem-solving and survival by Ben Milton. This engine
keeps its central rule intact: describe what the character does, and roll only when a danger is
still risky after the player's preparation and choices.

## Sources and licence

Everything mechanical here was taken from the rulebook itself, not from summaries of it:

- [Core Rules](https://rules.moddable.games/maze-rats/rules/core-rules/) — danger rolls, advantage,
  NPC reactions, initiative, combat, NPC morale, healing, encumbrance, levelling, monster stats
- [Character Creation](https://rules.moddable.games/maze-rats/rules/character-creation/) — the
  twelve steps, starting gear, and spell generation and casting
- The seven machine-readable table files under
  [`rules.moddable.games/games/maze-rats/data/`](https://rules.moddable.games/games/maze-rats/data/)

Maze Rats is copyright Ben Milton (questingblog.com), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The pack at
`src/aidm/engines/mazerats/packs/srd.json` is a transcription of the CC BY tables and carries that
attribution and licence. `tools/import_mazerats_pack.py` regenerates it from the source files and is
the record of how it was made.

**Maze Rats has three rules pages: Core Rules, Character Creation, Character Sheet.** It has no
dungeon clock, no wandering-monster check, no travel rates and no district encounter chances. If a
future change wants one of those, it is a house rule and belongs in this list, not in the engine as
if it were printed.

## The tools

Seven game-master tools, one per section of the SRD's own core rules:

| tool | SRD section |
|---|---|
| `danger_roll` | Danger Rolls, Advantage, Opposed Danger Rolls, **and NPC Morale** |
| `reaction` | NPC Reactions |
| `attack` | Initiative and Combat |
| `cast_spell` | Casting a Spell |
| `rest` | Healing |
| `level_up` | Levelling Up |
| `stow` | Encumbrance |

Morale has no tool of its own on purpose. The SRD says the GM "may call for a WIL danger roll to see
if they rout or beg for mercy" — it *is* a danger roll, not a separate procedure.

`change_world`, `move` and `unlock_way` belong to the rooms kit, not to Maze Rats.

## Deviations

Each of these departs from the printed rules, with the reason.

### Because there is no second human at the table

1. **An NPC's shield decision is made by the resolver.** The SRD gives the choice to the defender:
   "If the defender has a shield, they may choose to shatter it." When the defender is the player or
   a companion, the player is asked. When an NPC is the defender, the engine shatters the shield only
   if the hit would take it to zero health or less, and otherwise takes the hit.
2. **Session end is an explicit action.** `level_up` awards the SRD's 1–3 XP. A tabletop group
   decides when a session ends; a browser game that survives reloads needs someone to say so.

### Because a place is the unit of space

3. **No thirty-foot positioning inside a place.** The SRD measures movement and range in fictional
   space. The map's unit is a place, so distance inside one is fiction the game master narrates.
4. **Ranged attacks are refused only once combat is open.** The SRD says "attacking with a ranged
   weapon is impossible while in melee combat". The shot that *starts* the fight is allowed, because
   the first shot happens before there are any sides, and the strict reading would make ranged
   weapons unusable at the moment they are most useful.
5. **"Once per day" for medicine is bounded by rests, not by a clock.** A dose sets a flag that any
   rest clears, so two doses cannot fall inside one rest cycle. With no time-keeping in the game,
   a rest is the only day boundary there is.
6. **Backpack items are found immediately.** The SRD says "backpack items take 1d rounds to find".
   Belt capacity (two items) and the two-hand budget *are* enforced; the retrieval delay is not,
   because it needs a round-by-round action economy outside combat, which the SRD does not otherwise
   have.

### Character creation

7. **Creation asks twelve steps.** SRD steps 1–11 are asked, step 2 (record 4 health) is a constant
   rather than a question, step 5 is split into two weapon picks so both are choosable, and one step
   that is ours — the table set — comes first. SRD step 12 records name, level and XP; the app
   collects the name outside the step list, and level 1 with zero XP are defaults.
8. **The alternate ability method is not offered.** The SRD's "roll 1d for each ability separately"
   is explicitly a GM permission, and there is no GM-permission concept in character creation. The
   six printed rows are.
9. **Weapons are picked by class, not by name.** The player chooses light, heavy or ranged; the
   SRD's example names are shown as the option's detail. Only the class changes a rule.
10. **Carry positions are assigned, not chosen.** Armour is worn, the shield is held, the first
    one-handed weapon fills the other hand, and the rest go to belt and backpack within the limits.
    The SRD lets the player record any legal location. During play `stow` moves any carried item
    between the four locations, so the assignment is only a starting layout.

### The tables

11. **A table roll is uniform over the table's real length.** The book says to roll 2d on a 36-entry
    table, the first die picking a group of six and the second the entry within it. That is the same
    uniform distribution, and it is the only defined resolution for the tables the source prints with
    34, 35 or 37 entries.
12. **The source's pointer tables ship inert.** `npc-names`, `npc-professions`, `inn-names`,
    `animal` and `items` name other tables to roll on. They are carried verbatim so the pack is a
    complete record of the source, but nothing expands their `{table}` placeholders yet.
13. **Four tables come from the rules page, not the data files.** `starting-items` and the three
    weapon lists are printed as prose in Character Creation. They are transcribed verbatim and
    capitalised to match the data files' style; each says so in its own `note`.

### Combat and rolls

14. **Combat is enlisted, not conscripted.** The SRD never says who is in a fight; it says only that
    "both sides roll a die when combat breaks out". Opening a fight puts the player and their
    companions on one side and the attacker and target on the other. Anyone else standing in the
    place is a bystander until they attack or are attacked, at which point they join the side
    opposite their opponent and may act in that side's current turn. Enlisting the whole room would
    make a friendly NPC an enemy who must attack the party or die before the round could end.
15. **An ambush is refused once combat is open.** The SRD grants an ambush automatic initiative and
    first-round advantage, and both are properties of a fight's opening. `attack` refuses `ambush`
    in a fight already under way rather than silently ignoring it; a surprise mid-fight is advantage
    on the attack, which the situation already grants.
16. **Each side of an opposed danger roll uses its own ability.** The SRD says only that "both
    characters make a danger roll", leaving the defender's ability to the GM. `danger_roll` takes
    `opposed_ability` for the resisting side, defaulting to the actor's own ability when it is null —
    a shove is strength against a defender's dexterity if that is what the fiction says.

## Fidelity

Implemented as printed, and worth naming because an earlier version of this engine got them wrong:

- **XP thresholds are 2, 6, 12, 20, 30, 42.**
- **Every level grants +2 maximum health and does not change current health.** Levels 2, 4 and 6
  raise an ability by 1 to a maximum of +4; levels 3, 5 and 7 pick attack bonus +1, a new path, or a
  spell slot. **Level 7 gets its pick**, and may then retire.
- **Healing is flat.** A meal and a full night restore 1 health; 24 hours safe restores all of it; a
  dose of medicine restores 1.
- **Initiative is rerolled after every round**, so a side can act twice in a row.
- **Each character on the acting side takes one action per side-turn**, not one action per side.
- **An ambush** seizes initiative and grants advantage on the ambusher's attack rolls in round 1.
- **Heavy armour denies advantage** on DEX danger rolls and on ambush attack rolls.
- **Damage** is the attack total minus armour; heavy weapons add 1, unarmed attacks subtract 1 but
  never below 1, and double sixes double the total.
- **Armour** is 6 plus light armour (+1) or heavy armour (+2) plus a shield (+1). A monster's sheet
  carries its armour as the 0–4 bonus above the base 6, matching the SRD's 6–10 categories.
- **Opposed danger rolls** are implemented, and defenders win ties.
- **An ability already at +4 is not offered** at levels 2, 4 and 6. The SRD caps abilities at
  +4, and the level's benefit is a real choice, so a maxed ability is removed from the options
  rather than silently clamped.
- **Paths** grant advantage on a related danger roll: the game master passes `advantage`.
- **A spell's name is generated and its effect is a ruling.** This is the SRD procedure — "the GM
  then tells the player the spell's general effects, based on its name" — and not a deviation.

The authored map that Maze Rats plays on belongs to this app's rooms kit, not to Maze Rats. The game
supplies dungeon, wilderness and city tables to build such a place with; it prescribes no structure
for one.
