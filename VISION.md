# AIDM Vision

## Purpose

AIDM should make it easy to build rich AI-driven tabletop roleplaying experiences without requiring every rules engine, scenario, or gameplay feature to become a new Python subsystem.

The long-term goal is a small, understandable core that supports:

* multiple tabletop rules engines;
* multiple content packs for an engine;
* persistent locations and connections between them;
* NPC relationships and party membership;
* memories for NPCs, locations, and the world;
* quests, narrative threads, events, clocks, and hooks;
* character creation and advancement workflows;
* scenarios authored manually or generated from a premise;
* scenario and engine ingestion from PDFs or other source material;
* multiple specialised AI roles;
* role-specific information and read-only tools;
* optional image, voice, and other media generation.

The system should gain this flexibility **without making runtime gameplay depend on a large autonomous agent correctly executing a long sequence of tool calls**.

AIDM targets small, fast, inexpensive models. Runtime architecture must therefore make each model's job narrow, bounded, easy to demonstrate with examples, and easy to validate.

---

# The core idea

AIDM should evolve toward:

```text
PLAYER
  │
  ▼
SCENE DIRECTOR
  │
  │  decides dramatic focus, intent, pressure, relevant threads
  ▼
RULES DIRECTOR
  │
  │  produces one strict structured mechanical plan
  ▼
GENERIC RULE VM
  │
  │  deterministic rules, dice, costs, outcomes and state changes
  ▼
FACTS
  │
  ├────────► DETERMINISTIC HOOKS
  │
  ▼
NARRATOR
  │
  ▼
WORLD / MEMORY / THREAD MAINTENANCE
  │
  ▼
OPTIONAL MEDIA PRODUCTION
```

The important architectural boundary is:

> **Models decide and propose. Code validates and executes.**

Models do not become the rules engine.

Models do not perform arbitrary state mutation.

Models do not control an open-ended tool loop.

Models do not decide which agent to invoke next.

The application controls the workflow.

Each role performs one bounded task and produces one validated result.

---

# Why this direction

There are two attractive but incompatible extremes.

## Extreme 1: implement every game system in Python

This gives excellent mechanical reliability.

It also means that adding a rules engine tends to require:

* new action classes;
* new record classes;
* new validators;
* new resolvers;
* new engine-specific advancement code;
* new importers;
* new mechanical helper functions.

The Python codebase gradually becomes a reimplementation of every tabletop RPG AIDM supports.

That does not scale toward arbitrary engines, community content, or AI-generated engines.

## Extreme 2: make the LLM the rules engine

This gives excellent theoretical flexibility.

An engine could consist almost entirely of a `rules.md`, searchable content, and a few generic state tools.

In practice this asks the runtime model to maintain an agentic control loop:

```text
understand rule
→ look something up
→ decide whether to roll
→ roll
→ interpret result
→ maybe look something else up
→ mutate state
→ maybe roll again
→ decide whether the turn is finished
```

Small models have proven unreliable at this.

They may over-resolve and play an entire combat sequence, under-resolve and stop too early, misuse a tool, forget a consequence, or perform rules arithmetic incorrectly.

AIDM should therefore keep the structured-plan architecture while making the machinery behind that plan dramatically more generic.

---

# The target abstraction

The Rules Director should behave like a compiler front-end.

It converts natural-language play into a small structured instruction:

```text
player intent
      ↓
structured action plan
```

The generic Rule VM is the execution engine:

```text
structured action plan
      ↓
deterministic execution
      ↓
facts + new state
```

An engine therefore defines the **instruction set** available to the Rules Director rather than implementing a new execution framework in Python.

---

# 1. Engine-neutral world state

The core world should understand game concepts that apply across many rules engines.

It should not understand D&D-specific concepts such as spell slots, armour classes, spell schools, or saving throws.

The central persistent concepts should be small and general.

## Entity

An Entity is a thing that exists in the game world.

Examples:

* player;
* NPC;
* location;
* item.

An entity may have engine-neutral identity and fiction:

```text
id
kind
name
brief
detail
known
```

