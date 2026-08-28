Yes — and I think there are actually **two different things you could mean by “reward player skill”**, and they lead to two very different fourth engines.

**Pokémon/Showdown rewards tactical skill.**
**Maze Rats rewards problem-solving skill.**

Of those, I think **Maze Rats is probably the better fourth *core* engine**, while the Pokémon idea is potentially the more exciting architectural experiment immediately after it.

### Why I like the Pokémon idea

The separation is extremely attractive:

```text
TTRPG world / Director
        |
        |  battle starts
        v
  Battle subsystem
  - teams
  - moves
  - switching
  - status
  - damage
  - AI opponent
        |
        |  battle ends
        v
BattleResult
- winner
- surviving/fainted creatures
- important events
- maybe injuries/rewards
        |
        v
TTRPG world resumes
```

Pokémon Showdown is unusually suitable for this. It explicitly ships as a JavaScript battle-simulation library and command-line simulator, supports Generations 1–9, and exposes player choices through a stream protocol. ([GitHub][1]) Its simulator accepts exactly the sorts of choices you'd want—moves, switches, team selections—and its repository even contains a `RandomPlayerAI` that randomly samples legal moves and switches. ([GitHub][2])

So your dumb-v1 NPC basically already exists.

And Showdown itself is MIT licensed. ([GitHub][3]) The obvious caveat is that an MIT license on Showdown's *software* isn't a license to commercially use Pokémon's characters, names, artwork, trademarks, etc.; I'd treat an actual Pokémon implementation as prototype/fan-project territory unless you separately settle that question.

But architecturally, I **really like it**.

The important change I'd make to your proposed interface is this:

**don't have `start_battle()` synchronously return the final result.**

If it does, the player didn't actually play anything.

Instead:

```text
Director:
    start_battle(enemy_id)

Engine:
    -> Battle started.
    -> normal TTRPG play suspends.

Player <-> Showdown
    choose move
    choose switch
    choose move
    ...

Showdown:
    -> BattleResult

Engine:
    apply BattleResult
    resume TTRPG

Narrator:
    describes aftermath
```

From the **Director's perspective**, though, your intuition is still correct: the battle is effectively opaque. It starts it and later receives "Alice won; Mon A fainted; Mon B has 23% HP; enemy fled" or whatever your domain result looks like.

That's extremely healthy.

It proves something new:

> **An engine mechanic doesn't have to be implemented by the AIDM rules framework at all. An engine can delegate a bounded domain to another deterministic system.**

That's a much more interesting architectural capability than adding another ten resolver functions.

### Your existing architecture is tantalizingly close already

You already allow an engine decision to resolve and immediately open another decision; `Engine.resume()` explicitly says it “may set `pending` again.” 

So conceptually:

```text
Battle decision:
    [Thunderbolt]
    [Quick Attack]
    [Switch to X]

player chooses Thunderbolt

Showdown resolves turn

Battle decision:
    [Thunderbolt]
    [Switch to X]
    ...

...
```

The problem is that the current turn loop still invokes the Director after every player input.  That would be pointless during a Showdown battle.

I **wouldn't solve that now**. Breathless first.

If Pokémon becomes engine four/five, that's when I'd introduce the concept of an **engine-owned interaction**: something where core hands control to deterministic engine code until that interaction finishes, without repeatedly waking the Director.

And importantly, following your existing YAGNI philosophy, I wouldn't invent a huge generic `SubgameFramework` ahead of time. Pokémon should prove what abstraction you actually need.

---

## But: Pokémon does not completely solve your “rails” concern

It solves it magnificently **inside combat**.

Outside combat, you could still get:

> Go here → talk → roll → succeed/fail → go there → battle → repeat.

And the Pokémon battle may actually make that contrast *more* visible: suddenly the player gets a rich decision space for ten minutes, then returns to a world where most decisions are interpreted by an LLM and resolved through one mechanic.

That's why I'd seriously consider **Maze Rats before Pokémon**.

