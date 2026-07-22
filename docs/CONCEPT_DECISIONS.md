# AI Dungeon Master — Concept Decisions

This file preserves the product and architecture decisions made during concept
development. `CONCEPT.md` is the concise implementation brief; this file records the
alternatives and rationale so later simplification does not erase intent.

The later **Adversarial review amendments** section supersedes earlier choices where
they conflict. Earlier entries remain as decision history.

## Decision principles

- Simplicity means fewer responsibilities per component, not fewer integrity checks.
- Typed structure is most valuable at state, tool, and persistence boundaries.
- Creative prose should not carry machine-oriented bookkeeping.
- The design deliberately trades extra serial model calls for clearer small-model roles.
- Local, inspectable data is preferred over infrastructure.

## Product and game model

### Ruleset-agnostic core

**Chosen:** The core is independent of any tabletop ruleset.

The core owns campaigns, scenario canon, turns, persistence, retrieval, agents, and UI.
Rulesets own character/rules schemas, commands, tools, random tables, and pure
resolvers. This prevents D&D-like assumptions from spreading through the application.

**Not chosen:** A rules-light engine hard-coded into the core, a D&D-specific engine,
or a full established ruleset implementation.

### Hybrid ruleset packages

**Chosen:** Trusted Python packages define typed behavior and schemas; declarative data
files contain tables, catalogs, configuration, and prompt guidance.

**Why:** Pure data rulesets make validation and debugging harder, while code-only
packages make content unnecessarily awkward. Campaigns pin the package and version.

### Reference ruleset

**Chosen:** Ship a small original fantasy ruleset with attributes, checks, combat,
inventory, and conditions.

**Not chosen:** A larger D&D-like package or an abstract core with no playable proof.

### Seeded living scenario

**Chosen:** Campaigns start from authored structure and grow when play reaches a real
gap. Existing NPCs, locations, and hooks should be reused before new ones are invented.

**Not chosen:** Strictly authored adventures that only repair gaps, or open sandboxes
that treat source content as loose inspiration.

### Player scope

**Chosen:** One human controls one player character.

**Deferred:** Multiple characters, multiple players, ownership models, permissions,
concurrent prompts, and turn coordination. The first domain model need not pretend to
be multiplayer-ready.

### Combat

**Chosen:** Combat uses the same conversational pipeline as all other play. The
ruleset exposes encounter, initiative, action, attack, damage, and condition tools.

**Not chosen:** A tactical frontend or a ruleset replacing the orchestration pipeline.

### Randomness

**Chosen:** The engine performs all rolls with seeded, recorded randomness.

**Why:** Physical/manual dice interrupt the conversational flow. Recorded draws allow
mechanical reproduction and correct rollback/undo behavior.

## Canon, state, and knowledge

### Separate domains

**Chosen:** Keep four distinct concerns:

- Ruleset: how mechanics work.
- Scenario: private canonical people, places, facts, relationships, and hooks.
- Game state: current mutable reality and player knowledge.
- Turn history: why state and scenario changed.

Actor tools mutate game state. Maintainer and Creator work on scenario canon. Neither
may silently take over the other's responsibility.

### Authority order

**Chosen:** Committed game state outranks structured scenario canon, which outranks
retrieved source material, which outranks model invention.

This lets play diverge from a source book without forgetting that the book is binding
where play has not changed it.

### Binding source material

**Chosen:** Imported books and documents are binding starting canon.

**Not chosen:** Treating all source material as inspiration or configuring authority
separately for every document in the first release.

### Fact-level knowledge

**Chosen:** Meaningful facts can independently be hidden, hinted, or discovered.
Claims and truth can coexist, allowing secrets, lies, suspicions, and partial clues.

**Not chosen:** Coarse entity-only discovery or inferring knowledge from transcript
text alone.

### Hidden canon mutability

**Chosen:** Maintainer may add and refine missing details but may not contradict an
existing canonical fact, even when the player has not discovered it.

