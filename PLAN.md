# PLAN — one seam, one scaffold, one name per thing

Three phases. Phase 1 is the engine seam and the two families (P1 tail, P2, P4, the engine half of
P6 and P7). Phase 2 is the per-engine scaffold (P3, D5), the platform (P5, D2, D6, the platform
half of P6 and P7, R2, R6, R7, R8) and the tests (P8). Phase 3 is explicit over implicit (R1, R3,
R4, R5, R9): the shapes that were strings, flags and tags. P and D numbers are `PROPOSALS.md`'s
(deleted; `git show 322cc0d:PROPOSALS.md`); R numbers are the second session's reasoning
proposals, approved 2026-09-05: R1 button actions, R2 transition, R3 scene status, R4 job ids,
R5 row types, R6 three names, R7 page accessors, R8 admission, R9 note lifetime. Every decision
letter is applied below and nothing is left to decide; D7 B (show `pack.source` on the create page)
is dropped because it adds code and simplifies nothing. R2 overrides D19 A and R5 overrides round
two's lean on `PanelRow`; the maintainer's approval is the later word. Line numbers are as of
master `e2db974`; find a site by the name quoted beside it (Phases 1 and 2 move Phase 3's lines).
R evidence was read on `fc4d354`; where `e2db974` moved it, the step says so.

## How to work

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Run the four after every step; each step is one action, done in order, tests changed in the same step.
2. Goldens: `AIDM_GOLDEN_REGEN=1 uv run pytest` (exits red by design), then `uv run pytest`, then read every
   changed line. Phase 1 changes only `tests/core/fixtures/schemas/*/master_tools.json`, one line each
   (step 3). Phase 2 changes no fixture. Phase 3 changes no fixture: the golden turns play the four
   one-shots, so THE BOARD's new `[id]` (step 34) never reaches `tests/core/fixtures/prompts/*/master.txt`,
   and no fact in `tests/core/fixtures/turn/*.json` changes shape (R3 and R4 change state, not facts;
   `master.md` and `narrator.md` are untouched). Worldsmith prompts have no golden. Anything else
   changing is a bug.
3. `src` line count, at the start and end of each phase: `find src -name '*.py' | xargs cat | wc -l`.
4. One commit per phase; the phase skill's `PROGRESS.md` entry rides in it (Phase 1 recreates the file).
   Phase 3's one commit makes every save stale (R3, R4); the two land together.
5. Standing limits: fifteen engine tools (plus `commission`), `engines/<id>/` under 2,000 lines, imports
   `core <- engines <- turn <- app <- ui`, no `Any` beyond the `Game[P]` bounds, empty `__init__.py`,
   `ScriptedSpawner` only, `Refusal` the one message; `RoomEngine` stays (D3 C), the four `ChangeWorld`
   classes stay (D5 A), `Turn.commissioned` stays, P9 is not taken. `crossing()` goes in step 13 (R2
   overrides D19 A); `PanelRow` becomes three classes in step 31 (R5 overrides round two's lean); no
   second tool registry (R1): an action is checked against the rows the engine offers.
6. A delete, move or rename lists the grep the orchestrator runs afterwards (`grep -rn <name> src tests
   --include=*.py`) and what it must find.

| phase | what lands | `src` after | about |
|---|---|---|---|
| start | | 9,367 | |
| 1 — the seam and the two families | `*Proposal`, `check_scenario` gone, `CommissionArgs` base + concrete `commission_tool`, one `worldsmith_prompt` in `hub.py`, `on_order_lines`, hub residents moved, `apply_next/apply_job/apply_return`, `install_next/job/return`, the hub forwarders and `Engine.answer` inlined, `Subject.row`, rooms on scenes' lifecycle names | 9,290–9,320 | 9 h |
| 2 — the scaffold, the platform, the tests | concrete `create_character`/`creation_steps`, `items_shown`, Loner/24XX folds and methods; `play`/`move_on` on `Transition` (R2), `Runtime.operation` (R8), `Presentation` + the page's accessors (R7), `save`/`validated`/`revalidated` (R6), prompt constants, `narration_refusal`, `parse` at two boundaries, `Installed` + `FileStore.restore`, `way_on_panel` gone; nineteen tests folded | 9,290–9,320 (R2, R7, R8 add ~30 over the earlier estimate) | 10 h |
| 3 — explicit over implicit | `take_notes` + `extra_notes` (R9), `ActionRow`/`EntityRow`/`InfoRow` (R5), `Action` + `Engine.transition(state, action)` + `check_offered` (R1), `Open`/`Settled`/`Departed` (R3), `Offer.id`/`Job.id`/`job_id` tags/`posted`/`board_unmet` (R4); saves stale | 9,410–9,450 | 8 h |

---

## Phase 1 — the seam and the two families

Split: A then B, sequential (B adopts the shapes A makes; A's steps 2 and 3 include the one-line rooms
edits named there so A ends green).
- A: steps 1–8; owns `engines/seam.py`, `engines/hub.py`, `engines/base.py`, `engines/scenes/**`,
  `engines/rooms/tools.py`, `core/model.py`, `core/views.py`, `turn/run.py`; tests
  `tests/core/{test_hub,test_scenes,test_seam,test_master_tools,test_decisions}.py`,
  `tests/loner3e/{test_worldsmith,test_world}.py`, `tests/breathless/test_worldsmith.py`,
  `tests/twentyfourxx/{test_worldsmith,test_engine,test_create}.py`, `tests/tunnelgoons/test_views.py`,
  and every test whose `from aidm.engines.hub import` step 5 breaks.
- B: steps 9–12; owns `engines/rooms/{engine,world,worldsmith,proposals}.py`,
  `tests/tunnelgoons/test_worldsmith.py`, `tests/core/test_rooms.py`.

1. **P6, scenes (D3 A).** `git mv src/aidm/engines/scenes/drafts.py src/aidm/engines/scenes/proposals.py`;
   rename `SceneDraft→SceneProposal`, `NextDraft→NextProposal`, `JobDraft→JobProposal`,
   `HubDraft→HubProposal`, `ReturnDraft→ReturnProposal`, `CastDraft→CastProposal`,
   `opening_draft→opening_proposal`, `install_cast→install_commission`, and every parameter or local
   named `draft` that holds one of them (`scene_refusal`, `cast_refusal`, `scene_unmet`, `_cast_unmet`,
   `_hub_unmet`, `run_of`, `build_scenario`, `opening_canon`, `apply_scene`, `write_next`'s `model`)
   to `proposal`; `draft` stays for the transactional copy (`draft: G`). `scenes/worldsmith.py:191`
   ("the draft's own `hidden`") reads "the proposal's own"; the `Free:` docstrings at `:38,44` go
   (each is the whole docstring). Test helpers: `_draft`, `_return_draft` (all three scene
   `test_worldsmith.py`) and `_job_draft`, `_next_draft` (24XX only) become `_proposal`,
   `_return_proposal`, `_job_proposal`, `_next_proposal`; `_next_scene` in `tests/loner3e/test_world.py:62`
   becomes `_next_proposal` and builds a `NextProposal` (adds `recap`). Grep: `Draft` under
   `src/aidm/engines/scenes`, `tests/core`, `tests/loner3e`, `tests/breathless`, `tests/twentyfourxx`
   finds nothing; `draft` in `scenes/worldsmith.py` and `scenes/proposals.py` finds nothing.
2. **P1 tail.** Delete `Engine.check_scenario` (`seam.py:190–192`) and its calls (`scenes/engine.py:120`,
   `rooms/engine.py:82`); `check_character` (`seam.py:80`) keeps only the player-id line.
   `Library._check_filed` stays. Tests: delete `tests/twentyfourxx/test_engine.py:103–115` (the two
   `_by_new_game` foreign tests; `tests/core/test_integrity_boundaries.py:94` covers `begin`) and
   `tests/twentyfourxx/test_create.py:101` (`test_preview_character_refuses_foreign_character_type`:
   a payload with no `id` is now a bug, not a refusal); `test_engine.py`'s `SCENARIO_MODELS` import goes
   with them. Grep: `check_scenario` finds nothing; `incompatible` finds nothing.
3. **P2, the commission tool.** In `seam.py` replace the `CommissionArgs` Protocol by
   `class CommissionArgs(Frozen)` with `kind: str`, `brief: str = Field(min_length=20, description=
   "Who or what it is and why the scene needs it, in a few lines.")`, `later: bool = Field(default=False,
   description="True to have it written into the next scene or region instead of now.")` (`kind`
   is first in both families today, so the schema order holds; only `later`'s description unifies).
   `SceneCommission(CommissionArgs)` in `scenes/tools.py` and `RoomCommission(CommissionArgs)` in
   `rooms/tools.py` keep only their `kind: Literal[...] = Field(description=…)` line. `Engine` gains
   class attributes `commission_args:
   type[CommissionArgs]`, `commission_hint: str`, and a concrete
   `commission_tool(self) -> MasterTool[G]: return master_tool(COMMISSION, COMMISSION_BRIEF +
   self.commission_hint, self.commission_args, self.ask_worldsmith)`; the abstract declaration
   (`seam.py:217`) goes. `SceneEngine`: `commission_args = SceneCommission`, `commission_hint` = the
   string after `COMMISSION_BRIEF +` in `scenes/engine.py:208–216`, its `commission_tool` override
   deleted (rooms' override at `rooms/engine.py:208` stays until step 10). Fold `Engine.commission`
   (`seam.py:134–146`) into `ask_worldsmith(self, draft: G, args: CommissionArgs, _rng: Random) ->
   list[Fact]`, text unchanged. Golden: regenerate; `git diff --stat` shows the four
   `master_tools.json` and one changed line each (`later`). Tests: `tests/core/test_turn.py:364`
   ("already on order") holds. Grep: `Protocol` in `seam.py` finds nothing; `\.commission(` finds
   nothing; `def commission_tool` finds one, in `seam.py`.
4. **P2, one worldsmith frame (D1 A).** In `hub.py` add `SURPRISE` (moved from
   `scenes/worldsmith.py:21`), `NO_SOURCE = "(none — write from the world below)"`, and
   `worldsmith_prompt(role: str, *, source: str, history: str, world: Sections, guidance: str,
   intent: str, answer: type[BaseModel], hub: Sections = (), asked: str = "") -> str` rendering, in
   this order: `YOUR ROLE`, `SOURCE MATERIAL` (`source or NO_SOURCE`), `SCENES SO FAR`, `*hub`,
   `*world`, `ENGINE GUIDANCE`, `THE GAME MASTER ASKED FOR` (when `asked`), `WHAT COMES NEXT`,
   `STANDING INSTRUCTION` (`SURPRISE`), `ANSWER WITH`. Delete `scenes/worldsmith.py:135–160`;
   `scenes/engine.py` imports it from `hub` and passes `world=(("THE WHOLE CAST", world.cast_lines()),)`
   in `render_next` and `world=(("THE WHOLE CAST", "(no cast yet — write the people and things this
   scene needs)"),)` in `render_opening`. In `core/model.py` add `Game.on_order_lines(self) -> str:
   return "\n".join(f"- {c.kind}: {c.brief}" for c in self.on_order())` after `on_order`;
   `write_next` (`scenes/engine.py:335–336`) uses it (the scenes' `- a {kind}` spelling goes; no test
   names it). `hub_sections` is not hoisted (a hook per differing part nets no lines). Test,
   `tests/core/test_hub.py`: `worldsmith_prompt` renders `hub` before `world`
   before `ENGINE GUIDANCE` before `WHAT COMES NEXT` before `STANDING INSTRUCTION` (`str.index`).
   Grep: `def worldsmith_prompt` finds `hub.py` and `rooms/worldsmith.py` (until step 11);
   `write from the cast` finds nothing.
5. **P2, the scenes-only residents leave `hub.py`.** Move `GO_HOME`, `HOME_ROW`, `HUB_ROW`, `JOB_DONE` to
   `scenes/world.py`; `HUB_QUESTION`, `ONE_SHOT_OPENING`, `CAMPAIGN_OPENING`, `TAKE_BRIEF`, `AWAY_BRIEF`,
   `WRITE_HUB_SCENE`, `place_unmet` to `scenes/worldsmith.py`; `MIN_JOB` to `scenes/proposals.py`
   (checked: each has callers under `engines/scenes` only). `OFFER_ASK`, `RETURN_BRIEF`, `TAKE_JOB`,
   `OPEN_SUFFIX`, `MIN_RECAP`, `MIN_SUMMARY`, `walk_start`, `named_unmet`, `title_unmet`, `check_kind`
   are shared and stay; `swap_out` is a `Campaign` method and stays. Tests: imports follow
   (`grep -rn "from aidm.engines.hub import" tests` lists the fifteen files);
   `test_place_unmet_refuses_the_wrong_place_for_the_moment` moves to `tests/core/test_scenes.py`.
   Grep: each moved name in `hub.py` finds nothing; `question_heading` is step 8's.
6. **P4, the world.** In `scenes/world.py` replace `apply_scene` (`:301–334`) by
   `apply_next(self, proposal: NextProposal[C]) -> None`, `apply_job(self, proposal: JobProposal[C],
   *, reopening: Job | None) -> None`, `apply_return(self, proposal: ReturnProposal[C]) -> Job`, and
   private `_land(self, proposal: NextProposal[C] | ReturnProposal[C], job: str) -> None` (deep-copies
   the proposal, merges the cast, resolves `present`/`hidden`, marks present known, stamps
   `self.run.recap = proposal.recap`, sets `self.arc`, appends `run_of(…, [*self.party, *present,
   *hidden], job)`). `apply_next` lands under the open job's title or `""`; `apply_job` refuses
   `"a one-shot has no hub to take a job from"` without a campaign, reopens or appends the `Job` as
   today, lands under its title; `apply_return` refuses `"no job is open to close"` without a campaign
   or an open job, closes it, swaps the board, lands under `""`, returns the job (the no-campaign
   return now reads "no job is open to close"; no test matches the old text). `install`
   (`scenes/engine.py:342`) meanwhile takes `scene: NextProposal[C] | ReturnProposal[C]`, drops its own
   `model_copy` (`_land` copies), and dispatches in this order: `isinstance(scene, ReturnProposal)` →
   `job = world.apply_return(scene)`; `isinstance(scene, JobProposal)` → `world.apply_job(scene,
   reopening=reopening)`; else `world.apply_next(scene)` (the remainder narrows to `NextProposal[C]`);
   `write_next`'s `model` annotation and return become `type[NextProposal[C] | ReturnProposal[C]]` /
   `NextProposal[C] | ReturnProposal[C]`; step 7 removes the dispatch. In
   `scenes/proposals.py` add `SceneProposal.opening_campaign(self) -> Campaign | None: return None`
   and the `HubProposal` override `Campaign(place=self.place, board=self.offers)`;
   `opening_canon` (`scenes/engine.py:309–311`) calls it. Tests: `tests/core/test_scenes.py:199–296`
   call `apply_next`, `apply_job(…, reopening=job)`, `apply_return`; `tests/loner3e/test_world.py:80,
   107,110,163` and `tests/twentyfourxx/test_worldsmith.py:48–66,86,206` call `apply_next` with a
   `_next_proposal(...)`; a bare `_proposal(...)` passed to `install` becomes `_next_proposal(...)`,
   added to `tests/breathless/test_worldsmith.py` as 24XX's builds it; `tests/core/test_master_tools.py:71`
   builds `NextProposal[Loner3eSheet].model_validate_json(_scene())`. Grep: `apply_scene`
   finds nothing; `isinstance` in `scenes/world.py` finds nothing.
7. **P4, the engine.** `render_next` (`scenes/engine.py:244`) becomes `render_next(self, draft: G,
   intent: str, answer: type[BaseModel], *, returning: bool, follows_arc: bool, reopening: Job | None
   = None, asked: str = "") -> str` and drops the two `issubclass` reads (`:255`); `render_commission` passes `returning=False,
   follows_arc=False`. `write_next` becomes generic: `async def write_next[M: BaseModel](self, draft:
   G, intent: str, worldsmith: WorldsmithAnswer, model: type[M], refusal: Check[M], *, returning:
   bool = False, reopening: Job | None = None) -> M` = render (`follows_arc=not returning`,
   `asked=draft.on_order_lines()`) then `await worldsmith(prompt, model, refusal)`. `install`
   (`:342–366`) becomes `install_next(draft, proposal: NextProposal[C]) -> list[Fact]`,
   `install_job(draft, proposal: JobProposal[C], *, reopening: Job | None)` (card line `The job:
   …`), `install_return(draft, proposal: ReturnProposal[C])` (the finished note, then `[job.closed(),
   opened]`), sharing `opened(self, draft: G, proposal: SceneProposal[C], label: str, *lines: str)
   -> Fact` (clears `draft.commissions`, the trace with the party, the card `label: title` /
   `At stake: question` / `*lines`). `advance` computes `reopening`, `later = draft.on_order()`, a
   local `bar(answer: SceneProposal[C]) -> str | None` over `scene_refusal`, then one of three
   branches — `returning` (campaign, away, `intent == GO_HOME`): `ReturnProposal[self.cast]` →
   `install_return`; `world.at_hub`: `JobProposal[self.cast]` with `reopening` → `install_job`; else
   `NextProposal[self.cast]` → `install_next` — each `(*self.leaving(draft), *install)`. Tests:
   `tests/core/test_master_tools.py:71` `_SilentEngine.advance` calls `install_next`;
   `tests/twentyfourxx/test_worldsmith.py:331–372` becomes three fresh `hub_world()`s through
   `advance` asserting the model recorded (`GO_HOME` → `ReturnProposal`, hub with the job run popped +
   `TAKE_JOB` → `JobProposal`, on the job → `NextProposal`); every other `ENGINE.write_next(game,
   intent, answer)` there becomes `ENGINE.advance(game, intent, answer)`, and every `advance` in
   `test_write_next_shows_this_job_only_on_a_return` and `test_the_arc_line_only_reaches_a_next_draft_
   prompt` (`:375–397`) runs on its own fresh `hub_world()` (two on one world would ask for a
   `JobProposal` the script answers as a `NextProposal`); every `ENGINE.install(…)` in the three scene
   `test_worldsmith.py` and `tests/loner3e/test_world.py:95` becomes `install_next`/`install_job(…,
   reopening=None)`/`install_return` with the matching proposal; `render_next` calls there add
   `returning=False, follows_arc=False`. Grep: `def install(` under `engines/scenes` finds nothing;
   `issubclass\|isinstance` under `engines/scenes` outside `worldsmith.py` finds nothing.
8. **P7, the engine folds.** (a) `question_heading` (`hub.py:378`) inlined into `master_sections`
   (`scenes/engine.py:124`); `tests/core/test_hub.py:180` deleted. (b) `Campaign.terms` (`hub.py:157`)
   inlined into `scene_rows` (`scenes/world.py:347`: `(job := self.campaign.open_job()) is not None
   and job.terms`); `sections` (`:266`) into `hub_block`; `board_rows` (`:233`) into `board_panel`;
   `job_row` (`:277`) into `tail`. `tests/core/test_hub.py:124,134` read `board_panel(at_hub=True)[0]
   .rows`, `:226` asserts the panel's title and row count instead of comparing against `board_rows()`,
   `:121–162,209–226` otherwise call `hub_block(title, brief, (), returning=…, reopening=None)` and
   `dict(tail(at_hub=False))["THE JOB"]`; `tests/tunnelgoons/test_views.py:68` reads
   `board_panel(at_hub=True)[0].rows`.
   (c) `here_lines`/`hidden_lines` (`scenes/world.py:201–205`) inlined into `master_sections`.
   (d) `Subject.row(self, label: str | None = None) -> PanelRow` in `core/views.py` (`label` defaults
   to `name`, `detail=brief`, `icon_id=id`); move `PanelRow` and its comment (`views.py:33–40`) above
   `Subject` first, or the annotation raises `NameError` at import; `here_panel` (`base.py:147–148`) and `party_panel`
   (`scenes/world.py:344`, via `m.subject().row()`) use it; rooms' site is step 12. (e) `Engine.answer`
   (`seam.py:102–109`) inlined into `Turn._consume` (`turn/run.py:84`): `try: found = engine.tool(
   option.name) except Refusal as missing: raise Refusal(f"the {engine.id!r} engine has no tool
   {option.name!r} to play option {chosen!r}") from missing` (`chosen` is `option.id`, so the text
   holds), then `self._apply(lambda copy, dice: found.call(copy, option.args, dice))`; `tests/core/test_decisions.py:204–206` drive the same two
   refusals through `Turn.begin(engine, _pending(state, decision-with-that-option), Answer(option_id=
   "lantern"), Random(0))`, same `match`. (f) D5 A: drop the `Free:` docstrings at `base.py:145` and
   `scenes/world.py:396` (each is the whole docstring). Grep: each name in (a)–(e) finds nothing;
   `Free:` under `engines/scenes` and `base.py` finds nothing.
9. **P6, rooms (D3 A).** `git mv src/aidm/engines/rooms/drafts.py src/aidm/engines/rooms/proposals.py`;
   `MapDraft→MapProposal`, `NpcDraft→NpcProposal`, `ItemDraft→ItemProposal`, `ReturnDraft→
   ReturnProposal`; `map_draft()→opening_proposal()`, `render_map→render_opening`,
   `render_extension→render_next`, `write_extension→write_next`, `install_extension→install_next`
   (it installs what `write_next` wrote, return included; `install_commission` already matches);
   parameters `draft`/`extension` holding a proposal → `proposal` (`rooms/worldsmith.py` bars,
   `build_scenario`, `opening_canon`, `install_next`). Rooms' three `isinstance` on proposals
   (`rooms/engine.py:308,356,359`) stay: `RoomEngine` is not reshaped (D3 C). Tests:
   `tests/tunnelgoons/test_worldsmith.py` follows. Grep: `Draft` under `engines/rooms` and
   `tests/tunnelgoons` finds nothing; `render_map\|write_extension\|install_extension\|map_draft`
   finds nothing.
10. **P2, rooms adopt the shared tool and line.** Delete `commission_tool` (`rooms/engine.py:208–217`);
    `RoomEngine.commission_args = RoomCommission`, `commission_hint` = the string after
    `COMMISSION_BRIEF +` (`:212–214`). `write_next` uses `draft.on_order_lines()` (`:286`). Grep:
    `def commission_tool` finds `seam.py` only.
11. **P2, rooms adopt the frame (D1 A).** Delete `rooms/worldsmith.py:36–62`; `rooms/engine.py` imports
    `worldsmith_prompt` from `hub` and passes `world=(("MAP SO FAR", world.map_so_far()), ("THE PLAYER",
    world.line(world.player)))` in `render_next` and `world=(("MAP SO FAR", "(no map yet)"), ("THE
    PLAYER", "(no player yet — the map is authored before anyone stands in it)"))` in
    `render_opening`. Tunnel Goons' prompt gains `STANDING INSTRUCTION`, its `ENGINE GUIDANCE` moves
    before `WHAT COMES NEXT`, and `MAP SO FAR`/`THE PLAYER` move after `SCENES SO FAR` and the hub
    block (no test asserts the order). Test, `tests/tunnelgoons/test_worldsmith.py:432`
    (`..._prompt_carries_scenes_so_far`): also asserts `"STANDING INSTRUCTION:\n" in prompt`. Grep:
    `def worldsmith_prompt` finds `hub.py` only; `write from the setting` finds nothing.
12. **P7, rooms.** The Carrying rows (`rooms/engine.py:138`) become `item.subject().row()`; drop the
    `Free:` docstring at `rooms/worldsmith.py:66`. Grep: `PanelRow(label=` under `engines/rooms` finds
    the `Ways out` rows and `REPORT_ROW` only; `Free:` under `engines/rooms` finds nothing.

---

## Phase 2 — the scaffold, the platform, the tests

Split: A and B parallel, then C.
- A, the platform: steps 13–20; owns `app/**`, `turn/context.py`, `core/io.py`, `core/views.py`,
  `core/play.py`, `ui/game.py`, `ui/settings.py`; tests `tests/core/{test_game_service,test_master_tools,
  test_speech,test_views,test_store,test_integrity_boundaries,test_golden_turn,test_decisions,
  test_turn}.py`, `tests/ui/*`, `tests/tunnelgoons/test_play.py`, `tests/twentyfourxx/test_engine.py`,
  `tests/support/{table,loner}.py`.
- B, the scaffold: steps 21–26; owns `engines/seam.py`, `engines/base.py`, `engines/scenes/engine.py`,
  `engines/rooms/engine.py`, `engines/{loner3e,breathless,twentyfourxx,tunnelgoons}/**`; tests
  `tests/*/test_create.py`, `tests/breathless/test_views.py`, `tests/twentyfourxx/test_world.py`,
  `tests/core/{test_seam,test_rooms}.py`. Step 13 needs `Engine.transition` in `seam.py`,
  `scenes/engine.py` and `rooms/engine.py` (B's files): A writes those three methods and deletes
  `crossing` in step 13, before B starts on the same files; B's steps 21–26 do not touch `transition`.
  So the phase runs A's step 13 first, then A (14–20) and B (21–26) in parallel, then C.
- C, the tests and the three names: steps 27–29; owns `tests/**`, and for step 27 `core/model.py`,
  `engines/seam.py`, `turn/run.py`, `app/runtime.py` (R6's three renames cross A's and B's files,
  so they land after both).

13. **P5 with D8 A, R2 and R8.** (R2 evidence, `fc4d354`, is stale by one line: `e2db974` added the
    `mastered`/`page_word` read at `runtime.py:115`; it is carried through.) In `core/play.py` after
    `Answer` add `type TransitionMode = Literal["turn_then_advance", "advance_only"]` and
    `class Transition(Frozen)` with `mode: TransitionMode`, `brief: str | None = None` (the
    narrator's arrival brief) and a validator raising `ValueError("a turn's transition carries the
    arrival brief; a silent one carries none")` unless `(mode == "turn_then_advance") == (brief is not
    None)`. In `seam.py` replace `crossing` (`:72–74`) by the abstract `transition(self, state: G,
    pursuit: str) -> Transition` (Phase 3 step 32 passes an `Action`); `SceneEngine.transition`
    (replacing `scenes/engine.py:101–102`) returns `Transition(mode="turn_then_advance",
    brief=CROSSING.format(left=self.world(state).run.title, pursuit=pursuit))`; `RoomEngine.transition`
    (new, after `ready`) returns `Transition(mode="advance_only")`. `page_word` stays until step 32.
    In `app/runtime.py` split `play` (`:104–136`) and `extend` (`:171–184`): `async def play(self,
    answer: Answer) -> None: await self._turn(answer)`; private `async def _turn(self, answer: Answer,
    *, mastered: bool = True) -> None` is today's `play` body without the `moving_on` lines, passing
    `mastered` to `Turn.begin` and the `_run_master` guard; `async def move_on(self, answer: Answer)
    -> None` refuses `"a transition needs written intent"` on an `option_id` and `"the world offers
    no transition from here"` unless `engine.ready`, computes `transition = self.engine.transition(
    self.state, answer.text)`, then under one `try/finally` that resets `self.intent, self.phase =
    "", None`: `turn_then_advance` → `await self._turn(answer, mastered=not self.engine.page_word(
    self.state, answer.text))` and `return` if `self.engine.over(self.state) is not None`;
    `advance_only` → `self.intent = answer.text`; both then `await self._grow(answer.text,
    transition.brief)` + `self._present()` (the brief decides the narration only; the mode decides
    whether a turn runs). `extend` goes, and with it its "a turn is already in flight" and "no
    frontier to extend" refusals. R8: `GameService.busy` (`:83–85`) becomes the field `busy: bool =
    False` after `intent` (the claim); `open` guards on `if self.engine.history(self.state): return`
    (it runs inside the claim, so `unopened`, which reads `busy`, would refuse it); `Runtime` gains
    `@contextmanager def operation(self, session: GameService) -> Iterator[None]`: raises `Refusal(
    "The settings changed. Reload this page before you play on.")` unless `self._sessions.get(
    session.slug) is session`, raises `Refusal(refusal)` when `self.busy_refusal()` is not `None`,
    sets `session.busy = True`, yields, resets it in `finally`; `play_refusal` (`:360–364`) goes;
    `busy_refusal` stays (the settings reload reads the same claim through it); `runtime.lock` stays
    on the MCP call only; the service's own continuations (`_grow`, `_fulfil`, `open` from `restart`)
    never enter it. `ui/game.py`: `_run` (`:376`) wraps `await playing()` in `with self.runtime.
    operation(self.session):` inside `working()` (a refusal is notified there); `refuse_play`
    (`:327–332`) and `_send` (`:393`) go; `decision_panel.answer` runs `self._run(partial(session.play,
    Answer(option_id=…)))`; `submit(moving_on)` runs `partial(session.move_on if moving_on else
    session.play, Answer(text=typed))`; `move_on(intent)` runs `partial(session.move_on, Answer(text=
    intent))` and drops its "Choose an option above." pre-check (`Turn._consume` refuses the same);
    `restart` runs `self._run(self._restart)` where `async def _restart` is `session.restart()`,
    `self.poll_turn()`, `await session.open()` (one claim for both); `_open` returns when
    `self.session.busy or not self.session.unopened()` (a second tab's timer stays silent). Tests:
    `tests/support/table.py` `play_turn` awaits `move_on(answer)` when `moving_on` else `play(answer)`;
    every `service.play(…, moving_on=True)` (`tests/core/test_master_tools.py:258,278,301,326`,
    `tests/tunnelgoons/test_play.py:91`) becomes `service.move_on(Answer(...))`;
    `test_master_tools.py` `_SilentEngine.crossing` (`:59`) becomes `transition(self, state, pursuit)
    -> Transition: return Transition(mode="advance_only")`; `:230–262` (the `intent` bubble) and the
    four page-word tests (`:288–340`) hold; `tests/core/test_turn.py` adds: `Transition(mode=
    "turn_then_advance")` raises `ValueError`; `tests/ui/test_settings.py:73–75` set `session.busy =
    True`, `:80–89` replace `play_refusal` by `with runtime.operation(session): pass` raising `Refusal`
    matching "The settings changed", and add: inside one `operation`, a second raises "A turn is in
    flight"; `tests/core/test_game_service.py:111–118` wraps `play_turn` in `table.runtime.operation(
    table.service)` and asserts `(busy, phase, turn) == (False, None, None)` after the `OSError`. Grep:
    `moving_on` in `src` finds nothing; `def extend\|\.extend(answer` finds nothing; `_send` finds
    nothing; `crossing` finds `CROSSING` only; `play_refusal\|refuse_play` finds nothing.
14. **D2 A and the page's reach (R7).** New `app/present.py`: `@dataclass(slots=True) class Presentation`
    with `media: Illustrator | None = None`, `reader: Reader | None = None`, `_background: set[Task[
    None]] = field(default_factory=set, repr=False)` and the six methods moved from `GameService`
    (`runtime.py:147–150,258–291`), each taking what it read from the game: `scene_art(scene:
    NarratorView)`, `icon(entity_id)`, `newest_clip(newest: Exchange | None)`, `illustrate(scene, player:
    Subject, narration: str = "")`, `speak(newest)`, `show(scene, player, newest)` (was `_present`), plus
    private `_retain`. `GameService` loses `media`, `reader`, `_background`, gains `present: Presentation
    = field(default_factory=Presentation)` after `store`; `_present(self)` calls `self.present.show(
    self.scene(), self.player_view().player, self.newest())`. R7 adds no class of its own (its "no new
    service class" is its own scope, not a veto of D2 A: both stand). Add `history(self) ->
    tuple[Exchange, ...]`, `scene(self) -> NarratorView`, `ready(self) -> bool`, `newest(self) ->
    Exchange | None` (was `_newest`), `tools(self) -> tuple[MasterTool[AnyGame], ...]`, `live_facts(self)
    -> tuple[Fact, ...]` (`()` without a turn, else the turn's facts with `told`), `live_prompt(self) ->
    str` (the turn's `prompt`, else `self.intent`), and the properties `title` (`scenario.meta.title`),
    `premise` (`scenario.meta.premise`), `rules` (`engine.title`); `unopened` and `Runtime.
    published_tools` read them. `Runtime._open` passes `present=Presentation(media=open_illustrator(…),
    reader=open_reader(…))`. `ui/game.py`: `Observed.of` (`:58–65`) reads `session.phase`, `len(session.
    live_facts())`, `len(session.history())`, `session.ready()`, `session.player_view().over`;
    `session.history()` (`:162,268`), `session.scene()` (`:141`), `session.ready()` (`:206,368`),
    `session.title`/`session.rules` (`:92`), `session.premise` (`:164`), `session.player_view().prompt is
    not None` (`:166`), `live_turn` (`:187–201`) shows `_bubble(…, session.live_prompt(), sent=True)`
    when it is not empty and `cards(session.live_facts())` (the `turn`/`intent` branches go),
    `session.present.illustrate(session.scene(), session.player_view().player)` (`:91`),
    `session.present.scene_art(session.scene())` (`:148,316`), `session.present.newest_clip(session.
    newest())` (`:121,181,320`), `session.present.icon(…)` (`:258,435`), `session.present.media is not
    None or session.present.reader is not None` (`:126`). Tests: `tests/core/test_speech.py:148–164` use
    `session.present.reader = …`, `session.present.speak(session.newest())`, `session.present.
    _background`, `session.present.newest_clip(session.newest())`, `session.newest()`; `tests/core/
    test_game_service.py` adds: with `service.turn = Turn.begin(...)` holding one told and one untold
    fact, `live_facts()` is the told one and `live_prompt()` the turn's prompt; `title`/`rules` read the
    scenario and the engine. Grep: `session\.state\|session\.engine\|session\.turn\|session\.intent` in
    `ui/` finds nothing; `_newest\|def illustrate\|def speak` in `runtime.py` finds nothing. Costs
    about +40 lines (the module header, five accessors, two live reads, three properties); D2 A and
    R7 accept it.
15. **P7, prompt files one way.** `turn/context.py`: `MASTER = (_PROMPTS_DIR / "master.md").read_text(
    encoding=ENCODING)` and `NARRATOR = …` as module constants; `_prompt` and the `cache` import go.
    Grep: `_prompt(` in `turn/` finds nothing; `@cache` in `src` finds nothing.
16. **P7, one speaker rule.** `core/views.py`: `spoken`'s refusal (`:76`) becomes `f"nobody here has id
    {line.speaker_id!r}. Only the player or someone here with them speaks; leave `speaker_id` null
    for narration."`; `narration_refusal` returns the empty-lines message, else `try: self.spoken(
    narration.lines) except Refusal as refused: return str(refused)`, else `None`; `speakers_refusal`
    (`:81–90`) goes. Lost: the re-prompt names the first stranger, not every stranger. Test, `tests/core/test_views.py`: `narration_refusal` names a stranger's id and
    `None` for a subject who speaks. Grep: `speakers_refusal` finds nothing.
17. **P7, `parse` at two boundaries.** `ui/settings.py:91`: `parse(Settings, merged)` under `except
    Refusal`; `app/spawn.py:87`: `result = parse(_ClaudeResult, decode(output))` under `except Refusal
    as broken: raise Refusal(f"claude printed no JSON result: {output[-500:]}") from broken`
    (`tests/core/test_spawn.py:63` holds; `_object` at `:265` keeps `ValidationError`). Grep:
    `ValidationError` in `src` finds `core/entities.py` and `spawn.py:_object` only.
18. **P7, one decode-and-restore.** `core/io.py`: `class Installed(Protocol)` with `scenario: type[
    AnyScenario]` and `def restore(self, value: JsonValue) -> AnyGame: ...` (`core` names no engine;
    two methods need it); `FileStore.load` → `restore(self, slug: str, engines: Mapping[EngineId,
    Installed]) -> AnyGame | None` (read, `decode`, `routed`, `engine.restore`); `Library.read_scenario(
    name, engines: Mapping[EngineId, Installed])` and `read_scenarios(engines)` parse with
    `routed(value, engines).scenario`. `GameService.__post_init__` (`runtime.py:73–77`) holds one
    engine: `saved = self.store.restore(self.slug, {self.engine.id: self.engine})` (a foreign save now
    reads "the 'x' engine is not installed"; no test matches the old text); `Runtime._open`
    (`:406–409`) and `launch.py:70,97–102` pass `self.engines`/`engines` (`engine = engines[state.
    engine]`; `decode`, `routed` imports in `launch.py` go).
    Tests: `SCENARIO_MODELS` (`tests/support/table.py:47`) goes, its six users pass `ENGINES_BUILT`;
    `Table.saved` and `tests/core/test_store.py:37,48`, `test_game_service.py:37` call `store.restore(
    slug, ENGINES_BUILT)`. Grep: `\.load(` in `src tests` finds nothing; `SCENARIO_MODELS` finds
    nothing; `scenario_models` finds nothing.
19. **D6 A.** Delete `way_on_panel` (`ui/game.py:204–217`), its call (`:106`) and its refresh (`:134`).
    Grep: `way_on_panel` finds nothing.
20. **D5 A, platform half.** Drop the `Free:` line (first line only) of the docstrings at
    `app/providers.py:20` and `app/media.py:168`. Grep: `Free:` in `src` finds nothing.
21. **P3, one `create_character`.** `Engine.create_character(self, name: str, brief: str, picks: Picks)
    -> AnyCharacter` becomes concrete: `check_picks(self.creation_steps(picks), picks)`, then `return
    self.character(id=slug(name, ()), engine=self.id, payload=self.sheet(name, brief, picks))`; new
    abstract `sheet(self, name: str, brief: str, picks: Picks) -> P`. The four `create_character`
    (`loner3e/engine.py:108`, `breathless/engine.py:129`, `twentyfourxx/engine.py:150`,
    `tunnelgoons/engine.py:118`) become `sheet` returning the sheet (Tunnel Goons keeps its
    `ABILITY_POINTS` refusal inside). Tests: `tests/core/test_seam.py:63` and `test_rooms.py:56` stubs
    define `sheet` instead; `test_seam.py:130` passes `{"pack": "srd"}` (empty picks are now refused
    by `check_picks`); the four `test_create.py` hold. Grep: `def create_character` finds
    `seam.py` only.
22. **P3, one `creation_steps` for scenes.** `SceneEngine.creation_steps(picks)` concrete: `first =
    self.pack_step()`, `pack = self.packs.get(picked(picks, "pack"))`, `(first,)` if `None` else
    `(first, *self.pack_steps(pack, picks))`; new abstract `pack_steps(self, pack: K, picks: Picks) ->
    tuple[CreationStep, ...]`. Loner (`:79–106`), Breathless (`:108–127`), 24XX (`:105–148`) keep only
    the steps after `first`; `Engine.creation_steps` stays abstract for Tunnel Goons.
    `tests/core/test_seam.py:60` stub defines `pack_steps` returning `()`. Grep: `def creation_steps`
    finds `seam.py`, `scenes/engine.py`, `tunnelgoons/engine.py`, `tests/core/test_rooms.py`.
23. **P3, one items hook.** `base.py`: `Person.items_title: ClassVar[str] = ""` (a `ClassVar`, so no
    save changes shape), `items_shown(self) -> tuple[tuple[str, str, str], ...]` returning `()`
    (id, name, detail; the id is empty for a line that is no item, Breathless's med kit), `items_lines(self) -> str` = `lines_of(f"- {name}" + (f"[{id}]" if id else
    "") + (f" — {detail}" if detail else ""))`, `items_panel(self) -> Panel` = `Panel(title=
    self.items_title, rows=(PanelRow(label=name, detail=detail) …))`. `Survivor`: `items_title =
    "Backpack"`, `items_shown` = `(key, item.name, f"d{item.die}")` per item, then `("", "Med kit",
    "held")` when `med_kit`; `Operator`: `"Gear"`, `(key, item.name, item.detail())`; `Goon`: `"Items"`,
    `("", name, "")` per `kit` entry. `SceneEngine.master_sections` renders `((player.items_title.
    upper(), player.items_lines()),)` where `sheet_sections` was, when `items_title`; `player_view`
    renders `player.items_panel()` where `panels` was, when `items_title`; `Engine.preview_character`
    appends `(sheet.items_title, ", ".join(names))` when `items_title`. Delete the three defs
    `preview_character`, `sheet_sections`, `panels` in `breathless/engine.py` and
    `twentyfourxx/engine.py` (`guidance` sits between them and stays) and `preview_character` in
    `tunnelgoons/engine.py:135–137`.
    Byte-equal except the med-kit master line, now `- Med kit — held` (the panel's spelling);
    `tests/breathless/test_views.py:29` follows; no golden holds a med kit. Goldens: none change.
    Grep: `sheet_sections\|def panels\|def preview_character` finds `seam.py` once.
24. **P7, Loner's glossary in one method.** `Loner3eEngine.glossary` (`loner3e/engine.py:140`) absorbs
    `meanings` (`:147`) and `pack_meanings` (`loner3e/tools.py:124`): the packs from `state.packs`, a
    `detail_of` over their skills, frailties and gear, the tags of everyone `here()` in that order;
    the two callees go. the `WHAT THE TAGS IN PLAY MEAN` section of
    `tests/core/fixtures/prompts/loner3e/master.txt` pins it. Grep:
    `meanings` finds nothing.
25. **D5 A, Loner.** `_strike`, `_refuse_unless_ready`, `_pair` (`loner3e/engine.py:268–308`) become
    private methods on `Loner3eEngine` with `self` first; `_absorbed` (a list) stays free. Grep:
    `^def _strike\|^def _refuse_unless_ready\|^def _pair` finds nothing.
26. **D5 A, 24XX.** `starting_items` (`twentyfourxx/engine.py:346`) becomes `Pack.starting_items(self,
    specialty: Specialty, weapon: Kit | None) -> dict[EntityId, Item]` in `twentyfourxx/worldsmith.py`
    (the pack owns the kits: `(*self.starting_kit, *specialty.kit, *(() if weapon is None else
    (weapon,)))`; `worldsmith.py` gains the `EntityId`, `slug` and `Item` imports, no cycle since
    `world.py` does not import it); `sheet` calls it. Test: `tests/twentyfourxx/test_world.py:103` moves
    to `tests/twentyfourxx/test_create.py` as `ENGINE.packs["srd"].model_copy(update={"starting_kit":
    (Kit(name="Comm"), Kit(name="Comm"))}).starting_items(Specialty(id="bare", label="Bare",
    detail="none", skills={}), None)` keyed `["comm", "comm-2"]`. Grep: `^def starting_items` finds nothing.
27. **P6 and R6, three names.** `GameService.commit` (`runtime.py:298`) → `save` (five callers in
    `runtime.py`, plus step 13's `move_on` and `_grow`; `tests/core/test_speech.py:149`,
    `test_golden_turn.py:33`, `test_decisions.py:103`, `test_master_tools.py:297`); `Engine.commit`
    (`seam.py:158–160`) → `validated(self, draft: G) -> G` (`self.validate(draft)` then `return
    draft.revalidated()`; callers `seam.py:156,184`, `turn/run.py:152`, `runtime.py:249` now
    `self.save(self.engine.validated(draft))`); `Game.commit` (`core/model.py:118`) → `revalidated`,
    docstring "Revalidated whole, so a state the rules refuse never lands." (the ~35 `draft.commit()`
    test sites: `tests/support/loner.py:68`, the four `tests/*/golden_turn.py`, `tests/loner3e/
    {test_world,test_tools,test_engine}.py`, `tests/tunnelgoons/{test_world,test_worldsmith}.py`,
    `tests/core/{test_store,test_integrity_boundaries,test_decisions,test_media,test_game_service}.py`
    call `.revalidated()`). No forwarding alias. `save` still writes before it assigns `self.state`.
    Grep: `\.commit(\|def commit` in `src tests` finds nothing.
28. **P8, the tests fold into `tests/core`.** `tests/support/table.py`: `SCENE_ENGINE_IDS = (LONER3E,
    BREATHLESS, TWENTYFOURXX)`. `tests/support/scenes.py`: `HubNames` gains `keeper: EntityId` (the
    three `NAMES` set it; `hub_runs(names)` reads it) and gains `return_proposal(names, cast: type[C])
    -> ReturnProposal[C]` and `next_proposal(names, cast, **fields) -> NextProposal[C]` built from the
    three `_return_proposal` bodies. New `tests/core/test_scene_engines.py` with `HUBS = {LONER3E:
    loner.hub_world, BREATHLESS: breathless.hub_world, TWENTYFOURXX: twentyfourxx.hub_world}`,
    parametrized over `SCENE_ENGINE_IDS`: `test_install_scene_on_a_hub_draft_lands_a_home_card`
    (`install_return`), `test_install_scene_appends_a_run_and_returns_the_opened_fact`
    (`install_next`), `test_render_worldsmith_lists_the_player_first`,
    `test_opening_canon_sets_the_hub_and_board_for_a_campaign_only`,
    `test_check_game_refuses_a_hub_with_a_one_shot_meta`, `test_a_player_id_cast_entry_is_refused_by_
    new_game` (`engine.scenario(...)`, `engine.new_game`), `test_a_scenario_with_no_packs_is_refused_
    by_check_packs`, `test_next_scene_with_job_done_settles_the_job_and_is_refused_at_the_hub` (through
    `engine.tools["next_scene"].call`); over `ENGINE_IDS`: `test_check_game_refuses_a_campaign_meta_
    with_no_hub`. Into `tests/core/test_seam.py` over `ENGINE_IDS`: `test_restored_round_trips`. Into
    `tests/core/test_scenes.py` on its `_world` (add `DAX`, unknown): `test_the_bar_refuses_a_scene_
    that_lists_the_player`, `test_the_bar_refuses_a_draft_cast_entry_under_player_id`, `test_the_
    opening_needs_a_cast_member`, `test_the_next_scene_needs_one_brought_back`, `test_a_dead_draft_
    cast_member_is_refused`, `test_a_hidden_multi_word_name_in_situation_is_refused`, `test_a_cast_
    that_holds_the_player_is_refused`, `test_a_return_naming_an_unmet_cast_member_in_the_debrief_is_
    refused`, `test_only_the_players_own_fields_are_checked_for_what_they_have_not_met`. Every other
    copy is deleted. Stays: `test_luck_facts_are_untold` (each reads its own `TestLuck` args, a rule);
    the three `hub_world` builders (the engine-specific tests need them); the four `golden_turn.behind`
    (Loner's inserts a run, the others append an exchange). Grep: `grep -rhoE "def test_\w+" tests/{loner3e,breathless,twentyfourxx,tunnelgoons}
    | sort | uniq -d` prints `def test_luck_facts_are_untold` only. About −300 test lines.
29. **P8, one opener.** Delete `open_game_for` (`tests/support/table.py:199`) and `support.loner.open_game`
    (`:94`); callers use `open_table(saves, engine_id=…, state_type=…, …)` (`ENGINES_BUILT[id].game`
    where the engine is a parameter, `Loner3eGame` for Loner; `engine=` passes through). Grep:
    `open_game_for\|open_game\b` in `tests` finds nothing.

---

## Phase 3 — explicit over implicit

Names below are the tree's after Phases 1 and 2 (`*Proposal`, `install_next/job/return`,
`apply_next/job/return`, `_land`, `Subject.row`, `items_panel`, `board_panel` with the rows inlined,
`save`/`validated`/`revalidated`, `move_on(answer)`, `_turn`, `_grow(intent, brief)`,
`transition(state, pursuit)`, `HOME_ROW`/`HUB_ROW`/`GO_HOME` in `scenes/world.py`); the `e2db974`
line numbers quoted are where the name is today.

Split: A then B, sequential (B edits files A finished; the skill's "make them sequential" case).
- A, the actions: steps 30–32; owns `core/play.py`, `core/views.py`, `core/model.py`, `turn/run.py`,
  `app/runtime.py`, `ui/game.py`, `engines/base.py`, `engines/seam.py`, `engines/hub.py`,
  `engines/scenes/{world,engine}.py`, `engines/rooms/engine.py`; tests `tests/core/{test_turn,
  test_hub,test_scenes,test_master_tools,test_views,test_engines_base,test_game_service}.py`,
  `tests/support/table.py`, `tests/{breathless,twentyfourxx,tunnelgoons}/test_views.py`,
  `tests/breathless/test_tools.py`, `tests/twentyfourxx/test_worldsmith.py`,
  `tests/tunnelgoons/{test_worldsmith,test_play}.py`.
- B, the stored shapes: steps 33–35; owns `core/play.py` (`SceneRecord` only), `engines/hub.py`,
  `engines/seam.py`, `engines/scenes/{world,engine,proposals,worldsmith}.py`,
  `engines/rooms/{world,engine,proposals,worldsmith}.py`, `scenarios/{amber-tap,buried-bell,
  salt-lantern,waystation}/world.json`; tests `tests/support/{scenes,tunnelgoons}.py`,
  `tests/core/{test_hub,test_scenes,test_master_tools,test_turn}.py`, `tests/loner3e/test_engine.py`,
  `tests/breathless/test_tools.py`, `tests/twentyfourxx/{test_tools,test_worldsmith}.py`,
  `tests/tunnelgoons/{test_world,test_tools,test_worldsmith,test_views}.py`.

30. **R9, the notes' lifetime.** (Evidence moved: `e2db974` put the swap under `if mastered:` at
    `turn/run.py:57–58`; the rule is kept.) `core/model.py`: `Game.take_notes(self) -> list[str]`
    after `note`: `taken, self.notes = self.notes, []; return taken`. `turn/run.py`: `Turn.begin` replaces
    `:58` by `turn.notes = turn.draft.take_notes()` under the same `if mastered:` (a page-word turn
    spawns no master, so its notes stay on the draft for the next master: `test_the_pages_own_words_
    spawn_no_master_and_keep_the_notes` holds); `picture(self, extra_notes: Sequence[str] = ()) -> str`
    renders `notes=(*self.notes, *self.draft.notes, *extra_notes)` (the commission note was appended
    last today, so the order holds). `app/runtime.py`: `_act(self, turn: Turn, extra_notes: Sequence[
    str] = ())` calls `turn.picture(extra_notes)`; `_run_master` (`:138–145`) becomes `await self._act(
    turn)` then, per `wanted()`, `note = await self._fulfil(turn, asked)`, `self.phase = "master"`,
    `await self._act(turn, extra_notes=(note,))` (the `notes.remove` line goes); `_fulfil` (`:152–169`)
    returns the note without `turn.draft.note(note)`. The retry inside `_act` sees the same
    `extra_notes`. Test, `tests/core/test_turn.py`: `Turn.begin` on a state with one note empties
    `draft.notes` into `turn.notes`; `picture(extra_notes=("x",))` prints `- x` under NOTES FROM THE
    RULES and leaves `draft.notes == []`. `test_game_service.py:121–157` holds. Grep: `notes.remove\|
    draft.note(note)` finds nothing; `turn.notes, turn.draft.notes` finds nothing.
31. **R5 and R1's value: three rows, one `Action`.** `core/play.py` after `Answer`: `PURSUE = "pursue"`
    (the composer's action: the words are the whole intent) and `class Action(Frozen)` with `name:
    Slug`, `args: dict[str, JsonValue] = {}`, `text: str = Field(min_length=1)` (the chat bubble and the
    exchange's prompt). `core/views.py`: replace `PanelRow` and its comment (`:33–40`) by `class
    ActionRow(Frozen)` (`kind: Literal["action"] = "action"`, `label: str`, `detail: str = ""`, `action:
    Action`), `class EntityRow(Frozen)` (`kind: Literal["entity"] = "entity"`, `label`, `detail: str`,
    `icon_id: EntityId`), `class InfoRow(Frozen)` (`kind: Literal["info"] = "info"`, `label`, `detail: str
    = ""`; an empty detail renders a bare label), and `type PanelRow = Annotated[ActionRow | EntityRow |
    InfoRow, Field(discriminator="kind")]`; `Panel.rows: tuple[PanelRow, ...]` stays; `Subject.row`
    returns `EntityRow`. Action names beside their button words: `hub.py` `TAKE_JOB = "take_job"` and
    `TAKE_JOB_TEXT = 'I take the job "{title}".'` (the sentence renamed); `scenes/world.py` `GO_HOME =
    "go_home"`, `GO_HOME_TEXT = "Go home."` (renamed), `GO_ON = "go_on"`; `rooms/engine.py` `REPORT_IN =
    "report_in"`, `REPORT_IN_TEXT = "Report in."` (renamed); every reader of a sentence follows for now
    (`scenes/engine.py` `advance`'s `intent == GO_HOME_TEXT`, `rooms/engine.py` `write_next`'s `intent ==
    REPORT_IN_TEXT`, `hub.job_title` over `TAKE_JOB_TEXT`; step 32 deletes them). Rows: `HOME_ROW =
    ActionRow(label="Go home", detail="Back to base; the job closes on a card.", action=Action(name=
    GO_HOME, text=GO_HOME_TEXT))`; `HUB_ROW = InfoRow(label="Take a job from the board, or name where you
    go.")`; `REPORT_ROW = ActionRow(label="Report in", detail="Tell the tavern how it went.", action=
    Action(name=REPORT_IN, text=REPORT_IN_TEXT))`; the board rows in `board_panel` → `ActionRow(label=
    offer.title + suffix, detail=offer.pitch, action=Action(name=TAKE_JOB, args={"title": offer.title},
    text=TAKE_JOB_TEXT.format(title=offer.title)))`; `scene_rows` → `InfoRow(label=self.run.question)`,
    `InfoRow(label="The job", detail=terms)`, `ActionRow(label="Go on", detail=left, action=Action(name=
    GO_ON, text=left))`, `InfoRow(label="Way on", detail="Keep playing, or name where you go and move
    on.")`; `jobs_panel`, `character_panel`, `trail_panel`, `items_panel` (step 23), rooms' `Ways out`
    rows → `InfoRow`. `ui/game.py` `sidebar` (`:250–262`) matches `case ActionRow()` (the button on
    `partial(self.move_on, row.action)`, the detail label when set), `case EntityRow()` (`entity_row`),
    `case InfoRow()` (`labeled_value` when `detail`, else the bare label); `move_on(self, action:
    Action)` runs `partial(self.session.move_on, Answer(text=action.text))` until step 32. Tests:
    `tests/core/test_hub.py:121–137` read `row.action == Action(name=TAKE_JOB, args={"title": …},
    text=TAKE_JOB_TEXT.format(title=…))`; `tests/core/test_scenes.py:155` `ActionRow(label="Go on",
    detail=…, action=Action(name=GO_ON, text=…))`, `:168` `InfoRow(label="The job", detail=JOB)`;
    `tests/breathless/test_tools.py:221` `isinstance(row, ActionRow) and row.action.text == …`;
    `tests/twentyfourxx/test_views.py:35`, `tests/breathless/test_views.py:15–16` → `InfoRow(...)`;
    reads of `icon_id` (`tests/core/test_engines_base.py:27–28`, `test_views.py:103`, `tests/tunnelgoons/
    test_views.py:37`) narrow with `isinstance(row, EntityRow)` first (the union has no such
    attribute); `GO_HOME`/`TAKE_JOB.format`/`REPORT_IN` in `tests/twentyfourxx/test_worldsmith.py:23,
    349,356,380,393,426` and `tests/tunnelgoons/test_worldsmith.py:13,218,235,246,251` read the `_TEXT`
    names; `tests/core/test_views.py` adds: a `Panel` of the three rows round-trips through
    `Panel.model_validate(panel.model_dump())` picking each by `kind`. Grep: `PanelRow(` finds
    nothing; `\.intent\b` in `src` finds `app/runtime.py` only.
32. **R1, buttons play typed actions.** (Evidence moved: `e2db974` split the sentence parse into
    `job_title` at `hub.py:348` with two readers, `Campaign.taken` and `SceneEngine.page_word`.)
    `hub.py`: `class TakeJob(Frozen)` with `title: str = Field(min_length=1)` (step 34 makes it
    `offer_id`); `job_title` (`:348–354`) and `Campaign.taken` (`:194–196`) go. `seam.py`: `transition(
    self, state: G, action: Action) -> Transition` (abstract) and `advance(self, draft: G, action:
    Action, worldsmith: WorldsmithAnswer)`; `page_word` (`:76–78`, `scenes/engine.py:104–106`) goes;
    `reopening(self, state: G, action: Action) -> Job | None` returns `None` unless `action.name ==
    TAKE_JOB`, the campaign exists and `world.at_hub`, else `campaign.left_open(parse(TakeJob,
    action.args).title)`; new concrete `check_offered(self, state: G, action: Action) -> None`: for
    `PURSUE` raise `Refusal("the world offers no transition from here")` unless `self.ready(state)`;
    otherwise raise `Refusal(f"the page offers no {action.name!r} here")` unless `action` equals the
    `action` of an `ActionRow` in `self.player_view(state).panels` (a list, `in`: `Action` holds a
    dict and is not hashable). `SceneEngine.transition(state, action)`: `self.check_offered(state,
    action)` then `Transition(mode="turn_then_advance", brief=CROSSING.format(left=…, pursuit=action.
    text))`; `advance(draft, action, worldsmith)`: `reopening = self.reopening(draft, action)`,
    `returning` = campaign, away, `action.name == GO_HOME`, the worldsmith's intent is `action.text`.
    `RoomEngine.transition`: `check_offered` then `Transition(mode="advance_only")`; `advance` and
    `write_next(self, draft: G, action: Action, worldsmith, *, reopening)` read `action.name ==
    REPORT_IN` for `returning` and pass `action.text` as the intent. `app/runtime.py`: `move_on(self,
    action: Action)` drops the `option_id` and `ready` refusals (`transition` refuses), computes
    `transition = self.engine.transition(self.state, action)`, runs `_turn(Answer(text=action.text),
    mastered=action.name == PURSUE)` for `turn_then_advance` (the page's own words spawn no master:
    decided by the name, no string is matched), sets `self.intent = action.text` for `advance_only`,
    then `_grow(action, transition.brief)`; `_grow(self, action: Action, brief: str | None)` calls
    `engine.advance(draft, action, …)` and files `action.text` where `intent` was. `ui/game.py`:
    `move_on(action)` runs `partial(self.session.move_on, action)`; `submit(moving_on)` runs `partial(
    session.move_on, Action(name=PURSUE, text=typed))` when moving on. Tests: `tests/support/table.py`
    `play_turn` moves on with `Action(name=PURSUE, text=answer.text)`; `tests/core/test_master_tools.py`
    `_SilentEngine.transition(state, action)` / `advance(draft, action, worldsmith)` and `Watching.
    advance` follow, `service.move_on(Answer(text=…))` → `Action(name=PURSUE, text=…)`, the two
    `pursuit` moves (`:301,326`) → `Action(name=GO_ON, text=pursuit)`; `tests/tunnelgoons/test_play.py:91`
    → `Action(name=PURSUE, text="Deeper in.")`; `tests/twentyfourxx/test_worldsmith.py` passes `Action(
    name=GO_HOME, text=GO_HOME_TEXT)`, `Action(name=TAKE_JOB, args={"title": "Job One"}, text=
    TAKE_JOB_TEXT.format(title="Job One"))` and `Action(name=PURSUE, text="I look around the
    warehouse.")` to `advance`; `tests/tunnelgoons/test_worldsmith.py:401,422,450` replace `campaign.
    taken(…)` by `ENGINE.reopening(state, Action(name=TAKE_JOB, args={"title": "Crates off Deck 9"},
    text=…))`, `:218–251` pass `Action(name=REPORT_IN, text=REPORT_IN_TEXT)` and `:440` `Action(name=
    PURSUE, text="Nose around the docks.")` to `write_next`; `tests/core/test_hub.py:346–351` (`taken`)
    deleted; `tests/core/test_master_tools.py` adds: on the one-shot, `move_on(Action(name=GO_HOME,
    text=GO_HOME_TEXT))` raises `Refusal` matching "offers no 'go_home'" and spawns nothing. Grep:
    `page_word\|job_title\|def taken\|_TEXT ==\|== .*_TEXT` finds nothing; `intent: str` in `seam.py`,
    `scenes/engine.py`, `rooms/engine.py` finds `render_next`/`write_next`'s worldsmith intent only.
33. **R3, the scene's status.** `scenes/world.py`: `class Open(Frozen)` (`kind: Literal["open"] =
    "open"`), `class Settled(Frozen)` (`kind: Literal["settled"] = "settled"`), `class Departed(Frozen)`
    (`kind: Literal["departed"] = "departed"`, `pursuit: str = Field(min_length=1)`), `type SceneStatus =
    Annotated[Open | Settled | Departed, Field(discriminator="kind")]`, above `SceneRun`; `SceneRun.left`
    (`:51–52`) becomes `status: SceneStatus = Open()`; `_playable_canon` (`:71`) refuses `opening.status.
    kind != "open"`; `settle` (`:278–288`) refuses `"this scene is already settled; the player has the
    way on"` unless `self.run.status.kind == "open"`, sets `Departed(pursuit=pursuit)` when `pursuit`
    else `Settled()`; `scene_rows` matches `case Departed(pursuit=pursuit)` (the Go on row), `case
    Settled()` (the Way on row), `case Open()` (nothing), then `HOME_ROW` under a campaign when not
    `Open`; `SceneEngine.ready` reads `world.run.status.kind != "open" or world.at_hub`. Tests: every
    `run.left` (`tests/core/test_master_tools.py:210,228,411`, `test_turn.py:173`, `test_scenes.py:141,
    147,151`, `tests/loner3e/test_engine.py:259`, `tests/breathless/test_tools.py:204,218`,
    `tests/twentyfourxx/test_tools.py:200,210`) reads `run.status.kind != "open"`, sets `run.status =
    Settled()` / `Departed(pursuit="the maintenance grate")`, or asserts `run.status == Open()` /
    `Departed(pursuit="the control deck")`; `tests/core/test_scenes.py` adds: `settle(False, "x")`
    leaves `Departed(pursuit="x")`, `settle(False, "")` leaves `Settled()`, and `Departed(pursuit="")`
    raises `ValueError`. Grep: `\.left\b` in `src tests` finds nothing.
34. **R4, offers and jobs by id.** `hub.py`: `class OfferProposal(Frozen)` with `id: Slug | None =
    Field(default=None, description="The id THE BOARD shows for an offer kept; omit it for a new
    one.")`, `title`, `pitch` (as today's `Offer`); `Offer` gains `id: Slug` first; `type BoardProposal`
    beside `Board`, same bounds, over `OfferProposal`; `Job` gains `id: Slug` first; `_jobs_in_order`
    requires unique `job.id` (the casefolded titles go); `Campaign.job(self, job_id: str) -> Job | None`
    replaces `titled` for id reads (`titled` stays for `history` until step 35), `left_open(self,
    job_id: str)` reads by id, `offer(self, offer_id: str) -> Offer` raises `Refusal(f"no offer
    {offer_id!r} is on the board")`, `job_ids(self) -> tuple[Slug, ...]`; the board rows' `args`
    become `{"offer_id": offer.id}` and their suffix reads `self.left_open(offer.id)`; `board_lines`
    prints `- {title} [{id}]{suffix}: {pitch}` (the worldsmith keeps an offer by that id). Free
    functions: `posted(offers: Sequence[OfferProposal], taken: Iterable[str]) -> tuple[Offer, ...]`
    (a given id is kept; a missing one is `slug(title, …)` clear of `taken`, the ids given and the ids
    allocated before it) and `board_unmet(offers: Sequence[OfferProposal], campaign: Campaign) ->
    list[str]` (a given id must be on `campaign.board` or a job's that is not `finished`, and given
    once; texts `"offer ids from THE BOARD or a job left open; these are neither: {ids}"`, `"each kept
    offer once: {ids}"`); `title_unmet` (`:370–375`) goes: the campaign is unique on ids, so a title
    is prose (the id check that replaces it is `board_unmet` at the return, and `apply_job`'s refusal
    below). `TakeJob.offer_id: Slug` replaces `title`. `seam.py`: `taken(self, state: G, action:
    Action) -> Offer | None` (`None` unless `action.name == TAKE_JOB`; refuses `"no board is here to
    take a job from"` off the hub; else `campaign.offer(parse(TakeJob, action.args).offer_id)`);
    `reopening` becomes `None if (offer := self.taken(state, action)) is None else campaign.left_open(
    offer.id)`. Proposals: `HubProposal.offers`, scenes' and rooms' `ReturnProposal.offers`, and
    `MapProposal.board` are `BoardProposal`; `HubProposal.opening_campaign` and rooms' `opening_canon`
    build `Campaign(place=…, board=posted(offers, ()))`; scenes' `apply_return` and rooms' `apply_return`
    set `campaign.board = posted(proposal.offers, campaign.job_ids())`. `apply_job(self, proposal, *,
    reopening: Job | None, job_id: Slug | None)` and rooms' `apply_extension(self, region, start, *,
    reopening, job_id: Slug | None)` build the new `Job(id=job_id or slug(title, campaign.job_ids()),
    …)` and refuse `f"job {new_id!r} was taken before and is not left open"` when `campaign.job(new_id)`
    exists; scenes' `advance` passes `job_id=None if (offer := self.taken(draft, action)) is None else
    offer.id` through `install_job(draft, proposal, *, reopening, job_id)`, rooms' through
    `install_next(draft, proposal, *, reopening, job_id)`. Bars: `scenes/worldsmith.py` `_hub_unmet`
    replaces its `title_unmet` line by `board_unmet(proposal.offers, campaign)` for a `ReturnProposal`
    under a campaign; `rooms/worldsmith.py` `job_refusal` drops its `title_unmet` lines and
    `return_refusal` adds `board_unmet(proposal.offers, campaign)` under a campaign; the `reopening`
    parameter of `scene_refusal`, `scene_unmet`, `_hub_unmet` and `job_refusal` goes with them
    (`advance`'s bar lambdas follow). The four shipped campaigns gain an `"id"` per offer:
    `scenarios/amber-tap/world.json` `the-debt-to-ruiz`, `the-quiet-contract`, `deck-9-crate-run`;
    `buried-bell` `the-sealed-cairn`, `the-drowned-archive`, `the-widow-s-debt`; `salt-lantern`
    `the-flooded-chapel`, `pell-s-debt`, `the-whistling-stair`; `waystation` `the-sick-room`,
    `the-supply-drop`, `the-sanctuary-rumor` (each `slug(title, ())`). Tests: every `Job(title=T, …)`
    and `Offer(title=T, …)` in tests gains `id=slug(T, ())` spelled out (`tests/support/{scenes,
    tunnelgoons}.py`, `tests/core/{test_hub,test_scenes}.py`, `tests/tunnelgoons/{test_world,test_tools,
    test_worldsmith,test_views}.py`, `tests/twentyfourxx/test_tools.py`; `Offer` in a proposal becomes
    `OfferProposal`); `test_two_jobs_with_one_title_are_refused` → one id, match "duplicate job ids";
    `tests/core/test_scenes.py:317–345` and `tests/tunnelgoons/test_worldsmith.py:604–616` (title taken
    before) deleted; the `TakeJob` args in `tests/twentyfourxx/test_worldsmith.py` and
    `tests/tunnelgoons/test_worldsmith.py` become `{"offer_id": "job-one"}` / `{"offer_id":
    "crates-off-deck-9"}`; `tests/core/test_hub.py` adds: `posted` keeps a given id and allocates
    `crates-2` beside `Job(id="crates")`; `board_unmet` refuses an unknown id and a finished job's id;
    `offer("nowhere")` refuses. Grep: `title_unmet\|def titled\b` finds `titled` in `hub.py` only
    (step 35); `casefold` in `hub.py` finds `named_unmet` only.
35. **R4, the walk by id.** `core/play.py`: `SceneRecord.job: str = ""` → `job_id: Slug | None = None`.
    `scenes/world.py`: `SceneRun.job` (`:54`) → `job_id: Slug | None = None`; `walked() -> list[Slug |
    None]`; `records()` and `run_of(…, job_id: Slug | None = None)` and `_land(…, job_id)` carry it;
    `apply_next` lands under the open job's `id` or `None`, `apply_return` under `None`. `rooms/world.py`:
    `Visit.job` (`:40`) → `job_id: Slug | None = None`; `walked_job` reads `self.visit.job_id == job.id`;
    `move` appends `Visit(place=…, job_id=None if job is None else job.id)`; `apply_return` sets
    `self.visit.job_id = None`; `records()` carries `job_id`. `hub.py`: `walk_start(walked: Sequence[Slug
    | None])` tests `walked[-1] is not None`; `check_walk(self, places, walked: Sequence[Slug | None])`
    reads ids (`f"run {index} walks a job the campaign never took: {job_id!r}"` and the other texts
    keep their shape); `records_of` compares `record.job_id == job.id`; `history` groups by `job_id`
    and looks the job up with `self.job`; `swap_out(walked: Sequence[Slug | None])` compares ids;
    `titled` goes. Tests: `tests/core/test_hub.py` `_record(title, job_id=None)` and every `check_walk`
    / `swap_out` list spells ids (`[None, "a1"]`, `[None, "ghost"]`; matches follow, e.g. "never took:
    'ghost'"); `tests/core/test_scenes.py` `_run(…, job_id: Slug | None = None)` and `runs[-1].job_id ==
    "b1"` / `is None`; `tests/support/scenes.py` `hub_runs` sets `job_id=slug(names.job_title, ())`;
    `tests/tunnelgoons/{test_world,test_tools,test_worldsmith,test_views}.py` `Visit(…, job="Bandits")`
    → `job_id="bandits"` and `visit.job == …` → `visit.job_id == …`; `tests/twentyfourxx/test_worldsmith.
    py:405,431` set and read `job_id`; `tests/core/test_hub.py` adds: `history` binds two jobs titled
    alike (`bandits`, `bandits-2`) as two chapters by id. Grep: `\.job ==\|\.job =\|job=\|def titled`
    in `src tests` finds nothing; `job: str` in `src` finds `breathless/world.py` (the Survivor's job)
    and `scenes/proposals.py` (the terms) only.