Maze Rats is almost explicitly designed around the thing you're asking for. Its rules say that whenever possible actions should be resolved by the player simply describing what they do; a Danger Roll happens when something is risky and difficult to resolve through description. Its GM guidance says clever solutions should generally work, that combat is deliberately neither balanced nor fair, and that players should use preparation and ingenuity to rig situations in their favor. ([Scribd][4])

And the current rules are CC BY 4.0. ([Moddable Rules][5])

That's fascinating for AIDM because the gameplay becomes:

```text
"There are six goblins behind the door."

24XX:
    What skill do you use?
    What is the risk?
    Roll.

Breathless:
    What skill?
    How much resource pressure?
    Roll.

Maze Rats:
    "I pour lamp oil under the door,
     wedge the rear exit shut,
     light the oil,
     and shout that the shrine guards
     are coming from the north."

Engine:
    ...maybe no roll whatsoever.
```

**That's player skill.**

The player's ability to understand the fictional world becomes mechanically valuable.

And that puts pressure on an area of AIDM that none of the first three really test:

> **Can the system recognize that a good plan has changed or eliminated the uncertainty, instead of blindly funneling everything into a roll?**

That is exactly the anti-rail test I'd want.

### It also creates a beautiful four-engine portfolio

I would actually love this sequence:

| Engine         | What it tests               | Where player agency comes from                                 |
| -------------- | --------------------------- | -------------------------------------------------------------- |
| **Loner 3e**   | narrative/oracle play       | interpreting uncertainty                                       |
| **24XX**       | lightweight competency/risk | choosing approach and accepting risk                           |
| **Breathless** | resource pressure           | deciding when/how to spend dwindling resources                 |
| **Maze Rats**  | fictional problem solving   | **avoiding or reshaping mechanical tests through clever play** |

Those four are meaningfully different.

Maze Rats also has an enormous set of procedural tables for spells, monsters, NPCs, treasure, wilderness, dungeons, etc. ([Moddable Rules][5]) That's particularly interesting for your scenario/world-growth system without requiring another massive mechanical architecture.

Then:

### Engine five: Pokémon-style delegated tactical engine

That gives you another entirely new axis:

| Engine       | New architectural question                                                      |
| ------------ | ------------------------------------------------------------------------------- |
| Pokémon-like | Can an engine delegate an entire mechanic to an external interactive subsystem? |

At that point you're no longer merely collecting RPG mechanics. You're demonstrating that AIDM can support fundamentally different **kinds of games**.

---

## There are two other serious candidates, but I'd rank them lower

**Fate Accelerated** actually rewards clever tactical setup much more than I gave it credit for in the previous discussion. "Create an Advantage" lets the player manipulate the fictional situation, discover weaknesses, create aspects, and bank free invokes for later. ([Fate SRD][6]) A player who keeps saying "attack" is often substantially worse off than one who changes the environment and engineers advantages.

So Fate can absolutely reward player skill.

But it's **system-mastery skill**:

> discover weakness → create aspect → accumulate invokes → spend Fate → decisive action.

That's interesting, but it brings back precisely the negotiation/state machinery we've been wary of. I'd revisit Fate after architecture confidence returns.

**Forged in the Dark** is also strongly player-driven. The player chooses the action rating, while their fictional approach changes the GM's position and effect; fighting six people in the open versus forcing them through a narrow choke point can mechanically change the situation. ([Blades in the Dark][7]) Flashbacks, stress, resistance and resource expenditure make player decisions important too.

But I think it'd be another Cairn-scale architecture bomb. The SRD is CC BY, so licensing isn't the blocker. ([Blades in the Dark][8]) Complexity is.

### So my ordering would be

**Loner → 24XX → Breathless → Maze Rats → Pokémon/Showdown**

And I like that more than:

**Loner → 24XX → Breathless → Fate**

because each new engine teaches you something far more orthogonal.

