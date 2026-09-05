Refocus: adventure structure belongs to scenarios and engines

Status: agreed direction, ready for implementation planning. This document specifies behavior and boundaries, not an implementation sequence. Additional brainstorming proposals are outside its scope.

Repository baseline reviewed: mmerah/ai-dnd-concept, e2db974508f3049777d1c8f5da68fb96c50e37f8. Recheck affected code against the implementation branch before planning edits.

Goal

Reduce code and prescribed adventure structure together. The platform coordinates execution; scenarios establish the fiction and its scope; engines decide how their games play.

Keep transactional state changes, strict boundary validation, code-owned dice and rules, restricted narrator input, persistence, and role execution. Remove shared assumptions about hubs, jobs, campaign progression, and adventure completion. Do not replace them with a configurable campaign framework.

Retain all four engines and both scene and room world models. Their different play experiences are intentional. Preserve independently authored, stored, selectable, and reusable scenarios and characters as product features; do not collapse their lifecycle into game creation.

1. Scenarios have a premise, scope, and opening

Remove the one-shot/campaign distinction from scenario metadata, authoring, launcher/create UI, validation, and prompts.

Every scenario has:

|Element|Responsibility                                                                                  |
|-------|------------------------------------------------------------------------------------------------|
|Premise|The situation that makes this adventure worth playing.                                          |
|Scope  |Required prose guidance about the intended extent, development, and possible resolution of play.|
|Opening|An engine-typed starting scene or map that gives the player something concrete to do.           |

Scope is a named field, not a mode, turn budget, geography constraint enforced by Python, or automatic ending condition. Authoring guidance should explain the intended reach of the adventure, how consequences develop, and whether it tends toward a resolution or continuing concerns. These are writing prompts, not additional required schema fields.

Examples:

• “Play through one dangerous night inside the monastery. Resolving the disappearance should bring the scenario toward an ending.”
• “Follow the crew across connected expeditions. Let debts and discoveries create subsequent adventures; no final objective is prescribed.”
• “Begin with a village dispute and let its consequences reach the kingdom when events in play justify that expansion.”

The master and worldsmith receive premise and scope during relevant generation and play. Scope remains stable through ordinary play. An engine’s hidden arc, where retained, is separate and may evolve; it is not a predetermined plot or a new platform requirement. Narrator inputs continue to exclude hidden information.

An opening may be a hub with a job offer, a crisis, an exploration site, or something else. Neither a hub nor looking for work is mandatory in the schema or default authoring instructions. Room engines retain an opening map rather than being forced into a scene representation.

2. Remove the shared hub and job system

Delete shared campaign models and behavior: required home location, boards and offers as platform concepts, taking/returning/reporting/reopening jobs, job-ledger ordering, campaign-specific authoring drafts, and one-shot/campaign consistency checks.

Remove their UI controls, mandatory panels, prompt sections, and English command parsing. Do not preserve Go home., Report in., or job-title parsing as hidden platform routing conventions.

Ordinary fictional equivalents remain possible. A tavern is a place; an offer is something an NPC says; returning is movement permitted by the engine. These do not invoke a platform campaign lifecycle.

Audit engines/hub.py before deletion: relocate still-needed world/history primitives without retaining its campaign semantics. Shared placement under engines/ does not justify a universal gameplay rule.

Engine-owned jobs

An engine may own a job concept when its rules need one. For 24XX, preserve the rules-defined completion and advancement behavior through engine-owned state and tools. Illustrative operations are accept_job(terms) and finish_job(outcome, chosen_skill); exact tool names and arguments belong to the implementation plan.

The GM calls the lifecycle tools. The engine validates eligibility and prevents duplicate rewards. Preserve player choices required by the rules, using the existing decision mechanism where needed. Closing work need not require a hub visit, generated debrief, replacement board, or reopenable ledger.

Audit other engines for existing between-job or completion rules before removing shared plumbing. Retain necessary rules locally; do not give every engine a job abstraction merely because 24XX needs one.