**Not chosen:** Retconning generated hidden facts or source-derived hidden facts.
Scenario hook statuses may evolve without rewriting facts.

### Scenario entity model

**Chosen:** Use a shared entity base and a deliberately small built-in set: NPC,
location, faction, quest, item, encounter, and fact. Rulesets may register explicit
typed extensions where needed.

This combines the clarity of fixed types with controlled extensibility. Arbitrary
attribute dictionaries and a single fully generic entity are rejected.

### Creator completeness

**Chosen:** When a Creator creates an entity, it fills the complete validated schema.

Progressive extraction limits which entities are created up front; it does not permit
half-shaped entities. Full schema completion may include new non-conflicting canon.

## Turn pipeline

### Fixed roles

**Chosen:** Every gameplay turn runs:

`Director → Actor → Narrator → Maintainer`

An empty output or empty tool list is still meaningful. Specialized Creators run only
when Maintainer requests growth.

**Not chosen:** Conditional role routing or a classifier deciding which core roles to
skip. The fixed sequence prioritizes predictability over saving calls.

### Director output

**Chosen:** Concise natural-language instructions inside a minimal typed envelope.

**Not chosen:** A detailed structured screenplay or a schema separating every goal,
check, revelation, branch, and constraint. The Director remains bounded by its role,
not by a large output model.

### Ambiguity

**Chosen:** Director selects the most reasonable interpretation of player input.

**Not chosen:** Asking clarifying questions whenever several readings exist or only
when consequences differ materially. This favors uninterrupted play.

### Actor loop

**Chosen:** Actor uses a bounded PydanticAI tool-call loop and then produces a concise
compiled report. Later tool calls may depend on earlier results.

**Not chosen:** Planning all calls before execution or allowing only one tool call.

### Narrator output

**Chosen:** Narrator produces prose only. It may freely introduce people, places, and
other durable details.

The Narrator must not emit structured growth candidates. Requiring it to write prose
and machine bookkeeping would complicate the creative role and couple it to scenario
schemas.

### Maintainer growth detection

**Chosen:** Maintainer reads the Narrator prose, detects durable additions, and uses
typed growth tools such as `create_npc`, `create_location`, or `add_fact`.

Typed tool calls are the mutation boundary. A separate custom JSON maintenance plan
or prose passed onward to Creators is unnecessary.

### Maintainer scope

**Chosen:** Maintainer persists growth, refines underdeveloped canon, and updates
scenario hooks affected by the turn.

**Boundary:** It does not simulate the full off-screen world every turn and cannot
perform ruleset/game-state mutations owned by Actor.

### Canon validation and retry

**Chosen:** Maintainer accepts narration or rejects it with a short contradiction
reason. A rejection reruns Narrator once against the unchanged Director and Actor
results. A second rejection fails the entire turn.

**Not chosen:** Letting contradictions pass for later repair or silently changing
canon to make the prose true.

### Creator organization

**Chosen:** Specialized NPC, location, faction, quest, item, encounter, and fact
Creators share one typed implementation interface but use narrow prompts and schemas.

**Not chosen:** One generic Creator or making Maintainer produce complete entities.

### Display timing

**Chosen:** Do not display Narrator prose until Maintainer, required Creators, final
validation, and persistence have succeeded.

**Why:** The player must never see an entity or fact that failed to become canon.
Narration is therefore not streamed early; the UI shows role progress instead.

### Transactionality

**Chosen:** Actor changes, random progress, scenario growth, narration, and the turn
record commit atomically. Any exhausted retry or technical error restores the entire
pre-turn state.

Fictional failure is a valid committed outcome. Invalid model data, illegal tools,
broken invariants, and persistence errors are transaction failures.

## Context and retrieval

### Deterministic views plus semantic retrieval

**Chosen:** Python deterministically includes the current location, referenced
entities, active hooks, knowledge, and recent turns. Semantic retrieval supplements
that core with relevant book passages and older events.