The Pokémon concept in particular I would **keep**. I wouldn't even try to find a tabletop Pokémon RPG and implement its combat rules. That loses the beautiful property of your idea. The whole point is:

> AIDM handles the RPG.
> Showdown handles Pokémon battles.
> Neither needs to understand the other's internals.

That boundary is the interesting part.

And if, after doing Pokémon, you later discover another mechanic worth delegating—a tactical grid battle, card game, hacking minigame, spaceship combat, whatever—*then* you have the second implementation that justifies extracting a generic external/subgame interface. That would also line up perfectly with the architecture rule you already have about waiting for a second implementation before introducing an abstraction. 

[1]: https://github.com/smogon/pokemon-showdown "GitHub - smogon/pokemon-showdown: Pokémon battle simulator. · GitHub"
[2]: https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md?utm_source=chatgpt.com "pokemon-showdown/sim/SIM-PROTOCOL.md at master · smogon/pokemon-showdown · GitHub"
[3]: https://github.com/smogon/pokemon-showdown/blob/master/LICENSE?utm_source=chatgpt.com "pokemon-showdown/LICENSE at master · smogon/pokemon-showdown · GitHub"
[4]: https://www.scribd.com/document/745208557/Maze-Rats-Revised-Pages?utm_source=chatgpt.com "Maze Rats Revised Pages | PDF"
[5]: https://rules.moddable.games/maze-rats/index.html?utm_source=chatgpt.com "Maze Rats — Official Rulebook v0.1.0"
[6]: https://fate-srd.com/fate-accelerated/how-do-stuff-outcomes-actions-and-approaches?utm_source=chatgpt.com "How To Do Stuff: Outcomes, Actions, and Approaches • Fate Accelerated"
[7]: https://bladesinthedark.com/action-roll?utm_source=chatgpt.com "Action Roll | Blades in the Dark RPG"
[8]: https://bladesinthedark.com/licensing?utm_source=chatgpt.com "Licensing | Blades in the Dark RPG"

# DEV REQUEST

"What would a maze rat implementation look like if we want to be as high fidelity to its SRD as possible"

# RESEARCH OUTPUT

I think a high-fidelity Maze Rats implementation would be **surprisingly small mechanically, but quite demanding on the Director and scenario authoring**.

The mistake would be implementing it as “generic fantasy RPG + 2d6.” Maze Rats' actual identity is that the **character sheet is the fallback when the player's plan wasn't sufficient**. The rules explicitly say actions should normally be resolved through description; Danger Rolls come in only when something remains risky and difficult to settle from the fiction. ([Moddable Rules][1])

So I would target something like **8–9 Maze Rats mechanics/tools, one modest engine state, and a very opinionated Director/authoring prompt**.

## 1. The sheet would stay tiny

Something approximately like:

```python
class MazeSheet:
    strength: int  # +0..+4
    dexterity: int
    will: int

    health: Counter
    attack_bonus: int

    level: int  # 1..7
    xp: int

    paths: tuple[Path, ...]
    spell_slots: tuple[Spell | None, ...]

    equipment: dict[EntityId, CarryPosition]
```

`CarryPosition` matters because Maze Rats explicitly distinguishes **worn / belt / backpack / hands**. Belt capacity is two items; backpack capacity is deliberately “whatever reasonably fits,” and backpack items take 1d rounds to retrieve during combat. ([Moddable Rules][1])

I would **not** turn that into Cairn-style numeric inventory slots. That would actually reduce fidelity.

NPC sheets could be the same basic mechanical vocabulary—Health, Armor, AB, STR/DEX/WIL—but without XP, paths, etc. The SRD gives explicit shorthand levels for generating those values. ([Moddable Rules][1])

Items would mostly remain ordinary fictional objects. Only the few categories with actual rules need engine marks:

```text
light-weapon
heavy-weapon
ranged-weapon
shield
light-armor
heavy-armor
medicine
```

