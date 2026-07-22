# AI Dungeon Master — Implementation Planning

## Purpose and authority

This document turns the agreed concept into an executable sequence. [`CONCEPT.md`](CONCEPT.md)
and [`CONCEPT_DECISIONS.md`](CONCEPT_DECISIONS.md) remain authoritative when this plan is ambiguous.

Phases are ordered by dependency and risk and must leave a tested increment. If an
agreed boundary must change, update both source-of-truth documents before this plan.

## Delivery rules

- Build the prepared-scenario gameplay spine before source-driven setup or breadth.
- Add abstractions and dependencies only with their first implementation and consumer.
- Keep transformations pure and side effects behind narrow typed boundaries.
- Keep deterministic tests offline; real-model evaluations are opt-in.
- Treat persisted campaign formats as versioned public contracts from Phase 4 onward.
- Finish each phase's integrity and failure-path tests before starting the next phase.
- Keep concept, planning, and user setup documentation current as behavior lands.

## Phase 0 — Engineering baseline

### Outcome

A reproducible Python project whose empty application passes its complete quality gate.

### Work

1. Create `pyproject.toml`, the `src/ai_dnd` package, and the test directories.
2. Configure `uv`, Ruff formatting and linting, strict basedpyright, and pytest.
3. Set the supported Python version and centralize package/app version metadata.
4. Add the smallest application entry point and validated settings loader needed for a
   smoke test. Do not add model, UI, PDF, embedding, or image dependencies yet.
5. Document the standard install, check, and test commands in the repository README.
6. Establish test helpers for strict Pydantic models and immutable-value assertions.

### Verification

