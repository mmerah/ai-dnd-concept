# PROGRESS

One entry per PLAN.md phase: the counts, what was decided off-plan, what was refuted in review
and why, and what is known and accepted.

## Phase 1 — the fixes and the two boundary conventions

- `src` lines: 9,481 before, 9,483 after. The plan's band was 9,430 to 9,460. The five
  `parse(model, {...})` spellings of step 4 cost three lines each over the keyword form they
  replace, and `Observed` costs eleven over the tuple; the `panels.py` fold and the two
  `__init__` deletions did not cover that. Nothing was padded and nothing was cut past the plan.
- Split: B (platform) then A (engines), sequential. Off-plan assignment: step 13's `WORLDSMITH`
  constants edit `engines/scenes/engine.py` and `engines/rooms/engine.py`, so they went to A;
  step 3's `CLAUDE.md` line went to B, which owns `CLAUDE.md`. No file was edited by two parts.
- Off-plan edit: `PLAN.md` added to ruff's `extend-exclude` in `pyproject.toml`, beside
  `NEXT-SPECS.md` and for the same reason (ruff 0.16 formats markdown code blocks). On HEAD,
  `uv run ruff format --check` was already red on `PLAN.md`'s Phase 2 code block; the four
  commands cannot be green without it. Awaiting the maintainer's call; revert the one line if
  formatting `PLAN.md` is preferred.
- Cut folded from review: the `canon = deepcopy(canon)` in `SceneWorld.begin` and
  `RoomWorld.begin` went. `parse` with `revalidate_instances="always"` rebuilds every nested
  `Mutable` instance and container (checked: no npc, dict, list or way is aliased after `begin`).
- Cut folded from review: the unasserted `caplog` in the new `read_characters` test went.
- Refuted: "restore keyword construction in `begin_game` and the four `parse(cls, {...})` sites;
  a construction bug now reads as a `Refusal` and the dict loses static field checking." PLAN.md
  Phase 1 step 4 names all five sites and the reason (`Engine.compose` re-prompts only on a
  `Refusal` from `build`); `Game.commit` already turns a refused state into a `Refusal` the same
  way. The lost static check on the dict keys is known and accepted (below).
- Refuted: "`content_id` inside the engine loop warns twice for a non-slug folder holding two
  engine files." PLAN.md step 1 names that shape; the case needs a backup folder that also holds
  two engine sheets, and the cost is a repeated log line.
- Refuted: "`can_type` was made public only for the test." PLAN.md step 10 names the rename.
- Refuted: "the `PanelRow` class comment duplicates the two field comments." The field comments
  say what the sidebar draws for each shape (an icon, a Move-on button); the class comment says
  the order the shapes are told apart in. Neither is in the code.
- Known and accepted: the five `parse(model, {...})` sites pass a `dict[str, object]`, so a
  renamed field there fails at runtime, not under basedpyright; the phase's own tests cover each.
- Known and accepted: `PendingOption.name` is required. Every `src` site names its tool, so no
  save changes; a save whose open decision held a nameless option would now be stale.
- Known and accepted: the two new comments (`EngineId`, `PanelRow`) wrap onto two `#` lines to
  stay under the 100-column limit.
- Reviews: Fable (`reviewer` agent) and Opus (`reviewer` agent, `model: opus`); no `codex` on
  the machine, so no Codex Sol review ran.
- Verified: four commands green; golden regen changes no fixture; `uv run aidm` serves the home
  page with a `My Backup` folder and a `.DS_Store` under `characters/`;
  `ROLES__NARATOR__MODEL=x` makes `read_settings()` exit naming `narator`.
- Follow-up prose cut, same branch: 9,483 → 9,444 lines. Twenty-nine docstrings and comments
  that restated a name, a signature or the line below went; the `RoomEngine` docstring is one
  line; `SceneEngine.world` is one line. No schema description changed (golden regen clean).

## Phase 2 — the engine seam and the two families

