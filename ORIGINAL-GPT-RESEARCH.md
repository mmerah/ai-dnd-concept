## Conclusion

For the system you described, I would **not use 5e, and I would not use Ironsworn unchanged**.

I would build a small universal rules layer I’ll call the **Scenario Kernel**, with **Loner 3e as the starting mechanical chassis**, then steal three very specific ideas from other games:

**Loner 3e resolution + characters** → **Ironsworn/Starforged progress clocks** → **GUMSHOE's guaranteed core clues** → optionally **Cairn procedures for location-crawl scenarios**.

The important architectural choice is: **the PDF generates a scenario kit, not a new RPG system**. Characters and tools should run on one stable underlying kernel across every scenario.

That distinction solves a surprising number of problems.

---

# Why Loner is the best starting point

I hadn't expected Loner to come out on top when I started looking. It fits almost freakishly well.

The currently published Loner SRD identifies itself as **3rd Edition, published July 31, 2026**. It describes itself as solo-first, rules-light, tag-based, emergent, genre-independent, and built around one core mechanic. Its standard character is essentially:

> Concept + two Skills + Frailty + two Gear + Goal/Motive + optional Nemesis + 6 Luck.

There are no conventional stats. ([Loner SRD][1])

Even better for your software architecture, Loner says **"everything is a character"**: NPCs, factions, organizations, vehicles, curses, and other significant objects can all use basically the same Concept/Skills/Frailties/Tags structure. Environmental details and conditions are tags too. ([Loner SRD][1])

That gives you an extremely nice canonical data model.

```text
Entity
  id
  name
  concept
  capability_tags[]
  weakness_tags[]
  detail_tags[]
  condition_tags[]
  goal?
  motive?
  relationships[]
  luck?
  source_refs[]
```

The same structure can represent:

```text
Mara Venn
Concept: Disgraced polar explorer
Skills: Ice Navigation, Field Medicine
Frailty: Recklessly Curious
Gear: Flare Pistol, Survey Kit
Goal: Find the lost expedition

The Borealis Station
Concept: Abandoned Arctic research station
Skills: Hardened Structure, Emergency Generator
Frailty: Flooded Lower Deck
Conditions: Failing Power, Something in Ventilation

Northern Minerals Consortium
Concept: Secretive extraction company
Skills: Political Influence, Deep Pockets
Frailty: Internal Rivalry
Goal: Recover the samples before anyone learns what they contain
```

For PDF→game conversion, that's dramatically nicer than generating STR/DEX/CON, armor classes, challenge ratings, spell lists, saving throws, levels, monster abilities, etc.

### The resolution mechanic is also almost ideal for an LLM referee

Loner asks a closed question and compares a **Chance d6** against a **Risk d6**. The resulting semantics are:

| Dice result            | Fictional result          |
| ---------------------- | ------------------------- |
| Chance wins, both high | Yes, and…                 |
| Chance wins            | Yes                       |
| Chance wins, both low  | Yes, but…                 |
| Risk wins, both low    | No, but…                  |
| Risk wins              | No                        |
| Risk wins, both high   | No, and…                  |
| Tie                    | Yes, but… + Twist Counter |

Advantage adds a second Chance die; disadvantage adds a second Risk die; only the highest is kept. Crucially, positive and negative tags cancel and **you can never stack beyond two dice**. ([Loner SRD][1])

That's exceptionally LLM-friendly. Your referee only has to answer:

```text
Is this outcome uncertain?
Which existing tags genuinely matter?
Advantage / neutral / disadvantage?
```

The tool does everything else.

The LLM doesn't get to invent a +7 because it really likes the player's plan.

Loner also has a Twist Counter: doubles accumulate tension and every third such result triggers a contextual twist. ([Loner SRD][1]) Its conflict rules explicitly allow fights, chases, negotiations, sabotage, etc. to be resolved as a series of important actions rather than switching into a separate tactical minigame. ([Loner SRD][1])