Most Maze Rats equipment should have **no mechanics whatsoever**. Rope, acid, chalk, marbles, crowbars, caltrops, wire, tongs, glue, etc. matter because of what the player does with them. That's the whole point.

## 2. The Director toolset would be tiny

I think I'd want approximately this:

| Tool                                 | What it does                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------------ |
| `danger_roll`                        | 2d6 + ability vs 10, optionally Advantage; also handles opposed rolls                |
| `encounter`                          | Reveals an unknown NPC/monster and rolls Reaction if disposition isn't predetermined |
| `begin_combat`                       | Establishes sides, surprise and rolls initiative                                     |
| `attack`                             | Resolves exactly one attack                                                          |
| `morale`                             | Resolves an NPC/group morale check                                                   |
| `cast_spell`                         | Consumes a spell and applies the GM's ruling                                         |
| `rest`                               | Meal/night or safe 24h recovery, plus morning spell generation                       |
| `pass_time` / exploration procedures | Advances dungeon/wilderness/city procedures                                          |
| `award_xp`                           | End-of-session 1–3 XP and opens advancement choices                                  |

Plus the small curated subset of your world tools that Maze Rats actually needs: movement, reveal, item transfer, traits, threads, death, etc.

Notably: **no generic skill check, no difficulty number, no consequences table, no success-with-cost system.**

### `danger_roll` is important semantically

I would not define it as:

```python
goal = "open the door"
```

I'd define it as:

```python
DangerRoll(
    actor_id="player",
    ability="dexterity",
    danger="The rusted mechanism snaps and jams permanently.",
    advantage="The player dismantled the outer plate first.",
)
```

Maze Rats says the roll determines whether you **avoid the danger**, not whether the action abstractly “succeeds.” ([Moddable Rules][1])

That's an important distinction.

If the player says:

> I loop my rope around the statue, stand behind the wall and pull the lever from twenty feet away.

and that completely removes the danger...

**the Director should call nothing.**

That's success.

If preparation merely reduces the risk, it gets Advantage: 3d6, keep the best two. And if several advantages stack up, the SRD says the action is usually no longer risky at all. ([Moddable Rules][1])

That rule should be practically screamed at the Director in its instructions.

## 3. Combat should be implemented faithfully, but not Cairn-style

I would **not** make one giant `fight_round` resolver.

Maze Rats combat contains meaningful player decisions turn-by-turn.

The engine owns a small transient:

```python
class CombatState:
    round: int
    player_side: tuple[EntityId, ...]
    enemy_side: tuple[EntityId, ...]
    acting_side: Side
    surprise: Side | None
```

`begin_combat()` rolls d6 initiative for each side, rerolling ties. Initiative rerolls every round, meaning the same side can act twice consecutively. Ambushers automatically win initiative and get Advantage on first-round attacks; the ambushed side's leader may get a WIL Danger Roll against surprise. ([Moddable Rules][1])

Then `attack()` implements exactly:

```text
2d6 + AB
must EXCEED armor

damage = attack_total - armor

heavy weapon: +1 damage
unarmed: -1 damage, minimum 1

double six:
    critical
    normally double damage
    OR GM chooses another appropriate effect
```

Those are the actual rules. ([Moddable Rules][1])

And **shield shattering must be a real player decision**.

Attack lands:

```text
Bandit attack: 10
Your armor: 8
2 damage incoming.
```

Engine opens:

> Shatter your shield and ignore the attack?

That maps beautifully onto the pending-decision system you already have; an engine decision can resolve through `Engine.resume()`. 

So:

```text
attack
 ↓
would damage PC with shield
 ↓
pending: shatter shield?
 ↓
YES → destroy shield, 0 damage
NO  → apply damage
```

That's highly faithful and requires no new core abstraction.

I'd also enforce ranged attacks being impossible while engaged in melee and heavy armor preventing Advantage on DEX Danger Rolls and surprise attacks. ([Moddable Rules][1])

## 4. Morale and reactions matter a lot

