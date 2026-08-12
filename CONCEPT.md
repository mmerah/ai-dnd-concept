# CONCEPT.md - Agentic Solo RPG Platform

Status: architectural reorientation proposal

## 1. Executive decision

The project should stop trying to make RPG rules engine-agnostic.

Instead, make the **fictional world engine-agnostic** and make RPG engines **replaceable mechanical projections** over that world.

The platform should have five major layers:

1. **World Core** - canonical entities, locations, relationships, possession, party membership, world facts, time, events, memories, story threads, source provenance, and media identity.
2. **Narrative Runtime** - Director, Referee, Narrator, Archivist, context assembly, and tool routing.
3. **Engine Runtime** - a selected rules engine package with its own schemas, rules, tools, character adaptation, and scenario compilation.
4. **Content Layer** - engine-neutral scenario packs, engine-specific content packs, and optional genre/presentation packs.
5. **Media Layer** - image, voice, music/ambience, and other generated assets attached to canonical entities but never treated as game truth.

A campaign run is bound to one rules engine. A character or scenario can be adapted to many engines, but the system should **not promise lossless conversion or live hot-swapping between engines**.

The first engine should be a tiny native narrative engine, working name **Oracle Engine**, inspired by the design strengths of Loner, Ironsworn/Starforged, GUMSHOE, and lightweight tag-based games. It should itself be implemented as an ordinary engine package rather than hard-coded into World Core.

D&D 5e/5.5e should not be an architectural target for the core. It can become a later high-complexity engine plugin whose internal complexity is isolated behind the same engine boundary. The current D&D SRD itself spans classes, spells, monsters, actions, weapons, exploration, and a large rules glossary; that is a strong signal that its complexity belongs inside a dedicated engine service rather than in universal platform types.[R14]

---

## 2. Why the previous direction failed

The original idea - common character fields plus an engine-agnostic mechanical abstraction - works until an engine has enough interacting rules that its concepts leak into everything.

D&D is a particularly effective stress test because it brings in:

- attributes and derived modifiers;
- classes, levels, subclasses, species/background choices;
- skills and saving throws;
- HP, temporary HP, hit dice, death saves;
- AC and multiple defenses;
- actions, bonus actions, reactions, movement, initiative, rounds;
- spell slots, prepared spells, spell components, concentration;
- conditions and condition-specific rules;
- equipment, attunement, weapon properties, mastery, encumbrance;
- rests and recovery;
- hundreds of exception-like features.

Trying to normalize these concepts into a universal schema means the supposedly generic core slowly becomes "D&D with nullable fields."

The fix is not a smarter universal sheet. The fix is a stronger boundary.

**Universalize identity and fictional state, not mechanics.**

---

## 3. Product thesis

The product is a **persistent solo role-playing world runtime** in which:

- the player creates reusable character personas;
- the player creates or imports reusable scenarios;
- a scenario can be generated from a premise or an arbitrary source PDF;
- the player chooses a supported rules engine and compatible content packs;
- the system compiles the persona and scenario into an engine-specific playable campaign;
- a small team of specialized LLM agents acts as the GM;
- deterministic tools, not prose generation, own game state and mechanical outcomes;
- characters, NPCs, items, locations, factions, quests, and memories persist across long sessions;
- media generation enriches important entities without becoming authoritative state.

The project is therefore not "an AI Dungeon Master."

It is closer to:

> **A world model + story runtime + pluggable tabletop rules engines + agentic GM interface.**

---

## 4. Core architectural law

### 4.1 What "engine-agnostic" means

Engine-agnostic means:

- World Core does not know what AC, HP, Edge, Momentum, Fate Points, spell slots, moves, stress boxes, skill dice, or saving throws are.
- World Core knows that an entity exists, where it is, who owns it, what happened to it, what facts are true about it, who knows those facts, and how it relates to other entities.
- An engine may attach arbitrary mechanical state to any relevant core entity.
- Engine mechanics can cause fictional consequences, but they do so through explicit bridge events into World Core.

### 4.2 What is not engine-agnostic

The following belong entirely to the active Engine Package:

- character stats;
- combat state;
- mechanical conditions;
- resources and currencies that are rules constructs;
- action economy;
- dice formulas;
- legal action checks;
- powers, spells, moves, feats, assets, stunts, classes;
- engine-specific advancement;
- engine-specific NPC stat blocks;
- engine-specific item properties.

### 4.3 Shared concepts are bridged, not merged

Some things exist in both fiction and mechanics.

Example: poison.

World Core might contain:

```yaml
fictional_state:
  tags:
    - poisoned_by_blackroot
```

A Cairn binding might contain a specific mechanical consequence. A D&D binding might contain the Poisoned condition plus save timing. An Oracle Engine binding might apply Risk disadvantage when relevant.

These do not need one universal "Poison" type.

The engine owns mechanics. World Core owns the fictional fact that the character is suffering from poison.

---

## 5. System boundaries

| Concept | World Core | Engine | Scenario | Content Pack |
|---|---|---|---|---|
| Character name / brief / appearance | Yes | No | Optional defaults | Optional suggestions |
| Character personality / drives | Yes | May interpret | Yes | May suggest |
| Character stats / HP / class | No | Yes | No | May provide options |
| Location and exits | Yes | May add mechanics | Yes | May add templates |
| Entity location | Yes | No | Initial state | No |
| Item ownership | Yes | May add inventory rules | Initial state | Catalog entries |
| Weight / encumbrance | No | Yes | No | Engine data |
| NPC identity / motive | Yes | May attach stat block | Yes | Archetype suggestions |
| Party membership | Yes | May attach companion rules | Initial state | No |
| Quest / threat / mystery thread | Yes | May attach progress mechanics | Yes | Templates |
| Combat resolution | No | Yes | Encounter intent only | May add enemies/rules |
| World event history | Yes | May emit events | Seeds/triggers | Templates |
| Memories / beliefs | Yes | May use them as modifiers | Seeds | No |
| PDF source provenance | Yes | No | Yes | No |
| Portrait / voice identity | Yes | No | May seed | Style packs |

This table should be treated as an architectural guardrail.

---

## 6. The World Core

The World Core is the most important piece of the project. If it is correct, every engine becomes easier.

### 6.1 Entity model

Use an Entity-Component style model conceptually, even if the implementation is ordinary relational tables plus JSON. Modern game engines use Entity Component System designs to compose heterogeneous objects from data components rather than requiring one giant inheritance hierarchy.[R15]

Every meaningful thing is an entity:

```ts
type EntityId = string;

type EntityKind =
  | "character"
  | "npc"
  | "location"
  | "item"
  | "faction"
  | "creature"
  | "vehicle"
  | "organization"
  | "document"
  | "concept"
  | "other";

interface EntityCore {
  id: EntityId;
  kind: EntityKind;
  name: string;
  brief: string;
  tags: string[];
  visibility: "public" | "discovered" | "secret";
  sourceRefs: SourceRef[];
  createdAt: string;
  updatedAt: string;
}
```

Do not force all entities into the same mechanical shape. The common shape is intentionally boring.

### 6.2 Components

Core entities can have optional engine-neutral components:

- `PersonaComponent`
- `PhysicalDescriptionComponent`
- `MotivationComponent`
- `LocationComponent`
- `ContainerComponent`
- `FactionComponent`
- `MediaIdentityComponent`
- `SourceProvenanceComponent`
- `MemorySubjectComponent`
- `TimeStateComponent`

Engines attach their own namespaced components:

```json
{
  "engineComponents": {
    "oracle-engine@1": { "luck": 5, "capabilityTags": ["Locksmith"] },
    "cairn-2e@1": { "str": 9, "dex": 15, "wil": 11, "hp": 4 },
    "dnd-srd-5.2.1@1": { "...": "arbitrary engine-owned schema" }
  }
}
```

World Core must never inspect the internals of these engine components.

### 6.3 Relationships are first-class

Use typed edges rather than burying relationships in prose.

Examples:

```text
LOCATED_IN
CONNECTED_TO
CONTAINS
OWNS
CARRIES
MEMBER_OF
PARTY_MEMBER_OF
ALLIED_WITH
HOSTILE_TO
KNOWS
RELATED_TO
SERVES
OWES
REQUIRES
REVEALS
POINTS_TO
```

A relation can have properties:

```ts
interface Relation {
  id: string;
  from: EntityId;
  to: EntityId;
  type: string;
  properties: Record<string, unknown>;
  sourceRefs: SourceRef[];
}
```

For locations, `CONNECTED_TO` can contain travel mode, distance, hidden/known status, prerequisites, danger, and whether the route is currently blocked.

You do not need a graph database initially. A relational `entities` table plus `relations` table is enough. What matters is the graph-shaped domain model.

---

## 7. Locations

Locations should be stateful objects, not descriptions regenerated from chat history.

```ts
interface LocationComponent {
  parentLocationId?: EntityId;
  atmosphere?: string;
  environmentalTags: string[];
  discovered: boolean;
  currentSummary: string;
}
```

A location's full runtime state is the combination of:

- its core entity;
- current conditions;
- contained entities;
- connected locations;
- event history at that location;
- source facts;
- observer memories;
- optional engine component.

### 7.1 Location memory

Do not literally give locations an LLM memory system.

Instead distinguish:

1. **World history at the location** - events that objectively happened there.
2. **Current location state** - the materialized projection after those events.
3. **Observer memory of the location** - what a PC or NPC remembers seeing there.

This makes it possible for the player to return to a room and discover that it changed while their character still remembers the old state.

---

## 8. Events: the backbone of persistence

Use an append-only world event log as the authoritative history of meaningful changes.

Do not necessarily build a distributed Event Sourcing architecture. For a hobby application, one `world_events` table plus normal current-state projections can give most of the benefit.

The important design property is that state-changing actions create meaningful domain events:

```json
{
  "type": "EntityMoved",
  "actorId": "pc_1",
  "entityId": "npc_mara",
  "fromLocationId": "station_lab",
  "toLocationId": "station_corridor",
  "campaignTime": "day-2/scene-14",
  "causedBy": "turn_993"
}
```

Not:

```json
{
  "type": "FieldUpdated",
  "path": "npc_mara.locationId",
  "value": "station_corridor"
}
```

Event-sourcing guidance emphasizes intent-bearing immutable events because they preserve history, support reconstruction, and provide a meaningful audit trail.[R12]

This model gives the project several unusually valuable features almost for free:

- save/load;
- undo or rewind by fork;
- debug a hallucinated state transition;
- reconstruct "what happened here?";
- derive NPC memories;
- derive quest progress;
- generate session summaries;
- fork alternate timelines;
- migrate engines without losing fictional history.

---

## 9. The Character Core

The reusable character is a **persona**, not a universal character sheet.

Recommended core:

```ts
interface CharacterPersona {
  name: string;
  brief: string;
  appearance?: string;
  pronouns?: string;
  personalityTags: string[];
  capabilityTags: string[];
  weaknessTags: string[];
  drives: string[];
  beliefs?: string[];
  relationships?: RelationshipSeed[];
  signaturePossessions?: EntityId[];
  persistentNarrativeConditions?: string[];
  milestones?: string[];
  visualProfile?: VisualProfile;
  voiceProfile?: VoiceProfile;
}
```

The core `capabilityTags` are narrative statements such as:

- veteran field medic;
- exceptional climber;
- knows old occult languages;
- former naval engineer.

They are not guaranteed bonuses. Each engine decides how, or whether, to translate them mechanically.

### 9.1 Engine bindings

A character can have multiple persistent engine bindings:

```text
Character: Evelyn Park
  Persona: engine neutral
  Oracle Engine binding: v3
  Cairn binding: v1
  Ironsworn binding: v2
```

Bindings are not continuously converted into one another.

The persona is the stable identity. Engine bindings are separate interpretations of that identity.

### 9.2 Adaptation workflow

When a persona enters an engine for the first time:

1. Engine adapter reads persona.
2. Engine adapter proposes a mechanical interpretation.
3. AI explains important compromises or ambiguous choices.
4. Player confirms or changes choices that materially affect identity/gameplay.
5. Engine binding is stored permanently.

Example:

```text
"Veteran Field Medic"

Oracle Engine -> capability tag
Cairn -> high WIL suggestion + medical gear/background
Ironsworn -> asset suggestions
D&D -> class/background/skill suggestions, but requires explicit player choice
```

### 9.3 Syncing back to the persona

Only durable fictional consequences should sync back automatically:

- lost an eye;
- became captain of the vessel;
- gained the Moon-Key artifact;
- now hates the Crimson Court;
- learned that their brother survived.

Do not automatically sync:

- +1 Strength;
- level 5;
- 3 spell slots remaining;
- Fate refresh;
- Momentum 7.

Those remain engine-specific.

---

## 10. Campaigns are engine-bound

A campaign instance should contain:

