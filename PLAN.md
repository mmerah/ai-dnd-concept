# PLAN — two measured cuts before MVP0: dispatch, companion speech

Two phases, in order. **Phase 1** folds the one-caller `apply_change` dispatch into `change_world`
where it only forwards (proposal 5). **Phase 2** moves the companion's words into the narrator's
own answer and deletes the separate background run (proposal 3).

**Both were built end to end and measured before this plan was written**, on a scratch worktree
off `f81dfc1`, each to a green full check. The line counts below are measurements, not estimates.
Proposal 1's journal was built the same way, measured at **+16 lines**, and is refused; proposals
2 and 4 are out of scope. All three reasons are at the end.

Self-standing: an implementer needs this file, `CLAUDE.md` and the code. `PROPOSALS.md` stays in
the repository as the evidence document behind it; every claim this plan relies on was re-checked
against the working tree and the line numbers below name that tree.

`src` is **10,080** lines at the start of Phase 1 and **10,046** at the end of Phase 2, Python and
JavaScript together, the vendored dice library excluded:

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

`PROPOSALS.md`'s LOC ranges do not survive being built. All three were implemented to a green
full check and counted; every range came in far below its estimate, and one came in positive:

| Proposal | `PROPOSALS.md` estimate | Built and measured | Gates |
| --- | ---: | ---: | --- |
| 5, dispatch | −8 to −25 | **−9** | 564 pass, all four green |
| 3, companion | −80 to −140 | **−25** | 562 pass, all four green |
| 1, journal | −150 to −350 | **+16** | `src` clean, tests not finished |

Three findings behind those numbers:

1. **The journal cannot pay for itself, because it does not replace a sequence — it adds one.**
   It removes 42 lines of duplicate storage (`RoomWorld.record/records` 12,
   `SceneWorld.record/records` 13, `World.records/record/exchanges` 9,
   `Engine.record/history/scenes` 8). But `Visit` and `SceneRun` must stay: the trail reads
   visits, and `last_seen`, the offer and the cast read runs. So after the move there are two
   parallel sequences — world visits/runs and journal blocks — that code must keep 1:1 by hand,
   at `RoomEngine.move` and `SceneEngine.install`. Built minimally (three operations, no
   `enrich`) it measured **+24**; with `Visit` further collapsed to a bare id list, **+16**.
2. **Deleting 152 lines of companion machinery buys back only 25.** Phase 2 removes the whole
   background run and its prompt, then spends 116 lines on the typed `Suggestion` and `Proposal`,
   the extended refusal, the draw, the prompt section and the `final` plumbing. The deletion is
   real; the net is not what the document promised.
3. **Only Tunnel Goons is a room engine.** Breathless, Loner and 24XX are all `SceneEngine`, so
   the document's slice 1 already converts both family bases; its later slices add no new family.

## Decisions

1. **The order is 5, then 3.** Not the document's order. Phase 1 touches nothing Phase 2 touches,
   so it lands first and green.
2. **A phase that does not measure net-negative does not land.** `src` is counted before and
   after every phase, and the count goes in `PROGRESS.md`. This is how proposal 1 was refused:
   it was built, it measured +16, it was dropped. The same rule holds for these two if a review
   makes them grow.
3. **The companion's words ride the last narrator call of the submission.** Which call that is
   is decided without proposal 2: in `_turn` the narration is final when
   `turn.draft.generation is None`; in `_generate` it is final only when `_generate` was called
   from the tail of `_turn`, never from `act`'s pre-generation route. One `final: bool` parameter
   carries it. Proposal 2 later deletes that parameter; roughly eight lines are knowingly
   temporary.
4. **The selection draw stays where it is in the RNG order.** The existing ordered d10 against
   `INTERJECTION_ODDS[chattiness]` on `self.rng`, drawn after every mechanic has landed and
   before the final narrator call. `Engine.advance` takes no `Random`, so the seeded trace is
   unchanged. No second RNG is created.
5. **One companion path is lost and that is accepted.** Today a member may speak after a
   worldsmith failure, which closes an exchange with no narration. With the words inside the
   narrator's answer, a submission that never narrates has nobody to speak. No fallback is built
   to keep that path: a fallback would keep the machinery this phase is for deleting.
6. **The narrator's answer carries one optional typed value, not loose fields.** `Suggestion`
   on `Narration` (speaker id, lines, proposal) and `Proposal` on `Exchange` (speaker name,
   text). `Exchange.proposal: str` becomes `Exchange.proposal: Proposal | None`, so the
   proposing speaker is stored and `ui/game.py` stops guessing at `lines[0].speaker`.
7. **The schema is one shape, always.** `Narration.suggestion` is always present and optional.
   When no member was selected the refusal check requires it to be `None`. No second dynamic
   schema is built for the eligible and ineligible cases.
8. **24XX keeps both dispatch methods.** Every arm must reach `_succession()` after its
   mutation; that postcondition stays one explicit statement in `change_world`. The fold in
   Phase 1 applies only where `change_world` does nothing but forward.
9. **The save changes once and is not migrated.** Phase 2 turns `Exchange.proposal` from a
   string into `Proposal | None`. The current policy stands: no version field, a stale save is
   invalid, and the stale-save warning keeps working. Fixtures are regenerated in that phase.

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

**Measured: −9 lines** (10,080 → 10,071), 564 tests passing, all four gates green. Two lines per
engine from the fold, plus one dead `WorldChange` import each — that annotation was its only
user. 24XX keeps both methods by decision 8. Nothing the model sees changes: the four
`master_tools.json` goldens and the four `turn/*.json` fact goldens are byte-identical.

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
3. **Drop the three dead imports.** With `apply_change` gone, `WorldChange` has no user left in
   any of the three engine modules. Ruff and basedpyright both flag it; delete the import line.
