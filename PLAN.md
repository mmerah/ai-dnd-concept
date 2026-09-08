# PLAN — three cuts before MVP0: dispatch, companion speech, the journal

Three phases, in order, cut from `PROPOSALS.md` and re-measured against the code on 2026-09-08.
**Phase 1** folds the one-caller `apply_change` dispatch into `change_world` where it only
forwards (proposal 5). **Phase 2** moves the companion's words into the narrator's own answer and
deletes the separate background run (proposal 3). **Phase 3** gives `Game` one typed journal and
deletes the two families' duplicate exchange storage (proposal 1), **under a gate**: it is kept
only if the measured diff is net-negative.

Proposals 2 and 4 are not in this plan. Their reasons are at the end.

Self-standing: an implementer needs this file, `CLAUDE.md` and the code. `PROPOSALS.md` stays in
the repository as the evidence document behind it; every claim this plan relies on was re-checked
against the working tree and the line numbers below name that tree.

`src` is **10,080** lines at the start of Phase 1, Python and JavaScript together, the vendored
dice library excluded:

```bash
find src \( -name '*.py' -o -name '*.js' \) -not -path '*/lib/*' | xargs cat | wc -l
```

## What was verified before this plan was written

Every measurable claim in `PROPOSALS.md` reproduces. Recorded here so no phase re-does the work:

- The baseline is exact: 10,080 total; `engines` 5,239; `ui` 1,913; `app` + `config.py` 1,712;
  `core` + `turn` 1,216.
- The three hire-specific `advance()` overrides span exactly 20, 29 and 24 lines
  (`tunnelgoons/engine.py:156-175`, `breathless/engine.py:195-223`,
  `twentyfourxx/engine.py:303-326`).
- All four engines carry `change_world` and `apply_change`. Three only forward; 24XX alone adds
  `_succession()` after the mutation. One test calls `apply_change` directly
  (`tests/loner3e/test_engine.py:217`).
- The interjection machinery is exactly as described: `GameService.interject`
  (`runtime.py:166-212`), `hush` (160-164), `_speaking` (75), `Interjection`
  (`core/play.py:44-59`), `interjection_refusal` (`core/views.py:124-131`),
  `render_interjection` (`turn/context.py:60-78`), `INTERJECTION_MARK` (`runtime.py:36`) and
  `turn/prompts/interjection.md`.
- `ui/game.py:236` does read the proposing speaker off `exchange.lines[0].speaker`.
- `Observed` counts `facts` and `exchanges` (`ui/game.py:53-56`) and `_landed` (491) reads a new
  exchange as a closed one.
- The role-order table holds. More map is worldsmith, master, narrator, because
  `RoomEngine.advance` returns `((), None)` and `_generate` therefore does not narrate before
  `act` runs the turn. Scene departure is master, narrator, worldsmith, narrator.
- `Engine.advance` takes no `Random`, so nothing consumes the RNG between the master's last tool
  call and the end of the submission. Phase 2 depends on this.
- The `loot_check` gap is real: `breathless/engine.py:319-322` returns the master's own `granted`
  and `choice` without rolling, though `tools.py:85` tells the model to leave them null. It is
  **not** in this plan; see the end.

Two findings revise `PROPOSALS.md` downward. They set Phase 3's gate and both phase targets:

1. **The journal alone is not a reduction.** The code it removes is 42 lines:
   `RoomWorld.record/records` 12 (`rooms/world.py:384-395`), `SceneWorld.record/records` 13
   (`scenes/world.py:125-137`), `World.records/record/exchanges` 9 (`base.py:118-126`), and
   `Engine.record/history/scenes` 8 (`seam.py:171-178`). A `Journal` that carries the two
   families' different projection rules costs at least that. The 150-350 estimate belongs to the
   broader shared-world extraction, which `PROPOSALS.md` itself gates as conditional.
2. **Only Tunnel Goons is a room engine.** Breathless, Loner and 24XX are all `SceneEngine`. So
   the document's slice 1 (Tunnel Goons and Breathless) already converts both family bases;
   slices 2 and 3 add no new family, only the two remaining scene engines and the optional
   presence work.

## Decisions

1. **The order is 5, then 3, then 1.** Not the document's order. Phase 1 is a one-hour cleanup
   that touches nothing the other two touch, so it lands first and green. Phase 2 is
   self-contained and deletes the most code, so it lands before the phase that might be refused.
   Phase 3 is last because it is the only one that can fail its own gate.