```ts
interface Campaign {
  scenarioId: string;
  engineId: string;
  engineVersion: string;
  contentPackIds: string[];
  playerCharacterIds: string[];
  currentLocationId: string;
  campaignClock: CampaignClock;
  activeThreadIds: string[];
}
```

**Rule:** a running campaign uses exactly one active rules engine.

Changing engines is a migration operation:

1. snapshot/fork campaign;
2. preserve World Core and event history;
3. compile a new scenario overlay;
4. adapt active characters and mechanically relevant NPCs;
5. present an adaptation report;
6. begin a new campaign branch.

This is intentionally explicit and potentially lossy.

---

## 11. Engine Package contract

An Engine Package is a plugin with no direct authority over the World Core database.

Recommended package shape:

```text
engine/
  manifest.json
  schemas/
    character.schema.json
    campaign.schema.json
    entity.schema.json
  adapter/
    adapt-character
    compile-scenario
    export-fictional-consequences
  rules/
    deterministic rules implementation
  tools/
    tool declarations
    tool handlers
  context/
    build-rules-context
  creator/
    character-creation-workflow
  renderer/
    character-sheet-view
  tests/
    engine-compliance-suite
```

### 11.1 Manifest

```json
{
  "id": "oracle-engine",
  "version": "1.0.0",
  "displayName": "Oracle Engine",
  "capabilities": [
    "solo",
    "party",
    "generic-conflict",
    "inventory",
    "progress-tracks"
  ],
  "licenses": [],
  "compatibleContentPacks": ["oracle-engine/*"]
}
```

### 11.2 Engine API

Do not force every engine to expose identical mechanics.

Force them to satisfy lifecycle contracts instead:

```ts
interface EngineAdapter {
  adaptCharacter(...): AdaptationResult;
  compileScenario(...): ScenarioOverlay;
  buildTurnContext(...): EngineContext;
  getAgentTools(...): ToolDefinition[];
  validateState(...): ValidationResult;
  exportFictionalConsequences(...): CoreCommand[];
}
```

This is the actual engine-agnostic boundary.

### 11.3 Keep LLM-facing tools high-level

A complex engine may need hundreds of internal rules, but the agent should not see hundreds of tools.

Bad:

```text
roll_strength_save
roll_dex_save
roll_arcana
consume_spell_slot
apply_concentration
apply_prone
...
```

Better:

```text
resolve_action
resolve_conflict_step
use_ability
recover
inspect_engine_state
```

The engine service can perform complex deterministic work behind those tools.

This follows the broader lesson from RPG LLM evaluation: current LLMs can generate engaging material while becoming unreliable when they themselves must consistently enforce complex, verifiable mechanics over long play.[R9]

---

## 12. The native Oracle Engine

Build a first-party engine specifically optimized for the agent architecture.

It should be **a plugin, not the core**.

### 12.1 Design goals

- genre-neutral;
- solo-first;
- extremely small mechanical state;
- descriptive tags rather than broad stat taxonomies;
- deterministic/random resolution done in code;
- one conflict model usable for combat, debate, chases, hacking, survival, etc.;
- bounded modifiers so the Referee cannot create modifier soup;
- strong support for partial success and complications;
- progress/threat structures that propel solo play;
- easy PDF-to-scenario compilation.

### 12.2 Research basis

Loner 3e is especially relevant because it is explicitly solo, minimalist, tag-based, and built around one Oracle mechanic; it defines characters and situations descriptively instead of through heavy numerical simulation.[R1] Loner also demonstrates genre/adventure packs and special rules layered over the same compact base.

Ironsworn is valuable for a different reason: it was built for solo/co-op/guided play and uses moves, oracles, Momentum, and progress structures to create forward motion without a traditional GM.[R2]

24XX demonstrates how very small rules can be adapted across many microgames while prioritizing fictional positioning over procedural detail.[R3]

QuestWorlds is another useful proof that scalable character descriptions and abstract conflict resolution can work across broad genres, and its ecosystem explicitly supports genre packs.[R5]

### 12.3 Proposed mechanic

Do not copy an external SRD blindly. Build a small first-party rules kernel with original terminology and implementation.

Suggested shape:

Character engine state:

```yaml
concept: Disgraced polar explorer
edges:
  - Ice Navigation
  - Field Medicine
burden:
  - Recklessly Curious
signature_gear:
  - Survey Kit
  - Flare Pistol
fortune: 6
```

Resolution:

- Referee phrases a binary dramatic question.
- Relevant capability/gear/world tags can improve position.
- Relevant burdens/hazards can worsen position.
- Positive and negative factors cancel.
- Advantage and disadvantage are capped.
- Deterministic dice tool produces one of six semantic outcomes:
  - strong success;
  - success;
  - success with cost;
  - failure with opportunity;
  - failure;
  - severe failure.

The exact dice formulation can be tuned later. The important API is the **semantic outcome ladder**, not a specific borrowed die expression.

### 12.4 Progress and danger

Add first-class tracks:

```ts
type TrackKind = "progress" | "danger" | "relationship" | "mystery";

interface Track {
  label: string;
  max: number;
  value: number;
  stakes: string;
}
```

This borrows the useful campaign-propulsion concept from Ironsworn/Starforged without requiring every Ironsworn move.[R2]

### 12.5 Clue invariant

For investigations, adopt the GUMSHOE design principle that essential clues should not disappear behind failed random checks. GUMSHOE explicitly designates core clues that move the investigation forward.[R7]

Platform rule:

> If a fact is marked `coreClue=true` and the player takes a credible action that would expose it, the fact is revealed. Resolution can determine additional detail, danger, cost, time, or consequences - not whether the scenario becomes unwinnable.

This should be a World/Scenario runtime invariant, not a special case in one engine.

---

## 13. Content packs

Use two different pack concepts.

### 13.1 Engine Content Pack

Adds reusable content to a specific engine and can be used by any compatible scenario.

Examples:

```text
oracle-engine/fantasy
oracle-engine/cyberpunk
oracle-engine/occult-investigation
cairn/firearms
ironsworn/custom-assets
```

An Engine Content Pack may contain:

- item catalogs;
- archetypes;
- enemy templates;
- abilities/spells/assets;
- oracle tables;
- optional subsystems;
- character creator options;
- scenario compiler rules;
- rule handlers registered behind the engine API.

It should normally **not add dozens of new LLM tools**. It extends the engine's data/rules behind the existing high-level tools.

### 13.2 Narrative Content Pack

Engine-neutral material usable with any scenario/engine:

```text
noir
cosmic-horror
heist
space-opera
cozy-mystery
```