It may also carry generic rules state:

```text
numbers
counters
tags
notes
content references
```

Whether these remain separate `Entity` and `Sheet` Python objects is an implementation detail.

Conceptually they form one entity state.

The important requirement is that adding a new rules engine does not require adding new core entity classes.

---

# 2. Relations are first-class state

Not every important fact is a property of one entity.

AIDM needs relationships between entities.

Examples:

```text
room A  ──connected-to──► room B
Mara    ──party-member──► player
Mara    ──trusts────────► player
sword   ──owned-by──────► Kael
door    ──guards────────► vault
```

Relations should therefore be first-class records.

A relation can itself have state:

```text
id
kind
source
target
directed
known
tags
notes
```

This allows the connection between two locations to be:

* hidden;
* locked;
* collapsed;
* flooded;
* one-way;
* magically sealed.

The state belongs to the connection rather than being awkwardly duplicated on either location.

The same primitive supports:

* maps;
* exits;
* party membership;
* alliances;
* rivalries;
* ownership;
* faction membership;
* social relationships.

---

# 3. Facts are the event stream

A Fact records something that actually happened.

Examples:

```text
player moved to cloister
Mara joined the party
vault door became unlocked
Kael took 4 damage
vault map was discovered
quest stage advanced
```

Facts are immutable records of committed events.

They serve several purposes simultaneously:

* debugging;
* traces;
* narrator evidence;
* deterministic event triggers;
* quest progression;
* memory extraction;
* future analytics and replay.

The system should prefer:

```text
state transition
→ Fact
→ interested systems react
```

over directly coupling every feature to every other feature.

This makes Facts the natural event bus of AIDM.

---

# 4. Threads represent ongoing narrative state

AIDM needs something more structured than prose notes for ongoing situations.

A Thread is a persistent narrative process.

Examples:

* a quest;
* an investigation;
* an NPC relationship arc;
* an approaching threat;
* a faction conflict;
* a countdown;
* an unresolved promise;
* a mystery;
* a character goal.

A thread might contain:

```text
id
kind
title
status
stage
tags
notes
related entities
```

The exact schema should remain small.

A quest should not require a special quest engine if the same primitive can also represent an investigation or countdown.

---

# 5. Hooks react to Facts and state

Many narrative events can be deterministic.

For example:

```yaml
when:
  fact: entity-discovered
  entity: vault-map

if:
  mara: here

once: true

effects:
  - activate-thread: mara-suspicion
```

A hook should normally consist of:

```text
trigger
conditions
effects
once/repeat behaviour
```

The deterministic hook engine observes newly committed Facts and applies validated generic Effects.

This allows scenarios to contain authored logic without requiring scenario-specific Python.

Not every narrative transition can be expressed deterministically.

For fuzzy questions such as:

> Has the player finally earned Mara's trust?

a specialised model role may propose a transition.

That proposal remains structured and restricted to legal thread transitions.

---

# 6. Memory is explicit state

Conversation history is not sufficient long-term memory.

AIDM should maintain durable memories about important events and relationships.

A memory should be small and addressable.

Examples:

```text
Mara remembers that Kael lied about the vault.
The cloister was flooded during the storm.
Kael promised Tomas he would return the bell.
The party learned that Elena performed the sealing rite.
```

Memories may belong to:

* an NPC;
* the player;
* a location;
* a faction;
* the shared world.

A Memorykeeper role can periodically propose a small number of durable memories from recent Facts and narration.

The role does not mutate arbitrary state.

It produces validated memory proposals which core admits, updates, merges, or rejects according to explicit rules.

Runtime prompts should retrieve relevant memories rather than continually expanding full conversation history.

---

# 7. Content is mostly data, not Python classes

A content pack should not require a new Python model for every kind of rulebook record.

The common content representation should be approximately:

```json
{
  "id": "fireball",
  "kind": "spell",
  "name": "Fireball",
  "text": "Full rules text...",
  "facts": {
    "level": 3,
    "save": "dexterity",
    "damage": "8d6",
    "damage-type": "fire",
    "save-result": "half"
  },
  "tags": []
}
```