2. **The journal is built with the operations that have callers today, and no others.**
   Append an exchange, open a block, set the previous block's recap. **Not** "enrich a
   checkpointed exchange": that operation exists only for proposal 2's crash checkpoint, and
   proposal 2 is not in this plan. Building it now is building for a future need.
3. **Phase 3 is gated on its own diff.** `src` is counted before and after. If the phase is not
   net-negative once the forwarding chain is deleted, it is reverted and `PROGRESS.md` records
   the measurement and the refusal. A neutral abstraction is not kept on the promise of a later
   phase.
4. **The companion's words ride the last narrator call of the submission.** Which call that is
   is decided without proposal 2: in `_turn` the narration is final when
   `turn.draft.generation is None`; in `_generate` it is final only when `_generate` was called
   from the tail of `_turn`, never from `act`'s pre-generation route. One `final: bool` parameter
   carries it. Proposal 2 later deletes that parameter; roughly eight lines are knowingly
   temporary.
5. **The selection draw stays where it is in the RNG order.** The existing ordered d10 against
   `INTERJECTION_ODDS[chattiness]` on `self.rng`, drawn after every mechanic has landed and
   before the final narrator call. `Engine.advance` takes no `Random`, so the seeded trace is
   unchanged. No second RNG is created.
6. **One companion path is lost and that is accepted.** Today a member may speak after a
   worldsmith failure, which closes an exchange with no narration. With the words inside the
   narrator's answer, a submission that never narrates has nobody to speak. No fallback is built
   to keep that path: a fallback would keep the machinery this phase is for deleting.
7. **The narrator's answer carries one optional typed value, not loose fields.** `Suggestion`
   on `Narration` (speaker id, lines, proposal) and `Proposal` on `Exchange` (speaker name,
   text). `Exchange.proposal: str` becomes `Exchange.proposal: Proposal | None`, so the
   proposing speaker is stored and `ui/game.py` stops guessing at `lines[0].speaker`.
8. **The schema is one shape, always.** `Narration.suggestion` is always present and optional.
   When no member was selected the refusal check requires it to be `None`. No second dynamic
   schema is built for the eligible and ineligible cases.
9. **24XX keeps both dispatch methods.** Every arm must reach `_succession()` after its
   mutation; that postcondition stays one explicit statement in `change_world`. The fold in
   Phase 1 applies only where `change_world` does nothing but forward.
10. **Saves change twice and neither is migrated.** Phase 2 changes `Exchange.proposal`;
    Phase 3 moves exchanges out of the world payload. The current policy stands: no version
    field, a stale save is invalid, and the stale-save warning keeps working. Fixtures are
    regenerated in the phase that changes them.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action on the files it names. Finish it before the next.
2. **Change a shape and its tests in the same step.** One test per new behaviour; no test of
   prose or wiring. A test of a deleted behaviour is deleted with it, never kept alive by
   stubbing. Tests never start a process; roles are stubbed with `ScriptedSpawner`.
3. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file. The command is at the top of this plan.
4. **If a phase runs half again past its target, stop and say so.** Never pad.
5. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
6. **One commit per phase.** The full check is green before the commit. Never leave two versions
   of one thing alive at a commit.
7. **Review each phase adversarially against its staged diff before the commit.**
8. **The standing limits hold.** Imports flow `core <- engines <- turn <- app <- ui`; no `Any`
   outside the existing generic-state exception; every `__init__.py` empty; `Refusal` stays the
   one message-bearing exception; state models mutable, value models frozen; validate at every
   boundary with strict Pydantic V2.
9. **Delete, do not preserve.** A method left with no caller goes in the step that removed its
   last caller. No permanent alias is kept for a test; the test moves to the surviving call.

---

## Phase 1 — the dispatch that only forwards

Target: **−6 lines** in `engines/`. Not the 8-25 of `PROPOSALS.md`: the fold saves two lines per
engine and 24XX keeps both methods by decision 9. The gain is one less hop to read, not LOC.
Nothing the model sees changes.

### Steps

1. **Fold `apply_change` into `change_world` in the three engines that only forward.**
   `breathless/engine.py:181-193`, `loner3e/engine.py:162-182`, `tunnelgoons/engine.py:146-155`.
   The surviving method is `change_world(self, draft, args, _rng)`; its body opens
   `world = draft.payload` and matches on `args.change`; the arms and their order are untouched,
   `shared_change` stays the `case _` fallback. The `apply_change` definition and the forwarding
   `return` line go.