May contain:

- tone guidance;
- scene templates;
- hook templates;
- NPC personality generators;
- location descriptors;
- visual style defaults;
- voice direction;
- safety/content preferences.

### 13.3 Pack manifest

```json
{
  "id": "oracle-engine/occult-investigation",
  "version": "1.2.0",
  "kind": "engine-content",
  "engine": "oracle-engine",
  "dependencies": [],
  "provides": ["archetypes", "items", "oracles", "scenario-rules"],
  "license": "project-defined"
}
```

---

## 14. Scenario model

A Scenario Pack is primarily engine-neutral.

```ts
interface Scenario {
  id: string;
  title: string;
  premise: string;
  tone: string[];
  worldTruthIds: string[];
  startingLocationId: string;
  entityIds: string[];
  threadIds: string[];
  triggerIds: string[];
  sourceDocumentIds: string[];
  suggestedNarrativePacks: string[];
  sourcePolicy: SourcePolicy;
}
```

The scenario should contain **possibility space**, not a prewritten plot.

A scenario defines:

- places;
- people/factions;
- tensions;
- goals;
- secrets;
- hooks;
- clocks;
- event triggers;
- encounter ingredients;
- source truths;
- things likely to change if the player does nothing.

This is consistent with research framing tabletop RPG systems themselves as procedural content generators that define possibility spaces and generative pipelines.[R16]

---

## 15. Threads, hooks, events, and quests

Do not make "Quest" one giant object that tries to represent every narrative structure.

Use four concepts.

### 15.1 StoryThread

A persistent unresolved situation:

```ts
type ThreadKind =
  | "quest"
  | "threat"
  | "mystery"
  | "opportunity"
  | "relationship"
  | "personal";

interface StoryThread {
  id: string;
  kind: ThreadKind;
  title: string;
  summary: string;
  status: "latent" | "active" | "resolved" | "failed" | "abandoned";
  relatedEntityIds: string[];
  trackIds: string[];
  sourceRefs: SourceRef[];
}
```

### 15.2 Hook

A discoverable invitation into a thread.

A rumor, letter, body, job offer, strange noise, missing person, or overheard conversation can all be hooks.

Multiple hooks may point at the same thread.

### 15.3 Trigger

A conditional rule:

```text
When time reaches nightfall AND the generator is still broken,
create event "Station loses main power".
```

Triggers can be code-like predicates or LLM-evaluated high-level conditions, but their execution should ultimately emit explicit events.

### 15.4 WorldEvent

A thing that actually happened and is now part of history.

This distinction gives the Director a clear job: choose which unresolved threads and triggers deserve attention without inventing a predetermined plot.

---

## 16. NPC model

NPCs are ordinary core entities with persona/motivation/relationship components plus optional engine bindings.

Do not stat every NPC on creation.

Use **lazy mechanical compilation**:

- bartender only needs identity/memory/relationships;
- when bartender joins the party or becomes mechanically relevant, ask the active engine to create a binding;
- if they stop being mechanically relevant, keep the binding but do not continuously process it.

### 16.1 Party membership

Party membership is a core relation:

```text
NPC --PARTY_MEMBER_OF--> CampaignParty
```

When an NPC joins:

1. World Core commits `PartyMemberJoined`.
2. Active engine ensures an engine binding exists.
3. Context builder begins including the NPC in party context.
4. Referee includes the NPC in mechanically relevant actions.
5. Archivist continues recording their memories and relationship changes.

No engine gets to invent its own separate concept of "who is in the party" as the authoritative source.

---

## 17. Memory architecture

Do not use chat transcripts as memory.

Use explicit memory records linked to events and entities.

Research on generative agents found value in storing experiences, retrieving them dynamically, and synthesizing higher-level reflections; its ablation results indicated observation, planning, and reflection all contributed to believable behavior.[R10] MemGPT likewise motivates hierarchical external memory rather than assuming the entire lifetime of an agent belongs in the active context window.[R11]

### 17.1 Three kinds of knowledge

#### World truth

What is objectively true in the scenario.

#### Observation / episodic memory

What an observer experienced.

```ts
interface Memory {
  id: string;
  observerId: EntityId;
  eventId: string;
  aboutEntityIds: EntityId[];
  summary: string;
  salience: number;
  confidence: number;
  emotionalTags: string[];
  learnedAt: CampaignTime;
}
```

#### Belief / reflection

A derived conclusion that may be false.

```text
Mara believes the captain sabotaged the reactor.
```

A belief must never silently become World Truth.

### 17.2 Retrieval

At turn time, retrieve a small number of memories using:

- semantic relevance to current situation;
- recency;
- salience;
- relationship relevance;
- location relevance.

Do not dump an NPC's full memory history into context.

### 17.3 Reflection

For important recurring NPCs, periodically summarize many low-level memories into higher-level beliefs/relationship impressions.

Do not run reflection after every turn.

### 17.4 NPC knowledge boundaries

An NPC should only receive:

- public world facts;
- things they directly observed;
- things communicated to them;
- beliefs/reflections derived from those memories;
- explicit scenario secrets they are authored to know.

This prevents omniscient NPC dialogue.

---

## 18. Attention-based world simulation

Do not turn every NPC into an autonomous LLM agent.

Use three simulation levels:

### Foreground

Current location, current party, active conversation, combat/conflict participants.

High detail. Included every turn.

### Active offscreen

Important NPCs, factions, threats, and scheduled events tied to active StoryThreads.

Advance at scene boundaries or meaningful time changes.

### Background

Everything else.

No continuous simulation. Reactivate when needed.

This keeps cost predictable while preserving the illusion of a living world.

---

## 19. The runtime agent team

The runtime should use a small team of narrow agents, not a committee that discusses every turn.

A 2025 solo-RPG study reached a closely related architecture: a Narrator plus an Archivist using JSON tools to maintain characters and environments; the agentic version improved modularity and reported player experience in a small comparative study.[R8]

### 19.1 Director

Invoked at scene boundaries or when the scene loses direction.

Owns:

- dramatic pressure;
- selecting relevant StoryThreads;
- deciding whether an offscreen development should surface;
- choosing scene framing;
- pacing.

Does not:

- decide dice outcomes;
- mutate mechanics;
- write final prose;
- predetermine player choices.

Output:

```json
{
  "sceneGoal": "Force a decision about whether to trust Mara",
  "activeThreads": ["reactor_sabotage", "mara_loyalty"],
  "pressure": "The backup generator is failing",
  "doNotResolve": ["identity_of_saboteur"]
}
```

