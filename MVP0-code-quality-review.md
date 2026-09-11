# MVP0 Python quality review

**D1–D5 are decided and folded into the requirements below.** F1–F5 and Q1–Q4 retain their separate acceptance status; the F5 process policy remains open.

Repository: `mmerah/ai-dnd-concept` · branch: `master` · commit: [`a549d8158fabb5e230b4cf8a2545b484a363adf9`](https://github.com/mmerah/ai-dnd-concept/tree/a549d8158fabb5e230b4cf8a2545b484a363adf9) · reviewed: 11 September 2026.

**Assessment:** Keep the current architecture. The main weaknesses are inconsistent boundary guarantees, ownership of async work, and type information lost at engine boundaries. Formatting and general module organization do not need another broad rewrite.

## Acceptance table

### Fixes recommended before MVP0

| ID | Proposal | Feature impact | Your response |
| --- | --- | --- | --- |
| F1 | Release image claims on every exit | Failed or cancelled art can be retried | Accept / defer |
| F2 | Observe and drain background tasks | Failures become visible; shutdown completes cleanup | Accept / defer |
| F3 | Use one safe file-publication pattern | Readers do not see partially written media; writers do not share temporary files | Accept / defer |
| F4 | Handle expected file errors consistently | Bad files produce useful messages instead of page failures | Accept / defer |
| F5 | Enforce turn admission in the application layer | UI, future eval, and other callers obey the same concurrency rule | Accept / defer |

### Accepted implementation requirements

| ID | Accepted choice | Required change | Status |
| --- | --- | --- | --- |
| D1 | A | Strict scalar validation with explicit JSON collection handling | Decided; not implemented |
| D2 | A | Commit gameplay RNG with the saved turn; separate cosmetic RNG | Decided; not implemented |
| D3 | B | Carry precise types through engines, sessions, and turns; erase types only in one registry adapter | Decided; not implemented |
| D4 | A1 / B1 / C1 | Selected packs only; explicit primary plus supplements; content fingerprints for resume compatibility | Decided; not implemented |
| D5 | A | Shallow freezing with documented ownership and defensive copies | Decided; not implemented |

### Focused quality changes

| ID | Proposal | Feature impact | Your response |
| --- | --- | --- | --- |
| Q1 | Parse CLI events by their actual event shape | Avoid mistaking tool or reasoning text for the final answer | Accept / defer |
| Q2 | Give uploaded documents a defined lifetime | Retries retain the source; abandoned uploads are removed | Accept / defer |
| Q3 | Make engine helpers honest about mutation | No intended rules change | Accept / defer |
| Q4 | Reduce compressed expressions and split UI responsibilities selectively | No intended UI or save-format change | Accept / defer |

## Fixes

### F1 — Protect the image claim before the first await

**Evidence:** [`app/media.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/media.py), `Illustrator.illustrate`.

**Now:** The scene key is claimed, then `_drawn_icon(player)` is awaited outside the `try/finally`. Cancellation or an exception there skips release of the scene key. I reproduced cancellation at this await: the scene claim remains held.

**Change to:** Put every operation after a successful claim inside its cleanup scope. Release only a claim acquired by that invocation. Keep generating a player icon when scene art already exists.

**Code and feature impact:** Small control-flow change. Later attempts can generate the scene instead of silently treating it as already in progress. No rules or save-format change.

**Done when:** Cancellation during the player-icon await leaves no claim; a second call can generate the scene. Keep the existing duplicate-generation test.

### F2 — Background tasks need an error observer and an awaited shutdown

**Evidence:** [`app/runtime.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/runtime.py), `_retain`, `settled`, `stop`, `reload_settings`; [`ui/app.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/ui/app.py), `_register_pages`.

**Now:** A completion callback only removes the task from the set. A failed task can disappear before `settled()` observes it. `stop()` cancels tasks without awaiting their cleanup. The registered shutdown closes the MCP lifespan but does not explicitly drain runtime sessions.

**Change to:** Give `GameService` one task-completion handler that removes the task, treats cancellation as expected, and reports other exceptions with a traceback. Add async close methods that cancel and await owned tasks. Call them during settings replacement and application shutdown. Keep unexpected errors visible rather than converting them to successful results.

**Code and feature impact:** Async lifecycle methods replace fire-and-forget cleanup. Art, speech, and interjection behavior stays the same during normal play. Shutdown and settings changes wait for cancellation cleanup.

**Done when:** A task that fails before `settled()` is still reported. Closing a runtime leaves no owned task running. Use stub coroutines; no real processes or providers.

### F3 — Publish files through unique temporary files

**Evidence:** [`core/io.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/io.py), `write_text`; [`app/media.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/media.py), `_write`; [`app/speech.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/speech.py), `Reader.read`.

**Now:** Saves use a fixed `.writing` name, speech uses a fixed `.part` name, and images write directly to the final path. Two writers can interfere with the same staging file. A partial image can exist at a path that `_existing()` treats as a valid cached result.

**Change to:** Create a unique temporary file beside the destination, finish and close it, then atomically replace the destination. Remove unfinished temporary files in `finally`. Reuse this publication pattern for JSON, image bytes, and WAV output.

**Code and feature impact:** One small file helper is justified by three callers. Existing filenames and save schemas remain unchanged. This fixes publication safety; it does **not** resolve two processes overwriting each other's valid game state. That policy belongs to F5.

**Done when:** A failed write leaves the old final file intact and no partial final image. Two publishers never use the same staging path.

### F4 — Classify expected I/O failures at the boundary

**Evidence:** [`core/io.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/io.py), `_read_text`, `FileStore.discard`; [`core/source.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/source.py), `whole_text`; [`app/media.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/media.py), `_data_uri`, `_write`.

**Now:** Save writes translate `OSError` into `Refusal`; save/source reads generally do not. Scenario listing skips `Refusal`, so permission errors or files disappearing during a read can escape that recovery path. Speech handles disk failures; image generation does not handle equivalent file failures.

**Change to:** Translate expected file-access errors into contextual `Refusal` at user-file boundaries. At optional media boundaries, log expected I/O failures and leave no cache entry. Keep programming errors uncaught. Distinguish broken bundled resources, which should fail startup, from an invalid user-created pack, which should identify the file and error.

**Code and feature impact:** Consistent failure behavior without adding a large exception hierarchy. A bad user file no longer needs to break the launcher. Optional art failure does not affect the saved turn.

**Done when:** Permission failures, missing files during reads, and media write failures each follow their intended user-visible or logged path.

### F5 — Put the single-turn rule inside Runtime

**Evidence:** [`app/runtime.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/runtime.py), `playing`, `play_refusal`, `GameService.play`, `open`; [`ui/game.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/ui/game.py), `refuse_play`, `_open`.

**Now:** Normal UI actions ask Runtime whether play is allowed. The public service methods do not enforce that rule. Automatic opening checks only its own session. `Runtime.playing()` chooses the first active turn, which assumes there cannot be two. A future eval or another caller can bypass the UI checks.

**Change to:** Make Runtime own admission and the active session explicitly. Route opening, play, actions, restart, and settings replacement through guarded application methods. Acquire admission before awaiting work; release it in `finally`. The UI should display a refusal, not own the rule. For MVP0, retain the current global single-active-operation policy because the CLI MCP endpoint has no per-turn routing identity.

**Code and feature impact:** Some UI call sites move from direct service calls to Runtime commands. Competing actions receive a clear refusal. This does not introduce parallel games.

**Done when:** Two concurrent application calls cannot open competing turns, including calls that bypass the UI. A second game's automatic opening obeys the same rule.

**Deployment decision:** Choose **one process per save directory** for MVP0 (recommended), or add cross-process locking/conflict detection. The latter is extra work; an asyncio guard and atomic replacement alone do not provide it.

## Accepted implementation requirements

### D1 — Enforce strict scalar validation

**Evidence:** [`core/entities.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/entities.py), `Frozen`, `Mutable`, `Loose`, `parse`; repository guidance requires strict Pydantic boundary models.

**Now:** The base configurations do not set strict validation. `parse()` uses ordinary `model_validate()`. A probe using these actual bases accepted `{"count":"4","enabled":"false"}` as integer `4` and boolean `False`. Unknown-field rejection and strict value types are different guarantees.

**Accepted: A — strict scalar values.**

**Change to:** Require real numeric and boolean values in file and tool schemas. Preserve deliberate JSON-array-to-tuple handling and explicit normalization. Keep environment-string parsing in settings and duplicate-key rejection.

**Code and feature impact:** Malformed saves and packs are rejected; malformed model replies may need the existing retry. Valid JSON arrays continue working. Do not simply turn on `strict=True` globally: the current `decode()` → Python objects → tuple-typed fields path also needs attention.

**Done when:** Tests on the locked dependencies reject numeric strings and inappropriate boolean/number substitutions, while accepting valid arrays, settings strings, and saved-data round trips.

### D2 — Commit dice with the turn and isolate cosmetic randomness

**Evidence:** [`turn/run.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/turn/run.py), `Turn.begin`, `apply`; [`app/runtime.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/runtime.py), `_turn`, `_speaks`.

**Now:** Individual refused tool calls preserve RNG state. Successful tool calls advance the service's RNG immediately. If narration or saving subsequently fails, game state stays unchanged but dice have advanced. Interjection selection also draws from that same RNG despite its comment saying it is not the game's die. The existing failed-narration test checks game state, not RNG state.

**Accepted: A — transactional gameplay RNG with separate cosmetic randomness.**

**Change to:** Copy the gameplay RNG when opening a turn. Publish its final state only after the turn saves successfully. Give interjection selection its own random generator. Preserve the existing rollback of refused tool calls within the turn.

**Code and feature impact:** Failed turns do not consume gameplay randomness. Toggling companion chatter does not alter later gameplay rolls. Seeded fixtures may change. Persisting RNG across application restarts remains outside this requirement.

**Done when:** A roll followed by narrator failure or save failure leaves the committed game and gameplay RNG unchanged. Successful turns advance both. Enabling interjections does not change the gameplay sequence.

### D3 — Carry precise types through engines, sessions, and turns

**Evidence:** [`core/model.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/model.py), `AnyScenario`, `AnyCharacter`, `AnyGame`; [`engines/seam.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/seam.py), `Engine.player_of`; [`engines/scenes/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/scenes/engine.py), `new_game`, `world_of`.

**Now:** The exception for invariant game generics extends to scenario and character payloads. `player_of()` returns `P` from an `Any` payload after checking only `id` and `known`. Annotating an assignment from `Any` does not prove its shape. The engine ID checks protect normal routing, but static checking cannot prove these payload relationships.

**Accepted: B — carry precise types through the whole engine/session/turn chain.**

**Change to:** Parameterize the engine, service/session, and turn relationships together with their scenario and character types. Preserve those relationships through tool dispatch, role calls, and persistence interfaces. Keep type erasure inside one registry adapter that joins heterogeneous concrete engines to the application. Validate external data against the selected concrete model before admitting it to the typed chain. Do not replace `Any` with unchecked casts.

**Code and feature impact:** The type checker can verify that an engine receives its matching game, scenario, and character types throughout a session. This is a broader refactor with more generic machinery and more call sites to review. No intended rules or save-format change comes from typing alone.

**Done when:** Basedpyright verifies the typed chain without unchecked payload access or casts that hide mismatches. A focused negative typing check rejects mismatched engine/game/scenario/character combinations. Boundary tests refuse incorrectly routed external payloads before attribute access. Existing behavior tests and serialized fixtures remain unchanged unless another accepted requirement explicitly changes them.

### D4 — Make pack selection one explicit policy

**Evidence:** [`engines/scenes/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/scenes/engine.py), `first_pack`, `pack_content`, `validate`; [`engines/twentyfourxx/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/twentyfourxx/engine.py), `resolve_skill`, `hire_check`; [`engines/loner3e/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/loner3e/engine.py), `_meanings`; [`core/model.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/model.py), `Character`.

**Now:** Character creation selects one pack. Scenario creation defaults to all packs. Hiring uses the first selected pack. Loner meanings use selected packs. 24XX skill lookup searches every installed pack. Characters do not retain the pack used to create them. These are different policies behind the same “table sets” concept.

**Accepted: A1 / B1 / C1 — selected scope, explicit primary, and content fingerprints.**

| Requirement | Change to code | Feature impact |
| --- | --- | --- |
| A1: selected packs only | Active scenario packs define lookup scope. Record the character’s creation pack and check compatibility at launch. | Installing another pack does not silently widen an existing game's rules. Incompatible characters are refused at launch. |
| B1: primary plus supplements | Make the primary pack explicit for hiring. Selected supplements add content. Reject ambiguous duplicate IDs or meanings. | Pack order does not silently override content; conflicts produce a useful error. |
| C1: fingerprint compatibility | Store content fingerprints and refuse incompatible pack changes on resume. Account for bundled SRD dependencies explicitly. | Missing or incompatible changed packs prevent resume with an explanation. Saves do not embed a full pack snapshot. |

**Change to:** Put this policy in one typed pack-selection/resolution object used by creation, launch validation, prompts, skill lookup, and hiring. Validate unknown or empty selections before indexing or starting generation. Keep engine-specific pack schemas. Keep user-authored files outside installed Python package directories.

**Code and feature impact:** This changes which characters launch, which skills are legal, and how old saves resume. Creation-pack metadata, explicit primary selection, and fingerprints must be persisted where needed. Under the current no-migration policy, affected old files need regeneration; a conversion would be separate work. Implement this policy with pack authoring.

**Done when:** Test two packs with an overlapping entry, a character from an inactive pack, an installed-but-unselected skill, and an edited/missing active pack. Official Loner pack content and licensing were not audited here.

### D5 — Keep shallow freezing with explicit ownership

**Evidence:** [`core/play.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/play.py), `PendingOption.args`; [`core/model.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/core/model.py), frozen envelopes around mutable payloads.

**Now:** `frozen=True` prevents field assignment, not changes inside a dictionary or nested mutable object. A probe confirmed dictionary mutation through a frozen model. “The frozen call” and “value models are frozen” can suggest a stronger guarantee than the code supplies. This is an ownership risk, not evidence that current play mutates an option incorrectly.

**Accepted: A — explicit shallow freezing and ownership.**

**Change to:** Document that frozen models prevent field reassignment but do not freeze nested objects. Copy mutable payloads when ownership changes. Do not expose internal mutable collections for callers to edit. Keep mutable world state and commit-time validation.

**Code and feature impact:** No intended save-format or gameplay change. The protection comes from explicit ownership and defensive copies. Deep immutable representations are not required.

**Done when:** Mutating a draft cannot modify the committed state or authored scenario. Callers cannot accidentally mutate owned nested values through an exposed reference. Do not enable assignment validation on every mutable world field: intermediate draft states are deliberately validated at commit.

## Focused quality changes

### Q1 — Replace generic CLI text search with driver-specific event parsing

**Evidence:** [`app/spawn.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/spawn.py), `CodexDriver.read_result`, `_last_said`, `_found`, `final_message`.

**Now:** The last recursively discovered `text` value in a multi-line JSON stream is treated as the answer. The parser does not establish that it belongs to a final assistant message. The shared fallback also scans arbitrary trailing objects.

**Change to:** Let each driver recognize supported event types and final-answer fields explicitly. Use small typed event models; tolerate unrelated event fields where appropriate. Keep raw/fenced JSON extraction as a separate fallback for actual message text. Reject an event stream that has no final answer instead of interpreting arbitrary nested text.

**Code and feature impact:** More explicit adapter code, fewer heuristics. Supported valid responses behave the same. Unsupported CLI output shapes fail clearly. Confirm the supported installed CLI versions before changing their event contracts; this review did not run either CLI.

**Done when:** Recorded fixtures cover final answers, reasoning/tool text after an answer, failed events, and an absent final answer. Do not spawn a CLI in unit tests.

### Q2 — Make the form own its upload until success or dismissal

**Evidence:** [`ui/create.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/ui/create.py), `ScenarioForm.uploaded`, `write`, `_discard_upload`.

**Now:** Each upload allocates a new directory. Replacing an upload overwrites the only reference to the old directory. Leaving the page has no explicit cleanup. Conversely, `write()` deletes the source even when generation fails, forcing a new upload for retry.

**Change to:** Track one temporary upload owner per form. Clean up a replaced upload and clean up on form/client disposal. Retain the current document after a recoverable generation failure; delete it after successful creation or explicit dismissal. Prevent upload replacement from deleting a file currently being read.

**Code and feature impact:** A small lifecycle owner replaces scattered directory creation/deletion. Failed authoring can retry the same source. No game or save-format change.

**Done when:** Upload replacement removes the old directory, retry retains the current source, and disposal releases it.

### Q3 — Separate preparation from mutation in engine helpers

**Evidence:** [`engines/breathless/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/breathless/engine.py), `_pool`; [`engines/loner3e/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/loner3e/engine.py), `_strike`.

**Now:** Breathless `_pool()` sounds like a calculation but spends the actor's stunt. Loner `_strike()` combines harm application, luck recovery, facts, and a note on the enclosing game. Similar operations elsewhere sit on the owning actor/world.

**Change to:** Make pool calculation pure; spend the stunt explicitly in the resolution path. Move the Loner conflict state changes into a world/actor operation returning facts and a named conflict result. Let the engine add the turn note and pending decision. Preserve validation and mutation order inside the transactional draft.

**Code and feature impact:** The code states where costs are paid and which object owns the change. No intended dice, fact-order, or rules change. Keep engine-specific rules separate rather than introducing a universal RPG action framework.

**Done when:** Existing stunt, conflict, and refused-call behavior tests pass unchanged. Add a focused case only if an uncovered rollback path is exposed.

### Q4 — Prefer named steps over compressed expressions; split only cohesive UI parts

**Evidence:** [`app/roles.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/app/roles.py), `_picture`; [`engines/base.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/base.py), `party_panel`; [`engines/twentyfourxx/engine.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/engines/twentyfourxx/engine.py), `create_character`; [`ui/game.py`](https://github.com/mmerah/ai-dnd-concept/blob/a549d8158fabb5e230b4cf8a2545b484a363adf9/src/aidm/ui/game.py), `GamePage`.

**Now:** Nested starred tuples, conditional tuple fragments, and nested comprehensions save lines but make optional branches harder to follow. `GamePage` combines transcript rendering, journal/sidebar rendering, composer events, polling, dice, audio, and scrolling.

**Change to:** Build optional sections/rows in named local variables or straightforward loops. Extract transcript/card rendering and journal/sidebar rendering into focused UI modules while `GamePage` continues to own tab state and polling. Rename ambiguous internal methods where it helps: `Turn.picture()` → `master_prompt()`, `Turn.told()` → `has_visible_facts()`, `Engine.land()` → `validate_and_commit()`.

**Code and feature impact:** Internal refactor only. Preserve prompt text, tool names, serialized field names, fact order, and UI behavior. Do not split every long method or move every free function into a class. Dataclasses for services and Pydantic for boundaries are an appropriate distinction, not an inconsistency.

**Done when:** Existing golden prompt/schema fixtures and UI behavior tests remain unchanged. Review the diff for clarity; line-count reduction is not the acceptance criterion.

## Verification and scope

- Inspected the source structure across all 70 Python files using AST parsing; manually reviewed the application lifecycle, persistence, model/tool boundaries, all four concrete engine classes, both engine families, and primary UI flows. Read relevant behavior tests, repository guidance, `IDEAS.md`, project configuration, and CI configuration. This is a coding-pattern review, not a complete rules/security/license audit.
- The pinned commit's [GitHub check job passed](https://github.com/mmerah/ai-dnd-concept/actions/runs/34641547953/job/103402236328). Its configured gates are pytest, Ruff lint/format, and basedpyright. Preserve those gates and the package-boundary tests.
- Local probes confirmed base-model coercion and shallow freezing using Python 3.12.14/Pydantic 2.13.5. An isolated execution of the actual `illustrate` method, with annotations removed and dependencies stubbed, confirmed the cancellation claim leak. These are focused reproductions, not a full application test run.
- The locked project requires Python 3.13 and Pydantic 2.13.4. Python 3.13 was unavailable locally, and required application dependencies were missing. The full suite was not rerun here. Remaining failure paths are source-derived findings with explicit verification steps above.
- No repository code was changed. Pack authoring, official pack additions, the eval, and the README GIF remain separate work. Use the accepted application boundary and RNG policy in the new eval; keep paid/model-quality evals separate from deterministic unit-test gates.

## Suggested implementation order

1. D1–D5 are closed. Confirm acceptance of the remaining F/Q proposals and settle the F5 process policy before their implementation.
2. Fix F1–F5; implement D2 with the service boundary changes.
3. Implement D1 strict validation, D3 full-chain typing, and D5 ownership rules, plus accepted Q1–Q3 changes. Keep each behavior change separate from formatting.
4. Implement D4 selected packs, explicit primary, and fingerprints with pack authoring. Apply Q4 if accepted as a behavior-preserving cleanup.
5. Run the existing gates and the targeted failure tests above. Then restore the eval and record the demo against the accepted behavior.