**Not chosen:** Passing everything to every role or relying entirely on opaque
semantic retrieval.

### Role-specific disclosure

**Chosen:** Director sees the richest private/source context. Actor receives only
mechanically relevant state and tools. Narrator receives a disclosure-safe program
and visible context. Maintainer sees private canon and source context relevant to the
prose. Creator sees only the material needed for its requested entity.

This is the primary secret-leak prevention mechanism.

### Long history

**Chosen:** Persist every turn, pass recent turns deterministically, and retrieve
older events semantically.

**Not chosen:** Sending the complete transcript or depending on a lossy rolling summary.

### Embedding implementation

**Chosen:** Define an embedding interface that supports local or remote providers and
ship one small local default. The local index is derived and rebuildable.

Changing the embedding model requires rebuilding the index, not migrating canon.

## Campaign setup and persistence

### Campaign origins

**Chosen:** Support prepared scenario packages and source-derived scenarios.

### Progressive source extraction

**Chosen:** Land between exhaustive and minimal extraction. Index the entire source,
then build a comprehensive campaign skeleton and detailed starting region: major
entities, factions, relationships, chronology, story structure, active threads, and
entry point. Materialize secondary detail later through retrieval.

**Not chosen:** Converting every book detail before play or deferring all structure
until the corresponding fact appears in narration.

### Source formats

**Chosen:** Text, Markdown, and text-based PDF.

**Deferred:** EPUB, office formats, scanned PDFs, images, and OCR. Users may preprocess
these externally.

### Setup confirmation

**Chosen:** After schema validation, show a concise campaign summary and starting
configuration for user confirmation.

**Not chosen:** Starting immediately or requiring manual JSON inspection and editing.

### Character creation

**Chosen:** Ruleset-provided typed forms for mechanics plus an optional conversational
step for concept and background.

### Storage form

**Chosen:** A portable campaign directory containing JSON snapshots, JSONL turn
records, copied sources, a rebuildable index, and assets.

**Not chosen:** One giant JSON file or SQLite. Files are the primary debugging surface.
Cross-file commits therefore use staged writes and one atomic head marker for recovery.

### Snapshot plus turn records

**Chosen:** Load directly from current validated snapshots and retain append-only
records explaining each turn.

**Not chosen:** Snapshot-only persistence or pure event sourcing. This gives trivial
loading without requiring replay for normal operation.

### Trace depth

**Chosen:** Store all role inputs and outputs, tool calls and results, retrieved source
IDs, random events, and state changes for every turn.

**Not chosen:** A compact final-output-only record or campaign-configurable trace depth.

### Undo

**Chosen:** Undo the last committed turn, restoring game state, scenario state, and
random state together. Preserve the original trace.

**Deferred:** Arbitrary rollback, save branches, and alternate timelines.

### Version compatibility

**Chosen:** Pin app schema, ruleset, and ruleset schema versions. Fail clearly on load
unless an explicit migration exists.

**Not chosen:** Permissive field filling or a promise to migrate every version forever.

## Models and services

### Language model configuration

**Chosen:** One configured language model and endpoint for all textual roles.

**Why:** Role separation comes from prompts, tools, and context, not from model routing.
The target is a small, fast model, no larger than roughly gpt-oss-120b.

**Not chosen:** Per-role overrides or mandatory independent role configuration.
Embedding and image providers remain separate modality-specific interfaces.

### PydanticAI

**Chosen:** Use PydanticAI for role agents, typed dependencies and outputs, bounded tool
loops, tool schemas, usage limits, and the embedding abstraction.

Plain async Python orchestrates the fixed pipeline. A workflow graph would add little
value to a fixed serial sequence.

### Images

**Chosen:** Text plus generated player-character, NPC, and location images are in the
first release. Images are generated on demand from canonical visual descriptions and
stored as derivative, non-canonical assets.

**Not chosen:** Synchronous image generation during entity creation or background
generation after every commit. Image failure never invalidates a gameplay turn.