- Package import and settings smoke tests.
- Invalid and unknown configuration fields fail with actionable errors.
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run basedpyright`
- `uv run pytest`

### Exit gate

A fresh checkout can create its environment and pass every configured check using only
the documented commands.

## Phase 1 — Typed domain, reference ruleset, and prepared scenario

### Outcome

The application can load one typed prepared campaign with the bundled fantasy ruleset, without a model call.

### Work

1. Define strict, frozen where practical, JSON-serializable identifiers and version
   models. Give scenario entities, runtime entities, facts, claims, disclosures, hooks,
   events, and turns stable typed IDs rather than interchangeable strings.
2. Define the ruleset-neutral `Campaign`, `GameState`, `Scenario`, `EntityState`,
   `Knowledge`, and initial turn/random-state models. Forbid extra fields at every
   authoritative boundary.
3. Model NPC, location, faction, quest, item, encounter, and fact definitions as a
   statically registered discriminated union. Keep mutable played-world values out of
   scenario definitions.
4. Define the ruleset contract for character models, ruleset state, commands, events,
   invariant validation, character-creation schema, and prompt guidance.
5. Implement the original reference fantasy ruleset's data models and enough catalogs
   for attributes, checks, combat, inventory, and conditions. Mechanical transitions
   are deferred to Phase 2.
6. Create a small prepared scenario fixture containing at least two locations, two
   NPCs, an item, a hook, a private fact, a false claim, a hint disclosure, and a
   starting encounter. Materialized entities share IDs between `Scenario` and
   `GameState`.
7. Add cross-model validation for references, entity/state pairing, disclosure
   targets, ruleset/version pins, and required operational fields.

### Verification

- Prepared fixture validates and round-trips through canonical JSON.
- Unknown fields, duplicate IDs, dangling references, incompatible ruleset payloads,
  and wrong schema versions are rejected.
- Private facts, claims, disclosures, and actor knowledge remain distinct after
  serialization.
- The ruleset-neutral core contains no fantasy mechanics imports.

### Exit gate

A command or test loads the prepared fixture, validates every cross-reference and
ruleset invariant, and prints a public summary without exposing its private facts.

## Phase 2 — Deterministic mechanics and state transitions

### Outcome

Pure intent resolvers play essential mechanics and return a validated draft plus typed events.

### Work

1. Define discriminated command and event unions with explicit visibility and stable
   event IDs.
2. Implement engine-owned random state and recorded draws. Resolvers consume explicit
   random input and never use ambient or module-global randomness.
3. Implement reference-ruleset intent tools and reducers for checks, search,
   movement/escape, item transfer/use, encounters, initiative, attack, damage,
   death/resurrection, conditions, and disposition/allegiance changes.
4. Route pre-existing disclosure acquisition through a typed Actor event and the
   idempotent core knowledge reducer, never through the ruleset.
5. Make each intent resolver own its complete causal transition. Where a dependent
   low-level action is unavoidable, require a transaction-local, single-use capability
   issued by the causal event.
6. Implement the idempotent core hook reducer. Derive hook progress only from typed
   events.
7. Validate preconditions before every transition and validate core plus ruleset
   invariants on the returned value. Never mutate the supplied state.
8. Define the sequential tool-execution service that rejects stale, duplicated, or
   unauthorized effects while allowing safe provider retries to return the original
   result.

### Verification

- Identical starting state, command, and random input produce identical state and
  events.
- Success and failure paths for search, transfer, and attack cannot apply unsupported
  consequences.
- Duplicate tool calls do not duplicate damage, inventory, disclosures, or hook
  progress.
- Movement/escape, death/resurrection, and allegiance changes preserve entity and
  encounter invariants on both success and rejection paths.
- An NPC learns a pre-existing secret only through an authorized Actor event; neither
  a ruleset resolver nor prose can write `Knowledge` directly.
- Dependent calls cannot reuse or bypass capability authorization.
- Batched stateful calls execute in declared sequence.
- A failed transition leaves state and random progress unchanged.
- Hint acquisition never exposes the private fact payload.

### Exit gate

An offline test plays a short deterministic sequence—search, discovery, dialogue, and
combat—through intent commands and asserts the exact typed state transitions and
recorded random events.

## Phase 3 — Complete in-memory gameplay pipeline

### Outcome

One player prompt runs through Director, Actor, Narrator, Maintainer, optional NPC
creation, and an all-or-nothing in-memory commit using scripted fake models.

### Work

1. Add PydanticAI and define typed dependencies, outputs, tool limits, and a narrow
   text-model/provider boundary. Supply a scripted fake implementation for tests.
2. Implement deterministic role context builders. Start with the current location,
   mentioned/resolved entities, active hooks, actor knowledge, recent history, and an
   empty retrieval adapter.
3. Implement and validate the Director envelope: turn kind, resolved targets,
   permitted disclosure IDs, private instructions, and prose-free public narrative
   directive. Resolve irreversible ambiguity to a no-op clarification.
4. Implement the Actor tool loop over Phase 2 resolvers. Execute stateful calls
   sequentially, preserve the original prompt, and treat the final prose report as
   private and non-authoritative.
5. Build Narrator input from public data only: the original prompt, narrative
   directive, safe disclosure wording, visible events/state, and preferences. Narrator
   returns prose only.
6. Validate directive adherence, disclosures, current state, prepared scenario canon,
   and bidirectional narration/event fidelity. Every operational durable assertion
   needs typed events or supported growth; reject unsupported growth before display.
7. Define the exhaustive typed growth-request union and shared constrained Creator
   interface, then implement one NPC Creator and `GrowthCommit` as the vertical slice.
   Validate Creator output against the exact approved fields, existing IDs, and
   prepared canon; forbid recursive growth and unknown references.
8. Restrict new-disclosure recipients to prompt-resolved speakers/addressees and public
   Director targets; use the same idempotent knowledge reducer as Actor events.
9. Add immutable `TurnDraft` values, aggregate wall-time/request/context/output/tool/
   retry/growth limits, failure classification, and rollback. Give each narration
   attempt a fresh maintenance sub-draft and discard rejected growth/recipients. Meta
   turns cannot grow canon; upstream failures cannot trigger Narrator repair.
10. Record the complete proposed `TurnRecord`: all role inputs/outputs, tool calls and
   results, retrieved IDs, random events, state changes, retry reason, and parent ID.
11. Implement the real-provider startup capability probe before enabling live play.

### Verification

- Scripted action, dialogue, recap, and rules-question turns invoke all four roles.
- The Narrator cannot receive private facts, private Director prose, Actor prose, or
  private events.
- Invalid Director IDs fail before Actor runs.
- Unsupported narrated mechanics are rejected; omitted visible outcomes are also
  rejected.
- Narration contradicting a prepared relationship, private fact, or other scenario
  canon is rejected even when no mechanical event is involved.
- Narrator deviation retries once against unchanged upstream results; a second failure
  rolls back the entire draft.
- Growth and recipient proposals from rejected narration cannot survive into its
  retry.
- An introduced NPC is either fully created with runtime/knowledge initialization or
  absent after failure.
- Creator fields outside the approved request, recursive references, unknown IDs, and
  disclosure recipients outside the participant allowlist are rejected.
- Until the remaining Creator variants land, narration requiring any other growth
  variant fails clearly rather than committing prose-only operational canon.
- Growth beyond the configured cap cannot fan out recursively.
- The original prompt reaches Actor and Narrator unchanged.

### Exit gate

One fake-model integration test exercises a successful mechanical turn, one NPC-growth
turn, one Narrator retry, and one total rollback without modifying its input campaign.

## Phase 4 — Immutable persistence, recovery, lineage, and undo

### Outcome

Play survives restarts and failures without partial state or leakage from an undone turn.

### Work

1. Define the portable campaign directory and strict app/core/ruleset/source pins. Keep
   provider credentials and runtime settings external; persist only required non-secret
   compatibility identifiers in derived-index metadata or traces.
2. Implement initial-generation creation as a staged, fully validated operation. A
   prepared campaign is not selectable until its durable `HEAD` exists.
3. Implement strict loading of the initial generation and current `HEAD`. Validate all
   snapshots and cross-references before exposing a campaign to the application.
4. Persist each successful turn to an immutable generation containing `state.json`,
   `scenario.json`, `random.json`, and `turn.json`, with the parent generation ID.
5. Stage and durably write every generation file before atomically replacing `HEAD`.
   Keep staging on the same filesystem as the campaign directory.
6. Shield persistence plus `HEAD` replacement. Cancellation before commit discards the
   draft; after commit starts, retain the lock, await the inner commit, reload `HEAD`,
   then release the lock and propagate cancellation.
7. Add the single-open-campaign/single-active-turn lock and guarantee its release on
   success, validation failure, provider failure, timeout, and cancellation.
8. Implement recovery that removes or quarantines unheaded stages, validates headed
   generations, and fails clearly rather than guessing when committed data is corrupt.
9. Implement active-ancestry traversal and one-turn undo by atomically moving `HEAD`
   to its parent. Preserve abandoned generations and audit the undo outside canonical
   turn history.
10. Define an allowed-field core correction command and digest-bound preview for the
    active `HEAD`. Confirmation rejects stale previews, revalidates every invariant,
    and commits an immutable, audited, undoable generation outside gameplay history.
11. Store failed attempts in a bounded, non-authoritative diagnostic area that is never
   available to role contexts or retrieval.
12. Make top-level readable snapshots or JSONL logs derived, rebuildable views only if
    a concrete debugging/UI consumer needs them.

### Verification

- Fault injection before, between, and after generation file writes never exposes a
  partial commit.
- Fault injection around `HEAD` replacement resolves to exactly the old or new
  generation.
- Corrupt headed data and incompatible versions fail fast; unheaded stages never
  become canon.
- Cancellation before persistence rolls back random state and preserves the prompt for
  retry; cancellation during/after the shielded boundary reloads the committed turn.
- A competing turn cannot acquire the campaign lock while a cancellation-shielded
  commit is still running.
- Undo restores game, scenario, and random state together.
- Invalid, stale, or unconfirmed correction previews create no generation. A confirmed
  correction survives reload, is auditable and undoable, and remains atomic under
  fault injection.
- Active ancestry excludes undone branches and failed diagnostics.
- All persistence tests use temporary directories and require no network.

### Exit gate

An integration test commits several turns, restarts the application, undoes one turn,
restarts again, and proves that state, narration, random progress, and active lineage
all match the selected `HEAD`.

## Phase 5 — Minimal playable NiceGUI application

### Outcome

A local user can open the prepared campaign, play complete committed turns, inspect
public state, retry technical failures, and undo the last turn from a browser.

### Work

1. Add NiceGUI behind a presentation layer that consumes validated application models
   and invokes orchestration services; keep UI objects out of snapshots and core code.
2. Implement a minimal prepared-campaign flow and reference-ruleset character form.
   Validate the completed character and starting state, then use Phase 4's staged
   initial-generation service; failed creation must leave no selectable campaign.
3. Implement chat input, role progress, preserved failed input, non-spoiler errors, and
   post-commit narration display. Disable input while the turn lock is held.
4. Add read-only character, inventory, journal, and known-world panels projected only
   from player-visible state.
5. Add optional `@entity` autocomplete over discovered entities and submit stable IDs
   as hints without making mentions mandatory.
6. Add undo with confirmation and immediate panel/history refresh.
7. Expose Phase 4's correction service: show its typed patch preview, require explicit
   confirmation, and never construct or write authoritative patched snapshots in UI
   code.
8. Implement and document the supported subset of Pydantic/JSON Schema for generated
   forms and panels. Fail clearly on unsupported schema constructs.

### Verification

- Pure presenter/view-model tests cover visibility filtering, form conversion, entity
  mentions, progress states, and error mapping.
- A UI smoke test covers load, prompt submission, committed response, retryable
  failure, undo, and reload.
- Private facts and private traces never appear in rendered or serialized UI state.
- Failed character creation leaves no openable campaign. Unconfirmed, stale, or
  invalid corrections cannot mutate authoritative state; confirmed corrections go
  only through the core persistence service.

### Exit gate

An offline manual walkthrough can create the reference character, play the prepared
scenario through exploration/dialogue/combat, inspect all public panels, undo a turn,
and recover cleanly from a scripted provider failure.

## Phase 6 — Source ingestion and role-safe retrieval

### Outcome

Supported sources supplement deterministic role contexts without becoming state or leaking private material.

### Work

1. Bound source count/bytes/pages/text/chunks, disk, wall time, and embedding requests
   before metadata commit; clearly reject scanned/image-only PDFs.
2. Implement source copying, hashing, format validation, text extraction, and stable
   source references. Split content on document structure with per-chunk and aggregate
   token limits, and version the chunking algorithm.
3. Deterministically register names, aliases, major entities, and major claims with
   exact source references.
4. Provide the embedding interface, small local default, remote adapter, and fake.
   Bound batches, concurrency, total requests, dimensions, retries, and time.
5. Build a rebuildable campaign-local lexical/semantic index containing model ID,
   dimensions, normalization, chunking version, visibility ACL, and indexed campaign
   head.
6. Combine direct ID/name/alias/lexical lookup with semantic ranking under explicit
   result and context-token limits.
7. Index committed active-lineage events and exclude undone branches, diagnostics, and
   private role traces.
8. Feed role-filtered evidence into Director/Maintainer contexts and approved Creator
   requests. Treat it as quoted untrusted data and require exact evidence for claims of
   source authority.
9. Add typed reconciliation when stronger exact evidence conflicts with undisclosed
   provisional/generated facts. Preserve provenance/history, merge near-duplicates
   deterministically where possible, and reconcile displayed facts only forward.
10. Under the mutation lock, durably stage and validate an immutable source bundle,
    then atomically replace the campaign source manifest; ignore orphan stages. Update the derived index
    afterward and detect a stale indexed manifest/`HEAD` before every query.
11. Rebuild rather than migrate the index when embedding or chunking configuration is
   incompatible.

### Verification

- Stable input produces stable chunks, registries, references, and lexical results.
- Visibility/role ACL tests prove private chunks cannot enter Narrator context.
- Source-canon contradictions are rejected by Maintainer, and schema-valid Creator
  fields inconsistent with cited evidence are rejected.
- Retrieval follows active ancestry after undo.
- Stronger source evidence can supersede an undisclosed generated near-duplicate with
  provenance retained, while displayed history is left intact.
- Index metadata mismatches trigger rebuild or a clear setup error, never silent reuse.
- Malformed PDFs and first-use local-model failures do not corrupt campaign state.
- Resource limits fail without manifest changes; cancellation/fault injection exposes
  exactly the old or new complete source bundle.
- Pipeline tests demonstrate deterministic context still works with zero retrieval
  hits.

### Exit gate

A prepared campaign imports each supported format, retrieves cited evidence for a
known source entity and an older active turn, and proves that a forbidden passage and
an undone turn cannot reach the Narrator.

## Phase 7 — Progressive source setup

### Outcome

A user can turn supported source documents into an inspectable, validated starting
campaign without requiring exhaustive conversion before play.

### Work

1. Model setup as a separate bounded workflow with explicit draft, review, confirmed,
   failed, and cancelled states. Setup drafts are not playable campaign canon.
2. Reuse Phase 6 extraction, chunks, and registries to produce strict per-chunk entity,
   fact, claim, relationship, chronology, hook, and entry-point candidates with exact
   source references.
3. Merge exact identifiers and deterministic aliases first. Send only unresolved
   duplicate/relationship candidates to bounded model consolidation.
4. Validate a comprehensive scenario skeleton and a detailed starting region against
   all cross-reference and ruleset invariants.
5. Track provenance and distinguish authored or exact-source-verified facts from
   provisional model-extracted assertions.
6. Present an inspectable summary, unresolved warnings, starting configuration, and
   character creation before confirmation.
7. On confirmation, create the initial immutable generation and index. Promote only
   displayed setup facts to confirmed canon; retain any undisclosed assertions needed
   by the scaffold with explicit provisional provenance so they remain reconcilable.
8. Add the optional conversational character concept/background step, validating its
   result through the reference ruleset's typed form.
9. Support cancellation/retry without leaving a partially playable campaign.

### Verification

- Deterministic merge tests cover aliases, homonyms, duplicate candidates, and dangling
  relationships.
- Scripted consolidation tests cover incorrect source entity merges and splits.
- Schema-valid but source-inconsistent generated fields are rejected.
- Confirmation does not silently promote unseen provisional assertions to verified
  canon.
- Setup budgets cap source chunks, model requests, tokens, and consolidation work.
- Failed or cancelled setup leaves no selectable campaign generation.

### Exit gate

Given a small text-based adventure source, the workflow produces a reviewable skeleton
and starting region, accepts a reference-ruleset character, confirms an initial
generation, and successfully plays a cited first turn through the normal pipeline.

## Phase 8 — Multiple campaigns, media, and first-release completion

### Outcome

The local first release manages isolated campaigns and optional images without weakening gameplay integrity.

### Work

1. Complete live location, faction, quest, item, encounter, and fact Creators plus
   narrow claim/promise/disclosure/relationship growth. Exhaustively validate the union
   against each request/source and use `GrowthCommit` for runtime/knowledge setup.
2. Map NPC lies, beliefs, promises, and learned secrets to claims, disclosures, causal
   Actor events, and authorized recipients. State changes require events, never prose.
3. Implement create/open/list flows over explicitly configured campaign roots. Resolve
   and validate exact campaign paths; allow only one open campaign and active turn.
4. Complete campaign preferences for tone, perspective, verbosity, themes, and content
   boundaries, and apply them only to public narrative/image inputs.
5. Complete journal and known-world projections from disclosures, active hooks, and
   active committed history.
6. Define the image-provider interface and on-demand player-character, NPC, and
   location generation from canonical visual descriptions.
7. Store image assets and metadata in a separate derived-assets area, never inside or
   as part of an authoritative generation. Provider failure must leave gameplay state
   and `HEAD` unchanged.
8. Add provider/configuration diagnostics that expose capability failures without
   exposing private prompts or secrets.
9. Finish local packaging, startup, empty-state help, recovery messaging, and
   user-facing source/setup documentation.

### Verification

- Two campaigns with overlapping entity names cannot share state, indexes, assets,
  locks, diagnostics, or provider context.
- Fake-model turns cover every Creator/growth union variant, reject out-of-request
  fields, and verify lies, belief changes, promises, and new NPC knowledge without
  prose-only state mutation.
- Opening corrupt, incompatible, or wrong-ruleset campaigns fails before mutation.
- Image prompts include only permitted canonical visual information.
- Image timeout, malformed output, and storage failure do not invalidate or modify a
  gameplay turn.
- Full offline tests and static checks pass from a clean environment.

### Exit gate

A release walkthrough creates a prepared campaign and a source-derived campaign,
switches between them, plays and undoes turns, restarts safely, rebuilds retrieval,
generates each supported image type, and remains playable when image generation fails.

## First-release acceptance gate

Phase 8 is complete only after all cumulative checks pass and the required adversarial
use cases in `CONCEPT_DECISIONS.md` are represented by deterministic tests or, where
model semantics are essential, the opt-in evaluation set.

The final gate includes:

- all formatting, linting, strict typing, and offline pytest checks;
- fault-injected persistence, recovery, undo, and cancellation tests;
- disclosure ACL, narration/event fidelity, causal authorization, and growth-budget
  tests;
- prepared and source-derived end-to-end fake-model scenarios;
- provider capability checks against each documented live-provider profile;
- an opt-in small-model evaluation report for tool choice, disclosure safety, public
  directive adherence, contradiction rejection, growth detection, and source
  adherence;
- a documentation review confirming that shipped behavior and commands match the
  concept, decisions, planning, and user setup guides.

Known residual model risks are accepted only when they are bounded, visible in traces,
and recoverable as described in the concept. They are not reasons to weaken typed
state, visibility, transaction, or persistence guarantees.
