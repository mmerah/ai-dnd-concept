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