That's exactly the property I'd want for chat.

One current-version wrinkle: the Loner site also says **Loner 4e entered open beta on May 29, 2026**, even though the public SRD currently presents the 3e rules dated July 31. So I'd target the published 3e rules as your v0 semantics and read the 4e beta for ideas rather than tying your implementation to it. ([Loner SRD][1])

---

# Why not just use Ironsworn?

Ironsworn is the clear runner-up.

It was explicitly designed for **solo, co-op, and guided play** and has quests, moves, momentum, progress tracks and oracles built into the actual game rather than added as a GM emulator. ([Tomkin Press][2])

This is extremely attractive for an AI GM because Ironsworn already answers questions like:

* How do we create forward motion?
* What constitutes a scene-worthy action?
* How do quests progress?
* When does something go badly?
* How do we surprise a solo player?
* When is a story thread ready to resolve?

Starforged goes further and its playkit explicitly includes **progress tracks, clocks and scene challenges**. ([Tomkin Press][3])

The problem is that you'd inherit a lot more machinery than you need. Ironsworn has a move for most common situations, five stats, assets, momentum, action rolls versus challenge dice, vows, progress moves, and setting assumptions. ([Tomkin Press][2])

That is fantastic human-facing RPG design. For your use case, however, every additional named move creates another classification problem for a tiny referee model:

> Is this *Face Danger*, *Secure an Advantage*, *Gather Information*, *Compel*, *Undertake a Journey*, something else, or no move?

Loner collapses most of that to:

> "Is this uncertain, and what tags matter?"

I'd therefore **steal Ironsworn's campaign scaffolding rather than its entire action-resolution system**.

---

# The systems I would shortlist

This is my assessment for *your particular application*, not a claim about which RPG is generally "better."

| System                                         | Solo propulsion | Arbitrary PDF/genre |  Agent burden | My verdict                                                                   |
| ---------------------------------------------- | --------------: | ------------------: | ------------: | ---------------------------------------------------------------------------- |
| **Loner 3e** ([Loner SRD][1])                  |       Excellent |           Excellent |      Very low | **Best kernel**                                                              |
| **Ironsworn / Starforged** ([Tomkin Press][2]) |       Excellent |              Medium |        Medium | **Best source of campaign mechanics**                                        |
| **Push** ([itch.io][4])                        |            Good |           Excellent | Extremely low | Fascinating, but possibly *too* mechanically ungrounded                      |
| **24XX** ([itch.io][5])                        |            Weak |           Excellent |      Very low | Best alternative if you want skill-die differentiation                       |
| **QuestWorlds** ([QuestWorlds][6])             |            Weak |           Excellent |    Low-medium | Excellent universal narrative RPG; would need your own solo engine           |
| **Cairn 2e** ([Cairn][7])                      |            Weak |              Medium |      Very low | Excellent optional dungeon/exploration module                                |
| **Fate** ([fate-srd.com][8])                   |            Weak |           Excellent |        Medium | Aspects map well to PDFs, but Fate-point/invoke/compel state adds complexity |
| **D&D 5.5e / SRD 5.2.1** ([D&D Beyond][9])     |            Poor |         Poor-medium |          High | Wrong default; add later only if "play D&D" becomes a goal                   |

### A particularly interesting alternative: Push

Push deserves mention. It is GM-less, supports singleplayer, has no stats, and resolves everything with a single push-your-luck mechanic. Its design explicitly says characters, foes, weapons, items, and money carry no numerical mechanics. ([itch.io][4])

That's almost unbeatable for implementation simplicity.

But I'd still choose Loner because **Loner's tags mechanically constrain advantage/disadvantage**. With Push, character competence is deliberately less mechanically relevant. That's elegant tabletop design, but I think it gives your LLM too much authority over whether "Elite Safecracker" actually matters.

---

# Why 5e is the wrong abstraction