3. Separate job completion, scene resolution, and stopping play

|Event                       |Authority and behavior                                                                                           |
|----------------------------|-----------------------------------------------------------------------------------------------------------------|
|Rules-defined job completion|GM requests it through an engine tool; code validates and applies eligible consequences once.                    |
|Natural scene resolution    |GM signals resolution; the player may remain or describe the next pursuit.                                       |
|Whole-adventure ending      |Player may stop after a satisfying resolution or continue. Scope offers guidance, not a platform completion gate.|

Do not add a universal finish_adventure tool or mandatory completed-save state in this refactor. Existing engine terminal conditions, such as character death, remain engine-owned.

4. Remove commissions; preserve generation as an engine handoff

Delete immediate/deferred commission orders, queues, per-turn commission counters, fulfillment/withdrawal bookkeeping, temporary answer notes, and the master/worldsmith/master respawn loop used to satisfy a commission within one turn.

Generation remains available when an engine needs new authored material. The engine determines when it is legal, the required input/output types, and how to validate and install the result. The platform runs the requested role work without interpreting a universal complication, scene, job, or campaign lifecycle.

Scene engines: two transition behaviors

Player-directed continuation: the GM resolves the current scene and offers continuation. Resolution does not force departure. The player may keep playing there or describe their next pursuit. That pursuit becomes the generation brief.

GM-introduced complication: the GM can request a newly authored situation during play without asking permission for the complication itself. The request supplies its reason and brief. The next scene can occupy the same place and retain the same cast.

Generation changes the situation, not the player’s reaction. “Guards arrive to arrest you” may establish a complication. “You surrender and wake up in prison” improperly skips the player’s response unless those consequences have already been resolved under the rules.

If the existing world and tools can represent a complication, no generation is required.

Handoff and failure behavior

1. An accepted generation request ends the GM’s work for that turn; subsequent tool calls cannot continue changing that turn.
2. Preserve legal prior actions in a validated state. Generate from that state and install the result atomically through the engine.
3. Present the installed situation to the player. Do not respawn the GM in the same turn to consume the generated answer.
4. The next GM invocation follows player input. If generation or installation fails, retain the last valid state and provide a retry path without replaying prior actions or rewards.

Narration must not assert an uninstalled complication. Preserve distinct handling for failures before installation and presentation failures after installation: the latter must not cause duplicate generation or state application. The implementation plan must specify ownership of any minimal pending handoff state and its reload/retry behavior. It must not recreate a general commission queue.

Room engines keep their own generation semantics. For example, extending a map need not move the player or create a scene transition. Do not force the scene engines’ two transition reasons into all engines’ state models.

5. Flatten history

Remove job-tagged scene/visit spans, job summaries, and chapter reconstruction based on returning to or reopening work.

Keep chronological scene/visit records, exchanges, and recaps. Recent history can remain detailed and older history can use recaps. Both world families can project into shared chronological history types without sharing an adventure structure.

Preserve public/hidden information boundaries when constructing narrator history. Internal recaps must not become player-visible merely because the job/chapter layer is removed. Engine-owned job state need not reconstruct or group narrative history.

6. Validate integrity, not storytelling taste

Remove authoring validity requirements that prescribe scene composition: a mandatory cast member besides the player, forced reuse of existing cast, and arbitrary prose-length minimums used as proxies for narrative quality. Audit drafts and refusal checks for equivalent editorial constraints. A solitary scene, unfamiliar cast, quiet situation, or concise setup is not invalid for those reasons.

Retain strict structural validation, required meaningful inputs, valid references, state consistency, rules eligibility, ownership, and information-exposure checks. A mechanically required field or nonempty identifier is different from a minimum paragraph length. Move useful editorial advice into scenario/engine authoring guidance, without recreating the same requirements as unconditional prompt mandates.

7. Keep long-range setup with less ceremony