2. **Leave 24XX alone.** `twentyfourxx/engine.py:247-276` keeps `apply_change` and
   `change_world`, so `facts = ...; self._succession(draft); return facts` stays one readable
   postcondition. Add nothing; this step is a decision recorded, not an edit.
3. **Move the one direct test caller.** `tests/loner3e/test_engine.py:217` calls
   `ENGINE.apply_change(draft.payload, Reveal(...))`. It goes through the tool instead, with the
   helper that already exists at `tests/support/table.py:84`. No alias is left behind.
4. **Regenerate nothing.** `tests/core/fixtures/schemas/*/master_tools.json` must come back
   byte-identical: the tool names, order and argument schemas do not change. If a golden schema
   moves, the fold changed the public surface and is wrong.

### Done when

- `change_world` is the only dispatch entry in Breathless, Loner and Tunnel Goons; 24XX still has
  both, and `_succession` still runs after every successful arm.
- The four `master_tools.json` goldens are unchanged, and so are `tests/core/fixtures/turn/*.json`.
- 24XX death-and-succession and decision-replay tests pass untouched.
- Full check green. `src` is 10,074.

---

## Phase 2 — the companion speaks inside the narration

Target: **−50 to −100 lines**, mostly in `app/runtime.py`, `core/play.py`, `core/views.py` and
`turn/context.py`. Lower than the document's 80-140: the removals total about 104 lines, and the
typed suggestion, the refusal check, the selection helper and the temporary `final` parameter add
back about 50.

The companion's line now arrives with the narration instead of a second later. There is no second
narrator spawn, nothing to cancel, and no synthetic exchange.

### Steps

1. **`core/play.py` — the two typed values.** Add `Suggestion(Frozen)`: `speaker_id: EntityId`,
   `lines: tuple[Line, ...]`, `proposal: str = ""` with the existing `_stripped` validator moved
   onto it. Add `suggestion: Suggestion | None = None` to `Narration`, described for the model as
   the one optional companion aside. Add `Proposal(Frozen)`: `speaker: str` and `text: str`, both
   `min_length=1`. Change `Exchange.proposal: str = ""` to `proposal: Proposal | None = None`.
   Delete `Interjection` (44-59).
2. **`core/views.py` — one refusal, not two.** Delete `interjection_refusal` (124-131). Extend
   `narration_refusal` to check the suggestion: `None` is legal; when present its `speaker_id`
   must equal the member the code selected, every line's `speaker_id` must be that same member,
   a non-empty `proposal` requires at least one line, and the member must be a living, visible
   speaker. When no member was selected, a non-`None` suggestion is refused. The selected member
   is passed in, so the check is a method on the view taking `EntityId | None`.
3. **`turn/context.py` — one prompt, not two.** Delete `render_interjection` (60-78) and
   `turn/prompts/interjection.md`. `render_narrator` takes the selected member as
   `Subject | None` and, when it is set, adds one section naming them, their sheet rows and what
   an aside is for — the text of `interjection.md`, rewritten in the second person about a member
   the narrator writes rather than plays. When it is `None` the section is absent and the schema
   still shows `suggestion`.
4. **`engines/seam.py` — `close` carries the value.** `close(..., proposal: str = "")` becomes
   `close(..., proposal: Proposal | None = None)` and passes it to `Exchange`.
5. **`app/runtime.py` — the fold.** Delete `interject` (166-212), `hush` (160-164), the
   `_speaking` field and its comment (74-75), the `create_task(self.interject())` block at the
   end of `_turn` (152-158), and the `hush()` calls at 134, 336 and 441. Delete
   `INTERJECTION_MARK` (36) and drop it from `MARKS` (37). Keep `INTERJECTION_ODDS` and
   `_background`: illustration and speech still need the task set. Add one private
   `_companion(self) -> Person | None` holding the existing gate and draw, unchanged — the
   ordered walk over `world.members()` with `rng.randint(1, 10) <= INTERJECTION_ODDS[chattiness]`,
   returning `None` when `interjections` is off, a decision is pending, or the game is over. Call
   it once per submission, immediately before the final narrator call, and pass the member to
   `_narrate`, which forwards it to `render_narrator` and to the refusal check, and which returns
   the answer whole so the caller can read `suggestion`. Carry the same member across the one
   corrective retry; never draw twice.