## User interface and deployment

### NiceGUI scope

**Chosen:** NiceGUI chat plus character sheet, inventory, journal, and known-world
panels. Generic panels render from Pydantic/JSON schemas.

**Not chosen:** Chat-only UI, a permanent pipeline inspector, or mandatory custom
ruleset components. Campaign JSON and JSONL provide debugging detail.

### Entity references

**Chosen:** Natural language remains valid. Optional `@name` mentions use autocomplete
over discovered entities and resolve to stable IDs.

**Not chosen:** Requiring entity selection for every interaction.

### Multiple campaigns

**Chosen:** A create/open screen manages multiple campaign directories. Only one
campaign is open and one turn runs at a time.

### Deployment

**Chosen:** Local single-user NiceGUI app on localhost.

**Deferred:** Trusted-network operation, authentication, user isolation, and public
hosting.

### Narrative preferences

**Chosen:** A small validated campaign model controls tone, perspective, verbosity,
themes, and content boundaries.

**Not chosen:** One fixed fantasy style or free-form style instructions every turn.

## Engineering standards

### Functional core

**Chosen:** Pure resolvers take validated state, command, and random input and return
new state plus events. Side effects remain in thin adapters around models, files,
randomness, retrieval, and media.

### Validation

**Chosen:** Strict Pydantic v2 models, forbidden extra fields, explicit unions, and
frozen values where useful. State and scenario are validated at load, tool boundaries,
Creator output, and commit.

### Type checker

**Chosen:** `basedpyright` in strict mode.

**Not chosen:** `mypy --strict` or running two type checkers. One strict checker keeps
the feedback loop fast and configuration singular.

### Code quality

**Chosen:** Full Python backend/frontend, `uv`, Ruff, basedpyright, and pytest. Keep
functions below 100 lines and files below 500. Comments explain only why; docstrings
are as short as possible.

### Test scope

**Chosen:** Minimal tests around pure mechanics, invariants, authorization, transaction
rollback/commit, retry, undo, persistence, context secrecy, authority precedence, and
one fake-model pipeline. Do not assert exact creative prose.

## Explicit trade-offs

- Four serial text-role calls increase latency but make small-model responsibility
  failures easier to isolate.
- Maintainer, not Narrator, detects growth. This keeps Narrator simple but makes
  Maintainer quality critical.
- Holding narration until commit prevents streaming but protects canon integrity.
- Complete entity creation spends more tokens up front but prevents partial schemas.
- File persistence is transparent and portable but requires careful atomic commits.
- Semantic retrieval can miss relevant passages; deterministic role views remain the
  dependable context floor.
- Director resolves ambiguity, which keeps play moving but can occasionally choose a
  different interpretation than the player intended.
- Full local traces consume disk space but make model behavior and mutations auditable.

## Documentation split

**Chosen:** Keep `CONCEPT.md` below 500 lines as the implementation-facing brief and
retain this unrestricted decision record so rejected alternatives and rationale are
not lost.

## Adversarial review amendments

Three independent reviews challenged the concept from architecture, implementation,
and gameplay perspectives. They agreed that the libraries and role-based direction are
viable, but that several promised invariants were impossible with the original domain
and mutation boundaries. The following amendments are authoritative.

### Review outcome

The review identified these blocking failure classes:

1. Mutable NPC and world reality had no unambiguous owner.
2. Narrator could create player-visible knowledge or mechanical effects after Actor,
   with no legal way to commit them.
3. Secret safety relied on a small model redacting its own private instructions.
4. Schema-valid Actor tools could apply consequences not caused by prior outcomes, and
   stateful tool calls could run concurrently.

High-risk findings covered incomplete source retrieval, false precision from complete
entities, cross-file atomicity, undo-memory leakage, runtime plugin typing, Maintainer
overload, unbounded Creator fan-out, lossy handoff of player intent, provider capability
variance, setup complexity, and insufficient behavioral evaluation.

### Regression review outcome

