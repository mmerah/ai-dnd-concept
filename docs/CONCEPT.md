# AI Dungeon Master — Concept

## Purpose

Build a local, single-player AI Dungeon Master for small, fast language models.
Reliability comes from narrow roles, typed intent tools, deterministic mechanics,
focused context, and transactional state. Creative narration remains prose-only.

The first playable system supports one human controlling one character with a small
original fantasy ruleset behind a ruleset-agnostic core.

## Principles

- Committed play is the source of truth.
- Models propose intent; Python validates causality and performs mutations.
- Give every mutable field exactly one owner.
- Separate world truth, private canon, claims, disclosures, and knowledge.
- Prefer existing canon before creating an entity.
- Treat authored or exact-source-verified facts as binding starting canon.
- Let committed play override earlier scenario or source expectations.
- Give each role only the context and tools it needs.
- Run a fixed, observable gameplay pipeline.
- Commit a complete turn or none of it.
- Put structure at integrity boundaries, not in creative prose.
- Bound work and fail clearly.
- Favor pure functions, immutable values, DRY/KISS, and explicit dependencies.

## Scope

### Included

- Multiple local campaigns, one open campaign, and one active turn.
- Prepared scenarios and progressively extracted source scenarios.
- One player character; conversational exploration, dialogue, and combat.
- A seeded living scenario that grows with play.
- Engine-owned, recorded randomness.
- Fact-level secrets, claims, hints, disclosures, and knowledge.
- Chat, character, inventory, journal, and known-world panels.
- Optional `@entity` mentions with autocomplete.
- One-turn undo and inspectable JSON traces.
- On-demand player-character, NPC, and location images.

### Excluded

- Multiplayer, accounts, public hosting, and concurrent turns.
- A full established tabletop ruleset or tactical combat UI.
- Voice, audio, EPUB, OCR, and scanned-PDF ingestion.
- Streaming narration before validation and commit.
- A database, workflow graph, message bus, or dedicated debug UI.
- Arbitrary runtime ruleset plugins and automatic migration of every old save.
- Exhaustive book conversion before play.

## Authority and domain model

Authority applies only to assertions about world truth:

1. Resulting typed current state.
2. Typed events.
3. Accepted displayed narration.
4. Structured scenario canon.
5. Retrieved source evidence.
6. New model invention.

Narration is authoritative evidence of what the player was told, but it never overrides
typed current or mechanical truth. An unsupported mechanical assertion is a trace
defect; later turns follow typed reality without rewriting the displayed text.

Knowledge and beliefs are not truth candidates. A false claim may be committed player
knowledge without outranking the actual private fact.

All authoritative data is represented by strict, JSON-serializable Pydantic models.
Runtime clients, locks, model instances, and indexes never live in snapshots.

| Model | Responsibility |
| --- | --- |
| `Campaign` | Identity, pinned versions, ruleset, source manifest, preferences |
| `GameState` | Character, clock, runtime entities, hooks, encounter, inventory, knowledge |
| `EntityState` | Mutable position, status, disposition, ownership, conditions |
| `Scenario` | Private definitions, world facts, authored relationships, hook templates |
| `TurnRecord` | Input, accepted narration, events, trace, retrieval IDs, parent ID |
| `RulesetState` | Ruleset-owned typed mechanical extension |

### Entity ownership

Each materialized entity has one stable ID shared by:

- `ScenarioEntity`: identity, description, backstory, secrets, provenance, and plans.
- `EntityState`: every mutable played-world value.
- Optional ruleset payload: mechanical values validated by the ruleset.

Actor/core reducers own existing `EntityState`, existing `Knowledge`, and runtime hook
progress. Hook progress is a pure reduction of typed events. Maintainer requests new
scenario definitions, facts, claims, and disclosures. A system-owned `GrowthCommit`
may create those definitions, initialize a new entity, and pass every newly created,
turn-visible disclosure to validated recipient IDs through the idempotent knowledge
reducer. Recipients must be resolved speakers or addressees from the prompt and public
Director targets. Acquisition of a pre-existing disclosure uses a typed Actor event and
the same reducer. Maintainer and Creator never write snapshots.

Built-in scenario definitions cover NPC, location, faction, quest, item, encounter,
and fact. The first release uses a statically registered discriminated union of bundled
rulesets and extensions so strict static typing remains credible.

### Facts and knowledge

- `WorldFact`: private assertion about reality, with provenance and stable subject.
- `Claim`: what an actor says, suspects, or believes; it may be false.
- `Disclosure`: player-facing wording linked to a fact or claim.
- `Knowledge`: which actor received which disclosure.