### 19.2 Referee

Runs every meaningful player action.

Owns:

- interpreting intent;
- deciding whether rules resolution is required;
- calling engine tools;
- calling direct core-action tools when the player's intent clearly changes the world;
- producing a structured Resolution Envelope.

Does not write immersive prose.

```json
{
  "intent": "force open the maintenance hatch",
  "resolutionRequired": true,
  "engineResult": "success_with_cost",
  "factsEstablished": ["hatch_open"],
  "costs": ["alarm_triggered"],
  "allowedNarrativeRange": "The hatch opens; the alarm must become apparent."
}
```

### 19.3 Narrator

Owns:

- prose;
- sensory description;
- NPC dialogue;
- rendering consequences;
- offering a clear situation back to the player.

Has read-only access to world/engine context.

**Narrator never mutates canonical state.**

### 19.4 Archivist

Owns:

- detecting newly established soft facts;
- creating/updating descriptive entity information;
- recording memories;
- recording relationship developments;
- proposing new entities introduced by narration;
- ensuring narrative output did not imply uncommitted state changes.

The Archivist should not override engine results or silently retcon core state.

### 19.5 World Executor

Not an LLM.

Every state mutation goes through this deterministic command layer.

It validates:

- entity existence;
- location constraints;
- ownership invariants;
- party membership;
- engine permission;
- event schema;
- concurrency/version.

Then it appends events and updates projections.

---

## 20. Core tools vs engine tools

This distinction should be visible in code and prompts.

### 20.1 Core read tools

```text
get_scene_context
get_entity
get_location
get_party
get_thread
retrieve_memories
search_world
retrieve_source
```

### 20.2 Core command tools

Prefer narrow domain commands:

```text
move_entity
transfer_item
set_relation
remove_relation
join_party
leave_party
advance_time
reveal_fact
activate_thread
resolve_thread
schedule_trigger
record_observation
create_entity
```

Avoid a universal `update_json(path, value)` tool. It gives agents too much authority and destroys domain invariants.

### 20.3 Engine tools

Defined by the active Engine Package.

Oracle Engine may expose:

```text
resolve_risk
resolve_conflict
adjust_track
recover
inspect_character_mechanics
```

Ironsworn could expose moves/progress-related operations.

A future D&D engine could expose a small semantic facade over a much larger internal rules implementation.

### 20.4 Agent-specific tool visibility

Each agent only sees tools it needs.

Example:

```text
Director  -> read world, read threads, maybe schedule story trigger
Referee   -> read world + engine tools + permitted core commands
Narrator  -> read only
Archivist -> memory/entity-description commands; no dice/combat tools
```

The ChatRPG study similarly found that narrow JSON tools with explicit "when to use," examples, and input formats helped specialized agents maintain game state.[R8]

---

## 21. Context assembly

Do not send the entire database or entire conversation to every agent.

Build a Turn Context packet:

```yaml
scene:
  location: ...
  local_state: ...
  recent_events: ...

party:
  player: ...
  companions: ...

nearby_entities: ...

active_threads: ...

relevant_memories: ...

source_evidence: ...

engine:
  concise_state: ...
  relevant_rule_context: ...

director_intent: ...
```

For complex engines, the engine's context builder should retrieve **only the rules relevant to the current action**.

Never solve D&D complexity by injecting the entire SRD into the Referee prompt.

---

## 22. PDF-to-scenario architecture

"Any PDF" should mean the importer accepts many source types, not that every PDF is treated as if it were an adventure module.

Possible inputs:

- RPG sourcebook/adventure;
- novel or story;
- history book;
- travel guide;
- technical manual;
- scientific report;
- biography;
- academic paper;
- scanned/image-heavy document.

### 22.1 Separate source understanding from scenario invention

Pipeline:

```text
PDF
 -> document extraction
 -> source corpus
 -> entities / relations / claims / chronology
 -> source knowledge graph
 -> scenario design
 -> scenario validation
 -> engine compilation
 -> playable campaign
```

GraphRAG research is relevant here because it uses entity and relationship extraction plus higher-level summaries to reason over large unstructured corpora rather than relying only on nearest text chunks.[R13]

You do not need to implement Microsoft GraphRAG specifically. The important idea is to extract **relational structure** from source material because scenarios depend on who/what/where/how things connect.

### 22.2 Source corpus

Every extracted chunk should preserve provenance:

```ts
interface SourceRef {
  documentId: string;
  page?: number;
  section?: string;
  chunkId: string;
}
```

### 22.3 Fact classes

Every scenario fact should have a provenance class:

```text
SOURCE_FACT
DERIVED_FACT
GENERATED_FACT
PLAYER_ESTABLISHED_FACT
ENGINE_RESULT_FACT
```

Example:

```yaml
fact: "The coolant pump is rated for 240 C."
class: SOURCE_FACT
source: manual.pdf#page=37

fact: "Someone disabled the secondary coolant pump before the crew arrived."
class: GENERATED_FACT
source: scenario-generator/run-42
```

The Narrator may treat both as current scenario facts, but the authoring UI and retrieval layer can always distinguish them.

### 22.4 Source policy

Scenario creation should expose a simple user control:

```text
Faithful
Grounded
Inspired
Wild
```

- **Faithful** - preserve source facts strictly; invent only connective conflict.
- **Grounded** - preserve major facts, allow plausible fictionalization.
- **Inspired** - use source as worldbuilding material.
- **Wild** - remix freely.

### 22.5 Scenario authoring agents

These are separate from runtime agents.

Suggested authoring pipeline:

1. **Extractor** - entities, locations, factions, objects, claims, chronology, terminology.
2. **World Builder** - consolidates duplicate entities and constructs relations.
3. **Scenario Designer** - creates tensions, hooks, secrets, tracks, entry points, and triggers.
4. **Engine Compiler** - attaches engine overlay and content-pack material.
5. **Validator** - detects disconnected locations, impossible hooks, missing source evidence, unreachable core clues, empty factions, and engine incompatibilities.

---

## 23. Scenario compilation into an engine

Scenario Core stays mechanical-rule-free.

When starting a campaign:

```text
Scenario Core
+ Character Persona(s)
+ Engine Package
+ Engine Content Packs
+ Narrative Content Packs
= Campaign Instance
```

Engine compilation may create:

- mechanical NPC profiles;
- encounter difficulty;
- item mechanics;
- special hazard rules;
- engine-specific clocks/tracks;
- character adaptation suggestions.