There are two important layers.

## Raw text

`text` contains source material suitable for retrieval by a model.

This may come from:

* JSON;
* Markdown;
* imported databases;
* hand-authored text;
* parsed PDFs.

## Mechanical facts

`facts` contains normalized values the deterministic Rule VM needs.

These values remain generic data rather than Python subclasses such as:

```text
SpellRecord
WeaponRecord
MonsterRecord
FeatureRecord
```

An engine may declare required fields for certain content categories using data schemas.

That preserves validation without encoding each content format as a Python class hierarchy.

---

# 8. Engines become declarative packages

The ideal engine should contain little or no runtime Python.

An illustrative engine directory might eventually look like:

```text
engines/
  ironsworn/
    engine.yaml
    rules.md
    actions.yaml
    examples.json
    advancement.yaml
    character-creation.yaml
    content/
```

The exact filenames are not important.

The separation is.

## `rules.md`

Instructions for the Rules Director.

This explains:

* when a mechanic applies;
* how to select an action;
* important fictional rules;
* terminology;
* edge cases the model must understand.

## `actions.yaml`

The mechanical action definitions interpreted by the generic Rule VM.

## `examples.json`

Worked structured plans for the runtime model.

Examples remain important because small models learn the expected output very effectively from concrete demonstrations.

## Content

Searchable raw text plus normalized mechanical facts.

## Workflows

Optional declarative definitions for:

* character creation;
* advancement;
* other player choices.

---

# 9. Plans stay strict

The structured plan is a feature, not technical debt.

The Rules Director should continue to produce exactly one bounded plan for the current turn.

Its schema should be generated from the active engine definition.

For example, a D&D-like engine could expose:

```json
{
  "action": {
    "act": "attack",
    "actor_id": "player",
    "target_id": "goblin",
    "weapon_item_id": "longsword"
  }
}
```

An Ironsworn-like engine might expose:

```json
{
  "action": {
    "act": "face-danger",
    "actor_id": "player",
    "stat": "edge"
  }
}
```

The model chooses the action and fills the arguments.

It does **not** implement the action algorithm.

---

# 10. The generic Rule VM

The Rule VM is the central architectural change.

It is deterministic code capable of executing declarative action definitions.

The VM should have a deliberately small vocabulary.

Possible primitives include:

```text
read entity state
read relation state
read content fact
read content text
calculate arithmetic
lookup table value
validate condition
roll dice
compare values
choose outcome
spend counter
adjust counter
set number
add/remove tag
set note
move entity
add/remove relation
reveal something
advance thread
emit fact
apply selected outcome branch
```

The VM owns:

* rolls;
* arithmetic;
* mechanical costs;
* action legality;
* outcome selection;
* intrinsic consequences;
* state mutation.

The Rules Director owns:

* interpreting player intent;
* selecting the mechanic;
* selecting legal targets;
* supplying choices the rule explicitly leaves to the player or fiction;
* describing stakes and intent.

The VM must not contain an unrestricted scripting language.

In particular, engine programs should avoid:

* arbitrary Python;
* unbounded loops;
* recursion;
* arbitrary network access;
* arbitrary file access.

A rule program should always have a bounded execution path.

Given the same state, plan, engine definition, and random seed, resolution should be reproducible.

---

# 11. Do not solve everything with the VM

The Rule VM should express reusable game mechanics.

It should not become a second general-purpose programming language.

When a missing capability appears, ask:

1. Can it already be expressed by composing existing primitives?
2. Is this mechanic useful across multiple engines?
3. Would adding one small generic primitive make the mechanic straightforward?

Only then extend the VM.

A first-party engine should ideally require no engine-specific runtime Python.

If an unusual mechanic genuinely cannot be represented, a narrow extension may be justified, but it should be an explicit exception rather than the default architecture.

---

# 12. Runtime roles are specialists, not autonomous agents

AIDM should use multiple AI roles where dividing responsibility makes an individual inference simpler and more reliable.

The application controls their order.

A model never decides to spawn another model or continue an open-ended reasoning loop.

