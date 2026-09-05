# PROPOSALS — engine-owned pacing and one generation handoff

Status: proposals 1 and 2 accepted for planning on 2026-09-05. This document is input
to the next PLAN.md, not an implementation plan or a record of completed changes.
Read it with CLAUDE.md and the current code. The existing PLAN.md and PROGRESS.md
describe the completed campaign-layer removal and generation handoff.

## Goal and scope

Keep engines small and close to their own SRDs. Shared infrastructure must have
as little influence as possible on pacing, progression, and mechanical boundaries.
Share storage, validation, visibility, authoring, and execution where behavior
matches; engines decide when and why to use them.

Preserve the useful experience: the master can offer a way on, the player can stay
or leave, and the master can introduce a complication without making the player
leave. “Settled” becomes an invitation, not a closed state.

Only the following two proposals are in scope:

1. Separate the current situation and its history from engine-owned pacing.
2. Route departures, complications, and map extensions through one generation handoff.

The worldsmith cast-schema split was rejected as not worth its cost. Flattening
change_world into individual tools is excluded. Neither belongs in the resulting plan.

## What remains

- All four engines, both world families, all three AI roles, and separately authored,
  stored, and selected scenarios and characters remain.
- Rules and dice stay in code. Transactional drafts, RNG rollback on refused calls,
  strict boundary validation, and the commit gate remain.
- Narration receives revealed information only. Private authoring briefs and hidden
  facts must never become narrator inputs or player-facing action labels.
- Persistence, history, recaps, cast continuity, media, and existing rule procedures
  remain. Save versioning and migration are not introduced.
- Standing import rules, engine-size limits, tool-count limits, Refusal handling, and
  the single re-prompt for bad model output remain.

## Current implementation and the problem

SceneRun.left currently carries three meanings: None means open, an empty string
means settled here, and a nonempty string records the player's departure intent.
SceneWorld.settle and complicate both require an open run. Consequently, the player
can continue playing after settlement, but the master cannot request an authored
complication afterward.

Every shared SceneDraft requires a question about what the scene settles.
SceneEngine's shared instructions reinforce that structure for Loner, Breathless,
and 24XX. Installing a complication appends another run, while advance must skip
Loner's leaving behavior because the player has not left.

Generation is also reached through different routes. Player movement uses
GameService.play(moving_on=True), Engine.crossing, and Engine.page_word; map growth
uses extend; a master complication uses Game.handoff. page_word compares the input
text with the stored departure text to decide whether the master is skipped.

Relevant code:

| Area | Files |
| --- | --- |
| Situation state and authoring | src/aidm/engines/scenes/{world,drafts,worldsmith,engine,tools}.py; worldsmith.md |
| Engine contract | src/aidm/engines/seam.py |
| Runtime and turn | src/aidm/app/runtime.py; src/aidm/turn/run.py |
| Shared boundary types and presentation | src/aidm/core/{model,play,views}.py; src/aidm/turn/context.py |
| UI actions | src/aidm/ui/game.py |
| Engine-specific behavior | src/aidm/engines/{loner3e,breathless,twentyfourxx,tunnelgoons}/; src/aidm/engines/rooms/ |

## Proposal 1 — situations are shared; pacing belongs to engines

### Separate three meanings

| Concept | Owner | Meaning |
| --- | --- | --- |
| Current situation and history | Engine world; shared scene implementation where useful | Where play stands, who is here, what is known, and what happened |
| Optional offer to move on | Engine | A useful stopping point or an already-resolved route onward |
| Generation request | Engine creates; platform executes | An actual request for authored content |

An offer is not a PendingDecision. It does not suspend play, consume an answer, or
block tools. PendingDecision retains its existing use for genuine rules choices.

Replace the overloaded left field with an explicit optional offer representation.
Keep any already-resolved departure intent distinct from a general invitation to
choose a destination. The plan must choose the smallest typed representation that
makes that distinction; do not encode it with empty strings or prose comparison.

### Required behavior