Only mechanically relevant entities need to be compiled immediately. Others can be compiled lazily.

---

## 24. Character creator workflow

Make character creation two-stage.

### Stage A: Persona

Engine-neutral, conversational, portable.

Ask about:

- who are you?;
- what are you good at?;
- what gets you in trouble?;
- what do you want?;
- who/what matters to you?;
- what do you look/sound like?;
- signature possessions;
- tone/content preferences if desired.

AI can propose concise tags and a brief.

### Stage B: Engine adaptation

Only after selecting an engine.

The engine adapter should:

- infer obvious choices;
- present meaningful choices;
- explain ambiguities;
- validate the resulting sheet;
- never require the core persona to grow engine-specific fields.

This is also where engine-specific content packs contribute options.

---

## 25. Media generation

Media belongs outside the rules engine.

### 25.1 Visual identity

Core entities may have:

```ts
interface VisualProfile {
  canonicalDescription: string;
  distinctiveFeatures: string[];
  preferredStyle?: string;
  referenceAssetIds?: string[];
}
```

Generated portraits/location art are cached assets linked to the entity and generation settings.

### 25.2 Voice identity

```ts
interface VoiceProfile {
  description: string;
  accent?: string;
  pace?: string;
  tone?: string;
  providerVoiceId?: string;
}
```

The Narrator produces dialogue text. A media service renders it.

### 25.3 Rule

**Generated media is a representation of canonical state, never a source of canonical state.**

If an image accidentally adds a scar that the entity does not have in World Core, the scar is not real unless explicitly promoted into canon.

---

## 26. Native engine and supported-engine roadmap

### Engine 0: Oracle Engine

Purpose: optimize playability, cheap agent calls, PDF adaptation, and generic conflict.

This proves the product itself.

### Engine 1: a deliberately different lightweight engine

Recommended: 24XX or Cairn.

24XX is useful because its open SRD is tiny and explicitly intended for adaptation.[R3]

Cairn is useful because it introduces conventional attributes, HP, inventory pressure, hirelings, and explicit dungeon exploration procedures while remaining much smaller than D&D.[R4]

The purpose is not market coverage. It is to prove that the engine boundary survives a mechanically different game.

### Engine 2: Ironsworn

This stress-tests:

- move-driven resolution;
- assets;
- Momentum;
- progress tracks;
- solo-specific procedures.

Ironsworn's SRD content is available under CC BY 4.0 according to Tomkin Press licensing guidance, which also distinguishes separately licensed full-book material.[R17]

### Engine 3: optional QuestWorlds / Fate

Useful for testing highly descriptive characters and abstract conflicts. QuestWorlds explicitly markets scalable customizable character descriptions and genre packs.[R5] Fate demonstrates that aspects can attach to characters, situations, locations, and other game elements, but its Fate Point economy and invoke/compel machinery would stay entirely in its engine package.[R6]

### Engine 4: D&D SRD

Only attempt after the plugin boundary has survived the previous engines.

Treat D&D as an **isolated complex rules application embedded behind the Engine Package contract**, not as a set of concepts the platform should generalize.

---

## 27. D&D-specific containment strategy

If D&D is eventually supported:

1. D&D gets its own complete mechanical state model.
2. D&D owns character creation/leveling schemas.
3. D&D owns spells/features/conditions/combat resources.
4. D&D owns initiative and encounters.
5. World Core only sees fictional consequences and ordinary core actions.
6. Rule retrieval is just-in-time.
7. Mechanically relevant NPCs receive lazy D&D stat bindings.
8. High-level LLM tools call deterministic D&D services.

Example:

```text
Player: "I cast Hold Person on the guard."

Referee
 -> engine.use_ability(...)

D&D engine internally
 -> validates prepared spell
 -> validates slot
 -> checks target type/range
 -> consumes slot
 -> creates save
 -> resolves save
 -> applies concentration / condition if needed

Engine result
 -> fictional consequence: "guard is magically paralyzed"

World Executor
 -> records visible fictional state/event

Narrator
 -> describes it
```

Nothing about this requires World Core to know what a spell slot is.

---

## 28. Data persistence recommendation

For a hobby project, optimize for clarity before distributed scale.

Reasonable storage split:

- relational DB for entities, relations, campaigns, projections, engine-component blobs;
- append-only `world_events` table;
- vector retrieval for memories/source chunks;
- blob/object storage for PDFs and generated media.

Postgres plus vector extension is a natural all-in-one deployment later; SQLite plus a simple vector store can be enough locally.

Do not add Kafka, a dedicated graph database, or microservices just because the conceptual model uses events and graphs.

---

## 29. Turn execution

Recommended runtime sequence:

```text
PLAYER INPUT
    |
    v
Intent preprocessing
    |
    +--> assemble scene/world/memory/source context
    |
    v
Director (only if scene framing/pacing needed)
    |
    v
Referee
    |
    +--> core read tools
    +--> engine tools
    +--> permitted core commands
    |
    v
Resolution Envelope
    |
    v
Narrator (read-only)
    |
    v
Archivist
    |
    +--> memory/entity/relationship proposals
    |
    v
World Executor validates + commits events
    |
    +--> update projections
    +--> update memories
    +--> evaluate triggers/threads
    |
    v
UI response + optional media rendering
```

For direct unambiguous actions such as "I walk into the kitchen," Referee can commit movement before Narrator prose.

For newly invented soft facts introduced during narration, Archivist proposes the state additions afterward.

---

## 30. Invariants the code must enforce

These are more important than prompting quality.

### World invariants

- an entity has one authoritative current location unless explicitly modeled otherwise;
- ownership/containment transitions are transactional;
- party membership is canonical;
- world facts and beliefs are separate;
- source facts retain provenance;
- secret information has visibility rules;
- all meaningful state changes create events;
- Narrator output cannot directly mutate state.

### Engine invariants

- engine state is namespaced/versioned;
- only engine code mutates engine state;
- engine emits fictional consequences through bridge commands;
- engine plugins cannot write arbitrary World Core fields;
- character adaptation produces a validation report.

### Story invariants

- core clues cannot be permanently lost to a failed random check;
- resolved threads stop generating hooks unless reopened explicitly;
- triggers are idempotent or record whether they fired;
- NPCs cannot use secret facts they have not learned.

---

## 31. Evaluation strategy

The project should test objective consistency separately from subjective storytelling quality.

RPGBench makes the same broad distinction by evaluating structured event/state correctness alongside subjective RPG quality, and reports that long/complex mechanical consistency remains difficult for LLMs.[R9]