## Scene Director

The Scene Director answers:

> What should this turn be about?

It understands:

* the scenario;
* hidden canon;
* relevant memories;
* active threads;
* NPC intentions;
* dramatic pressure;
* the player's stated intent.

Its output is small and structured.

For example:

```json
{
  "focus": "Mara questions why Kael wants the map",
  "pressure": "Answering poorly may damage her trust",
  "relevant_threads": ["mara-trust"],
  "mechanical_stakes": "Whether Mara accepts the explanation"
}
```

It does not perform mechanics.

It does not mutate state.

---

## Rules Director

The Rules Director answers:

> What single mechanical plan represents this turn?

It receives the Scene Director's decision plus the mechanical state relevant to the scene.

It can use read-only tools such as:

```text
read_content
read_rule
```

It produces one engine-specific structured plan.

It never rolls dice.

It never writes state.

It never runs a combat loop.

---

## Rule VM

The VM is code, not a model.

It validates and executes the plan.

---

## Hook Engine

The Hook Engine is code.

It reacts to Facts and applies deterministic scenario logic.

---

## Narrator

The Narrator receives committed truth and writes player-facing prose.

It must not see unrevealed canon.

It does not decide what mechanically happened.

---

## Worldkeeper

The Worldkeeper proposes new canon introduced through play:

* NPCs;
* locations;
* items;
* possibly relations.

Its output is structured.

Core validates and admits the proposed changes.

---

## Memorykeeper

The Memorykeeper proposes durable memories worth retaining.

Most turns should produce few or no new memories.

---

## Threadkeeper

The Threadkeeper handles fuzzy narrative transitions which cannot be represented by deterministic hooks.

It operates only on existing threads and allowed transitions.

---

## Optional specialist roles

The host-controlled workflow may later include roles such as:

* Challenger — proposes pressure or opposition;
* NPC Director — chooses an important NPC's immediate intention;
* Rules Reviewer — checks unusual plans;
* Lorekeeper — resolves questions against large scenario canon;
* Producer — proposes image, music, sound, or voice generation.

Each role must have:

* one clear responsibility;
* a bounded input;
* a bounded output;
* only the information it needs;
* only the tools it needs.

Adding roles must not create an autonomous agent swarm.

---

# 13. Per-role tools remain narrow

Runtime tools should usually be read-only.

Examples:

### Scene Director

```text
search_memory
read_thread
read_hidden_canon
```

### Rules Director

```text
search_rules
read_content
```

### Narrator

Normally no tools.

### Memorykeeper

Possibly retrieval of existing memories to avoid duplicates.

### Producer

The Producer should preferably output a validated `MediaRequest`.

The application performs the actual generation as a side effect at the boundary.

This preserves the rule:

> models propose; application code performs effects.

---

# 14. Character creation becomes a generic workflow

Character creation should not require a custom UI and custom Python logic for every engine.

An engine should be able to define a validated choice workflow.

For example:

```text
choose ancestry
→ choose class
→ choose background
→ choose ability allocation
→ choose proficiencies
→ choose equipment
→ choose spells
→ derive final state
```

Another engine might instead define:

```text
choose assets
→ distribute stats
→ choose bonds
→ set momentum
```

The workflow engine handles:

* steps;
* legal choices;
* dependencies;
* minimum/maximum selections;
* derived values;
* preview;
* final validation.

The UI renders the workflow generically.

An optional Character Advisor may help explain choices or convert a player's natural-language concept into proposed selections.

It cannot bypass workflow legality.

Advancement should eventually use the same general workflow machinery where practical.

---

# 15. Separate authoring-time intelligence from play-time intelligence

This is one of the most important principles in the vision.

Runtime gameplay should optimise for:

* speed;
* cost;
* bounded inference;
* repeatability;
* reliability on small models.

Authoring can optimise for:

* deep reasoning;
* large context;
* iterative tool use;
* expensive models;
* human review.

Therefore difficult interpretation work should happen once where possible.

---

# 16. AI scenario creation

A Scenario Creator should be able to start from:

