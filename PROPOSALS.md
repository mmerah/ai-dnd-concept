# PROPOSALS — simplification before MVP0

This is a design and evidence document, not an implementation plan. Turn each accepted section into a bounded PLAN phase using its deletion targets, sequencing constraints, and acceptance checks. This commit changes documentation only.

## Decisions from the discussion

| Proposal | Direction |
| --- | --- |
| 1. Shared world bookkeeping | Accepted direction. Preserve the different room and scene games. Prove sharing with two engines before spreading it. |
| 2. One player-submission pipeline | Accepted direction. At most one final narrator call per submission, including generation. |
| 3. Companion interjections inside narration | Accepted direction. Preserve personality, dialogue, chattiness, and proposals; remove their separate background run. |
| 4. Deterministic hiring | Supported in principle, conditional on convincing net LOC reduction and explicit mechanical choices. Evidence below revises the original estimate downward. |
| 5. Tool dispatch cleanup | Cleanup only. Preserve public tool names, schemas, and the existing decision mechanism. |
| Readability / SOLID | Permitted only where application behavior stays the same. |

The drastic alternatives are out of scope: no engine removal, no scene-only replacement for Tunnel Goons, no removal of mechanical companions, and no removal of CLI providers. The private decision-resolver redesign from the initial review is also not part of proposal 5.

## Baseline, measurement, and confidence

Reviewed source: `a46e7ee09522ed11b673a0380cc373395ef0e1a3` on `master`, checked again before writing this document on 2026-09-08. All 72 first-party Python/JavaScript paths under `src` were inspected, including empty package files, together with prompts and packs. The vendored dice implementation and binary sound assets are excluded from the code count.

| Area | Physical Python / JavaScript lines |
| --- | ---: |
| `engines` | 5,239 |
| `ui` | 1,913 |
| `app` and `config.py` | 1,712 |
| `core` and `turn` | 1,216 |
| Total | 10,080 |

Counts include blank lines, comments, docstrings, and CSS embedded in Python. JSON and Markdown are excluded. Moving code to data, templates, generated code, or another directory is not a complexity reduction by itself: report those changes separately. Test deletions do not count toward the source target.

Reproduce the source count from the repository root:

```bash
python - <<'PY'
from pathlib import Path
files = sorted(p for p in Path('src').rglob('*')
               if p.suffix in {'.py', '.js'} and 'lib' not in p.parts)
print(sum(len(p.read_text().splitlines()) for p in files))
PY
```

| Proposal | Working net LOC estimate | Evidence level |
| --- | ---: | --- |
| 1 | 150–350 initially; 300–600 only if the full shared bookkeeping extraction earns it | Call-path analysis; replacement not implemented |
| 2 | 80–180 | Call-path analysis; failure semantics still need implementation proof |
| 3 | 80–140 | Identified removable background workflow; replacement not implemented |
| 4 | 60–110 | Measured deletion candidates and an executed 84-line scratch prototype; not production-ready |
| 5 | 8–25 | Small forwarding/dispatch cleanup only |
| Readability | No promised reduction | Changes must justify themselves without expanding architecture |

These ranges supersede the more optimistic estimates in the initial discussion. They are not additive: proposals 1–3 touch the same journal, narration, and runtime paths. A PLAN should count each deleted block once. Do not promise a percentage reduction before a complete replacement is measured.

Direct checks performed during review: all four engines instantiated; supplied scenario/character pairs began successfully; player and narrator views constructed; saves round-tripped through engine restoration; a refused tool preserved both draft state and RNG. A published Breathless loot call was also shown to accept a supplied award without a roll. Relevant tests were read, but the full test suite and live CLI/API gameplay were not run. Direct checks used Python 3.12.13 with Pydantic 2.13.4; the project's required Python >=3.13 and full gates remain necessary for implementation.

## Standing constraints

Keep all four rules engines, both world families, all provider choices, creation pages, authored scenarios, packs, media, speech, dictation, and the dice UI. Preserve hidden-information separation, deterministic rule procedures, tool-level atomicity, and player decisions. Only the explicitly described changes to proposals 2–4 may alter timing, response grouping, or newly hired sheets.