Preserve deliberate long-range setup during scenario authoring: hidden pressures, motives, secrets, and possible future developments can give play coherence. Do not remove this capability or substitute scope for it. Scope describes the intended extent of play; setup describes fictional possibilities within it.

Simplify the existing arc mechanism rather than introduce a plot-management subsystem. The implementation plan should use the following minimal design: author setup with the opening, retain it as engine-owned hidden context, and allow an explicit revision when developments in play warrant one. No minimum arc length and no requirement to rewrite or return the whole arc with every new scene. An omitted revision preserves existing setup; the plan must make any explicit clearing behavior unambiguous.

The master and worldsmith must interpret setup alongside established state and history. Resolved or contradicted possibilities do not override what happened. Setup does not prescribe the player’s actions or require a planned ending. Keep its hidden information out of narrator inputs. Exact field names and whether to retain the name arc are implementation choices.

Planning surface

The reviewed baseline suggests these areas; this is a dependency checklist, not a prescribed sequence:

|Area                                            |Expected work                                                                                                                                        |
|------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
|`core/model.py`, `core/play.py`, `core/views.py`|Remove scenario kind, commissions and job/chapter history semantics; add scope and retain minimal shared records.                                    |
|`engines/hub.py`, `engines/seam.py`             |Remove shared campaign behavior and commission API; relocate necessary shared primitives and define the minimal execution handoff.                   |
|`engines/scenes/` and `engines/rooms/`          |Simplify worlds, drafts, validation and authoring; remove editorial validity rules and mandatory arc rewrites; preserve different progression models.|
|Concrete engines, especially `twentyfourxx/`    |Own rules-specific lifecycle and rewards; remove commission tools.                                                                                   |
|`turn/`, `app/runtime.py`, `app/mcp.py`, `ui/`  |Remove commission respawn orchestration and campaign routing; support generation handoffs and failure/retry presentation.                            |

Update shipped scenarios with authored scope, removing campaign metadata and payload fields. Update guidance, README, engine documentation, fixtures, schema goldens and behavioral tests. Remove superseded campaign tests instead of retaining obsolete behavior to satisfy them.

Keep the repository’s existing strict-save policy: this refactor does not introduce save versioning or automatic migration. Document that incompatible old saves are rejected; do not silently reinterpret them or delete them.

Acceptance criteria

• All four engines can start and play without a platform campaign mode, hub, board, or shared job lifecycle. Shipped scenario examples include openings that are not employment at a home base.
• Scope is supplied to master/worldsmith context and has no hard-coded progression or completion branches. Engine-owned hidden material stays out of narrator input.
• 24XX retains its rules-defined job consequences, with invalid completion and duplicate rewards rejected. Other engines retain their necessary completion rules without importing a shared campaign system.
• Scene resolution allows continued play or player-described departure. A GM complication can generate a same-location situation without choosing the player’s response. Rooms retain independent generation behavior.
• Generation ends the GM turn, installs atomically, and returns control to the player. Failed generation is retryable without duplicating prior effects; no commission queue or same-turn fulfillment respawn remains.
• Chronological history and recaps work without job spans or chapter reconstruction, preserving information boundaries.
• Valid solitary scenes, new casts, and concise authoring are accepted; malformed references, illegal state and information exposure remain rejected.
• Authored long-range setup survives scene generation without a compulsory rewrite, can be deliberately revised, and cannot override established events or player agency. Reusable scenario and character selection/creation remain supported.
• Obsolete prompts, UI, models, tools, fixtures and guidance are removed. Repository test, lint, formatting and type-check gates pass after behavior-focused updates.

Boundaries of this agreement

This is a deletion-led refactor, not a new adventure workflow framework. Exact handoff types, retry storage, engine tool names, and module placement are implementation-plan decisions subject to the behavior above.

Removing engines, merging the AI roles, changing CLI providers, replacing strict integrity validation, and eliminating character creation are not agreed requirements here. Removing independently reusable scenarios and characters was explicitly rejected. Preserve long-range scenario setup while simplifying its ceremony as specified above.