* a short premise;
* notes;
* Markdown;
* an adventure PDF;
* other structured or unstructured source material.

The creator may use a more capable agentic workflow because scenario creation is not the turn loop.

It should produce normal AIDM scenario artifacts:

```text
scenario metadata
locations
connections
NPCs
items
initial relationships
threads
hooks
secrets
memories/canon
engine-specific overlays where necessary
```

The result must pass the same validation as a hand-authored scenario.

AI-created scenarios are not a separate runtime format.

---

# 17. AI-assisted engine creation

The same idea can eventually apply to rules engines.

Input:

```text
rulebook PDF
+ optional content files
+ engine metadata
```

Authoring workflow:

```text
ingest
→ identify important state
→ identify player-facing actions
→ normalize mechanical content
→ generate action definitions
→ generate examples
→ generate character workflow
→ generate advancement workflow
→ generate tests/evals
→ validate
```

Output:

```text
normal declarative AIDM engine package
```

The generated engine is then played exactly like a hand-authored engine.

The runtime model does not repeatedly reinterpret the original PDF.

The difficult interpretation work has been compiled into validated engine data.

---

# 18. Media generation stays outside the game rules

Image and voice generation should enrich presentation without becoming part of mechanical truth.

A Producer may receive:

* final narration;
* visible characters;
* visible location;
* mood;
* important newly revealed events.

It can propose:

```text
portrait request
scene illustration request
NPC voice line
ambient audio request
```

Media services execute these requests outside the deterministic game-state core.

The game must remain playable when all media services are disabled.

---

# Migration plan

The refactor should be incremental.

Each phase should leave a functioning game.

The existing implementation should act as an oracle while its replacement is built.

The live model evaluation benchmark is an architectural test, not merely a prompt-development tool.

A simplification that substantially harms small-model reliability is not a simplification.

---

# Phase 0 — Protect the baseline

## Goal

Make current behaviour measurable before changing architecture.

## Work

Record representative eval cases for:

* no-action turns;
* movement;
* conversation;
* checks;
* attacks;
* spells;
* rests;
* NPC actions;
* effects;
* invalid model plans;
* content lookup;
* hidden canon;
* world creation.

Measure at least:

```text
valid plan rate
retry rate
correct action selection
mechanical correctness
turn completion
model calls per turn
tokens per turn
latency
```

Keep deterministic resolver tests around current Story and D&D behaviour.

## Done when

A future architecture can be compared against the current one with evidence rather than intuition.

---

# Phase 1 — Strengthen the universal world model

## Goal

Make core capable of representing the requested gameplay features without engine-specific code.

## Work

Introduce first-class Relations.

Support generic operations such as:

```text
add relation
remove relation
change relation tags
change relation notes
reveal relation
```

Use relations to implement at least:

* location connections;
* connection state;
* NPC party membership.

Review `Entity` and `Sheet`.

Simplify them where useful, but do not rewrite them merely to achieve conceptual purity.

The target is engine-neutral state, not a particular class hierarchy.

## Done when

A location can connect to another location and that connection can become locked/unlocked without changing an engine.

An NPC can join or leave the party without changing an engine.

---

# Phase 2 — Make Facts drive world systems

## Goal

Build quests, events, hooks, and memories on one common event substrate.

## Work

Make Facts sufficiently structured for other systems to consume reliably.

Add Threads.

Add deterministic Hooks triggered by Facts and state.

Add Memory records and retrieval.

Start with manually authored memories or deterministic tests before adding the Memorykeeper role.

## Done when

A scenario can express:

```text
when X happens
and Y is true
advance thread Z
apply these effects
```

without scenario-specific Python.

A quest can advance because of committed Facts rather than because the Director remembered to update it.

---

# Phase 3 — Generalise content packs

## Goal

Remove the requirement for large families of engine-specific Python record classes.

## Work

Introduce generic content records containing:

```text
identity
kind
name
raw text
facts
tags
references
```

Allow an engine to declare mechanical content requirements through data.

Preserve read-only lookup tools.

Migrate simple content categories first.