### 31.1 Engine compliance suite

Every Engine Package should pass automated fixtures for:

1. adapt a generic persona;
2. validate character state;
3. resolve a risky non-combat action;
4. resolve a conflict;
5. apply/recover from engine effects;
6. handle defeat/death where relevant;
7. advance/progress a character where supported;
8. create a mechanically relevant NPC lazily;
9. export fictional consequences;
10. reload serialized state with no change.

### 31.2 World consistency suite

Test:

- movement graph legality;
- inventory conservation;
- party joins/leaves;
- location containment;
- event replay;
- rewind/fork;
- NPC knowledge boundaries;
- memory retrieval;
- thread activation/resolution;
- trigger idempotency.

### 31.3 Scenario compiler suite

Test:

- source citation coverage;
- duplicate entity consolidation;
- connected starting play area;
- at least one actionable hook;
- core clues reachable;
- generated/source fact separation;
- no scenario dependence on unsupported engine capability;
- engine overlay validates.

### 31.4 Runtime quality metrics

Track:

- tokens/cost per turn;
- latency per agent;
- tool-call count;
- state correction rate;
- hallucinated entity rate;
- NPC knowledge violations;
- rule violations;
- repeated narration;
- unresolved-thread abandonment;
- player-rated agency/immersion.

---

## 32. What to delete or quarantine from the current project

If the existing architecture contains any of these, move them out of core immediately:

- universal HP;
- universal attributes;
- universal AC/defense;
- universal skill checks;
- universal initiative;
- universal combat turns;
- universal damage types;
- universal conditions modeled mechanically;
- universal spell/ability structures;
- universal class/level fields;
- giant "character sheet" interfaces intended to cover all games.

Retain or promote:

- entity IDs;
- names/briefs;
- location state;
- entity movement;
- item transfer/ownership;
- relationships;
- party membership;
- world facts;
- story threads;
- events;
- source provenance;
- memory;
- media identity.

---

## 33. Explicit non-goals

The project should say no to these for now:

1. **Lossless conversion between RPG engines.** It is not a coherent requirement.
2. **Hot-swapping engines mid-scene.** Use migration/fork instead.
3. **A universal mechanical character schema.** Keep persona universal, mechanics local.
4. **LLMs enforcing rules from memory.** Rules execute in tools/code.
5. **One autonomous LLM per NPC.** Use memory plus attention-based activation.
6. **A custom rules engine generated for every PDF.** Generate scenario content, not arbitrary executable mechanics.
7. **Full world simulation every turn.** Simulate foreground and active offscreen threads only.
8. **A single giant GM prompt.** Preserve agent/tool specialization.
9. **Raw transcript as long-term memory.** Store structured events/memories and retrieve selectively.
10. **5e compatibility as a core acceptance criterion.** It is a later engine-isolation test.

---

## 34. Reorientation roadmap

### Phase 0 - stop the bleed

- freeze 5e work;
- mark engine-specific core fields deprecated;
- identify which current data is true World Core vs leaked engine mechanics;
- create migration notes, not compatibility hacks.

Deliverable: clean ownership map.

### Phase 1 - World Core

Implement:

- entities;
- relations;
- locations;
- movement;
- containment/ownership;
- party membership;
- world event log;
- current-state projections;
- source refs.

No fancy agents yet.

Deliverable: deterministic world runtime with tests.

### Phase 2 - Oracle Engine

Implement:

- persona adaptation;
- tiny tag-based character state;
- one risk resolution mechanism;
- generic conflicts;
- fortune/harm resource;
- progress/danger tracks;
- engine compliance interface.

Deliverable: rules engine that can be run without an LLM.

### Phase 3 - Agent runtime

Implement:

- context assembler;
- Referee;
- Narrator;
- Archivist;
- lightweight Director;
- World Executor command permissions.

Deliverable: coherent long-running chat play over deterministic state.

### Phase 4 - Threads and memory

Implement:

- StoryThreads;
- Hooks;
- Triggers;
- core-clue invariant;
- episodic memory;
- beliefs/reflections;
- NPC knowledge filtering;
- offscreen active-thread advancement.

Deliverable: a world that feels persistent rather than like episodic improv.

### Phase 5 - Scenario authoring

Implement:

- premise-to-scenario;
- PDF ingestion;
- source graph extraction;
- provenance classes;
- source-policy control;
- scenario validator;
- engine compilation.

Deliverable: PDF -> editable scenario -> playable campaign.

### Phase 6 - packs and media

Implement:

- engine content packs;
- narrative content packs;
- portrait generation;
- location art;
- voice/TTS profile;
- asset caching/versioning.

Deliverable: reusable ecosystem layer.

### Phase 7 - second and third engines

Implement one lightweight but structurally different engine, then Ironsworn or another solo-oriented system.

Every failure becomes a boundary fix, not a new universal field.

Deliverable: evidence that the plugin contract is real.

### Phase 8 - D&D experiment

Only now revisit SRD 5.2.1.

Build it as an isolated complex engine. If it requires internal subsystems far larger than Oracle Engine, that is acceptable. If it forces changes to World Core concepts such as HP, classes, initiative, spell slots, or conditions, the plugin boundary is leaking and should be fixed.

---

## 35. Recommended repository-level mental model

```text
/apps
  /web

/core
  /world
  /events
  /relations
  /memory
  /threads
  /sources
  /commands

/runtime
  /orchestrator
  /context
  /agents
    /director
    /referee
    /narrator
    /archivist

/engines
  /oracle-engine
  /24xx
  /ironsworn
  /dnd-srd-5.2.1   # much later

/packs
  /narrative
  /engine

/scenarios
  /schema
  /compiler
  /validator
  /ingestion

/media
  /images
  /voice

/tests
  /world-invariants
  /engine-compliance
  /scenario-quality
```

Names are illustrative. The boundary is the important part.

---

## 36. The architectural test question

For every new feature, ask:

> **Would this still exist if the campaign had no dice and no RPG rules engine at all?**

If yes, it probably belongs in World Core.

Examples:

- Mara is in the laboratory -> Core.
- Mara trusts Evelyn -> Core.
- Mara remembers seeing the broken pump -> Core.
- The revolver is in Evelyn's backpack -> Core.
- The northern tunnel connects to the mine -> Core.
- The reactor failed at midnight -> Core event.

If the answer is no, it belongs in an engine:

- Mara has 11 HP -> Engine.
- Evelyn has advantage -> Engine.
- The revolver deals 1d8 -> Engine.
- This is a Dexterity save -> Engine.
- The spell requires concentration -> Engine.

