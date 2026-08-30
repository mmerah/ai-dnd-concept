# PROGRESS: Phase 1 — kernel types, envelopes, protocol, service

Phase 0 shipped and committed (`3f21181`): `change_world` union kept, all four cases 100%.

Counts at phase start (`.py` lines): src 9073, tests 5708, evals 1820.
Counts at phase end, after the adversarial review below: src 9452 (+379), tests 5759
(+51), evals 1817 (−3).

**Overrun, reported per the plan's rule:** the phase estimate was +180 to +300; it landed
at +379 after the review's cuts. No deliverable was optional, so nothing else was cut.
The reviewer confirmed the remainder is structural, not fat. Where the extra sits:
denormalized speech (Speaker/SpokenLine, record/spoken/bubble plumbing) and the two-stage
parse at four boundaries were underpriced in the audit; the rest is the shim (payload
models + narrowing properties + `created()`/`restored`/`views` adapters, ~150 lines) that
Phase 3 deletes with the port. The final `src ≤ 9076` gate now leans harder on Phase 3;
re-check its estimate (−110 to −250) against the shim inventory before starting it.

Design decisions (locked at start, all held):

- `aidm/kernel/` sits between `state` and `content` in the layer flow.
- `Game`/`Scenario`/`Character` became envelope-shaped in place: kernel metadata +
  `payload: SerializeAsAny[BaseModel]`; their JSON dump IS the disk envelope. Stage-1
  mirrors (`payload: dict`) live in `kernel/envelope.py`. A before-validator rejects dict
  payloads so a bare BaseModel can never swallow one silently.
- Legacy payloads `WorldPayload{player_id, world}` / `ScenarioPayload` / `CharacterPayload`
  + narrowing properties keep world/engine call sites untouched until Phase 3.
  `pending_notes` moved off `WorldState` onto `Game.notes`.
- The old `Engine` dataclass satisfies the new protocol structurally (protocol params are
  positional-only so `Callable` fields conform); no wrapper class. Conformance asserted in
  `test_engine_contract.py`. The composition root still holds concrete `Engine`s — flips
  to `AnyEngine` when a second implementation exists (Phase 2 hostile engine).
- Protocol ships without `new_game`/`answer`/`Resolution`: `answer` now would duplicate
  `consume_answer`; `new_game` has no caller until the hostile engine. Phase 2 adds them
  when it drives them ("fix the kernel now" clause).
- Denormalized speech: `Exchange.speaker` + `SpokenLine.speaker{name, icon}` recorded at
  `close_segment`/`play_action`; chat, journal, and the prompt bubble stopped resolving
  ids through engine state (succession attribution fixed by construction). Narrator wire
  `Line` unchanged — narrator prompt and schema goldens did not move.
- `creation.created() -> (CharacterEnvelope, CreationPreview)`; the create page no longer
  touches the `Character` model.
- `GameService` (renamed) gained `view()`, `begin_turn` (commit-per-call in code mode,
  no-op in builtin), `end_turn` (records + commits); `submit` runs through them. The call
  member stays `Turn.call` — a service passthrough would add nothing.
- Launcher lists saves from `SaveEnvelope` alone, keeps skip-unreadable (the shipped stale
  save is skipped with a warning, by standing no-migration policy).
- `PlayerView` carries only label/player/prompt; art and subjects live on `NarratorView`
  once, not twice.

All 15 work items done: kernel package (envelope/views/protocol), state/content model
surgery, two-stage io, engine shim members, turn-loop speech + `run_segment(turn) ->
lines` split, service methods, UI onto persisted speakers + `created()`, boundary-test
layer list, shipped JSON (3 scenarios + 3 kael files), tests + goldens, evals.

Verification: 283 passed; ruff check, format, basedpyright clean; `uv run aidm` serves 200
and lists content. Goldens regenerated once and read: state fixtures byte-identical after
re-nesting (`world`→`payload.world`, `player_id`→`payload.player_id`, notes lifted); save
fixtures additionally gained `Exchange.speaker` + `SpokenLine` shape; prompt, instruction,
schema, and turn-fact fixtures unchanged — the Director surface and narrator input are
untouched, so no eval run was needed this phase.

Known, accepted:
- `Engine.views()`/`GameService.view()`/kernel view types have no direct test yet; the
  Phase-2 hostile engine drives them end to end through `GameService`.
- `Game.model_validate` passes a payload model through by reference; `committed()` dumps
  first and `draft()` deep-copies, so no live path aliases. Callers constructing `Game`
  from a payload they keep must copy first.
- One "skipping save" warning at boot is the stale pre-envelope save, by design.

Adversarial review (opus, staged diff): verdict "ship after fixes"; no blocking bug;
two-stage parse, payload aliasing, and goldens verified clean by probe. Applied:
- C1: `read_characters` now skips an unreadable/mis-filed character file like its
  siblings, instead of killing the home screen.