These are easy to miss but essential to Maze Rats.

When the players meet someone whose disposition is genuinely unknown:

```text
1    Hostile
2–3  Wary
4–5  Friendly
6    Helpful
```

([Moddable Rules][1])

I would wrap that into `encounter()` rather than asking the Director to remember:

```python
encounter("grave-robbers")
```

→ reveal them
→ disposition wasn't authored
→ engine rolls Reaction
→ returns `Wary`

That's better than exposing `reveal` followed by hoping the LLM remembers to call `reaction_roll`.

Morale should stay GM-triggered because the SRD says the GM *may* call one. Typical triggers include losing half the group, half an individual's Health, losing a leader, or being attacked with magic. NPCs should also retreat or bargain without rolling when that's plainly sensible. ([Moddable Rules][1])

So an attack that kills the third of six goblins could return:

```text
Three of six goblins remain.
This is a typical point for a morale check.
```

No generic `settle()` required.

The Director decides whether to call `morale()`.

## 5. Exploration is where Maze Rats becomes really interesting

I'd make **these engine-specific procedures**, not generic core lifecycle hooks.

For example:

```python
dungeon_time(minutes=10)
wilderness_travel(...)
city_travel(district_id)
```

Maze Rats' GM procedures actually specify pressure mechanisms.

Dungeon exploration checks for random encounters every 10 in-game minutes, with a 3-in-6 chance. Good dungeons are supposed to contain loops, branching routes, secrets and shortcuts so players can manipulate their environment and choose how to approach threats. ([Illusory Sensorium][2])

Wilderness travel has suggested rates of roughly 18 miles/day by road, 12 across open terrain and 6 through difficult terrain, with a 2-in-6 discovery check each day and each night. Multiple routes should offer different advantages and dangers. ([Scribd][3])

Cities use themed districts; moving through a district has a 1-in-6 encounter chance, and returning to town should expose the players to multiple adventure rumors so they choose what to pursue. ([Illusory Sensorium][2])

That is **exactly** how you combat rails.

The world isn't:

```text
A → B → C → boss
```

It's:

```text
             haunted woods
            /             \
town ── old bridge         ruined road ── dungeon
  \          |               /
   smugglers' trail ────────
```

And each route creates different risk/resource/information tradeoffs.

## 6. Magic is probably the most unusual implementation problem

Maze Rats magic is excellent for AIDM.

At character creation and every morning after a full night's rest, empty spell slots get **randomly generated spells**. A spell is built by rolling a formula and combining entries from the Effect/Element/Form tables. ([Moddable Rules][4])

The official CC material is already available as structured tables. For example the magic data contains the Physical/Ethereal Effects, Elements and Forms plus the spell formula table. 

So code should generate:

```text
Grasping + Shadow
→ Grasping Shadow
```

Not the LLM.

Then comes the intentionally fuzzy part:

> What does **Grasping Shadow** actually do?

The SRD says the GM tells the player its general effect based on the name, and players can later propose alternate uses if they strongly fit that name. ([Moddable Rules][4])

That means I would store:

```python
class Spell:
    name: str
    general_effect: str
```

The **name is mechanically generated**.

The **general effect is a Director ruling** that becomes stable once established.

Casting removes the spell from the slot. Offensive targets typically get Danger Rolls; if the spell deals damage, the GM may assign flat damage or 1–6 dice. ([Moddable Rules][4])

This is one place where I'd probably tolerate a tiny engine-specific LLM-assisted creation step, because interpreting generated spell names is explicitly a GM task in Maze Rats.

## 7. Character creation can be almost exact

You can reproduce the SRD's twelve steps essentially verbatim.

Characters begin with ability bonuses distributed among STR/DEX/WIL, 4 Health, and one starting specialization: +1 AB, one spell slot, or one Path. The four starting Paths grant Advantage in their domains. Players then receive six rolled/chosen utility items plus light armor, shield and two weapons, and roll or choose appearance/background/clothing/personality/mannerism before recording level 1 and 0 XP. ([Moddable Rules][4])