The same reviewers challenged the amended design again. They found remaining paths for:

- Prose contradicting typed state at equal authority.
- Secret leakage through “safe” Director or Actor prose.
- Split ownership of existing knowledge and hook progress.
- New operational canon being accepted without a typed record.
- Creator invention after semantic validation.
- Hidden setup extraction becoming binding without real verification.
- Model-classified correction bypassing mutation authority.
- Cancellation racing an already committed `HEAD` advance.
- New disclosures failing to reach player or existing-NPC knowledge.
- Removing private Director prose also removing safe narrative direction.

The amendments below close these paths with explicit precedence, typed public
directives, field-level ownership, bidirectional event fidelity, constrained Creators,
provisional extraction, confirmed corrections, and a shielded commit boundary. A final
targeted pass by all three reviewers reported no remaining Blocker or High finding.

### Authoritative state and entity ownership

**Supersedes:** The earlier separation that placed canonical entities and relationships
in `Scenario` without defining their mutable runtime representation.

**Amended decision:** Split every materialized world entity into:

- `ScenarioEntity`: identity, description, backstory, secrets, source provenance,
  authored relationships, and hook templates.
- `EntityState`: mutable position, life/status, disposition, ownership, conditions,
  and other played-world values, stored in `GameState` under the same stable entity ID.
- Ruleset payload: mechanical values owned and validated by the selected ruleset.

Active hook status, encounter state, inventory references, and player knowledge are
also current reality and belong to `GameState`. Scenario keeps hook definitions and
future possibilities. Every mutable field must have exactly one owner.

Actor/core reducers own changes to existing `EntityState`, existing `Knowledge`, and
runtime hook progress. Hook progress is a pure reduction of typed events. Maintainer
owns requests for new scenario definitions, facts, claims, and disclosures. A
system-owned `GrowthCommit` may atomically create those definitions, initialize a new
entity, and emit `KnowledgeAcquired` through the idempotent knowledge reducer for every
newly created turn-visible disclosure. Recipient IDs must be resolved speakers or
addressees from the prompt and public Director targets, so this covers both player and
existing-NPC knowledge without general Maintainer mutation authority. Acquisition of a
pre-existing disclosure uses a typed Actor event and the same reducer. Maintainer and
Creator never write snapshots directly.

### Committed narration and post-narration effects

**Supersedes:** The absolute claim that structured Maintainer extraction can guarantee
that every narrated fact was materialized, and the claim that Actor is the only path
for every game-state change without an initialization/disclosure exception.

**Amended decision:** Accepted, displayed narration is canonical historical evidence of
what the player was told. It does not override typed current or mechanical truth.

Maintainer may request new typed entities, facts, claims, and disclosures. Python
applies approved definitions and new-entity initialization through `GrowthCommit`.
Maintainer cannot grant items, move entities, deal damage, change conditions, update
existing knowledge, advance hooks, or assert other current-state consequences.
Narration containing any such effect without a matching Actor event is rejected.

Within committed play, resulting typed state outranks typed events, which outrank
accepted narration. Acceptance of a new named entity, disclosure, relationship, or
state-bearing fact requires matching typed growth or events. Non-operational color may
remain solely as historical prose. An undetected mismatch is an auditable trace defect;
later turns follow typed reality without rewriting displayed history.

Event fidelity is bidirectional for player-visible outcomes: prose consequences require
matching events, and every player-visible event or disclosure outcome must appear in
accepted narration.

### Disclosure safety

**Supersedes:** Treating a free-form Director program as disclosure-safe by prompt
instruction alone.

**Amended decision:** The Director envelope remains small but includes typed turn kind,
resolved target IDs, and permitted `DisclosureId` values. Python validates those IDs.
Narrator receives only stored player-safe disclosure wording and public target values,
never the linked private fact payload.