| Event | Required result |
| --- | --- |
| Master judges a useful stopping point | The engine offers Move on; ordinary play remains available |
| Player continues talking or exploring | Play continues in the current situation |
| Player accepts an already-resolved departure | The engine validates the current action and proceeds without repeating adjudication |
| Player supplies a new destination or attempts an escape | The master adjudicates it; clicking a button does not bypass obstacles |
| Master requests a complication after an offer | The request is allowed; a successfully installed complication clears the obsolete offer |
| Player tries to leave without an offer | Ordinary play may attempt departure; absence of a button is not a universal prohibition on leaving |
| Engine applies recovery or progression | Its own rule procedure decides; a new history record alone triggers nothing |

The accepted behavior is that a new complication clears the old offer until the
master offers a way on again. Planning default: clear it atomically with successful
installation. If generation fails, the unchanged situation keeps its prior offer.
An installed situation whose narration fails has still changed, so its old offer
remains cleared. A successful departure also consumes the offer.

For ordinary continued play, an offer can remain while it is still relevant. Its
availability and any direct-departure authority must be rechecked by the engine when
submitted; an old UI control never grants permission against changed state.

Complications here are master-authored requests. Adding a separate player-facing
“introduce a complication” control is outside this proposal.

### Remove the mandatory dramatic-question lifecycle

A shared authored situation need not have a question that must be settled. A
question may remain optional descriptive focus. The plan should choose whether to
retain that field name or use focus, and update authoring, prompts, views, and
shipped scenarios consistently.

If an existing engine needs a mandatory question, that requirement belongs in its
own schema or validation. Do not add engine-specific schemas speculatively. Empty
focus must render cleanly without an empty “At stake” panel or a prompt requiring
the model to invent a question.

Keep scene/run records for history, recaps, context compression, and presentation.
A complication may still append a record. It is not necessary to introduce an
in-place patch model, rewrite historical records, or rebuild memory management.
The architectural change is that record boundaries have no automatic rules meaning.

### Engine responsibilities

| Engine | Behavior to preserve and ownership to make explicit |
| --- | --- |
| Loner 3e | Its own departure and conflict/recovery behavior; a complication must not refill spent Luck |
| Breathless | Catching breath applies its existing resets and complication guidance; a situation update adds no extra recovery |
| 24XX | Job finding, taking, finishing, advancement, and payment remain engine-owned and independent of scene records |
| Tunnel Goons | Movement follows its authored map; extending the map does not move the player or impose scene settlement |

Keep shared implementation where these engines actually use the same operation.
Their tool selection, tool descriptions, authoring guidance, and mechanical effects
must be engine-owned. Moving an identical state machine into three engines is not
a simplification.

This refactor does not force catch_breath or every twist to invoke the worldsmith.
Existing cast changes and fiction can still express complications. Use generation
when genuinely new authored content is needed, as today.

## Proposal 2 — one generation handoff

### Minimal boundary contract

Replace the current string Game.handoff with one optional typed generation request.
The conceptual minimum is an operation identifier and an authoring brief. Exact
type and method names are the plan's responsibility.

The operation identifier belongs to the engine. Shared core, turn, app, and UI code
must not branch on identifiers such as departure, complication, or extension.
The engine validates allowed operations and their preconditions when requests are
created and restored. Strict typing and validation remain; an unvalidated arbitrary
dictionary or a string containing encoded routing commands is not a substitute.

There is exactly one request. Do not duplicate it in Game and the engine world,
add a queue, or introduce durable workflow state.

The existing advance seam becomes the consumer of this request. The engine authors
and installs on the draft and returns facts with an optional, revealed-only
narration instruction. No narration instruction means the platform does not invent
an arrival. Transcript attribution must also be explicit: player input stays player
input; an arrival or complication is a story entry. Reuse the current presentation
mechanism where possible without teaching the platform operation-specific rules.

### Operation mapping