Hints are separate disclosures and never expose a private fact payload. Dialogue
context contains only what the speaking NPC knows, believes, or may reveal.

### Growth

1. Reuse or deepen relevant canon first.
2. Add only facts compatible with committed play and binding source canon.
3. Create an entity only when no existing entity serves the purpose.
4. Require every operational field; leave irrelevant facts absent or explicitly unknown.
5. Record whether every fact came from source, setup, or live generation.
6. Never let a Creator recursively create more entities or reference unknown IDs.
7. Never retcon displayed facts.

Undisclosed generated facts may be reconciled when stronger source evidence appears.
Acceptance of a new named entity, disclosure, relationship, or state-bearing fact
requires matching typed growth or events. Only non-operational descriptive color may
remain solely as historical narration evidence. Failure to enforce this contract is an
auditable trace defect, not permission for prose to become unindexed operational canon.

## Ruleset boundary

A campaign pins one trusted hybrid Python ruleset and version. A ruleset provides:

- Pydantic character, runtime, command, and event models.
- Character-creation schema and defaults.
- Intent-level Actor tools and pure resolvers.
- Invariant checks, random tables, and mechanical data.
- Short Director and Actor guidance.
- Statically registered scenario extensions when necessary.

Python owns behavior and schemas; declarative files hold tables, catalogs, and prompt
guidance. The core owns campaigns, turns, canon, persistence, retrieval, orchestration,
and UI. It knows nothing about ability math, damage, or initiative.

The reference ruleset supplies attributes, checks, combat, inventory, and conditions.
Combat uses the normal conversational pipeline.

Intent-level tools such as `search` and `attack` own their full causal transition,
including rolls and conditional effects. If a ruleset exposes dependent low-level
tools, prior events issue transaction-local, single-use capability tokens.

## Sources and context

### Ingestion and retrieval

The first release accepts text, Markdown, and text-based PDFs. Ingestion:

1. Extracts text and stable source references.
2. Splits on document structure with a token-size cap.
3. Registers names, aliases, major entities, and major claims deterministically.
4. Embeds chunks through a configurable local-or-remote interface.
5. Builds a rebuildable campaign-local index with visibility metadata.

Retrieval combines direct entity/lexical lookup with semantic search. Retrieved text is
quoted, untrusted data rather than instructions. Unmaterialized passages are
authoritative evidence, but retrieval cannot guarantee that every passage constrains
every turn.

The index records embedding model ID, dimensions, normalization, chunking version,
visibility, and indexed campaign head. Changing the embedding configuration rebuilds
the index rather than migrating canon.

### Progressive setup

Prepared scenarios are supported first. Automated book setup is a separate bounded
workflow:

1. Deterministically extract, chunk, and register source identifiers.
2. Produce typed per-chunk candidates with source references.
3. Merge exact identifiers and aliases deterministically.
4. Run bounded model consolidation for unresolved duplicates and relationships.
5. Validate a comprehensive skeleton and detailed starting region.
6. Show an inspectable summary before confirmation.

Confirmation starts play and commits displayed setup facts; it does not certify unseen
model extraction. Undisclosed extracted facts remain provisional and correctable until
authored directly or verified against an exact cited passage. Character creation
combines typed ruleset forms with an optional conversational concept/background step.

### Role views

Python supplies a deterministic core from location, referenced entities, active hooks,
knowledge, active history, and the original prompt. Retrieval adds relevant source and
older active-lineage events.

| Role | Context |
| --- | --- |
| Director | Prompt, private local canon, current state, hooks, source/history evidence |
| Actor | Original prompt, validated Director program, draft state, ruleset tools |
| Narrator | Prompt, public directive/targets/disclosures, visible events/state, preferences |
| Maintainer | Full turn, private canon, allowed reveals, source evidence |
| Creator | Typed request, narrow schema, existing IDs, relevant source evidence |

Private traces and ACL-protected chunks are never retrieved into Narrator context.

## Gameplay pipeline

Every gameplay prompt runs:

`USER → DIRECTOR → ACTOR → NARRATOR → MAINTAINER → optional CREATORS → COMMIT`

All four core roles run even when their useful output is empty. Opening a campaign,
undo, and image generation are UI operations and bypass the gameplay pipeline.

### Director

Director protects scenario direction and resolves reasonable intent. Its minimal typed
envelope contains:

- Natural-language instructions.
- Turn kind: action, dialogue, recap, or rules question.
- Resolved target IDs.
- Permitted `DisclosureId` values.
- A typed public `NarrativeDirective`.