This fits your existing creation architecture extremely well.

And importantly:

**background should not become a skill.**

The SRD explicitly says background has no specific mechanical effect, although the GM can use it when judging what a character knows or who they know. ([Moddable Rules][4])

Perfect Director context.

## 8. Advancement is also nicely player-owned

Maze Rats awards the whole party 1–3 XP at session end based on achievement, with fixed level thresholds. Alternating levels grant ability increases versus a choice of AB/path/spell slot; Health rises every level, and level 7 allows retirement. ([Moddable Rules][1])

So `award_xp()` might automatically hit a threshold and open:

> You reached level 3. Choose one:
>
> Attack Bonus +1
> Learn a new Path
> Gain a spell slot

Again, that's exactly what your pending-decision architecture is good at.

The only awkward concept is **“session.”** AIDM currently thinks mostly in turns/adventures, whereas Maze Rats advancement literally happens at session boundaries. For maximum fidelity I'd expose an explicit **End Session** action rather than silently redefine “session” as “quest.”

## 9. The biggest implementation work should actually be authoring

This is where I would be strict.

A Maze Rats scenario creator should be forbidden from creating a predetermined chain of scenes. Its guidance should strongly encode:

> situations, not plots; player skill, not PC skill; tools, not upgrades; reveal the world; offer tough choices; reward clever solutions; bring the world to life.

The GM guide explicitly says not to prepare plots, to let player decisions determine direction, to provide enough information for meaningful decisions, and to make greater dangers more obvious. Clever solutions should generally work; combat is intentionally unbalanced, and players should rig circumstances in their favor through planning. ([Illusory Sensorium][2])

And I'd go one step further:

**Maze Rats scenario creation should actually roll Maze Rats tables.**

The SRD isn't just rules. It contains hundreds of tables for monsters, NPCs, cities, treasures, wildernesses, dungeons, spells, etc.; structured CC BY data is available for exactly that purpose. ([Moddable Rules][5])

So rather than:

```text
LLM: invent a monster
```

I'd have authoring do:

```text
roll monster base
roll features
roll trait
roll ability
roll weakness
roll tactic

→ hand results to Scenario Creator
→ Scenario Creator integrates them coherently
```

That would make generated Maze Rats campaigns feel substantially more like **Maze Rats**, rather than merely fantasy scenarios running its combat rules.

## What I think the architecture impact should be

Very little.

The existing concept of deterministic player actions already fits gear management nicely: those actions explicitly represent player-owned changes between turns without Director judgment. 

Your pending-decision mechanism fits shield destruction and advancement.

Your entity/world model fits open exploration.

Your packs can hold the Maze Rats procedural tables.

I would **not add `settle()`, generic encumbrance hooks, generic combat infrastructure, generic spell infrastructure, or generic exploration callbacks to core**.

Maze Rats owns all of those.

The one new thing I might want is better **engine-specific authoring tools**, because Maze Rats' random generators should ideally be callable tools rather than dumping thousands of table entries into the Scenario Creator prompt.

And that's actually a healthy architectural pressure.

### So my fidelity target would be very high

I think you could realistically ship Maze Rats with something like:

**Mechanical deviations: 0–2.**

The likely unavoidable/documented ones would be product-related rather than rules-related: how AIDM defines a “session,” and perhaps how precise 30-foot combat positioning is represented without implementing a tactical map.

Everything important—Danger Rolls, Advantage, opposed rolls, reaction, morale, initiative, attack/damage, criticals, shield shattering, encumbrance locations, healing, Paths, spells, XP/levels, procedural tables, wilderness/dungeon/city procedures—can fit without twisting the architecture badly.

And that's what makes me much more enthusiastic about it than Cairn: **high-fidelity Maze Rats should mostly require better GM behavior and richer scenario structure, not increasingly sophisticated core machinery.**