If it is reusable setting/rules data for one engine, it belongs in an Engine Content Pack.

If it is authored world/story material, it belongs in the Scenario.

This test is simple enough to use during code review.

---

## 37. Final recommendation

Reorient the project around **World Core first, engines second**.

The mistake was not choosing the wrong universal RPG abstraction. The mistake was expecting RPG mechanics to share a useful universal ontology at all.

They do not need one.

Characters can share identity without sharing stats.

Locations can share topology without sharing travel mechanics.

Items can share existence and ownership without sharing damage/weight rules.

NPCs can share memories and relationships without sharing stat blocks.

Scenarios can share truths, factions, hooks, clues, and events without sharing encounter math.

Agents can share core world tools while the Referee receives a small set of engine-specific tools.

That gives the system two stable foundations:

1. a persistent fictional world that the LLM cannot casually rewrite;
2. a rules engine boundary that lets simple engines stay simple and complex engines be complex without contaminating everything else.

The first proof should be the Oracle Engine plus a persistent location/NPC/party/thread/memory system. The second proof should be a mechanically different lightweight engine. D&D should be the final stress test, not the foundation.

If this architecture works, the most interesting capability is no longer "AI can run several RPG systems."

It becomes:

> **Create a person. Create or import a world. Choose how that world should play. Then let a persistent agentic GM run it without confusing story, memory, rules, and state.**

That is the project worth building.

---

## 38. Research notes and sources

### RPG systems

- **[R1] Loner 3e Core Rules**, Roberto Bisceglie. The July 31, 2026 SRD describes Loner as solo, minimalist, one-core-mechanic, tag-based, and emergent. Its published license is CC BY-SA 4.0.  
  https://lonersrd.zotiquestgames.com/core/loner-3e.html

- **[R2] Ironsworn**, Tomkin Press. Official material describes solo, co-op, and guided play with moves, oracles, Momentum, and progress-oriented quest play.  
  https://tomkinpress.com/pages/ironsworn

- **[R3] 24XX**, Jason Tocci. The SRD is a tiny adaptable version of the 2400 rules and is published under CC BY 4.0.  
  https://jasontocci.itch.io/24xx  
  https://24xx-srd.carrd.co/

- **[R4] Cairn 2e Core Rules and Procedures**, Yochai Gal. The rules include a small attribute/HP model, hirelings, a Die of Fate, and explicit dungeon exploration procedures.  
  https://cairnrpg.com/second-edition/players-guide/core-rules/  
  https://cairnrpg.com/second-edition/players-guide/procedures/

- **[R5] QuestWorlds**, Chaosium. Official description emphasizes rules/prep-light play, abstract conflict resolution, scalable customizable character descriptions, broad genre suitability, and genre packs.  
  https://questworlds.chaosium.com/

- **[R6] Fate Core SRD**. Aspects can apply to characters, situations, consequences, and the wider game; extras can carry aspects, skills, stunts, stress, and consequences.  
  https://fate-srd.com/fate-core/types-aspects  
  https://fate-srd.com/fate-core/extras

- **[R7] GUMSHOE SRD / Pelgrane Press**. GUMSHOE scenario design identifies core clues that move investigations forward rather than making essential information depend on a successful information-gathering roll.  
  https://pelgranepress.com/gumshoe/files/GUMSHOE_SRD_CC_3.pdf  
  https://pelgranepress.com/2018/02/14/gumshoe/

- **[R17] Ironsworn Licensing**, Tomkin Press. The Ironsworn SRD and specified rules/oracle/asset text are available under licenses described by Tomkin Press; the page distinguishes CC BY material from separately licensed full-book content.  
  https://tomkinpress.com/pages/licensing

### LLM RPG and agent architecture

- **[R8] Static Vs. Agentic Game Master AI for Facilitating Solo Role-Playing Experiences** (2025). The v2 architecture uses specialized Narrator and Archivist agents plus structured JSON tools for characters/environments; the paper reports improved modularity and player-experience measures in its comparative study.  
  https://arxiv.org/abs/2502.19519

- **[R9] RPGBENCH: Evaluating Large Language Models as Role-Playing Game Engines** (2025). Uses structured event-state representations and reports that LLMs can be engaging while still struggling with consistent, verifiable mechanics in long/complex scenarios.  
  https://arxiv.org/abs/2502.00595

- **[R10] Generative Agents: Interactive Simulacra of Human Behavior** (2023). Introduces persistent experiences, dynamic retrieval, reflection, and planning for believable long-running agents.  
  https://arxiv.org/abs/2304.03442

- **[R11] MemGPT: Towards LLMs as Operating Systems** (2023). Proposes hierarchical external memory / virtual context management for long-lived agents and document analysis beyond a single context window.  
  https://arxiv.org/abs/2310.08560

### Software/data architecture

- **[R12] Event Sourcing Pattern**, Microsoft Azure Architecture Center. Describes immutable append-only domain events, reconstruction of current state, materialized projections, audit history, and event versioning.  
  https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing

- **[R13] From Local to Global: A Graph RAG Approach to Query-Focused Summarization**, Microsoft Research (2024). Builds entity/relationship graphs from source documents and hierarchical summaries for corpus-level reasoning.  
  https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/

- **[R15] Unity Entities / ECS documentation**. Example of the Entity Component System composition pattern used in modern game architecture.  
  https://docs.unity3d.com/6000.0/Documentation/Manual/com.unity.entities.html

- **[R16] Tabletop Roleplaying Games as Procedural Content Generators** (2020). Frames TTRPG design in terms of possibility spaces, expressive ranges, and generative pipelines.  
  https://arxiv.org/abs/2007.06108

### D&D

- **[R14] D&D SRD 5.2 / 5.2.1 announcement**, D&D Beyond. Describes the current SRD as including updated foundational rules and content across the rules glossary, classes, spells, monsters, actions, exploration, and other systems; it is released under CC BY 4.0.  
  https://www.dndbeyond.com/posts/1949-you-can-now-publish-your-own-creations-using-the

---

## 39. Licensing note

This document is an architecture recommendation, not legal advice.

One correction to earlier research discussion is worth preserving in the repo: the current Loner 3e SRD page states **CC BY-SA 4.0**, not CC BY 4.0.[R1] Ironsworn's official licensing page separately identifies SRD and selected reference content that is available under CC BY 4.0.[R17] If the project later redistributes copied/adapted SRD text or data, review each source's exact license and attribution/share-alike requirements at that time.