Python validates every referenced ID and disclosure grant before Actor runs. Private
Director prose goes only to Actor and Maintainer. Narrator input is built
deterministically from its directive, turn kind, public targets, stored disclosure
wording, visible events/state, and the original prompt. The directive contains no prose:
only visible speaker/target IDs and enums such as stance, speech act, and response goal.
Director infers reversible or equivalent ambiguity. If an irreversible action has
materially different possible targets, it directs a no-op clarification instead of
guessing.

### Actor

Actor translates the validated program into mechanics through a bounded PydanticAI
tool loop. Stateful tool calls always execute sequentially. Resolvers validate causal
preconditions, are idempotent against duplicate calls, and return new draft state plus
typed events.

Actor finishes with a concise private report, but typed events are authoritative.
Narrator receives only visibility-filtered typed events, never Actor prose. Maintainer
receives the private report and event view needed for validation. An empty tool list is
valid for narrative and meta turns.

### Narrator

Narrator receives the original prompt, deterministic public guidance, visible events,
visible context, and narrative preferences. It returns prose only and never emits
growth metadata or calls tools.

It may introduce non-mechanical details, including new canon for Maintainer to
materialize. It may not assert item transfer, movement, damage, death, conditions, or
other current-state consequences absent matching Actor events. Maintainer rejects
unsupported consequences.

### Maintainer

Maintainer reads the full turn and:

1. Validates prose against the public directive, visible Actor events, permitted
   disclosures, current reality, scenario canon, and retrieved source evidence.
2. Requests new typed definitions, growth, and recipients for new disclosures found in
   the prompt or accepted prose.
3. Confirms every operational durable assertion has matching events or growth, and
   every player-visible event outcome appears in the narration.

It does not proactively simulate or refine the world. It cannot grant items, move
entities, apply damage, change conditions, acquire pre-existing disclosures, or advance
hooks. New-disclosure recipients are validated from resolved turn participants before
the core knowledge reducer applies them. Typed growth tools only register requests in a
maintenance sub-draft; hook reducers consume typed events later.

Maintainer classifies rejection origin. Narrator deviation retries Narrator once with
the reason. A Director or Actor error fails and rolls back the turn; Narrator is not
asked to repair invalid upstream inputs.

Meta turns cannot create canon. Correction is a separate explicit UI action or command
that shows a typed patch preview and requires user confirmation; Director
classification never grants mutation authority.

### Creators

Specialized NPC, location, faction, quest, item, encounter, and fact Creators share one
interface and narrow prompts. They fill only fields authorized by a typed growth
request and cannot invent extra facts, relationships, or disclosures. Required
operational fields and provenance are validated; optional details may remain unknown.

### Transaction and budgets

1. Lock and strictly load the active generation and pinned schemas.
2. Copy game, scenario, and random state into a draft.
3. Build contexts; run and validate Director, then Actor, Narrator, and Maintainer.
4. On Narrator rejection, discard maintenance changes and retry Narrator once.
5. Run required Creators within the remaining turn budget.
6. Validate Creator output against its approved request and source evidence.
7. Apply `GrowthCommit` to approved definitions, new runtime, and new knowledge events.
8. Validate cross-references, visibility, ruleset invariants, and event fidelity.
9. Persist one immutable generation and atomically advance `HEAD`.
10. Display narration and refresh UI panels.

The whole turn has limits for wall time, model requests, deterministic context,
provider output tokens, tool calls, retries, and growth requests. A small configurable
cap prevents one narration from creating unbounded entities.

Before persistence, timeout or cancellation discards the draft, releases the lock,
preserves player input, and offers a non-spoiler retry. Generation persistence and the
`HEAD` advance are shielded as one commit boundary. After `HEAD` advances, the turn is
committed and reconnect/reload displays its narration. The lock is always released.

## Persistence and undo

Each successful turn is stored as an immutable generation:

```text
commits/<turn-id>/
  state.json
  scenario.json
  random.json
  turn.json
HEAD
```

The generation records its parent. `HEAD` changes only after every generation file is
durable. Unheaded stages are discarded on recovery. Top-level `state.json`,
`scenario.json`, and `turns.jsonl` may be rebuilt as readable views; they are not the
commit boundary.

Undo moves `HEAD` to its parent. Abandoned branches remain auditable, but retrieval
follows only active ancestry. Failed attempts go to a bounded non-authoritative JSON
diagnostic area excluded from model context.

Campaigns pin app and ruleset schema versions. Loading fails when incompatible and no
explicit migration exists; persisted values are never guessed.

## User interface and media

NiceGUI provides campaign creation/opening, source setup, character creation, chat,
role progress, character/inventory/journal/known-world panels, `@name` autocomplete,
undo, and on-demand images.