Free-form Director instructions remain private to Actor and Maintainer, and Actor prose
never reaches Narrator. Director also returns a typed public `NarrativeDirective` with
visible speaker/target IDs and enums such as stance, speech act, and response goal. It
contains no free-form prose. Python constructs Narrator guidance deterministically from
that directive, the original prompt, turn kind, public targets, permitted disclosures,
visible typed events/state, and preferences. Actor events have explicit visibility.
Maintainer rejects directive deviation or unauthorized disclosure even when the latter
is canonically true.
Retrieval corpora and chunks carry visibility/role ACLs; private role traces are never
retrieved into Narrator context.

### Actor causality and PydanticAI tools

**Supersedes:** Assuming that typed low-level tools and final invariants alone authorize
mechanical consequences.

**Amended decision:** Prefer intent-level ruleset tools whose pure resolver owns the
entire causal transition, such as `search`, `attack`, or `give_item`. The resolver
performs rolls and applies only consequences allowed by the result.

When low-level dependent tools are unavoidable, prior events issue transaction-local,
single-use capability tokens required by consequential commands. Actor prose reports
are explanatory only; typed events are mechanically authoritative.

All stateful PydanticAI tools execute sequentially. Resolver preconditions and
idempotency still apply because provider retries or duplicate calls remain possible.

### Source authority and reconciliation

**Supersedes:** The combination of globally binding unmaterialized source, incomplete
retrieval, and a ban on reconciling generated hidden canon.

**Amended decision:** Directly authored prepared facts and extracted assertions verified
against an exact cited passage are binding starting canon. Unmaterialized source
passages are authoritative evidence, but probabilistic retrieval cannot guarantee that
every passage constrains every turn.

Ingestion builds a deterministic registry of names, aliases, major entities, and major
claims in addition to semantic chunks. Retrieval combines explicit entity/lexical
lookup with embeddings. Confirmation does not certify hidden model extraction:
undisclosed extracted setup facts remain provisional and correctable. Displayed facts
are historical evidence and are never rewritten. Undisclosed provisional or
live-generated facts may be reconciled when stronger evidence appears, with provenance
and history preserved.

### Truth, claims, hints, and knowledge

**Supersedes:** Representing hidden, hinted, and discovered as visibility states on one
fact payload.

**Amended decision:** Separate:

- `WorldFact`: a private assertion about world truth.
- `Claim`: what an actor says, suspects, or believes; it may be false.
- `Disclosure`: player-facing wording that may reference a fact or claim.
- `Knowledge`: which actor received which disclosure.

A hint never exposes the underlying private fact payload. Authority precedence applies
only to assertions about world truth; knowledge and beliefs are not truth candidates.
Dialogue context is projected from what the speaking NPC knows, believes, or is allowed
to reveal.

### Creator completeness and growth limits

**Supersedes:** Requiring every possible entity field to be invented immediately.

**Amended decision:** A complete entity has every required operational field validated.
Optional or irrelevant facts remain absent or explicitly unknown. A Creator fills only
fields authorized by its typed growth request; it cannot invent extra facts,
relationships, or disclosures. It may reference only existing stable IDs and the entity
under creation and cannot recursively trigger more entity creation. Python validates
the result against the approved request and relevant source evidence before commit.

Every turn has one aggregate budget for wall time, model requests, context/output
tokens, tool calls, retries, and growth requests. A configurable small cap limits new
durable entities per narration. Exceeding the cap causes Narrator retry or turn failure,
not unbounded Creator fan-out.

### Maintainer scope and retry ownership

**Supersedes:** Proactive refinement of underdeveloped canon and hook inference from
creative prose on every turn.

**Amended decision:** Maintainer has three responsibilities:

1. Validate narration against visible Actor events, permitted disclosures, current
   reality, the public directive, scenario canon, and retrieved source evidence.
2. Request new typed definitions, growth, and recipient edges for new disclosures found
   in the prompt or accepted prose.
3. Confirm every operational durable assertion has matching typed events or growth and
   every player-visible event outcome is represented in the narration.