Gradually move D&D mechanics away from Python record attributes and toward generic content facts.

## Done when

Adding a new D&D-compatible content pack does not require defining Python record subclasses.

Most content can arrive in arbitrary source formats and be normalized during import.

---

# Phase 4 — Build the Rule VM and migrate Story

## Goal

Prove that a declarative engine can preserve the reliability of the current structured-plan system.

## Work

Define the smallest useful Rule VM instruction set.

Define a declarative engine action format.

Generate the Rules Director's output schema from that format.

Reimplement the Story `risk` mechanic declaratively.

Run the old Story resolver and the new VM against equivalent test cases.

Run the live small-model eval suite against both schemas.

## Done when

Story requires no Story-specific runtime action or resolver Python.

Its gameplay behaviour remains equivalent.

Small-model plan reliability is equal to or better than the current implementation.

This is the architectural proof point.

Do not migrate D&D until this succeeds.

---

# Phase 5 — Migrate D&D incrementally

## Goal

Remove D&D-specific resolver and record machinery without losing deterministic rules.

## Suggested order

Migrate mechanics from simplest to hardest:

1. generic checks;
2. rests;
3. attacks;
4. limited-use features;
5. healing;
6. spell attacks;
7. spell saves;
8. spell scaling;
9. concentration and unusual riders;
10. advancement.

For every migrated mechanic:

```text
old resolver
vs
Rule VM
```

should be tested against the same state and seeded randomness.

Delete the old implementation only after parity is established.

## Done when

D&D is primarily:

```text
engine instructions
action definitions
content
examples
workflows
```

rather than a Python package containing bespoke rules logic.

At this point, adding another engine should mostly mean authoring data.

---

# Phase 6 — Split scene direction from rules direction

## Goal

Reduce the cognitive load placed on the runtime model.

## Work

Introduce the Scene Director.

Give it narrative state, hidden canon, threads, and memories.

Give the Rules Director a much narrower mechanical task.

Keep both stages one-shot and structured.

Evaluate:

```text
single Director
vs
Scene Director + Rules Director
```

on:

* plan correctness;
* dramatic coherence;
* token use;
* latency;
* retries.

Allow configuration to combine or disable stages where that performs better.

Control flow always remains host-owned.

## Done when

The Rules Director can concentrate on producing correct mechanical plans without simultaneously carrying the full burden of scenario direction.

---

# Phase 7 — Add maintenance specialists

## Goal

Move persistent narrative bookkeeping out of the Rules Director.

## Work

Add specialised one-shot roles where they improve measurable quality:

### Memorykeeper

Extract durable memories.

### Threadkeeper

Evaluate fuzzy thread transitions.

### Worldkeeper

Grow new canon under strict admission rules.

### Optional Challenger

Propose complications or opposition before the Rules Director acts.

Every role should operate through a minimal typed proposal.

## Done when

Persistent world development no longer depends on one general-purpose Director remembering every responsibility.

No role has arbitrary authority over state.

---

# Phase 8 — General character and advancement workflows

## Goal

Make characters portable across engines without custom Python workflows.

## Work

Build the generic choice/workflow system.

Use it first for one simple engine.

Then reproduce D&D character creation.

Move advancement onto the same substrate where practical.

Add an optional AI Character Advisor after deterministic workflow legality is working.

## Done when

A new engine can define character creation and advancement in data rather than implementing a new UI and Python workflow.

---

# Phase 9 — Build AI authoring workflows

## Goal

Make creation of engines and scenarios substantially easier than runtime implementation.

## Scenario Creator

Support:

```text
premise
→ complete scenario
```

and later:

```text
PDF / notes / Markdown
→ normalized scenario
```

## Engine Creator

Support:

```text
rules source
→ declarative engine package
```

The authoring agent may be sophisticated and iterative.

Its output must still pass deterministic validation, tests, and evals before becoming playable content.

## Done when

AI-generated and hand-authored engines/scenarios use exactly the same runtime format.

---

# Phase 10 — Add the experience layer

## Goal

Improve presentation without coupling media systems to game mechanics.

## Work