Input is disabled while a turn owns the lock. Narration appears only after commit.
Generic UI generation supports a documented small subset of Pydantic/JSON Schema and
fails clearly on unsupported constructs. Campaign JSON is the debugging surface.

Campaign preferences control tone, perspective, verbosity, themes, and content
boundaries. Player characters, NPCs, and locations contain canonical visual
descriptions. Generated images are derivative assets; image failure never affects play.

## Representative use cases

### Search with conditional consequences

**Player:** “I search the study.”

Director permits the relevant reveal. Actor calls one `search` intent tool; its resolver
rolls the check and conditionally discovers the map. Narrator follows visible events.
Maintainer rejects any narration that claims success after a failed event.

### Reuse existing canon

**Player:** “@Mara, who can help me enter the archives?”

Director selects Elena, permits only the relevant disclosure, and emits a public
directive to redirect the player. Actor records acquisition of the existing disclosure.
Narrator speaks as Mara and follows the directive. Maintainer creates nothing.

### Introduce a new NPC

Narrator says Elgin, an apothecary by the east gate, can help. Maintainer requests NPC
growth and `discover_entity`. Creator returns Elgin's required definition. GrowthCommit
adds definition, runtime state, and player disclosure together before display.

If Narrator instead says Elgin already handed over a key without an Actor event,
Maintainer rejects it; the retry may say Elgin offers the key.

### Combat changes runtime reality

An `attack` resolver records damage and death in the target's `EntityState`. Scenario
still holds the NPC's identity and backstory. Narrator follows the visible events; the
core hook reducer advances affected hooks from those events.

### Secrets, lies, and hints

Director grants a `DisclosureId`, never a private fact ID. Narrator receives only its
stored player-safe wording; private Director and Actor prose never enters its context.
An NPC's false story is a Claim and Disclosure, not world truth. If the player invents a
claim while speaking to an existing NPC, GrowthCommit records the new disclosure for
that resolved listener. A clue uses separate hint wording and never exposes the
underlying fact payload.

### Source discovered after generation

If later retrieval finds stronger source evidence, undisclosed generated or provisional
setup facts may be superseded with provenance retained. Anything already displayed is
historical evidence and the Director reconciles forward rather than rewriting history.

### Undo and history

Undo moves `HEAD` to the parent generation. Semantic retrieval excludes the abandoned
turn, so an undone promise cannot reappear as active history.

### Ambiguity, meta turns, and failure

"Attack him" with two materially different targets yields a no-op clarification. A
recap or rules question runs all roles but cannot grow canon. A correction requires a
confirmed typed patch outside the pipeline. Pre-commit timeout preserves the prompt,
releases the lock, rolls back draft randomness, and offers retry.

## Technical direction

- Python, Pydantic v2, pydantic-settings, PydanticAI, and NiceGUI.
- One OpenAI-compatible text model and endpoint for all textual roles.
- Configurable embeddings with a small local Sentence Transformers default.
- Separate image-provider interface.
- Local JSON generations and rebuildable search indexes.
- `uv`, strict basedpyright, Ruff, and pytest.

“OpenAI-compatible” is only transport compatibility. Startup probes required tool-call
IDs, structured-output mode, sequential stateful tools, context/output limits, and
provider profile settings. Unsupported configurations fail before campaign play.

Use plain async functions for orchestration. Avoid a database, workflow graph,
repository framework, and message bus until demonstrated need outweighs complexity.

## Code and verification

- Strict models forbid extras; authoritative collections are not mutated in place.
- Side effects live at model, file, randomness, retrieval, and media boundaries.
- Dependencies are explicit and provider behavior stays behind small interfaces.
- Functions remain below 100 lines and files below 500 lines.
- Comments explain only why; docstrings are minimal.

Minimal deterministic tests cover pure reducers, causal tool authorization, sequential
and duplicate tools, transaction rollback, fault-injected `HEAD` commits, recovery,
growth initialization, disclosure ACLs, active-lineage retrieval, undo, cancellation,
version rejection, and one fake-model pipeline.

A small opt-in model evaluation set checks tool choice, event fidelity, disclosure,
growth detection, public-directive adherence, contradiction rejection, and source
adherence without asserting exact prose or running in deterministic CI.

## Implementation order

1. One static reference ruleset and one prepared scenario fixture.
2. Runtime entity state, knowledge models, and atomic intent tools.
3. Fixed four-role pipeline with one NPC growth path and fake-model tests.
4. Immutable generations, active lineage, diagnostics, and undo.
5. Minimal NiceGUI chat and generic read-only panels.
6. Retrieval over already-ingested source chunks.
7. Automated progressive book setup.
8. Multiple campaigns and on-demand images.