4. **Move the one direct test caller.** `tests/loner3e/test_engine.py:217` calls
   `ENGINE.apply_change(draft.payload, Reveal(...))`. It becomes
   `change(ENGINE, draft, "reveal", entity_id=MAP)` — the helper is already imported in that file
   at line 5, so this also retires the file's `Reveal` import. No alias is left behind.
5. **Regenerate nothing.** `tests/core/fixtures/schemas/*/master_tools.json` must come back
   byte-identical: the tool names, order and argument schemas do not change. If a golden schema
   moves, the fold changed the public surface and is wrong.

### Done when

- `change_world` is the only dispatch entry in Breathless, Loner and Tunnel Goons; 24XX still has
  both, and `_succession` still runs after every successful arm.
- The four `master_tools.json` goldens are unchanged, and so are `tests/core/fixtures/turn/*.json`.
- 24XX death-and-succession and decision-replay tests pass untouched.
- Full check green. `src` is 10,071.

---

## Phase 2 — the companion speaks inside the narration

**Measured: −25 lines** (10,071 → 10,046), 562 tests passing, all four gates green. 152 lines
deleted, 116 added: `app/runtime.py` −134/+56, `turn/context.py` −48/+22, `core/play.py` +30 net,
`core/views.py` +21 net, `ui/game.py`, `turn/run.py` and `engines/seam.py` a handful each, and
`turn/prompts/interjection.md` (11 lines, uncounted) replaced by `aside.md` (10).

The RNG claim is verified, not argued: after this phase the four `tests/core/fixtures/turn/*.json`
fact goldens are byte-identical. Only the four `narrator.txt` prompt goldens move, and only
because the schema gained `Suggestion` and the prompt gained the aside section.

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
   `turn/prompts/interjection.md`; add `turn/prompts/aside.md`, the same text rewritten in the
   third person about a member the narrator writes rather than plays. `render_narrator` takes
   `member: Subject | None` and `sheet: Rows = ()` and calls a small `_aside(member, sheet)`
   that returns `()` or one `ONE OF THEM MAY SPEAK UP` section. When it is `None` the section is
   absent and the schema still shows `suggestion`. `_picture`'s `reader` parameter goes with it:
   the deleted renderer was its only caller, so `lead, beside` collapses to its constants.
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
   `(lines, proposal)` so the caller can close the exchange with both. Carry the same member
   across the one corrective retry; never draw twice.
   **`_companion` takes the draft, not `self.state`.** The committed game does not yet hold
   whoever joined, died or left this turn; reading it silently skips a member who joined on the
   same submission. This was caught by the 24XX golden turn, whose script joins Vessa Rune.
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
- Full check green; `src` is 10,046.

---

## Not in this plan, with the reason

- **Proposal 1, the shared journal — built, measured at +16 lines, refused.** `Game` gained a
  typed `Journal` of `Block`s with exactly three operations; `Visit.exchanges`,
  `SceneRun.exchanges`, `World.record/records/exchanges` and the `Engine` forwarding chain all
  went; `render_extension` was simplified to take the draft along the way; `src/` type-checked
  clean. It still came out **+24**, and **+16** with `Visit` collapsed to a bare id list. The
  reason is structural, not a matter of effort: the world must keep `visits` and `runs` for the
  trail, `last_seen`, the offer and the cast, so the journal does not replace a sequence, it adds
  a second one that `RoomEngine.move` and `SceneEngine.install` must keep in step by hand. The
  198 test failures it caused were all mechanical (a missing `journal` field in fixture dicts),
  so the number would not have improved by finishing them. Revisit it only with proposal 2, where
  the checkpoint gives the journal an operation the world genuinely cannot carry.
- **Proposal 2, one player-submission pipeline.** The largest change in the document: new failure
  semantics, a crash checkpoint, a revision counter on `Observed` because enriching an entry
  leaves `facts` and `exchanges` unmoved, a per-entry fact cursor so prose does not toss the same
  dice twice, and two-tab tests. It earns its own plan. Phase 2's `final` parameter is the one
  thing here it will delete, and proposal 1 should be reconsidered as part of it.
- **Proposal 4, deterministic hiring.** Its gate is at least 60 net lines removed after
  production gates, against a measured 180 removed and 84 added in a scratch prototype that was
  not type-checked. It also narrows what a recruit can be — 24XX loses its invented hindrances,
  Tunnel Goons its mixed 2/1 spreads. That is a game decision to take deliberately, not a
  simplification to slip into a cleanup.
- **The shared presence, party and panel layer** (`PROPOSALS.md` proposal 1, slices 2 and 3).
  If slice 1 measures +16, a larger extraction over the same code has no evidence behind it.
- **The `loot_check` bypass.** `breathless/engine.py:319-322` honours a `granted` and `choice`
  the master should never send. Real, reproduced from source, and out of scope: `PROPOSALS.md`
  says explicitly that dispatch cleanup must not be claimed to fix it. It needs its own decision
  about where a private resolution boundary lives.
- **Renaming `interjection` throughout.** The concept survives as the companion's suggestion;
  `INTERJECTION_ODDS` keeps its name because the odds are unchanged and a rename would touch
  every test for nothing.
- **A save version field or a migration path.** The policy stands: a stale save is invalid.

## What these two phases are worth

−34 lines on 10,080, or 0.34%. That is the honest total, and it is not why either phase is worth
doing: Phase 1 removes a hop that reads as ceremony, and Phase 2 removes a whole concurrent path
— a second narrator spawn, a cancellable task, a stale-result check and a synthetic exchange —
in exchange for one optional field. Neither is a simplification measured in lines. `PROPOSALS.md`
is right that "the completion criterion is a smaller, understandable implementation"; on this
evidence the understandable half is the part that is actually available.
