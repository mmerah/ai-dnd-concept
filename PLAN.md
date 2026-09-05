# PLAN — one seam, one scaffold, one name per thing

Two phases. Phase 1 is the engine seam and the two families (P1 tail, P2, P4, the engine half of
P6 and P7). Phase 2 is the per-engine scaffold (P3, D5, D7), the platform (P5, D2, D6, the platform
half of P6 and P7) and the tests (P8). P and D numbers are `PROPOSALS.md`'s (deleted; `git show
1732e73:PROPOSALS.md`); every decision letter is applied below and nothing is left to decide.
Line numbers are as of `1732e73` (`src` identical to `fc4d354`); find a site by the name quoted
beside it.

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
   (step 3). Phase 2 changes no fixture. Worldsmith prompts have no golden. Anything else changing is a bug.
3. `src` line count, at the start and end of each phase: `find src -name '*.py' | xargs cat | wc -l`.
4. One commit per phase; the phase skill's `PROGRESS.md` entry rides in it (Phase 1 recreates the file).
5. Standing limits: fifteen engine tools (plus `commission`), `engines/<id>/` under 2,000 lines, imports
   `core <- engines <- turn <- app <- ui`, no `Any` beyond the `Game[P]` bounds, empty `__init__.py`,
   `ScriptedSpawner` only, `Refusal` the one message; `RoomEngine` stays (D3 C), the four `ChangeWorld`
   classes stay (D5 A), `crossing() -> str | None` stays (D19 A), P9 is not taken.
6. A delete, move or rename lists the grep the orchestrator runs afterwards (`grep -rn <name> src tests
   --include=*.py`) and what it must find.

| phase | what lands | `src` after | about |
|---|---|---|---|
| start | | 9,330 | |
| 1 — the seam and the two families | `*Proposal`, `check_scenario` gone, `CommissionArgs` base + concrete `commission_tool`, one `worldsmith_prompt` in `hub.py`, `on_order_lines`, hub residents moved, `apply_next/apply_job/apply_return`, `install_next/job/return`, the hub forwarders and `Engine.answer` inlined, `Subject.row`, rooms on scenes' lifecycle names | 9,255–9,285 | 9 h |
| 2 — the scaffold, the platform, the tests | concrete `create_character`/`creation_steps`, `items_shown`, Loner/24XX folds and methods, `pack.source` shown; `play`/`move_on`, `Presentation`, `save`, prompt constants, `narration_refusal`, `parse` at two boundaries, `history/scene/ready/newest/tools`, `Installed` + `FileStore.restore`, `way_on_panel` gone; nineteen tests folded | 9,225–9,250 (D2 A's `Presentation` costs ~25) | 9 h |

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
2. **P1 tail.** Delete `Engine.check_scenario` (`seam.py:186–188`) and its calls (`scenes/engine.py:115`,
   `rooms/engine.py:82`); `check_character` (`seam.py:76`) keeps only the player-id line.
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
   (`seam.py:213`) goes. `SceneEngine`: `commission_args = SceneCommission`, `commission_hint` = the
   string after `COMMISSION_BRIEF +` at `scenes/engine.py:203–204`, its `commission_tool` override
   deleted (rooms' override at `rooms/engine.py:206` stays until step 11). Fold `Engine.commission`
   (`seam.py:130–142`) into `ask_worldsmith(self, draft: G, args: CommissionArgs, _rng: Random) ->
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
   `write_next` (`scenes/engine.py:326–327`) uses it (the scenes' `- a {kind}` spelling goes; no test
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
6. **P4, the world.** In `scenes/world.py` replace `apply_scene` (`:305–335`) by
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
   (`scenes/engine.py:333`) meanwhile takes `scene: NextProposal[C] | ReturnProposal[C]`, drops its own
   `model_copy` (`_land` copies), and dispatches in this order: `isinstance(scene, ReturnProposal)` →
   `job = world.apply_return(scene)`; `isinstance(scene, JobProposal)` → `world.apply_job(scene,
   reopening=reopening)`; else `world.apply_next(scene)` (the remainder narrows to `NextProposal[C]`);
   `write_next`'s `model` annotation and return become `type[NextProposal[C] | ReturnProposal[C]]` /
   `NextProposal[C] | ReturnProposal[C]`; step 7 removes the dispatch. In
   `scenes/proposals.py` add `SceneProposal.opening_campaign(self) -> Campaign | None: return None`
   and the `HubProposal` override `Campaign(place=self.place, board=self.offers)`;
   `opening_canon` (`scenes/engine.py:300–302`) calls it. Tests: `tests/core/test_scenes.py:199–296`
   call `apply_next`, `apply_job(…, reopening=job)`, `apply_return`; `tests/loner3e/test_world.py:80,
   107,110,163` and `tests/twentyfourxx/test_worldsmith.py:48–66,86,206` call `apply_next` with a
   `_next_proposal(...)`; a bare `_proposal(...)` passed to `install` becomes `_next_proposal(...)`,
   added to `tests/breathless/test_worldsmith.py` as 24XX's builds it; `tests/core/test_master_tools.py:67`
   builds `NextProposal[Loner3eSheet].model_validate_json(_scene())`. Grep: `apply_scene`
   finds nothing; `isinstance` in `scenes/world.py` finds nothing.
7. **P4, the engine.** `render_next(self, draft: G, intent: str, answer: type[BaseModel], *,
   returning: bool, follows_arc: bool, reopening: Job | None = None, asked: str = "") -> str`
   replaces the two `issubclass` reads (`:246`); `render_commission` passes `returning=False,
   follows_arc=False`. `write_next` becomes generic: `async def write_next[M: BaseModel](self, draft:
   G, intent: str, worldsmith: WorldsmithAnswer, model: type[M], refusal: Check[M], *, returning:
   bool = False, reopening: Job | None = None) -> M` = render (`follows_arc=not returning`,
   `asked=draft.on_order_lines()`) then `await worldsmith(prompt, model, refusal)`. `install`
   (`:333–357`) becomes `install_next(draft, proposal: NextProposal[C]) -> list[Fact]`,
   `install_job(draft, proposal: JobProposal[C], *, reopening: Job | None)` (card line `The job:
   …`), `install_return(draft, proposal: ReturnProposal[C])` (the finished note, then `[job.closed(),
   opened]`), sharing `opened(self, draft: G, proposal: SceneProposal[C], label: str, *lines: str)
   -> Fact` (clears `draft.commissions`, the trace with the party, the card `label: title` /
   `At stake: question` / `*lines`). `advance` computes `reopening`, `later = draft.on_order()`, a
   local `bar(answer: SceneProposal[C]) -> str | None` over `scene_refusal`, then one of three
   branches — `returning` (campaign, away, `intent == GO_HOME`): `ReturnProposal[self.cast]` →
   `install_return`; `world.at_hub`: `JobProposal[self.cast]` with `reopening` → `install_job`; else
   `NextProposal[self.cast]` → `install_next` — each `(*self.leaving(draft), *install)`. Tests:
   `tests/core/test_master_tools.py:67` `_SilentEngine.advance` calls `install_next`;
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
8. **P7, the engine folds.** (a) `question_heading` (`hub.py:372`) inlined into `master_sections`
   (`scenes/engine.py:125`); `tests/core/test_hub.py:180` deleted. (b) `Campaign.terms` (`hub.py:157`)
   inlined into `scene_rows` (`scenes/world.py:353`: `(job := self.campaign.open_job()) is not None
   and job.terms`); `sections` (`:269`) into `hub_block`; `board_rows` (`:236`) into `board_panel`;
   `job_row` (`:280`) into `tail`. `tests/core/test_hub.py:124,134` read `board_panel(at_hub=True)[0]
   .rows`, `:226` asserts the panel's title and row count instead of comparing against `board_rows()`,
   `:121–162,209–226` otherwise call `hub_block(title, brief, (), returning=…, reopening=None)` and
   `dict(tail(at_hub=False))["THE JOB"]`; `tests/tunnelgoons/test_views.py:68` reads
   `board_panel(at_hub=True)[0].rows`.
   (c) `here_lines`/`hidden_lines` (`scenes/world.py:201–205`) inlined into `master_sections`.
   (d) `Subject.row(self, label: str | None = None) -> PanelRow` in `core/views.py` (`label` defaults
   to `name`, `detail=brief`, `icon_id=id`); move `PanelRow` and its comment (`views.py:32–39`) above
   `Subject` first, or the annotation raises `NameError` at import; `here_panel` (`base.py:143–144`) and `party_panel`
   (`scenes/world.py:348`, via `m.subject().row()`) use it; rooms' site is step 12. (e) `Engine.answer`
   (`seam.py:98–105`) inlined into `Turn._consume` (`turn/run.py:74`): `try: found = engine.tool(
   option.name) except Refusal as missing: raise Refusal(f"the {engine.id!r} engine has no tool
   {option.name!r} to play option {chosen!r}") from missing` (`chosen` is `option.id`, so the text
   holds), then `self._apply(lambda copy, dice: found.call(copy, option.args, dice))`; `tests/core/test_decisions.py:204–206` drive the same two
   refusals through `Turn.begin(engine, _pending(state, decision-with-that-option), Answer(option_id=
   "lantern"), Random(0))`, same `match`. (f) D5 A: drop the `Free:` docstrings at `base.py:141` and
   `scenes/world.py:400` (each is the whole docstring). Grep: each name in (a)–(e) finds nothing;
   `Free:` under `engines/scenes` and `base.py` finds nothing.
9. **P6, rooms (D3 A).** `git mv src/aidm/engines/rooms/drafts.py src/aidm/engines/rooms/proposals.py`;
   `MapDraft→MapProposal`, `NpcDraft→NpcProposal`, `ItemDraft→ItemProposal`, `ReturnDraft→
   ReturnProposal`; `map_draft()→opening_proposal()`, `render_map→render_opening`,
   `render_extension→render_next`, `write_extension→write_next`, `install_extension→install_next`
   (it installs what `write_next` wrote, return included; `install_commission` already matches);
   parameters `draft`/`extension` holding a proposal → `proposal` (`rooms/worldsmith.py` bars,
   `build_scenario`, `opening_canon`, `install_next`). Rooms' three `isinstance` on proposals
   (`rooms/engine.py:306,354,357`) stay: `RoomEngine` is not reshaped (D3 C). Tests:
   `tests/tunnelgoons/test_worldsmith.py` follows. Grep: `Draft` under `engines/rooms` and
   `tests/tunnelgoons` finds nothing; `render_map\|write_extension\|install_extension\|map_draft`
   finds nothing.
10. **P2, rooms adopt the shared tool and line.** Delete `commission_tool` (`rooms/engine.py:206–215`);
    `RoomEngine.commission_args = RoomCommission`, `commission_hint` = the string after
    `COMMISSION_BRIEF +` (`:210–212`). `write_next` uses `draft.on_order_lines()` (`:284`). Grep:
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
12. **P7, rooms.** The Carrying rows (`rooms/engine.py:136`) become `item.subject().row()`; drop the
    `Free:` docstring at `rooms/worldsmith.py:66`. Grep: `PanelRow(label=` under `engines/rooms` finds
    the `Ways out` rows and `REPORT_ROW` only; `Free:` under `engines/rooms` finds nothing.

---

## Phase 2 — the scaffold, the platform, the tests

Split: A and B parallel, then C.
- A, the platform: steps 13–21; owns `app/**`, `turn/context.py`, `core/io.py`, `core/views.py`,
  `ui/game.py`, `ui/settings.py`; tests `tests/core/{test_game_service,test_master_tools,test_speech,
  test_views,test_store,test_integrity_boundaries,test_golden_turn,test_decisions,test_turn}.py`,
  `tests/ui/*`, `tests/tunnelgoons/test_play.py`, `tests/twentyfourxx/test_engine.py`,
  `tests/support/{table,loner}.py`.
- B, the scaffold: steps 22–28; owns `engines/seam.py`, `engines/base.py`, `engines/scenes/engine.py`,
  `engines/{loner3e,breathless,twentyfourxx,tunnelgoons}/**`, `ui/create.py`; tests
  `tests/*/test_create.py`, `tests/breathless/test_views.py`, `tests/twentyfourxx/test_world.py`,
  `tests/core/{test_seam,test_rooms}.py`.
- C, the tests: steps 29–30; owns `tests/**`.

13. **P5 with D8 A.** In `app/runtime.py` split `play` (`:100–131`) and `extend` (`:166–178`):
    `async def play(self, answer: Answer) -> None: await self._turn(answer)`; private `async def
    _turn(self, answer: Answer) -> str` is today's `play` body without the `moving_on` lines, returning
    `turn.prompt`; `async def move_on(self, answer: Answer) -> None` refuses `"the world offers no
    transition from here"` unless `engine.ready`, computes `brief = engine.crossing(state, answer.text)`,
    then under one `try/finally` that resets `self.intent, self.phase = "", None`: with a brief, `prompt
    = await self._turn(answer)` and, if `engine.over(self.state) is None`, `await self._grow(prompt,
    brief)` + `self._present()`; without one, refuse `"a transition needs written intent"` on an
    `option_id`, set `self.intent = answer.text`, `await self._grow(answer.text, None)`. `extend` goes,
    and with it its "a turn is already in flight" and "no frontier to extend" refusals: the page's
    `play_refusal` and `ready` gate both; no test matches either text.
    `ui/game.py`: `_send` (`:393`) goes; `decision_panel.answer` runs `self._run(partial(session.play,
    Answer(option_id=…)))`, `submit(moving_on)` runs `partial(session.move_on if moving_on else
    session.play, Answer(text=typed))`, `move_on(intent)` runs `partial(session.move_on, Answer(text=
    intent))`. Tests: `tests/support/table.py` `play_turn` awaits `move_on(answer)` when `moving_on`
    else `play(answer)`; `tests/core/test_master_tools.py:257,396` and `tests/tunnelgoons/test_play.py:91`
    call `move_on(Answer(...))`; `test_master_tools.py:239–260` (the `intent` bubble) holds. Grep:
    `moving_on` in `src` finds nothing; `def extend\|\.extend(answer` finds nothing; `_send` finds nothing.
14. **D2 A and the page's reach.** New `app/present.py`: `@dataclass(slots=True) class Presentation`
    with `media: Illustrator | None = None`, `reader: Reader | None = None`, `_background: set[Task[
    None]] = field(default_factory=set, repr=False)` and the six methods moved from `GameService`
    (`runtime.py:142–145,254–287`), each taking what it read from the game: `scene_art(scene:
    NarratorView)`, `icon(entity_id)`, `newest_clip(newest: Exchange | None)`, `illustrate(scene, player:
    Subject, narration: str = "")`, `speak(newest)`, `show(scene, player, newest)` (was `_present`), plus
    private `_retain`. `GameService` loses `media`, `reader`, `_background`, gains `present: Presentation
    = field(default_factory=Presentation)` after `store`; `_present(self)` calls `self.present.show(
    self.scene(), self.player_view().player, self.newest())`. Add `history(self) -> tuple[Exchange, ...]`,
    `scene(self) -> NarratorView`, `ready(self) -> bool`, `newest(self) -> Exchange | None` (was
    `_newest`), `tools(self) -> tuple[MasterTool[AnyGame], ...]`; `unopened` and `Runtime.published_tools`
    read them. `Runtime._open` passes `present=Presentation(media=open_illustrator(…), reader=
    open_reader(…))`. `ui/game.py`: `session.history()` (`:62,162,268`), `session.scene()` (`:141`),
    `session.ready()` (`:63,206,368`), `session.scenario.meta.title/.premise` (`:92,164`),
    `session.player_view().prompt is not None` (`:166`), `session.present.illustrate(session.scene(),
    session.player_view().player)` (`:91`), `session.present.scene_art(session.scene())` (`:148,316`),
    `session.present.newest_clip(session.newest())` (`:121,181,320`), `session.present.icon(…)`
    (`:258,435`), `session.present.media is not None or session.present.reader is not None` (`:126`).
    `session.engine.title` (`:92`) is the one read of `session.engine` left. Tests:
    `tests/core/test_speech.py:148–164` use `session.present.reader = …`, `session.present.speak(
    session.newest())`, `session.present._background`, `session.present.newest_clip(session.newest())`,
    `session.newest()`. Grep: `session\.state` in `ui/` finds nothing; `session\.engine` in `ui/` finds
    `ui/game.py` once (`.title`); `_newest\|def illustrate\|def speak` in `runtime.py` finds nothing. Costs
    about +25 lines (the module header and five accessors); D2 A accepts it.
15. **P6, `save`.** `GameService.commit` (`runtime.py:294`) → `save`; five callers in `runtime.py`;
    `tests/core/test_speech.py:149`, `test_golden_turn.py:33`, `test_decisions.py:103`. Grep:
    `self\.commit(\|service\.commit(\|session\.commit(` finds nothing (`Engine.commit`, `Game.commit`
    stay).
16. **P7, prompt files one way.** `turn/context.py`: `MASTER = (_PROMPTS_DIR / "master.md").read_text(
    encoding=ENCODING)` and `NARRATOR = …` as module constants; `_prompt` and the `cache` import go.
    Grep: `_prompt(` in `turn/` finds nothing; `@cache` in `src` finds nothing.
17. **P7, one speaker rule.** `core/views.py`: `spoken`'s refusal (`:73`) becomes `f"nobody here has id
    {line.speaker_id!r}. Only the player or someone here with them speaks; leave `speaker_id` null
    for narration."`; `narration_refusal` returns the empty-lines message, else `try: self.spoken(
    narration.lines) except Refusal as refused: return str(refused)`, else `None`; `speakers_refusal`
    (`:78–87`) goes. Lost: the re-prompt names the first stranger, not every stranger. Test, `tests/core/test_views.py`: `narration_refusal` names a stranger's id and
    `None` for a subject who speaks. Grep: `speakers_refusal` finds nothing.
18. **P7, `parse` at two boundaries.** `ui/settings.py:91`: `parse(Settings, merged)` under `except
    Refusal`; `app/spawn.py:87`: `result = parse(_ClaudeResult, decode(output))` under `except Refusal
    as broken: raise Refusal(f"claude printed no JSON result: {output[-500:]}") from broken`
    (`tests/core/test_spawn.py:63` holds; `_object` at `:265` keeps `ValidationError`). Grep:
    `ValidationError` in `src` finds `core/entities.py` and `spawn.py:_object` only.
19. **P7, one decode-and-restore.** `core/io.py`: `class Installed(Protocol)` with `scenario: type[
    AnyScenario]` and `def restore(self, value: JsonValue) -> AnyGame: ...` (`core` names no engine;
    two methods need it); `FileStore.load` → `restore(self, slug: str, engines: Mapping[EngineId,
    Installed]) -> AnyGame | None` (read, `decode`, `routed`, `engine.restore`); `Library.read_scenario(
    name, engines: Mapping[EngineId, Installed])` and `read_scenarios(engines)` parse with
    `routed(value, engines).scenario`. `GameService.__post_init__` (`runtime.py:69–73`) holds one
    engine: `saved = self.store.restore(self.slug, {self.engine.id: self.engine})` (a foreign save now
    reads "the 'x' engine is not installed"; no test matches the old text); `Runtime._open`
    (`:402–405`) and `launch.py:70,97–102` pass `self.engines`/`engines` (`engine = engines[state.
    engine]`; `decode`, `routed` imports in `launch.py` go).
    Tests: `SCENARIO_MODELS` (`tests/support/table.py:47`) goes, its six users pass `ENGINES_BUILT`;
    `Table.saved` and `tests/core/test_store.py:37,48`, `test_game_service.py:37` call `store.restore(
    slug, ENGINES_BUILT)`. Grep: `\.load(` in `src tests` finds nothing; `SCENARIO_MODELS` finds
    nothing; `scenario_models` finds nothing.
20. **D6 A.** Delete `way_on_panel` (`ui/game.py:203–217`), its call (`:106`) and its refresh (`:134`).
    Grep: `way_on_panel` finds nothing.
21. **D5 A, platform half.** Drop the `Free:` line (first line only) of the docstrings at
    `app/providers.py:20` and `app/media.py:168`. Grep: `Free:` in `src` finds nothing.
22. **P3, one `create_character`.** `Engine.create_character(self, name: str, brief: str, picks: Picks)
    -> AnyCharacter` becomes concrete: `check_picks(self.creation_steps(picks), picks)`, then `return
    self.character(id=slug(name, ()), engine=self.id, payload=self.sheet(name, brief, picks))`; new
    abstract `sheet(self, name: str, brief: str, picks: Picks) -> P`. The four `create_character`
    (`loner3e/engine.py:108`, `breathless/engine.py:129`, `twentyfourxx/engine.py:150`,
    `tunnelgoons/engine.py:118`) become `sheet` returning the sheet (Tunnel Goons keeps its
    `ABILITY_POINTS` refusal inside). Tests: `tests/core/test_seam.py:63` and `test_rooms.py:56` stubs
    define `sheet` instead; `test_seam.py:130` passes `{"pack": "srd"}` (empty picks are now refused
    by `check_picks`); the four `test_create.py` hold. Grep: `def create_character` finds
    `seam.py` only.
23. **P3, one `creation_steps` for scenes.** `SceneEngine.creation_steps(picks)` concrete: `first =
    self.pack_step()`, `pack = self.packs.get(picked(picks, "pack"))`, `(first,)` if `None` else
    `(first, *self.pack_steps(pack, picks))`; new abstract `pack_steps(self, pack: K, picks: Picks) ->
    tuple[CreationStep, ...]`. Loner (`:79–106`), Breathless (`:108–127`), 24XX (`:105–148`) keep only
    the steps after `first`; `Engine.creation_steps` stays abstract for Tunnel Goons.
    `tests/core/test_seam.py:60` stub defines `pack_steps` returning `()`. Grep: `def creation_steps`
    finds `seam.py`, `scenes/engine.py`, `tunnelgoons/engine.py`, `tests/core/test_rooms.py`.
24. **P3, one items hook.** `base.py`: `Person.items_title: ClassVar[str] = ""` (a `ClassVar`, so no
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
25. **P7, Loner's glossary in one method.** `Loner3eEngine.glossary` (`loner3e/engine.py:140`) absorbs
    `meanings` (`:147`) and `pack_meanings` (`loner3e/tools.py:124`): the packs from `state.packs`, a
    `detail_of` over their skills, frailties and gear, the tags of everyone `here()` in that order;
    the two callees go. `tests/core/fixtures/prompts/loner3e/master.txt:147` pins the section. Grep:
    `meanings` finds nothing.
26. **D5 A, Loner.** `_strike`, `_refuse_unless_ready`, `_pair` (`loner3e/engine.py:265–305`) become
    private methods on `Loner3eEngine` with `self` first; `_absorbed` (a list) stays free. Grep:
    `^def _strike\|^def _refuse_unless_ready\|^def _pair` finds nothing.
27. **D5 A, 24XX.** `starting_items` (`twentyfourxx/engine.py:346`) becomes `Pack.starting_items(self,
    specialty: Specialty, weapon: Kit | None) -> dict[EntityId, Item]` in `twentyfourxx/worldsmith.py`
    (the pack owns the kits: `(*self.starting_kit, *specialty.kit, *(() if weapon is None else
    (weapon,)))`; `worldsmith.py` gains the `EntityId`, `slug` and `Item` imports, no cycle since
    `world.py` does not import it); `sheet` calls it. Test: `tests/twentyfourxx/test_world.py:103` moves
    to `tests/twentyfourxx/test_create.py` as `ENGINE.packs["srd"].model_copy(update={"starting_kit":
    (Kit(name="Comm"), Kit(name="Comm"))}).starting_items(Specialty(id="bare", label="Bare",
    detail="none", skills={}), None)` keyed `["comm", "comm-2"]`. Grep: `^def starting_items` finds nothing.
28. **D7 B.** `SceneEngine.pack_options` (`scenes/engine.py:105`) sets `detail=pack.source`; the
    scenario form's Table sets select (`ui/create.py:164`) labels `f"{pack.label} — {pack.detail}"`;
    the character form's pack step shows it through its existing `detail` branch (`:73`). Test,
    `tests/core/test_seam.py:134` becomes `pack_options()[0].detail == "the test"`.
29. **P8, the tests fold into `tests/core`.** `tests/support/table.py`: `SCENE_ENGINE_IDS = (LONER3E,
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
30. **P8, one opener.** Delete `open_game_for` (`tests/support/table.py:199`) and `support.loner.open_game`
    (`:94`); callers use `open_table(saves, engine_id=…, state_type=…, …)` (`ENGINES_BUILT[id].game`
    where the engine is a parameter, `Loner3eGame` for Loner; `engine=` passes through). Grep:
    `open_game_for\|open_game\b` in `tests` finds nothing.