Follow repository guidance in `CLAUDE.md` / `AGENTS.md`: one-way imports, typed boundary validation, side effects at the edges, and no speculative abstractions. A refused tool must leave its candidate changes and RNG unused. Avoid event sourcing, JSON Patch mutation languages, general workflow engines, capability registries, and reflection-driven form/tool frameworks.

Save changes require an explicit decision in the PLAN. The current policy rejects stale saves and does not migrate them. Proposal 1 is likely to change the save shape; say which fields change, retain the stale-save warning behavior, and update fixtures. Do not silently add migration or versioning infrastructure.

## 1. Shared world bookkeeping

### Problem and current ownership

`engines/seam.py::Engine` owns character/scenario creation, tool lookup, validation, history forwarding, narration closure, hiring, and generation. `engines/base.py::World` then forwards history through abstract `records()` and flattens it through `exchanges()`.

Two families repeat the surrounding game bookkeeping:

| Responsibility | Room implementation | Scene implementation |
| --- | --- | --- |
| History storage | `rooms/world.py::Visit.exchanges` | `scenes/world.py::SceneRun.exchanges` |
| History projection | `RoomWorld.record/records` | `SceneWorld.record/records` |
| Presence | NPC `place`, current visit | `SceneRun.here`, entity `known` |
| Membership/death | `join_party`, `leave_party`, `kill` | Equivalent methods with different presence checks |
| Role/UI projections | `rooms/engine.py::master_sections/narrator_view/player_view` | Corresponding `SceneEngine` methods |

The common result types already exist: `Exchange`, `SceneRecord`, `NarratorView`, `PlayerView`, `Subject`, and panels. The rest of the application consumes those projections rather than the engine's history layout. This is the concrete feasibility evidence for sharing.

### Proposed ownership

The shared layer owns chronological exchanges, generic scene-history rendering, common party bookkeeping, and construction of public presentation values. Engines retain the rules for whether someone is here, can act, can die, can join, or can move. In particular, sharing mechanics of membership does not mean imposing the same eligibility policy.

Start with one typed journal owned by `Game`. Its blocks carry the existing `SceneRecord` information: title, focus, recap, and ordered exchanges. It must support appending an exchange, enriching a checkpointed exchange, opening a block, and setting the previous block's recap. Use concrete methods, not a command bus. The engine explicitly tells the journal when a room visit or scene starts.

World-specific history may remain where gameplay needs it: room visit locations support the trail; scene presence history supports `last_seen()`. Remove their exchange and recap storage when the journal takes ownership. Do not delete `runs` or `visits` merely because exchanges moved. Do not put cast IDs or hidden arc material into the public journal metadata.

During extraction, the existing `Engine.history/scenes/record` methods may temporarily forward to the journal. Delete that compatibility layer once callers move; do not keep two authoritative logs.

### Preserve the meaningful differences

| Keep in the engine/family | Why |
| --- | --- |
| Directed ways, locks, reachability, frontier checks | They make Tunnel Goons an authored-map game. |
| Item holders, dropped items, encumbrance | Room items are not the same concept as scene gear tags or degrading dice. |
| Scene cast, arc, presence history, brief updates | They support scene generation and recurring characters. |
| Loner scene-leaving refill | Departures refill luck; complications do not. |
| 24XX leadership and actor selection | A successor keeps their ID; the player is not permanently the entity named `player`. |

Shared presence/party helpers should accept checked engine results, or expose a very small existing-world operation, rather than inspecting both world shapes with `isinstance` branches. If an extraction requires many policy booleans or optional fields, retain the two implementations and share less.

For public projections, share assembly from already-selected subjects and rows. Keep selection of known/hidden entities and valid speakers in the family until a common representation actually removes code. Dead entities may remain subjects but cannot speak. The player's sheet remains visible; other hidden sheets do not become visible through sharing.

### Implementation slices and deletion targets

1. Extract the journal with Tunnel Goons and Breathless as the contrasting pair. Preserve chronological and scene-grouped views. Remove duplicated exchange storage and replace the `record/records/exchanges` forwarding chain.
2. Convert Loner and 24XX, preserving recaps, empty-current-scene behavior, trail order, and succession identity. Centralize generic close/record operations above engine rules.
3. Extract repeated public-panel and party assembly only where both families use the same operation. Remove forwarding methods and repeated branches that become unnecessary.