Licensing isn't the issue anymore. The current D&D SRD 5.2.x is CC BY 4.0 and contains the updated 5.5e foundational rules. ([D&D Beyond][9])

The problem is its *shape*.

The SRD itself encompasses character creation, classes, backgrounds, species, feats, spells, equipment, exploration, the rules glossary, magic items, monster stat blocks, and many interacting mechanics. ([D&D Beyond][9])

That complexity buys D&D something valuable: **D&D characters feel mechanically like D&D characters**.

But imagine importing:

* a Cold War espionage PDF;
* a book about Antarctic exploration;
* a Sherlock-Holmes-like story;
* a cyberpunk sourcebook;
* an archaeological catalog.

With 5e, your scenario compiler immediately has to answer nonsense questions like:

> What Challenge Rating is a corrupt customs official?

> Is an investigative journalist a Rogue or Bard?

> What's the AC of the locked archive?

> How many HP does existential dread have?

You can make all of that work, but you're fighting the representation.

With tags, the PDF's own language **becomes the representation**.

That's a major advantage for both retrieval fidelity and cheap-model reasoning.

---

# I would **not** generate a custom RPG for every PDF

This is probably the strongest design conclusion from the research.

Generating a bespoke ruleset sounds compelling—"this submarine manual deserves submarine mechanics!"—but I think it is exactly the wrong boundary.

Your goal requires **character portability**. If Alice was created in Scenario A, then you want Alice to enter Scenario B. That becomes very difficult if each scenario invents a new attribute system, damage model and resolution procedure.

It also makes your agents significantly harder to evaluate. A stable tool such as:

```text
resolve_risk(question, advantage_state)
```

can be tested tens of thousands of times.

A PDF-generated rule like:

```text
whenever navigating spiritual bureaucracy,
roll Bureaucratic Resonance + Past-Life Debt...
```

cannot.

Instead, I would let the PDF choose **a rules profile assembled from a small fixed library of modules**.

That is the sweet spot between universal RPG and bespoke RPG.

---

# The exact system I'd build

**Base rules: Loner-like. Scenario structure: custom.**

1. **Characters and everything important use tags.** Start essentially with Loner's Concept, two capabilities, one frailty, two signature items, drive/goal, conditions and six Luck. Significant NPCs, factions, vehicles and locations use the same schema. This symmetry comes directly from Loner and is one of its strongest ideas for software. ([Loner SRD][1])

2. **Use one universal six-outcome resolution tool.** Keep Loner's Chance/Risk dice, advantage/disadvantage cap, and `Yes and / Yes / Yes but / No but / No / No and`. Keep the Twist Counter inside that deterministic tool as well. ([Loner SRD][1])

3. **Add progress and danger clocks.** A scenario should contain `progress`, `threat`, and occasionally `relationship` tracks. This is the piece I'd borrow from Ironsworn/Starforged rather than importing all of Ironsworn. Starforged explicitly uses progress tracks and clocks as campaign/scene tools. ([Tomkin Press][3])

4. **Add the GUMSHOE "core clue" invariant.** If information is necessary for the adventure to continue and the player credibly investigates the right thing, they get it. A roll can determine extra information, cost, danger or complications—but not whether the campaign becomes impossible. GUMSHOE explicitly guarantees relevant core clues when the corresponding investigative approach is used. ([pelgranepress.com][10]) This is *extremely* important when an LLM controls mysteries.

5. **Use fixed optional procedure modules.** A dungeon/location scenario can activate an exploration cycle inspired by Cairn: turns, environmental events, signs/clues, resource pressure and meaningful searches. Cairn 2e has explicit dungeon turns and an event procedure, while retaining extremely light underlying resolution. ([Cairn][7]) A political scenario instead activates faction/relationship clocks; horror activates stress/dread; survival activates supply/exposure. These are predefined modules, not PDF-generated rules.