Maintainer cannot acquire a pre-existing disclosure or mutate hook progress. Recipient
edges proposed with a newly created disclosure are validated against resolved turn
participants; `GrowthCommit` emits the knowledge event and the core reducer applies it.
The Actor emits all other knowledge events. Pure core reducers derive hook progress
from typed events.

Director output is deterministically validated before Actor runs. Maintainer classifies
rejection origin. Only a Narrator deviation retries Narrator against unchanged inputs.
An upstream Director or Actor error fails and rolls back the turn rather than asking
Narrator to repair impossible inputs.

Actor and Narrator receive the original player prompt alongside Director guidance so
the pipeline does not discard tone, exact wording, or secondary intent.

The Director envelope includes a small turn kind such as action, dialogue, recap, or
rules question. Meta turns cannot create canon. Correction is a separate explicit UI
action or command that produces a typed patch preview and requires user confirmation;
Director classification alone never grants mutation authority.

### Ambiguity guardrail

**Supersedes:** Always committing the Director's best guess, including destructive
actions with several materially different targets.

**Amended decision:** Continue inferring reasonable intent for reversible or equivalent
interpretations. If an irreversible action has multiple materially different targets,
the fixed pipeline returns a no-op clarification. Resolved destructive targets use
stable IDs in the Director envelope.

### Persistence, undo, and diagnostics

**Supersedes:** Treating independently updated top-level snapshots and appended JSONL
as one atomic commit.

**Amended decision:** Each successful turn is an immutable generation directory that
contains game state, scenario, random state, parent ID, and the complete turn record.
After all files are durable, one atomic `HEAD` pointer selects the generation.

Top-level `state.json`, `scenario.json`, and `turns.jsonl` may exist as readable,
rebuildable views; they are not the commit boundary. Recovery discards unheaded stages
and never guesses that an interrupted stage should commit.

Undo moves `HEAD` to its parent and records the operation outside canonical turn
history. Retrieval follows only the active `HEAD` ancestry, so undone or abandoned
branch events remain auditable but cannot re-enter model context.

Failed attempts are written to a bounded, non-authoritative diagnostic area excluded
from campaign retrieval. This preserves debugging data without canonizing failure.

### Ruleset typing boundary

**Supersedes:** Runtime registration of arbitrary ruleset and scenario types while also
claiming exhaustive compile-time typing in the core.

**Amended decision:** The first release uses a statically registered discriminated
union of bundled rulesets and entity extensions. The reference fantasy ruleset remains
behind the intended interface, but third-party runtime discovery is deferred.

If arbitrary plugins are later required, the core will use an explicit type-erasure
boundary containing strict JSON values; each plugin validates those values into its own
fully typed models internally. The core will not claim exhaustive static typing across
that runtime boundary.

### Provider capability contract

**Amended decision:** “OpenAI-compatible” transport is necessary but not sufficient.
Application startup probes the configured model for the required tool calls and IDs,
structured-output mode, sequential stateful tool behavior, context/output limits, and
provider profile settings. Unsupported configurations fail before campaign play.

Request and tool-call limits are hard application bounds. Token safety also uses
deterministic context budgets and provider output-token limits because post-response
usage checks cannot prevent every over-budget response.

The local embedding index records model ID, dimensions, normalization, chunking
version, and indexed campaign head. First-use model download failure is a setup error,
not campaign corruption.

### Setup workflow

**Amended decision:** Progressive book setup is a separate bounded workflow, not an
implicit feature of ordinary retrieval:

1. Deterministically extract, chunk, and register source identifiers.
2. Produce typed per-chunk candidates with source references.
3. Merge exact identifiers and aliases deterministically.
4. Run a bounded model consolidation for unresolved duplicates and relationships.
5. Validate the scaffold and present an inspectable summary before confirmation.

Confirmation starts play and commits displayed setup facts; it does not certify unseen
model extraction. Undisclosed extracted facts remain provisional and correctable until
authored directly or verified against an exact cited passage. Prepared scenarios are
implemented before automated book setup so the gameplay spine can be validated
independently.