- `src` lines: 9,444 before, 9,438 after. The plan's band was 9,240 to 9,300. Both reviews
  found the band unreachable from the eighteen steps: every step is a move (engine → sheet,
  engine → world, registry → seam, the two hoists), so the real deletions (`begin_game`,
  `render_job`/`render_return`, the two lifecycle bodies) are cancelled by what the moves add
  (`World`, `CommissionArgs`, `worldsmith_prompt`, `apply_extension`/`apply_return`, keyword
  signatures on the sheet methods, nine one-line "Free" docstrings). The maintainer chose a
  prose sweep over the whole of `src` (Opus, every docstring and comment read): five lines
  went; the rest each carry a reason the code cannot show. Nothing was padded.
- Split: A (seam) → B1 (base, hub, scenes) → B2 (rooms) ∥ C1 (Loner) ∥ C2 (Breathless) ∥ C3
  (24XX). Off-plan assignments: step 11's free-function docstrings went by file owner; step 8's
  five `require_alive_here` call-site renames in `loner3e/engine.py` went to B1 so B1 left the
  tree green; the three `Pack` field deletions went to B1 with the base change. No file was
  edited by two implementers at once.
- Off-plan, on the maintainer's call: `Campaign.hub_block(hub_title, brief, records, *,
  returning, reopening)` replaces PLAN step 16's `this_job`/`job_before`; both families'
  `hub_sections` now keep only their guard, title and brief. Both reviews flagged the block
  spelled twice.
- Off-plan: PLAN step 11's docstring for the `*_refusal` builders ("neither may import the
  other's module") was false in one direction of each family (`scenes/world.py` imports the
  drafts; `rooms/drafts.py` imports the world). The lines now say what is true: rooms, "the
  world may not import the drafts; one bar module"; scenes, "the drafts may not import the
  world, and the authoring call has no world".
- Cuts folded from review: `write_extension` reads `world.at_hub` alone (it is False without a
  campaign) and calls `walked_job()` once; `NO_SOURCE` inlined; `apply_extension` reads
  `self.current` after `attach`; `apply_return` lands recaps through one comprehension;
  `Campaign.sections` spreads `tail(at_hub=True)`; the dead `current` set in
  `Operator.change_hindrances` went; `card` inlined in `install_extension`.
- Added from review: `tests/core/test_seam.py` tests `srd_pack`'s refusal, the one behaviour
  the phase added rather than moved.
- Refuted: "`_grow` lost the `validate` inside its `try`, so a `Refusal` from `engine.commit`
  now escapes to the UI." PLAN step 3 prescribes the drop; `validate` checks only the pack list
  and kind-vs-campaign, which `advance` never changes, and the `draft.commit()` revalidation at
  that site was already outside the `try`.
- Refuted: "`World.exchanges()` through `records()` builds a record and a `require_place` per
  visit." PLAN step 1 names the shape; `RoomWorld._playable` checks every visit's place, so it
  cannot raise on a committed state; the cost is one frozen record per visit per prompt.
- Refuted: "`roll_loot`'s face ladder as a table." Step 10 moves the body verbatim.
- Refuted: "one comment per module instead of nine docstrings." Step 11 asks for one line on
  each free function; each is now one line.
- Known and accepted: the `hub_block` fold's signature wraps to eight lines under the formatter,
  so the fold saved three lines, not the eighteen estimated.
- Known and accepted: `leave` and `kill` now refuse with "Bring them here first, or act on who is
  here." and name `entity.name` (PLAN step 8, intended).
- Known and accepted (D13): the rooms return prompt carries ENGINE GUIDANCE and THE HUB, and its
  WHAT COMES NEXT is the player's `Report in.`.
- Reviews: Fable (`reviewer` agent) and Opus (`reviewer` agent, `model: opus`); no `codex` on
  the machine, so no Codex Sol review ran.
- Verified: four commands green (538 tests); golden regen changes no fixture; every grep of
  steps 2, 3, 7, 8, 11, 13, 17 as stated; `Any` only in the `Game[Any]`/`Engine[Any, Any]`
  bounds; `engines/scenes/` 1,242 and `engines/rooms/` 1,200 lines; `uv run aidm` serves the
  home page; the Tunnel Goons campaign loop (take a job, walk into it, report in, take it again)
  run offline through `engine.advance` with a scripted worldsmith: the retake reopens at the
  job's own start with two attempts. The roles spawn a CLI, so the in-app loop was not run here.

## Phase 3 — the platform, the stored shapes, the tests

- `src` lines: 9,438 before, 9,486 after. The plan's band was 9,220 to 9,290. Both reviews
  found the band unreachable from the thirteen steps: every step is a move (free functions →
  `Library` methods, `read_catalog` → `LauncherCatalog.read`, `claim`/`post_bearer` → their own
  module, `_act` loop → `_run_master`), and what the moves add (`Library`'s wrapped signatures,
  `providers.py`'s imports, `Runtime.library`/`store`, `routed`, `Engine.tool`, `_withdrawing`,
  the two validators) outweighs the deletions (`Speaker`, `Game.turn`, `LaunchTarget.path`,
  `_scenario_ids`, the two `.get`+raise gates). Tests: 9,551 before, 9,586 after against
  "about 130 fewer": `tests/support/scenes.py` costs 49 lines to delete 76, `Library(...)` and
  `decode(...)` at the call sites add a line each, and the three new tests add 30. Nothing was
  padded; every cut both reviews named was folded.
- Split: A1 (the gates, `providers.py`, `_present`, `withdraw`) → A2 (`Library`, the catalog,
  `game_path`) → B (the stored shapes, the tests), sequential; the plan's A was two context
  windows of work. No file was edited by two implementers at once.
- Off-plan, from review: `routed` returns the routed value alone, not `(engine, value)`; both
  callers discarded the id. `game_path` formats `GAME_ROUTE` instead of spelling the route
  twice. `Runtime._mount()` builds `library` and `store` for `__post_init__` and
  `reload_settings`. `tests/support/scenes.py` has no `hub_scene`/`job_scene`: each had one
  caller, so `hub_runs` builds the two runs. `support.loner.loner3e_session` is `session`
  (the step 12 grep). `ui/game.py`'s clip line drops the dead `history and` guard.
- Added from review: `tests/core/test_views.py` tests `SpokenLine`'s validator (a speaker id
  without a name, a name without an id).
- Refuted: "`live_turn` builds `player_view()` on every idle tick." `live_turn` re-renders only
  from `GamePage.refresh`, which `poll_turn` calls when `Observed` changed, and `Observed.of`
  calls `player_view()` every tick regardless.
- Refuted: "`claim` does not belong in `providers.py`." PLAN step 4 (P17) names the module as
  holding both; each caller uses `claim` to hold one `post_bearer` in flight.
- Refuted: "cut `HubNames` to its four title/question fields." The situations and the terms
  feed `SceneRun.situation` and `Job.terms` inside the builder; cutting them adds three
  parameters to `hub_runs`/`hub_campaign`, the same count in another spelling.
- Awaiting the maintainer's call (reviewer cuts refuted on the orchestrator's own reading):
  "a `Runtime.catalog()` method replaces the two `LauncherCatalog.read(runtime.library,
  runtime.store, runtime.engines)` calls" (refuted: PLAN step 7 names that call at both sites,
  and the first argument is the library, not the runtime, so the method rule does not bind);
  "`_bubble`'s `chat_name` local is redundant" (refuted: reassigning the `name` parameter hides
  the caller's value; the local names what the chat shows).
- Known and accepted: a save from before this commit is stale (`Game.turn`, `SpokenLine.speaker`,
  `NarratorView.speakers` changed shape); the launcher skips it with "turn: Extra inputs are
  not permitted".
- Known and accepted: `Library.read_characters`'s docstring wraps to two lines at its new
  indentation.
- Reviews: Fable (`reviewer` agent) and Opus (`reviewer` agent, `model: opus`); no `codex` on
  the machine, so no Codex Sol review ran.
- Verified: four commands green (541 tests); golden regen changes the four `master.txt` by one
  line each (`turn 1` → `turn 3` for Loner, `turn 2` elsewhere) and nothing else; every grep of
  steps 1-4 and 7-13 as stated; `Any` only in the bounds and `entities.py`'s comment;
  `.validate(` in `src` finds `seam.py` only; `uv run aidm` serves the home, create and
  scenario pages and skips a Phase 2 save with the launcher's warning; one scripted turn offline:
  the exchange line carries `mara`/`Mara`, the journal reads `**Mara:** …`, the master prompt
  says turn 2, the catalog lists the save at turn 2. The roles spawn a CLI, so the in-app turn
  was not run here.