6. **Do not have a separate combat game by default.** A swordfight, trial, chase, argument, hacking duel and escape should all be "conflicts." Loner itself supports resolving conflicts through a sequence of key Oracle questions and even recommends treating coordinated mobs as one entity when useful. ([Loner SRD][1]) Reserve detailed tactical combat as a future optional rules profile.

That is the RPG I'd actually want the agents to operate.

---

# Then PDFs become "Scenario Packs"

This is where Loner gives you another useful precedent. Its existing Adventure Packs contain setting material followed by things like Concepts, Skills, Frailties, Gear, special rules and factions. ([Loner SRD][11]) The broader Loner line deliberately keeps the same underlying tags/oracle while changing genre. ([Loner][12])

Your PDF importer can generalize this enormously.

I would compile every PDF into something conceptually like:

```text
ScenarioPack
  premise
  tone
  source_fidelity

  world_truths[]
  world_rules[]

  locations[]
  characters[]
  factions[]
  objects[]

  open_threads[]
  core_clues[]
  optional_secrets[]

  progress_clocks[]
  threat_clocks[]

  encounter_tables[]
  inspiration_tables[]

  suggested_character_tags[]
  scenario_permissions[]
  active_modules[]

  source_refs[]
```

The critical distinction is between **source truth** and **generated connective tissue**.

For example:

```text
truth:
  "Reactor coolant must remain below X temperature."
  source: page 37

generated_scenario_fact:
  "Someone has disabled the secondary coolant pump."
  provenance: scenario_generator
```

Then your Narrator cannot accidentally turn the second thing into something supposedly stated in the PDF.

I would actually expose a simple scenario-generation setting with something like **Faithful / Inspired / Wild**. "Faithful" keeps source facts fixed and invents only conflicts around them; "Wild" is free to remix the document into something bizarre.

---

# The agent team should be smaller than you might think

There is directly relevant research here.

A 2025 study built almost exactly this sort of solo chat RPG. Their first design suffered from changing details, forgotten inventory, and worsening coherence as play continued. They redesigned it as **two LLM agents: Narrator + Archivist**, with persistent world state. ([arXiv][13])

The Archivist's job was explicitly to maintain characters/environments through narrow JSON tools. ([arXiv][13]) The tool descriptions standardized "when to use", examples, and JSON input structure. ([arXiv][13]) Their comparative evaluation reported improved modularity and game experience for the agentic version. ([arXiv][13])

I would therefore **not** make six LLMs debate every player message.

I'd use:

```text
                     ┌─ source_retrieval()
Player → Referee ────┼─ resolve_oracle()
                     ├─ roll_table()
                     ├─ tick_clock()
                     └─ apply_condition()
                           │
                           ▼
                       Narrator
                           │
                           ▼
                       Archivist
                           │
                           ▼
                    Canonical state
```

The "Referee" can be a tiny model—or often simple code—which determines whether a resolution is needed and identifies relevant tags. The Narrator owns prose. The Archivist owns state changes.

A **Director** can exist, but I'd invoke it only at scene boundaries to select the active thread, determine pressure and check pacing. Loner already treats scenes as units with short-term goals and has a procedure for changing scene mood. ([Loner SRD][1])

There is supporting interactive-fiction research for this separation too: ACL work has found that controlling longer stories through smaller narrative segments improves control, while later work specifically targets both dramatic structure and player agency rather than simply having an LLM freestyle indefinitely. ([ACL Anthology][14])

So I'd make the Director manage **threads and pressure, never plot outcomes**.

---

# One thing I would enforce ruthlessly

**LLMs describe; code decides.**

Randomness is a tool call.

Luck is code.

Clocks are code.

Inventory/state mutations are code.

Which source page says something is retrieval.

Whether an entity exists is state.

The LLM gets to decide things such as:

> "Given `No, but...`, the locked door remains shut, but Mara notices fresh boot prints disappearing into the service corridor."

It doesn't get to decide:

> "Actually the roll was probably a success."

That division is probably more important than which small model you eventually use.

---