6. **`app/runtime.py` — which narration is final.** `_generate` takes `final: bool`. `_turn`
   calls `_generate(final=True)` from its tail and narrates with a companion only when
   `turn.draft.generation is None`. `act` calls `_generate(words, final=False)` for the More map
   route, because `_turn` follows it. Mark the parameter with a one-line comment naming it as
   proposal 2's to delete.
7. **Flatten the suggestion into the exchange.** Where the final narration is closed, append the
   validated suggestion's lines to the narration's lines in order, so `NarratorView.spoken`
   resolves the speaker exactly as it does for dialogue, and pass
   `Proposal(speaker=<member name>, text=<proposal>)` when the proposal is non-empty. One
   exchange, one speech request, one set of cards.
8. **`ui/game.py` — read the stored speaker.** `standing_proposal` (602-608) reads
   `newest.proposal` as the optional value; the label at 236 reads `proposed.proposal.speaker`
   and `proposed.proposal.text`. Delete the `lines[0].speaker` guess. The Accept button still
   submits the text as ordinary player words through `session.play`.
9. **Tests.** In `tests/core/test_game_service.py`, delete the four `await
   table.service.interject()` tests and the stale-interjection and in-flight cases (298-392):
   they describe a background run that no longer exists. Replace them with, on the single
   narrator call: quiet, normal and chatty selection; no party; interjections disabled; a
   decision pending; game over; a member who dies or leaves in the same turn; an empty
   suggestion; a suggestion naming the wrong speaker; a proposal with no lines; a proposal after
   ordinary narration; and Accept submitting it. Assert exactly one narrator spawn on success
   and one corrective retry on an invalid answer. Keep
   `tests/core/test_turn.py:124`'s disabled-interjections case, pointed at the new path. In
   `tests/core/test_views.py`, rewrite the `interjection_refusal` tests (132-140) as
   `narration_refusal` suggestion tests. In `tests/core/test_golden_turn.py`, delete the
   interjection golden block (45-51) and
   `tests/core/fixtures/prompts/twentyfourxx/interjection.txt`; the four `narrator.txt` goldens
   are regenerated, and 24XX's gains the companion section.
10. **Play it.** `uv run aidm` through a provider: one ordinary turn with a party, one scene
    departure, one More map. Read that the companion's line sits in the same message as the
    narration and that Accept still sends their words.

### Done when

- One narrator call per submission on success; no `_speaking`, no `hush`, no `Interjection`, no
  `interjection.md`, no `INTERJECTION_MARK`.
- A companion's line and proposal live on the same exchange as the narration, and the proposing
  speaker is read from the stored `Proposal`, never from a line's position.
- A submission that never narrates produces no companion line, and `PROGRESS.md` records that as
  the one intended loss.
- The seeded trace of `tests/core/fixtures/turn/*.json` is unchanged: the draw did not move in
  the RNG order.
- Full check green.

---

## Phase 3 — one journal, under a gate

Target: **net-negative or reverted.** The duplicate storage is 42 lines (measured above); the
replacement must come in under that once the forwarding chain is deleted. Behaviour does not
change in this phase.

**The gate**: count `src` before the first edit and after the last. If the phase is not
net-negative, revert it, write the measurement and the refusal in `PROGRESS.md`, and stop. Do not
keep it against a later phase that might use it. Decision 3.

### Steps

1. **`core/model.py` — the journal.** Add `Block(Mutable)`: `title: str`, `focus: str = ""`,
   `recap: str = ""`, `exchanges: list[Exchange]`, and `empty: bool` meaning "drop this block from
   the record once it is not the current one" — the one flag that encodes the two families'
   difference, set by the caller that opens the block. Add `Journal(Mutable)` with
   `blocks: list[Block]` and exactly three methods: `append(exchange)` onto the last block,
   `open(title, focus, *, empty)` appending a block, and `recap(text)` setting the previous
   block's recap. Add `journal: Journal` to `Game`. No `enrich`; decision 2. A journal with no
   block has nothing to append to, so `Engine.begin` opens the first one from the starting place
   or scene, and a validator refuses a game whose journal is empty.
2. **`engines/seam.py` — the engine talks to the journal.** `record` appends to
   `state.journal`; `history` flattens it; `scenes` projects it, dropping a completed block whose
   `empty` is true and which holds no exchanges. Delete the forwarding into `world()` (171-178
   becomes journal calls, not world calls). `Engine.close` is unchanged above this.