Add typed media requests.

Support optional:

* scene illustrations;
* NPC portraits;
* character portraits;
* voice synthesis;
* ambient sound;
* music cues.

Keep generation asynchronous from the perspective of game architecture even if the current application waits for a result.

The game itself must not depend on media generation succeeding.

## Done when

Media providers can be changed or disabled without touching rules, world state, or scenario logic.

---

# Target engine authoring experience

A successful architecture should make a simple engine feel roughly like this:

```text
1. Write rules.md.
2. Define the engine's state template.
3. Define its actions declaratively.
4. Add several worked plan examples.
5. Add or ingest searchable content.
6. Define character creation and advancement if needed.
7. Run validation and evals.
8. Play.
```

Adding an engine should not normally require editing core AIDM.

---

# Target scenario authoring experience

A scenario author should be able to define:

```text
premise
locations
connections
NPCs
items
secrets
initial relationships
threads
hooks
```

without understanding the implementation of the active rules engine.

Engine-specific overlays should contain only genuinely engine-specific mechanical state.

---

# Architecture guardrails

The following principles should remain true throughout the migration.

## Models propose; code executes

No model directly mutates committed state.

## One bounded result per role

Runtime roles do not run open-ended action loops.

## Host-controlled workflow

The application decides which roles run and in what order.

## Deterministic mechanics

Dice, costs, legality, outcome selection, and state changes belong to deterministic code.

## Transactional state

A turn operates on a draft and commits only after complete validation.

## Facts describe committed truth

Narration follows Facts, never the reverse.

## Hidden information is structurally isolated

A role that must not know hidden canon should receive an input type that cannot contain it.

## Retrieval is preferred to giant prompts

Rules, content, memories, and distant world information should be looked up when relevant.

## Content and engines are data-first

Python extension points are exceptions, not the normal authoring path.

## Small-model reliability is a first-class requirement

A more elegant architecture is not better if it makes the target runtime models materially less reliable.

---

# Deliberate non-goals

## Do not turn game state into an arbitrary JSON blob

Generic does not mean unvalidated.

Core state should remain explicit and strongly validated.

## Do not turn the Rule VM into Python written in YAML

The VM should remain small, bounded, and purpose-built for tabletop mechanics.

## Do not make the runtime Director an autonomous agent

Agentic workflows are acceptable during authoring.

Runtime gameplay should remain tightly orchestrated.

## Do not make every possible future feature a core abstraction now

New primitives should be introduced when real implementations need them.

The vision defines direction, not permission to build speculative frameworks.

## Do not preserve old architecture merely for save compatibility

The save version remains the compatibility boundary.

A stale save may be refused rather than forcing permanent architectural complexity.

---

# What success looks like

The vision is substantially achieved when all of the following are true:

1. **Story runs entirely on the generic Rule VM.**

2. **D&D runs primarily from declarative engine definitions and generic content.**

3. **A new content pack does not require new Python record classes.**

4. **A new rules-light RPG can be added with little or no runtime Python.**

5. **Locations have stateful connections using core Relations.**

6. **NPC party membership and relationships use the same relation system.**

7. **Quests and narrative arcs use Threads and Facts rather than bespoke engine logic.**

8. **Scenario hooks react to Facts declaratively.**

9. **Relevant memories survive beyond the conversation-history window.**

10. **The default runtime flow separates scene direction from mechanical planning.**

11. **Every runtime model role has one bounded responsibility.**

12. **Character creation and advancement use generic validated workflows.**

13. **A scenario can be generated from a premise and validated into the normal scenario format.**

14. **A PDF can be ingested during authoring without requiring runtime models to repeatedly reinterpret it.**

15. **Optional image and voice generation can be added without affecting game-state correctness.**

16. **Small-model eval performance remains at least as strong as the structured-plan baseline.**

17. **The core codebase becomes smaller as supported gameplay capabilities increase.**

That final property is the real architectural objective:

> **Adding gameplay depth should increasingly mean adding data, rules definitions, content, and specialised bounded roles — not adding another parallel Python implementation of the game.**