Inspect `core/model.py`, `core/play.py`, `core/views.py`, `engines/base.py`, `engines/seam.py`, both family `world.py` and `engine.py` files, `turn/context.py`, `app/runtime.py`, `app/launch.py`, and `ui/game.py`.

### Required decisions and acceptance checks

- The journal remains an ordered record of existing exchanges during proposal 1. Changing the displayed turn count from exchange count to player-submission count is a separate product change; do not slip it into this extraction.
- Preserve room history's omission of empty completed visits and retention of the current visit; preserve scene history's current grouping/recap behavior. Encode the difference at block creation/projection without inventing a large policy system.
- Preserve narrator history's exclusion of hidden recaps and master/authoring history's intended recap access. The existing `told_history` versus `render_history` distinction matters.
- Add behavioral comparisons for return visits, departed NPC last-seen information, party movement, death, and 24XX succession. Compare facts and public projections, not class names.
- Require an actual net-negative diff after replacement and deletion. Stop after the journal if the broader shared world layer becomes larger or harder to read.

Existing anchors: `tests/core/test_rooms.py`, `test_scenes.py`, `test_context_boundary.py`, `test_views.py`, `test_integrity_boundaries.py`, `test_golden_turn.py`, plus engine world/view tests. Some stored-shape fixtures will intentionally change; public behavior should not change in this proposal alone.

## 2. One player-submission pipeline

### Current paths and their cost

`GameService._turn()` runs the master, conditionally narrates, commits, presents media, and then calls `_generate()`. `_generate()` may run another narrator and append another exchange. `GameService.act()` has a separate route: room expansion generates before starting the turn, while scene actions set a note and enter the ordinary turn path.

| Submission | Current role order |
| --- | --- |
| Ordinary action | Master, narrator |
| Scene departure | Master, narrator, worldsmith, narrator |
| Complication without public changes first | Master, worldsmith, narrator |
| More map | Worldsmith, master, narrator |
| Decision that immediately opens another decision | No master; narrator only when there are public facts |

The proposed common order is: consume input, run legal mechanics, perform requested generation if any, narrate at most once, finalize the journal entry, and start presentation work. A no-fiction handoff still need not narrate. Opening the game remains its own idempotent initialization operation.

### Input routing

Retain the visible Move on and More map controls and the stale-action checks. Route text, option IDs, and named actions through one service submission method. Dispatch the small input difference once at entry. Keep the existing engine action policy; do not add an AI `extend` tool merely to achieve one entry point.

For More map, preserve the current pre-generation behavior: validate frontier, generate the extension, and only if it succeeds run the master on the original words. Other generation follows master resolution. One pipeline may have these two explicit generation positions; it should not become a generic workflow executor.

Pending options still resolve through the existing mechanism. Consuming an option that opens another decision skips the master. The tool gate still stops after a pending decision or generation request appears.

### Transaction and journal semantics

Use the existing per-tool candidate draft and cloned RNG. This proposal changes presentation orchestration, not rule atomicity.

Checkpoint accepted mechanics before awaiting world generation. The checkpoint must also retain the player's words and facts; merely saving the mutated world would leave history missing the action after a crash. With proposal 1, append a narration-free journal entry and later enrich that same entry instead of appending synthetic departure/arrival exchanges. Keep the entry in its originating block; a newly opened destination block can remain empty until the next submission. For a More map request, create its entry in the current block before the worldsmith call.

Once generation succeeds, save the installed world even if final narration fails. This preserves the current principle that expensive successful authoring is not discarded. The final entry can remain facts-only, with the existing public situation and cards available on the page. Do not automatically replay the player's action to obtain prose.

For an ordinary turn with no generation, retain the current fatal-narrator behavior: failed narration leaves the committed game untouched. Avoid unifying this failure policy accidentally. For a checkpointed generation turn, use the existing nonfatal-arrival policy for the single final narration. A PLAN must make these two policies explicit in code and tests.