| Request | Engine performs | Platform performs |
| --- | --- | --- |
| Departure | Validate or adjudicate departure, install destination, apply its departure rules | Execute authoring, commit, narrate the installed result |
| Complication | Install the changed situation, preserve continuity, clear the old offer | Execute authoring, commit, narrate the installed result |
| Map extension | Attach new map content without moving the player | Execute authoring and commit; expose only the facts the engine allows |

Do not infer an extension from crossing returning None. Absence of narration is a
presentation instruction, not a signal to choose a different gameplay operation.

### One execution sequence

1. An engine tool or validated engine-provided UI action creates the request.
   A request created during a master turn stops later tool mutations.
2. Finish and commit any actual played turn, narrating only what already landed.
   The uninstalled request is not evidence that its proposed fiction happened.
3. Invoke the engine's author-and-install operation on a fresh transactional draft
   through the existing worldsmith capability.
4. Commit the installed result and clear the request, with its narration/history
   handled under the existing rule that failed arrival narration does not undo an
   installed world. Apply departure effects only on the successful install draft.
5. On expected generation failure, discard the candidate, clear the request on a
   fresh draft, and file the failure without losing an already-committed turn.

An existing map-extension action can still start generation without a master turn.
Do not manufacture a player turn, consume pending rules choices or master notes, or
spawn a master solely to fit the common executor.

Normal turn narration retains its current failure behavior. Only arrival/update
narration gets the existing nonfatal treatment. Refusals and supported external
failures follow existing handling; unexpected bugs must not be swallowed.

### UI actions and master skipping

Replace the universal Move on control and its moving_on boolean routing with an
optional engine-provided action description: identifier, label, and any input hint
or already-approved intent needed by the existing UI.

The UI submits the identifier and player input. The engine resolves the action
against current state; the browser does not supply trusted resolver arguments.
The common page renders the control without knowing what an engine considers
settled or what map growth means.

Preserve the current optimization for an already-resolved departure. Identify that
case through an explicit action and engine validation, never by comparing input
text with stored prose. New intent still requires master adjudication and only
creates a departure request when that adjudication permits it.

A nonblocking offer and a blocking rules choice remain different concepts.
Pending decisions retain precedence. A stale action or an action that conflicts
with the current rules decision is refused without changing state or dice.

### Failures, reloads, and continuity

| Case | Required outcome |
| --- | --- |
| Generation request created during a turn | Later tool calls wait; at most one request is executed after the turn |
| Worldsmith output fails its schema or install validation | Existing one re-prompt remains; after failure, discard all candidate changes |
| Generation ultimately fails | Prior committed turn and situation remain; request clears; failure is recorded |
| Arrival narration fails after valid installation | Installed state commits without fabricated narration; request clears |
| Reload finds a request | Clear it under the existing lost-write policy; do not auto-resume or add retry UI |
| Game is over before generation | No generation runs; no actionable request survives recovery/reload |
| Complication installs at the same place | Keep appropriate cast and party continuity; no departure-only mechanical effects |
| Hidden map extension succeeds | Player stays put; hidden content is not narrated or exposed through labels |

A failed complication must not erase the offer for the situation that still exists.
Recaps written for a complication describe the prior situation; they must not claim
that the player departed. Existing identity, sheet-protection, and visibility
validation remain in force.

## Planning handoff

### Replacement and deletion map

| Existing code or behavior | Planned replacement |
| --- | --- |
| SceneRun.left overload and shared open/settled refusal | Optional engine-owned offer with explicit departure authority where needed |
| Mandatory shared question and settlement instructions | Optional descriptive focus; engine-owned requirements and pacing guidance |
| Game.handoff string | Single typed engine-issued generation request |
| moving_on, crossing, page_word, separate extension routing | Validated engine actions and one generation executor |
| UI calling engine.ready to interpret a universal transition | Optional action in the engine's player-facing view |
| Recovery tied to shared scene closure | Engine-specific effects on the appropriate successful operation |

Some methods may survive with narrower responsibilities or different names. The
plan must inventory callers and delete obsolete paths instead of retaining adapters.
Do not count renames or code moved between modules as saved LOC.

### Decisions the plan must make concrete