### UI and technical failure behavior

**Amended decision:** Generic UI generation supports a deliberately small documented
subset of Pydantic/JSON Schema. Unsupported schema constructs fail clearly; rulesets do
not imply a general-purpose form framework.

Before persistence, timeout or cancellation discards the draft, releases the campaign
lock, preserves the player's input, and offers a non-spoiler retry. Generation
persistence plus the atomic `HEAD` advance is shielded from cancellation. After `HEAD`
advances, the turn is committed and reconnect/reload displays it. The lock is always
released. Private provider errors remain in the diagnostic trace.

### Verification amendments

The minimal integrity suite also covers:

- Fault injection around generation creation and `HEAD` replacement.
- Corrupt or unheaded generation recovery.
- Batched stateful tool calls and sequential execution.
- Duplicate/retried tool effects and causal authorization.
- Growth plus runtime and knowledge initialization.
- Bidirectional fidelity between visible events, narration, and knowledge.
- Retrieval ACLs and active-lineage filtering.
- Wrong ruleset package or adapter schema.
- Cancellation before persistence, during the shielded commit, and after `HEAD` moves.
- Correction attempts without an explicit confirmed typed patch.
- Creator output beyond its approved growth request.

A small opt-in model evaluation set asserts semantic outcomes—chosen tools, permitted
disclosures, growth detection, contradiction rejection, and source adherence—without
asserting exact prose. Fake-model tests remain the deterministic CI foundation.

### Revised implementation order

The implementation proceeds as a vertical gameplay spine:

1. One statically registered reference ruleset and one prepared scenario fixture.
2. Explicit runtime entity state, knowledge/disclosure models, and atomic intent tools.
3. The fixed four-role pipeline with one NPC growth path and fake-model tests.
4. Immutable-generation persistence, active lineage, diagnostics, and undo.
5. Minimal NiceGUI chat and state panels.
6. Retrieval over already-ingested source chunks.
7. Automated progressive book setup.
8. Multiple campaigns and on-demand images.

### Decisions preserved

The review does not change these central choices:

- Full Python backend and frontend.
- Ruleset-agnostic core proven by a small original fantasy ruleset.
- Fixed Director → Actor → Narrator → Maintainer pipeline.
- Narrator prose-only output; Maintainer detects growth from prose.
- Typed mutation boundaries and deterministic mechanics.
- One language model and endpoint for all textual roles.
- Transactional display-after-commit behavior.
- Deterministic context supplemented by semantic retrieval.
- Local JSON-based, inspectable campaign storage.
- NiceGUI, Pydantic v2, PydanticAI, basedpyright, Ruff, pytest, and `uv`.

### Required adversarial use cases

The concept and evaluation corpus must cover:

- NPC reveals a fact and gives or offers an item.
- NPC movement, death, escape, resurrection, and changed allegiance.
- Narrator contradicts a failed Actor outcome without contradicting prior canon.
- Director attempts to leak a hidden fact through a negative instruction.
- Actor submits dependent tools in one model response.
- Source entity appears after a generated near-duplicate has committed.
- Hint wording does not expose its private fact payload.
- NPC lies, changes belief, makes a promise, or learns a secret.
- Undo excludes the undone turn from semantic history.
- Narrator introduces more named entities than the growth budget permits.
- Provider timeout or cancellation after draft randomness was consumed.
- Ambiguous irreversible target produces a no-op clarification.
- Recap, rules question, and out-of-character correction.
- Creator returns schema-valid but source-inconsistent hidden fields.
- Setup extraction merges or splits major source entities incorrectly.

### Residual model risks

Even after these amendments, semantic retrieval can miss relevant passages, small
models can choose poor but legal actions, Maintainer can miss prose implications, setup
cannot perfectly recover a large book, and long-term coherence cannot be guaranteed.
The design must bound, audit, and recover from these failures rather than claim to make
them deterministic.