| Failure point | Required result |
| --- | --- |
| Illegal tool | Candidate and its RNG changes are discarded; master can correct it. |
| Master fails before anything lands | Existing one-retry behavior remains. |
| Master fails after legal effects | Keep the current partial-success policy; do not replay those effects. |
| Worldsmith fails | Keep the action checkpoint, retain the pre-generation world, clear request, attach the engine's unwritten fact. |
| Narrator fails after successful generation | Keep installed world and facts; leave the entry without prose. |

On reload, a saved request is still cleared rather than rerun. The checkpointed entry makes that abandonment understandable without a resumable-job subsystem. Preserve controls for continuing play. A checkpoint can reach the live UI before prose; finalization must update the existing entry without duplicating dice or cards.

`ui/game.py::Observed` currently watches exchange/fact counts, and `_landed()` assumes newly closed exchanges. Enriching an existing entry can leave those counts unchanged. Add a small in-memory commit revision to the observed session, or an equally explicit content-change signal, and keep a per-entry fact cursor so final prose does not toss the same dice again. An entry handle can be its block/index pair; no UUID service or event stream is needed. Replace the frozen exchange value at that handle rather than mutating its fields. Test a facts-only checkpoint becoming narrated without any count increase, including a second tab watching it.

### Context and generation changes required

The worldsmith currently sees prior history after departure narration has landed. In the new order, it must explicitly receive the current action and ordered committed facts as a separate section. `render_history()` alone is insufficient for a narration-free checkpoint because its prose projection does not carry every fact. Preserve full authoring context for the worldsmith; never forward that hidden context to the narrator.

Capture public departure information after mechanics and before installation. Pass it alongside the destination's public view to the final narrator. Use typed public projections for both; validate dialogue speakers against the appropriate visible, living speakers. A union of public speaker identities can support the combined passage, but a dead speaker must not become eligible merely because they appeared in older history. Do not expose the entire prior or current world.

The worldsmith's recap still closes the old scene; it now uses the action/facts instead of already-written departure prose. Preserve Loner's `leaving()` refill only for departure. A complication may open a new scene at the same place and must not refill luck.

### Deletions, intentional changes, and proof

Targets: duplicate orchestration in `GameService.act/_turn/_generate/_narrate`, duplicate presentation calls, the separate departure narration invocation, and prompt constants that only existed for that invocation. Engine authoring and installation stay. Adapt `turn/context.py`, family authoring prompts, and `ui/game.py` observation logic.

Intentional changes: one combined response for departure/arrival; fewer narrator calls; companion integration in proposal 3; fewer synthetic exchanges. Cards may precede prose. Transition prose arrives later than the old departure prose, while total completion time may improve. Media should be scheduled once for the final visible scene; preserving an intermediate departure illustration would defeat part of the simplification and is not promised.

Acceptance: test the role-order table's replacement, both generation failure paths, crash/reload checkpoints, no rerolled mechanics, exactly-once dice display, stale actions, no master while re-suspended, source-scene recap, and hidden-context isolation. Update relevant tests in `test_turn.py`, `test_game_service.py`, `test_decisions.py`, `test_golden_turn.py`, and UI tests. Play one departure, one complication, and one room expansion through both a CLI and an API provider before accepting the UX change.

## 3. Companion interjections inside the existing narrator response

### Existing duplication

`GameService.interject()` selects a companion, builds a second prompt, spawns the narrator again, checks whether the turn moved on, creates a synthetic exchange, and schedules speech. `_speaking`, `hush()`, reload/restart cancellation, `Interjection`, `render_interjection()`, its prompt file, and `INTERJECTION_MARK` support that path. Ordinary `Narration.lines` already supports named dialogue, and the chat/speech code already renders it.

### Proposed response and selection

After mechanics and any generation, choose at most one eligible companion using the existing ordered d10/chattiness selection. Only select when interjections are enabled, no player decision is pending, and the game is not over. Evaluate the final party after transitions and succession. Use one optional suggestion field on the narrator response; when nobody is eligible, require it to be empty rather than building a second dynamic schema.

The narrator writes normal narration/dialogue and may also return a small optional companion suggestion: speaker ID, dialogue, and proposed action. Validate that suggestion against the selected member, require dialogue when there is a proposal, and keep an empty suggestion legal. Code flattens the validated dialogue into the existing spoken lines and records the proposal on the same exchange.