# Character portability gets much easier

This is another reason I wouldn't choose D&D or scenario-specific rules.

A portable character could be only:

```text
Name
Concept

Capabilities × 2–3
Frailty × 1
Signature Gear × 2

Drive
Relationships

Persistent Conditions
Growth Tags

Luck
```

A character like:

> **Evelyn Park — Exhausted investigative reporter**
> Persistent Source Network
> Reads People Too Well
> Can't Let a Story Go
> Battered Recorder
> Press Credentials

works unchanged in 1920s London, a cyberpunk city, an Antarctic base, or a supernatural conspiracy.

The scenario merely establishes what the tags *permit*.

That is much closer to what you described—**create a character, then choose a world to throw them into**—than class/level systems are.

---

## What I'd prototype first

For a v0, I would resist adding anything else.

Implement **Loner-style characters + Oracle + Twist Counter + conditions**, your own simple six/ten-step `Progress` and `Threat` clocks, the guaranteed-core-clue rule, and a PDF compiler that produces entities, facts, clues, threads and scenario-specific oracle tables. Loner already includes scene-flow and random inspiration machinery, so you have enough structure to start testing immediately. ([Loner SRD][1])

Then test the same kernel against radically different documents—e.g. a conventional RPG adventure, a historical nonfiction PDF, a technical manual, and a novel/sourcebook.

If the **same six tools** can run all four, the abstraction is working.

My expected end state would be:

**70% Loner-shaped kernel + 15% Ironsworn-shaped campaign structure + 5% GUMSHOE clue discipline + 10% your own PDF/scenario machinery.**

That looks substantially better suited to cheap LLM agents than making them pretend to be a 5e DM, and it preserves the interesting part of your idea: **almost any document can become a playable possibility space rather than merely becoming lore pasted into a chatbot.** Viewing RPG systems as procedural-content generators is also consistent with prior PCG research on tabletop RPG design. ([arXiv][15])

If I were building this hobby project, **that's the direction I'd commit to for the first implementation.**

[1]: https://lonersrd.zotiquestgames.com/core/loner-3e.html "Loner - Core Rules 3rd Edition – Loner SRD"
[2]: https://tomkinpress.com/pages/ironsworn?utm_source=chatgpt.com "Ironsworn RPG – Tomkin Press"
[3]: https://tomkinpress.com/products/ironsworn-starforged-playkit?utm_source=chatgpt.com "Ironsworn: Starforged - Playkit – Tomkin Press"
[4]: https://capacle.itch.io/push "Push SRD by Cezar Capacle"
[5]: https://jasontocci.itch.io/24xx "24XX by Jason Tocci"
[6]: https://questworlds.chaosium.com/ "QuestWorlds – Worlds of Wonder"
[7]: https://cairnrpg.com/second-edition/players-guide/core-rules/ "Core Rules | Cairn"
[8]: https://fate-srd.com/official-licensing-fate "Official Licensing"
[9]: https://www.dndbeyond.com/srd "SRD v5.2.1 - System Reference Document - D&D Beyond"
[10]: https://pelgranepress.com/2017/09/29/gumshoe-rules-summary/ "GUMSHOE Rules Summary – Pelgrane Press Ltd"
[11]: https://lonersrd.zotiquestgames.com/adventure_packs/AP09_postapoc.html "Post-Apocalyptic Adventure Pack – Loner SRD"
[12]: https://loner.zotiquestgames.com/geared-towards-loner "Geared Towards Loner"
[13]: https://arxiv.org/html/2502.19519v2 "Static Vs. Agentic Game Master AI for Facilitating Solo Role-Playing Experiences"
[14]: https://aclanthology.org/2024.findings-acl.196/ "From Role-Play to Drama-Interaction: An LLM Solution - ACL Anthology"
[15]: https://arxiv.org/abs/2007.06108?utm_source=chatgpt.com "Tabletop Roleplaying Games as Procedural Content Generators"