1. Choose the offer, UI-action, request, and result types, including explicit action
   identity and how already-resolved departure authority is invalidated.
2. Specify each affected engine's tool/schema changes and recount tools and arms.
   Preserve the current caps without hiding semantic actions to reduce the count.
3. Specify request validation on creation and restore, transaction ordering,
   transcript attribution, and every failure/clear path.
4. Choose the optional-focus field shape and update shipped content, authoring
   prompts, views, documentation, and golden fixtures consistently.
5. Produce ordered implementation steps with concrete deletion and addition counts,
   test changes, and playable checkpoints.

These are implementation choices within the accepted behavior, not permission to
add a workflow framework, new gameplay features, or a third proposal.

### Acceptance checks for the resulting plan

Use behavioral tests and ScriptedSpawner; tests never start real processes.

| Boundary | Evidence required |
| --- | --- |
| Offer and continued play | Offering a way on does not block actions or force departure |
| Offer and complication | A complication is accepted after an offer; successful install clears it; failed install preserves it |
| Departure action | An explicit approved action skips repeated adjudication; new intent goes through the master |
| Action validation | Stale or conflicting actions are refused; prose equality cannot select an execution route |
| Generation | Each operation uses the same executor; a request stops later turn tools; only one request is executed |
| Rollback | Failed authoring/install leaves no partial cast, movement, recovery, or RNG changes |
| Narration and reload | Uninstalled or hidden content does not leak; failed arrival narration preserves installation; reload clears lost requests |
| Engine differences | Loner complication preserves spent Luck; 24XX jobs are unaffected; Tunnel Goons extension does not move the player |
| Optional focus | A situation without a question authors, installs, and renders without forcing one |
| Architecture | Core, turn, app, and UI neither inspect engine world shape nor branch on engine operation identifiers |

Preserve existing behavioral coverage rather than adding tests of prose or wiring.
Update goldens only for intended schema and prompt changes and inspect their diffs.

The implementation plan must run the repository checks from its root with
UV_CACHE_DIR unset:

~~~bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
~~~

Include a playable UI check of the preserved flows. If a live CLI is unavailable,
state that limitation and identify the scripted-spawner coverage; do not claim a
live end-to-end playtest.

Stored-shape changes follow the existing stale-save policy: reject/skip stale saves,
do not migrate, reinterpret, or delete them. Update shipped scenarios when their
schema changes. These proposals do not authorize changing saved user content.

## LOC estimate and expectations

The recorded baseline after the previous plan's follow-up is 8,109 Python lines
under src, down from 9,367 before that plan. Recount at the start of implementation;
the historical number is not a guarantee about a later checkout.

| Change | Estimated net Python lines removed |
| --- | ---: |
| Offer state and optional question handling | 15–40 |
| Consolidated generation routing, after replacement types and validation | 20–60 |
| Engine-provided action replacing special UI routing | 5–30 |
| Combined | 40–130 |

On that baseline, the estimate gives 7,979–8,069 lines. It excludes tests, Markdown,
generated schemas, and mere movement of code. It includes the cost of replacement
code. The estimates are not measured patch results or a target to satisfy by padding,
compressing formatting, weakening checks, or deleting features.

The relevant runtime methods play, extend, and _grow currently total about 76 lines
including comments and internal blank lines. Much of that is necessary execution
and failure handling. Their entire bodies cannot be counted as savings.

If concrete design work shows no net cut or a net increase, report that before
implementation and explain the cost. Engine independence may still justify a small
change, but it should not be presented as a large deletion.

## Are there drastic cuts left?

No additional cut on the scale of removing the campaign layer has been identified
in this review while preserving the current features and guarantees. This is not
proof that the whole repository is minimal: duplicate logic or a better design may
still be found through a broader audit.

The expected benefit here is modest LOC reduction and fewer shared gameplay
assumptions. Another reduction of roughly a thousand lines would likely require
removing a substantial feature or subsystem, accepting a materially different
product/behavior, or discovering substantial duplication not established here.
No such reduction is part of these accepted proposals.