Prefer a small typed optional value over loose fields whose relationship is enforced only by prose. The master still does not write the narrative response. The selected member's sheet is known player-side context; other hidden sheets remain excluded.

The Accept button still submits the proposal as ordinary player text. Adapt `standing_proposal()` and chat rendering: the proposing speaker is not necessarily `exchange.lines[0].speaker` once dialogue shares an exchange with narration. Store the proposing speaker explicitly, or use a typed suggestion value that retains them. Do not guess from the first line.

### Timing and deterministic behavior

Interjection timing intentionally changes: the companion's words arrive with the narration, not as a later independent message. There is no extra narrator spawn and no late result to cancel. Speech synthesis reads the completed exchange once, preserving distinct speaker voices.

Keep the current random selection policy for successful turns. Moving the draw earlier, or introducing a separate cosmetic RNG, can change seeded traces and failure behavior. The PLAN must specify the chosen draw point and test it; creating a separate RNG is not a behavior-preserving cleanup. Carry the selected companion across the narrator's one retry rather than selecting again.

### Removal and acceptance

Delete the independent `interject()` run, `_speaking`, `hush()` and their call sites, stale-interjection checks, the extra journal entry, and the dedicated prompt builder/file where no longer used. Replace rather than retain two response models. Do not delete `_background` or task retention wholesale: illustration and speech still require them.

Test quiet/normal/chatty selection, no eligible party, disabled interjections, pending decisions, game over, a member who dies or leaves this turn, succession, empty suggestions, incorrect speakers, Accept behavior, and a proposal following ordinary narration. Confirm one narrator call on success and only the standard corrective retry on invalid output. Confirm no extra interjection task and one speech request sequence for the final exchange.

Existing anchors: `test_game_service.py` interjection tests, `core/views.py::interjection_refusal`, `turn/context.py`, `test_context_boundary.py`, `test_golden_turn.py`, `ui/game.py::chat/standing_proposal`, and speech tests.

## 4. Deterministic hiring — conditional, with measured LOC evidence

### Proposal

Retain fully mechanical hired companions. Replace the dedicated worldsmith request with a typed hire request whose engine-owned recipe constructs the sheet immediately. The master selects legal recipe inputs; Python assigns the actual numbers. Preserve name, identity, existing brief, terms, party membership rules, and any already-established health. Loner has no hiring workflow and is unchanged.

This intentionally changes newly hired sheets and removes the hiring wait. It is not claimed to reproduce every sheet the current worldsmith can invent.

### Measured current deletion candidates

Counts below are inclusive definition spans at the reviewed commit, excluding surrounding blank lines and imports. They are conservative lexical deletion candidates, not whole-file counts.

| Current code | Lines |
| --- | ---: |
| Three hire-specific `advance()` overrides: Tunnel Goons 20, Breathless 29, 24XX 24 | 73 |
| Tunnel Goons `AbilitiesDraft`, `HIRE_GUIDANCE`, `HIRING` | 27 |
| Breathless `SheetDraft`, `HIRING` | 25 |
| 24XX `SheetDraft`, `HIRING`, `Pack.hire_guidance`, `_specialty_line` | 55 |
| Identified engine-local total | 180 |

Files: each engine's `engine.py` and `worldsmith.py`. The three overrides currently do nothing except delegate non-hiring operations and implement hiring; family `advance()` remains available once the overrides disappear. Do not delete `AUTHORING`, pack creation schemas, or general worldsmith support.

Further shared simplification may remove `Engine.hire`'s generation path (8 lines), its hiring-only `check_request` body (4), `hire_target` (4), the hire-specific unwritten fact, and hiring operation-list additions. Their replacements and surrounding cleanup overlap proposal 2, so they are excluded from the conservative 180-line subtotal. The existing `Hire` entity/terms input remains useful.

### Executed scratch prototype

An 84-physical-line scratch prototype, including imports, schemas, factories, blank lines, and three installation wrappers, was built during this review. It reused current `Abilities`, `SurvivorSheet`, `Sheet`, `starting_items`, `require_hireable`, and `sign_on` rather than adding a generic character-generation framework. It was not committed as production implementation.