3. **`engines/base.py` — the abstracts go.** Delete `records`, `record` and `exchanges` from
   `World` (118-126). `members` stays abstract.
4. **Tunnel Goons: the room family.** Delete `Visit.exchanges` (`rooms/world.py:35`) and
   `RoomWorld.record/records` (384-395). `RoomWorld.move` and `attach` — wherever a visit begins
   — call `journal.open(place.name, place.brief, empty=True)`, so a completed visit with no
   exchanges still drops out of the record and the current one is still kept. `visits` stays: the
   trail needs it. This freezes a room's title and focus at the moment the block opens, where
   `records()` reads them live off the place today; that is safe, and checked — nothing under
   `engines/` ever assigns `.name`, `.brief` or `.description` on a `Place` after it is built.
5. **The three scene engines.** Delete `SceneRun.exchanges` (`scenes/world.py:51`) and
   `SceneWorld.record/records` (125-137). `SceneWorld.apply_scene` calls
   `journal.open(title, focus, empty=False)` and `journal.recap(...)` where the worldsmith's
   recap closes the old scene. `runs` stays: `last_seen` walks `run.here`, and the offer and cast
   live there. Loner's `leaving()` refill and 24XX's succession are untouched.
6. **Nothing else moves.** No shared presence layer, no shared party helper, no shared panel
   assembly — `PROPOSALS.md`'s slices 2 and 3 are not in this phase. Directed ways, item holders,
   scene cast and arc, the Loner refill and 24XX leadership all stay exactly where they are.
7. **Fixtures and tests.** `Game`'s stored shape changes: `journal` is new at the top level and
   `payload`'s visits and runs lose their exchanges. Regenerate
   `tests/core/fixtures/turn/*.json` and any saved-game fixture; the stale-save warning path is
   tested and keeps working. Add behavioural comparisons, on facts and public projections rather
   than class names: a return visit to a room already recorded; a departed NPC's `last_seen`; the
   party moving; a death; 24XX succession; the narrator's history still carrying no hidden recap
   while the master's does (`told_history` against `render_history`).
8. **Measure and decide.** Count `src`. Net-negative: commit. Not: revert, record, stop.

### Done when

- `Game.journal` is the one authoritative log; no `Visit.exchanges`, no `SceneRun.exchanges`, no
  `World.record/records/exchanges`, and no compatibility forwarding left alive.
- Room history still omits an empty completed visit and still keeps the current one; scene
  history still carries its recaps and its grouping.
- `told_history` still excludes hidden recaps and `render_history` still reaches them.
- The public projections and the facts of a played turn are unchanged, on all four engines.
- Full check green, and `PROGRESS.md` carries the before and after counts either way.

---

## Not in this plan, with the reason

- **Proposal 2, one player-submission pipeline.** The largest change in the document: new failure
  semantics, a crash checkpoint, a revision counter on `Observed` because enriching an entry
  leaves `facts` and `exchanges` unmoved, a per-entry fact cursor so prose does not toss the same
  dice twice, and two-tab tests. It earns its own plan, written once Phase 3 has measured the
  journal. Phase 2's `final` parameter is the one thing here it will delete.
- **Proposal 4, deterministic hiring.** Its gate is at least 60 net lines removed after
  production gates, against a measured 180 removed and 84 added in a scratch prototype that was
  not type-checked. It also narrows what a recruit can be — 24XX loses its invented hindrances,
  Tunnel Goons its mixed 2/1 spreads. That is a game decision to take deliberately, not a
  simplification to slip into a cleanup.
- **The shared presence, party and panel layer** (`PROPOSALS.md` proposal 1, slices 2 and 3).
  Refused for now by decision 3's logic: the document itself says to stop after the journal if
  the broader layer is larger or harder to read, and nothing yet shows it is not.
- **The `loot_check` bypass.** `breathless/engine.py:319-322` honours a `granted` and `choice`
  the master should never send. Real, reproduced from source, and out of scope: `PROPOSALS.md`
  says explicitly that dispatch cleanup must not be claimed to fix it. It needs its own decision
  about where a private resolution boundary lives.
- **Renaming `interjection` throughout.** The concept survives as the companion's suggestion;
  `INTERJECTION_ODDS` keeps its name because the odds are unchanged and a rename would touch
  every test for nothing.
- **A save version field or a migration path.** The policy stands: a stale save is invalid.