- C2: the prompt's `Exchange.speaker` is captured in `Turn.begin` before the answer
  resolves, so a succession turn is attributed to who actually wrote it.
- C3: guard tests added — a raw dict payload is refused (the one check that prevents
  silent payload loss), and a save whose payload the engine rejects is refused.
- Cuts: `game_of` and the hand-copied `scenario_of`/`character_of` field mirrors collapse
  to `model_validate(envelope.model_dump() | {"payload": ...})`; code mode now uses
  `GameService.begin_turn`/`end_turn` (the second turn-boundary implementation is gone);
  one shared `require_parsed_payload`; dead `NarratorView.present` + `PlayerView.label`
  deleted; `_attributed_line` inlined; what-comments deleted per the delete-first bar.
- Naming: `_legacy` for all three payload-narrowing properties; `Speaker.icon` →
  `Speaker.id` (it holds an entity id). Save goldens re-carry that rename.
- Kept with reasons: `load_scenario` (test affordance, 2 lines beats 12 call sites);
  write asymmetry (`write_scenario` takes a validated `Scenario`, `write_character` the
  envelope its producer validated); protocol members as properties (a frozen dataclass
  field only satisfies a read-only member — now a comment in `protocol.py`).
- Recorded deviations, completed: VISION's protocol also lists `player_actions` and
  `authoring()`; both stay off the protocol with `new_game`/`answer` until a second
  implementation needs them (PLAN's own member list is satisfied).
- Pre-existing, not fixed here: code mode never shows the Director the notes consumed at
  `Turn.begin` (same shape before this phase); Phase 3's `Resolution` work must not
  re-inherit it.

---

# PROGRESS: Phase 2 — the hostile engine

Counts at phase start (`.py` lines): src 9452, tests 5759, evals 1817.
Estimate from PLAN: ≈ 0 src, ~+150 tests.

## What Phase 2 turned out to be

The hostile engine cannot run on today's kernel, so the phase is mostly the kernel fix
PLAN's "fix the kernel now" clause calls for. The turn loop and `GameService` still reached
into `Game.world`, `Game.player_id` and `engine.scene()`; a payload that holds no rooms world
cannot answer any of them. The inversion below is the price of the deliverable, not scope
creep, and Phase 3 needs it anyway.

- [x] 1. Kernel off the rooms scene
  - `VisibleScene` deleted; `NarratorView` is the one player-visible-scene type (it gains
    `key` for art caching and `speakers` for the roster the narrator validator checks).
  - ACTIVE THREADS moves into the rooms engine's own `director_sections`, so
    `render_director` takes sections and the director prompt stays byte-identical.
  - `spoken()`/`speakers_refusal()` read the view's speaker roster instead of `world`.
  - The secrecy check `revealed_from` did moves into the rooms engine's `views()` — VISION's
    "the leak checks move into the kit and are mandatory there", one phase early.
  - media reads `Views` (`ArtSubject` carries id/name/brief), which is VISION's Phase-4 item
    pulled in: keeping `VisibleScene` alive for media alone would leave two live types for
    one concept, which the plan's ground rules forbid.
- [x] 2. Protocol gains `new_game` and `answer` (Phase 1 deferred both to "when a second
      implementation drives them"). `begin_game` keeps only the envelope checks; the rooms
      body moves into the engine's `new_game`. `consume_answer` routes a chosen option
      through `engine.answer` instead of looking the tool up itself.
- [x] 3. `GameService.engine` becomes `AnyEngine`, with one `legacy` narrowing property for
      growth and player actions (same pattern as Phase 1's `Game._legacy`, dies in Phase 3).
- [x] 4. The hostile engine in `tests/hostile/`: one resource, two procedures, no rooms
      concepts, driven through `GameService` — begin, a turn with `FunctionModel`, save,
      restore, view render, a `PlayerPrompt` round-trip.

## Decisions

- No golden regeneration this phase (PLAN allows it only in Phases 0/1/3), so every
  prompt-shaped change is a pure move.
- `Resolution` (facts + rules-notes) is NOT introduced here: engines already write notes onto
  `Game.notes`, which is kernel-owned and payload-agnostic, so the hostile engine needs no
  new channel. Phase 3 owns `Resolution`.
- `player_actions` stays off the protocol: `PlayerAction` lives in `engines/core.py`, and
  importing it into `aidm/kernel` would make the imports cyclic. The hostile engine declares
  none. Phase 3 moves the type and the member together.
- The kernel's `entity_discovered` -> `when_reached` branch stays: moving it into
  `change_world` would turn a readback line into a persisted note, which changes the next
  turn's prompt and needs an eval. It is inert for a non-rooms engine. Phase 3 owns it.

## Landed (items 1-3)

Counts after the kernel inversion: src 9460 (+8), tests 5762 (+3), evals 1817 (unchanged).
`uv run pytest` 285 passed; ruff check, ruff format and basedpyright clean; no fixture file
moved, so the director and narrator prompts render byte-identical text.

Deviations, with reasons:

- **`Scenario`, `ScenarioPayload`, `Character` and `CharacterPayload` moved from
  `content/model.py` to `state/model.py`.** The protocol's `new_game(scenario, character)`
  must name those types, but `kernel` sits below `content` in the layer flow, so the
  package-boundary test forbids `kernel -> content`. Widening the parameters to `BaseModel`
  breaks protocol contravariance against the concrete engine. Per CLAUDE.md the smallest
  shared types moved down beside `Game`, which already carries the same "dies with the
  Phase-3 port" note. `content/model.py` keeps only `AuthoringTool`/`AuthoringBrief`.
- `Engine.new_game` returns `S` on the protocol, not the rooms payload: the kernel cannot
  name a rooms type, and `S` is the engine's own declared state.
- `test_scene.py` became a test of `Engine.views`: the reveal check has no standalone entry
  point now that `revealed_from` is gone. Both intents kept.
- `spoken()` raises when a line names an id outside the view's roster; `speakers_refusal`
  gates every path that reaches it.

## Review (opus, working tree)

No blocking bug. The reviewer checked out HEAD in a second worktree and diffed rendered
output from both trees, so the two load-bearing claims are measured, not asserted:

- **Director and narrator prompts are byte-identical**, including four threads with mixed
  statuses and unsorted ids, and a resolved-only world.
- **Media is byte-identical**: same cache key, same three prompts in the same order, same
  reference lists and ratios.

The secrecy check now also runs on the director path and at `Turn.begin`, so its coverage
grew; no call site lost it. The speaker roster is exactly the old `present_entity_ids`.

Taken (applied in the polish pass): fold the three thread helpers into one; drop the no-op
`EntityId` cast in media; record player actions through the views and delete
`Game.player_speaker`; one shared tool lookup behind `Engine.restored` and `Engine.answer`;
code mode checks speakers against the draft its lines are recorded against, not the
committed state; `Turn.speaker` becomes required and its dead fallback goes.

Refused, with reasons:

- **Point the UI's four `state.pending` reads at `PlayerView.prompt`.** The four reads sit in
  four separate timer-driven callbacks, so each would build a whole scene per UI tick.
  VISION gives the UI-onto-views move to Phase 4, which does it with one view per render
  pass. `PlayerPrompt` is not a second implementation: `Game.pending` stays the one source
  of truth and the view is its projection.
- **Delete `GameService.scene()`.** It is one honest name for the current narrator view,
  used three times; inlining it saves two lines and reads no better.

`PendingOption.name`/`args` gained defaults so a non-rooms engine can build an option it
resolves by id. Kept: forcing every engine to write `name=""` would be a required field half
the engines fill with a lie, and Phase 3 deletes both fields. The rooms guarantee that an
option names a real tool now lives in `Engine.restored` and `Engine.answer` rather than in
the model; no validate-time check was added, because an option with no name is engine-code
error, not bad data.

## Phase 2 closed

Counts at phase end: **src 9452** (phase start 9452, net 0 — the estimate was 0), tests 6044
(+285, estimate was +150; the engine is a whole second implementation, not a fixture),
evals 1817 (unchanged).

`uv run pytest` 289 passed. `ruff check`, `basedpyright` clean. `ruff format --check` is
clean over every tracked file; it reports only the untracked `NEW_VISION.md`, which this
phase did not write and did not touch. No golden fixture moved, so no eval run was owed.
`uv run aidm` serves the home page; the one skipped save is the stale pre-envelope save
Phase 1 already recorded.

The engine is `SignalEngine` in `tests/hostile/test_hostile_engine.py`: one integer resource,
a stage, two `director_tool` procedures (one spends and tells, one opens a two-option
`PendingDecision`), and `answer` resolving by option id. No entity, location, exit, party,
trait or sheet. Four tests: a turn through `GameService.submit` with both roles stubbed by
`FunctionModel`, the `PlayerPrompt` round-trip back through `answer`, restore over the same
`FileStore`, and one assertion that reading `state.world` raises — the kernel drove a payload
holding no world.

It needed exactly one production change of its own (`PendingOption.name`/`args` defaults),
which is the gap the phase existed to find. Everything else it needed was the inversion in
items 1-3.

Three rooms couplings survive in the kernel, all inert for a non-rooms engine and all owned
by Phase 3. Recorded so the port does not have to rediscover them:

- `state/tools.py:apply_to_draft` — the told-fact gate reads `draft.world.find(...)`; safe
  only because a hostile fact leaves `entity_id` None.
- `turn/run.py:_reached` — reads `when_reached`; safe only because no hostile fact has kind
  `entity_discovered`.
- `app/runtime.py:GameService.legacy` — `offers`, `act` and growth raise for a non-rooms
  engine; safe only because the hostile scenario sets `grows=False` and the test calls
  neither. This is the declared shim, not a surprise.

Phase 3 note: the `src <= 9076` gate still leans on Phase 3, which now has to delete both the
Phase-1 shim and this phase's `legacy` narrowing.