| Engine | Prototype recipe | Direct checks |
| --- | --- | --- |
| Tunnel Goons | Four profiles: 3 points in Brute, Skulker, or Erudite; or 1 in each | All four total exactly 3 and round-trip through existing `Abilities` |
| Breathless | Three distinct skills at d10/d8/d6; others d4; named d10 item; pronouns/job text | All 120 ordered skill spreads round-trip; repeated rated skills rejected |
| 24XX | Existing pack specialty; its first listed alternative where a pick is needed; first weapon alternative; zero credits | All six SRD specialties round-trip through existing `Sheet` |

The wrappers require a hireable entity, assign only its sheet, and call `sign_on`. Factories use ordinary typed model construction. No model request, generation marker, or separate narrator is required.

These checks establish that legal sheets can be constructed with the present models and data. They do not establish game balance, UI/model discoverability, strict type-checker compliance, or integration behavior. The prototype's thin installation wrappers lack production annotations, and its 24XX default choices are deliberately narrow.

### Net accounting and gate

| Budget item | Lines |
| --- | ---: |
| Measured engine-local candidates | -180 |
| Measured scratch replacement | +84 |
| Remaining gross saving before integration | 96 |
| Allowance for exact annotations, tool registration, recipe guidance, fact handling, tests-driven fixes | +20 to +40 |
| Potential additional shared/import cleanup, counted only once | -0 to -30 |
| Working rounded net estimate | 60–110 fewer lines |

The earlier 100–200 estimate was too optimistic; 200 is not supported by this evidence. If preserving more recruit variation requires enough extra machinery to erase the saving, keep the existing hiring model. A PLAN should require at least 60 net first-party source lines removed after production gates and count any added recipe data separately. Fewer provider calls and simpler failure behavior remain benefits, but must not be presented as proven LOC savings.

To reproduce the prototype's checks in the implementation branch: enumerate the four Goons profiles; enumerate `itertools.permutations(SKILLS, 3)` for Breathless; enumerate `TwentyfourxxEngine().srd_pack().specialties` for 24XX. Construct each sheet using the recipes above, serialize with `model_dump_json()`, and parse it through its existing concrete sheet model. Assert the Goons sum is 3, the Breathless sorted spread is `[4, 4, 4, 6, 8, 10]` and worn ratings equal initial ratings, and every 24XX specialty keeps its label and zero starting credits. Separately reject repeated Breathless picks and an unknown specialty. This is a reproducible feasibility check, not a substitute for turn integration tests.

### Mechanical choices that must be settled in the PLAN

- Tunnel Goons: four presets omit mixed 2/1 spreads. Either accept that restriction or add those profiles and remeasure. Do not overwrite existing NPC health or award a new starting inventory implicitly.
- Breathless: keep all 120 legal spreads. Validate three distinct skills; start worn dice at their ratings, preserve the d10 starting item and existing defaults. Freeform pronouns, job, and item still come from the typed hire request.
- 24XX: fixed specialty defaults remove arbitrary d10/d12 recruits and pre-existing generated hindrances. State whether that narrowing is wanted. Choosing among specialty alternatives needs an explicit input and validation; it is not free. Reusing kit metadata may grant bulky/harmless behavior that the current free-text hiring path did not encode, so specify the intended hired kit exactly.
- A hire no longer automatically ends the turn through `generation`. Recommended behavior is to let the master continue resolving the rest of the submitted action, with no volunteered companion action. Treat that pacing change as part of proposal 4 and test it. If a mandatory pause must remain, include its implementation in the LOC budget.
- Ensure recipe IDs and available specialties reach the master through existing tool descriptions or prompt sections. Successful factory construction alone does not prove the model can choose them.

Acceptance: invalid recipe rolls back the whole call; missing/dead/already-hired targets retain their refusal behavior; an already-travelling member is not joined twice; existing identity/health survive; the new sheet supports later rolls, help, rest, progression, and 24XX succession. Hiring should require no worldsmith call. Measure and report the final net diff, then play one hire per affected engine through an existing provider.

## 5. Tool dispatch cleanup only

### Strict scope