[1]: https://rules.moddable.games/maze-rats/rules/core-rules/ "Core Rules — Maze Rats"
[2]: https://illusorysensorium.com/content/files/2024/06/Maze-Rats.pdf?utm_source=chatgpt.com "Gamemaster’s Guide"
[3]: https://www.scribd.com/document/745208557/Maze-Rats-Revised-Pages?utm_source=chatgpt.com "Maze Rats Revised Pages | PDF"
[4]: https://rules.moddable.games/maze-rats/rules/character-creation/ "Character Creation — Maze Rats"
[5]: https://rules.moddable.games/maze-rats/index.html "Maze Rats — Official Rulebook v0.1.0"

# OPINION (2026-08-28, checked against the tree)

The research says "the architecture impact should be very little." The code agrees. No refactor of
scenario creation or growth is needed. Maze Rats is one engine package plus tables, and at most
one small core hook.

## What already fits

- `Entity.exits` is a graph with `known` and `locked` per exit. Loops, shortcuts and multiple
  routes are legal today. The authoring bar (`_bar_unmet` in `authoring/draft.py`) already demands
  hidden exits, locked exits, hidden items and `when_reached` consequences. That is "situations,
  not plots."
- Growth exists: `GrowthRun`, `extend_brief`, and the `growth_frontier` trigger in
  `app/runtime.py`. "Return to town, hear new rumors" and "cross into a new hex" are the same
  frontier trigger with an engine-specific briefing.
- `Engine.seed()` fills in rules for entities the model creates without them. Monster and NPC
  shorthand (Health, Armor, AB from level) and morning spells roll there. Breathless refuses a
  rules-less item; Maze Rats rolls one instead.
- `PendingDecision` + `Engine.resume()` carry shield shattering and level-up choices.
  `player_action` carries belt/backpack moves and End Session.
- Wilderness, dungeon and city procedures need no new location kind. A location's `rules` holds
  `{"terrain": "difficult", "miles": 6}` or `{"district": true}`; the engine's `pass_time` reads it.

## The engine package

| File | Contents | Size |
|---|---|---|
| `rules.py` | `Sheet` (STR/DEX/WIL, health, AB, level, xp, paths, spell slots), `ItemSheet` (weapon class, armor, carry position), `Mechanics` with a transient `CombatState`; rules `danger_roll`, `encounter`, `begin_combat`, `attack`, `morale`, `cast_spell`, `rest`; action `pass_time`; decisions `ShatterShield`, `LevelUp` | ~600 lines, like 24XX |
| `engine.py` | creation (the 12 SRD steps), `seed`, `validate` (belt ≤ 2), `authoring_instructions` | ~200 lines |
| `packs/srd.json` | the CC BY tables: spells, monsters, NPCs, treasure, dungeon/wilderness/city | data only |
| `director.md` | the one rule to scream: a plan that removes the danger means call nothing; a plan that reduces it means Advantage | prose |

## The one core change, if any

Authoring should get pre-rolled table results. The lazy path is zero core change:
`Engine.authoring_context()` is already engine-owned, so the Maze Rats engine rolls six monsters,
six NPCs and a dungeon seed and writes them into the briefing text. Add an
`Engine.authoring_tools` hook appended in `authoring_toolset` (about ten lines) only if the model
proves it needs to roll more mid-draft.

## Deviations: two

1. **Session.** An explicit `end_session` player action awards XP. Product-level, documented.
2. **30-foot positioning.** `CombatState` holds `engaged` only; ranged attacks refuse for engaged
   actors. No map.

A spell's `general_effect` stored as a Director ruling is per SRD, not a deviation.

## Order of work

1. Read `twentyfourxx/rules.py`; its combat transient is the closest template for `CombatState`.
2. `rules.py` + `engine.py` + `director.md` with the turn evals: two to three sessions.
3. Tables into `packs/srd.json` and the authoring prompt: one session.
4. Playtest the danger-roll rule against the weak model; tune `director.md`: one session.