Keep `change_world`, `roll`, `job`, and all other published tool names and argument schemas unchanged. Keep `MasterTool`, explicit Pydantic argument models, the existing `PendingOption(name, args)` representation, and `Engine.answer()` routing. Do not use this proposal to introduce a private decision resolver, flatten every verb into a new public tool, or change model-facing behavior.

All four engines currently have a `change_world()` entry and a separate `apply_change()` dispatch. Three entries simply forward; 24XX additionally performs `_succession()` afterward. Fold a redundant one-caller dispatch into its owning method where it actually shortens the code. Retain shared family dispatch where several engines need it. Check test callers before deleting methods; update behavioral test helpers rather than retaining permanent aliases.

For 24XX, every arm must still reach `_succession()` after its successful mutation. A refactor that changes `facts = ...; _succession(); return facts` into early returns can silently break death/succession. Keep that postcondition explicit.

### Evidence and acceptance

This is a small change: approximately 8–25 net lines, not the 50–120 estimate associated with the broader tool redesign. No new registry, decorator framework, schema generation, or dynamic method lookup is justified for this saving.

Require byte-equivalent normalized tool schemas and the same registered names, facts, refusals, pending choices, and RNG results. Run golden schemas and tool tests, specifically 24XX death/succession and decision replay.

Known issue kept separate: the review reproduced a Breathless `loot_check` call with a non-null award and choice bypassing the intended roll/decision flow. This document does not authorize fixing it through dispatch cleanup. A private resolution boundary or other behavioral fix needs a separately agreed change; do not claim this cleanup resolves it.

## Readability and SOLID — behavior-preserving work

Prefer ownership improvements that accompany the proposals over a new architectural layer. Shared journal and submission orchestration belong above engine mechanics. Stateful rules methods stay with their state; pure shared calculations stay small. The fact that `Engine` is broad is not a reason to replace it with many one-implementation interfaces.

Permitted examples: clarify misleading names, remove redundant forwarding, move an owned operation to its state owner, and extract a small duplicated pure calculation where two callers already need it. Splitting `runtime.py` into files may help navigation but saves no LOC by itself. Preserve acyclic imports, public schemas, messages, tool order, prompts, serialization, and behavior in a cleanup-only commit.

The earlier suggestion to replace full worldsmith character models with dedicated update DTOs is deferred from cleanup-only scope. It changes the model-facing contract and can change generated behavior. Revisit it only as an explicit authoring proposal with schema and gameplay validation; do not include it under an innocuous SOLID label.

Do not turn every state model into a capability interface or use untyped dictionaries to shorten annotations. Preserve mutable state/frozen value distinctions. Keep `Any` confined to the repository's existing generic-state exception.

## Turning this document into a PLAN

Recommended sequence:

1. Prove the journal extraction with Tunnel Goons and Breathless, measure it, then finish proposal 1 across the remaining engines. Defer broader shared presence work if it does not earn its abstraction.
2. Implement the common submission pipeline on that journal, including crash/failure checkpoints and the worldsmith's new current-action evidence. Establish one final narration before changing companion speech.
3. Fold companion speech and proposals into that narration. Remove the old background path completely.
4. Decide the hiring recipe tradeoffs, integrate a production version, and retain it only if its measured LOC reduction meets the gate.
5. Apply small dispatch and behavior-preserving readability cleanups after the larger code settles, so removed code is not polished first.

Every PLAN phase should list the exact old definitions removed, their replacements, intended observable changes, source-count delta, affected saved shapes, and required checks. Tests that describe intentionally removed behavior should be rewritten around the accepted behavior; tests for rollback, hidden context, mechanical outcomes, and player authority must remain meaningful.

Run the repository's required implementation gates: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, and `uv run basedpyright`. Use the existing deterministic `ScriptedSpawner` in tests; do not start processes inside tests. Inspect live provider and browser behavior separately for changed narration/controls. In particular, check two tabs, stale actions, saved composer drafts, restart, dice delivered once, and speech after a finalized entry.

The completion criterion is a smaller, understandable implementation of the agreed behavior. A smaller number of files, code moved into JSON, or a larger generic framework with fewer engine lines does not satisfy that criterion on its own.
