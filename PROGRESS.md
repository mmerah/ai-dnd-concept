# PROGRESS

One entry per phase of `PLAN.md`: counts before and after, decisions made off-plan, refuted
review findings and why, anything known and accepted.

## Phase 1 — the turn and the spawn

- `src` lines: 9,742 before, 9,466 after (target about 9,410). Tests: 476 after (485 in the tree
  the phase resumed from, 7 of them red on the half-landed part B).
- Goldens: `prompts/*/master.txt` gain, after THE RULES OF THIS GAME, exactly the sections
  `picture.txt` held (SCENARIO through WAITING ON THE PLAYER; PLAYER ACTION was already there);
  the four `picture.txt` are deleted. `narrator.txt`, `schemas/*`, `state/*`, `save/*`, `turn/*`
  unchanged.
- Smoke (`uv run aidm`, headless, no model credentials in the container): the MCP tool list is
  `[]` between turns, a tool call between turns is refused with `NO_TURN`, the game page renders a
  played save with no traceback, `saves/.sessions` is never written. A live turn was not played.
- Reviews: the Fable reviewer and a second Opus reviewer (no `codex` on the machine), spawned
  by the coordinating session on the staged tree; their reports and the fold are recorded
  below. Before they ran, the finishing session had no Agent tool, so the `code-review` skill and
  the finishing session's own pass by `.claude/prompts/review.md` stood in (kept in
  `/tmp/phase-1/` as history). Part B's first half was a Sonnet implementer that died; the rest
  of the phase was written by the finishing session directly.

### Decisions off-plan

- `tests/ui/test_settings.py:73` sets `session.phase = "master"` where it set `session.busy = True`:
  `busy` is a read-only property after 1.4.2 (a fifth test file for that step).
- `consume_answer` keeps its `RULES_WAIT` append to the traces when `engine.answer` leaves a
  decision pending; PLAN names nothing there for deletion.
- Four tests of gates PLAN 1.3 deletes, unnamed by PLAN: `test_a_told_fact_about_an_unmet_or_unknown_entity_is_refused`
  (`tests/core/test_integrity_boundaries.py`) and `test_attempt_refused_when_dead`
  (`tests/twentyfourxx/test_tools.py`) are deleted with their gate;
  `test_apply_scene_refuses_a_misfiled_cast_entry` (24XX) is the eighth `apply_scene` refusal
  test and becomes `test_the_bar_refuses_a_misfiled_cast_entry` on `scene_refusal` like the
  seven PLAN names; `test_an_id_the_worldsmith_got_wrong_resolves_by_name_before_it_is_refused`
  (Loner) now matches the `resolve_ids` message, which is where the raise comes from.
- `tests/core/test_pipeline.py::test_a_turn_that_applied_nothing_and_failed_is_refused` scripts
  two crashes: `_act` spawns a master that landed nothing once more (PLAN 1.2.4).
- `test_the_page_is_told_to_refresh_before_the_worldsmith_is_asked` (it used `on_commit`) is
  `test_the_turn_is_filed_before_the_worldsmith_is_asked`: a wrapping spawner reads the history
  length as the worldsmith is spawned and sees the turn's exchange already filed.
- `test_no_tool_runs_before_a_turn_is_open` keeps `NO_TURN` under test through an engine tool and
  also asserts the published list is empty between turns.
- From the reviews (PLAN did not name these):
  `GameService.intent` holds the typed intent while `extend` writes (Tunnel Goons "Move on"),
  cleared in its `finally`; `live_turn` shows it as the bubble when no turn is open. `play` skips
  the master spawn when the answer re-suspended (`turn.draft.pending` set after `consume_answer`):
  every tool would be refused; `_chained`/`CHAIN_THE_HIT` come back in `test_decisions.py` to test
  it. `ui/game.py::_observed` seeds `GameView.seen` at the end of `game_page` and after a restart,
  so neither the first tick after a load nor a restart that reproduces the old lengths misses or
  repeats a render. A forbidden tool argument stays under test (`{"junk": 1}` on `change_world`,
  refused "not permitted"). The stale "a driver may refuse to carry a session on" comment in
  `spawn.py` is gone. The NEXT-SPECS G.3 sentence sits after the parenthetical.

### Refuted findings

- "`poll_turn` runs `refresh_all()` on every landed fact" (`code-review` skill): the body is PLAN
  1.4.3's code verbatim, and the poll is once a second, so a turn costs at most one page render
  per second.
- "`render_master`'s `recent: int = 0` means the whole history" (Opus #4): `render_picture` had
  the same default and the same `told[-limit:]` since before this phase; PLAN 1.2.1 spells the
  signature with it; the one production caller passes `self.recent`. Not a regression of this
  phase. Awaiting the maintainer's call on making it required.
- "Inline `apply_to_draft` into `_apply`" (Opus cut): PLAN 1.3.1 defines its new four-argument
  shape and two tests call it directly; a later phase's cut, as is `Fact.entity_id`, which
  nothing reads now but `turn/*.json` and `save/*.json` serialise (Fable cut).

## Phase 2 — the history

- `src` lines: 9,466 before, 9,348 after (target about 9,270; every cut PLAN names is taken,
  the estimate was low by about 80). Tests: 472 after (470 before).
- Goldens: `state/{breathless,breathless-campaign,loner3e,loner3e-campaign,twentyfourxx,twentyfourxx-campaign}.json`
  and `save/{breathless,loner3e,twentyfourxx}.json` lose `settled`, `spent`, `pursuit` on every
  run and gain `"left": null`; `prompts/*/master.txt` for all four engines print RECENT PLAY as
  `SCENE: <title>`, the question, then the exchanges with no `[at ...]` tag. `narrator.txt`,
  `schemas/*`, `turn/*`, the Tunnel Goons state and save fixtures unchanged.
- Smoke (headless, no model credentials in the container; a live turn was not played): the
  catalog lists a played save filed under `whispering-vault--kael.json` with its last scene as
  `where`, the game page renders it at `/game/whispering-vault/kael` with the narration on it
  and no traceback, the master picture prints `SCENE: The Abbot's Study` with no `[at` tag, and
  the narrator prompt holds narration only, never a `> prompt` line.
- Implemented by three Sonnet implementers in sequence (A: 2.1, B: 2.2, C: 2.3 to 2.5), briefs
  in `/tmp/phase-2/`. Reviews: the Fable reviewer and a second Opus reviewer (no `codex` on
  the machine); the fold is recorded below.

### Decisions off-plan

- The worldsmith's prompt gets a `THE JOB` section with the open job's terms (`SceneWorld.job`)
  ahead of the hub rows: `scene_history`'s `the job:` line went with it and `SceneRecord` has
  no job field, so `render_history` could not carry it (both reviewers, one fix).
  `tests/twentyfourxx/test_worldsmith.py::test_render_worldsmith_prints_the_job_line_for_the_job_run`
  now asserts that section; it was deleted mid-phase as a test of `scene_history`'s prose and
  restored in the fold.
- A failed crossing is filed under `CROSSED`, not the player's intent, when a crossing was
  asked for (PLAN 2.3.1 wrote `intent`): the turn already filed the player's words, so filing
  them again showed the same bubble twice (Opus #2). A silent `extend` still files under the
  intent, its only bubble. `_grow` rebinds `draft` before filing the card, with a comment:
  the failed draft may hold the half-installed scene.
- `Runtime.session`'s `held.target != target` guard is deleted: with the slug derived from the
  two ids, equal slugs are equal targets and the branch was unreachable (both reviewers);
  `test_one_open_game_per_slug_and_it_keeps_the_origin_it_was_opened_with` becomes
  `test_one_open_game_per_slug`. `GameService.write_failure` had three clears, not PLAN's two
  (`restart` too); all three go.
- `load_catalog` checks the file stem against `target.slug` after `engine.restored`, so a save
  that fails to restore is still skipped for that reason; one test covers the stem skip.
  Every `LaunchTarget(slug=...)` in `tests/ui/test_settings.py`, `tests/core/test_speech.py`,
  `tests/core/test_media.py`, `tests/core/test_tool_surface.py` drops `slug` too (PLAN named
  three files); the `rival` target in `test_tool_surface.py` plays the Loner campaign scenario,
  since a derived slug made it the table's own session; saves the launcher tests must list are
  filed as `whispering-vault--kael`.
- `docs/{24XX,BREATHLESS,LONER-3E}.md` say "`next_scene` and `left` — `settle`'s answer is the
  only end a scene has" where they named `settled` and the turn cap.
- `tests/loner3e/loner3e_test_support.py` stops passing `settings=` (it built a `GameService`
  by hand); `tests/loner3e/test_world.py` loses `_carded`, unused once the cap tests went.
- `SaveOption.where` stays (it is the launcher's own field); PLAN's `\.where\b` grep finds its
  two reads and nothing of `Exchange.where`.

### Refuted findings

- "Inline Tunnel Goons' module `record` into `TunnelGoonsEngine.record`" (Opus cut): PLAN 2.1.3
  names the module function's new shape, and Phase 3.3 reshapes that module; a later cut.
  Awaiting the maintainer's call.
- "`src` is 77 over the target" (Fable #3): no named cut is missing; the count is recorded, not
  padded.

## Phase 3 — the world

- `src` lines: 9,348 before, 9,257 after (target about 9,050; every cut PLAN names is taken,
  and the fold added the checks below); `engines/scenes/world.py` 666 (target under 600).
  Tests: 472 after (472 before).
- Goldens: every `state/*.json` and `save/*.json` holds `payload` as the world with no `world`
  key, `"jobs": []` after `board`; the six scene fixtures' runs carry `place`, `title`,
  `question`, `situation`, `secret`, `here`, `exchanges`, `left`, `recap`; the Tunnel Goons
  visits carry `place` and `exchanges` and the world no `job_done`; `loner3e*.json` carry `twist`
  last; `schemas/twentyfourxx/master_tools.json` and `prompts/twentyfourxx/master.txt` say
  `after_job`. The other `master.txt`, every `narrator.txt` and `turn/*.json` unchanged. The
  eight `scenarios/*/world.json` were rewritten by scratchpad scripts (`payload` is the canon;
  `opening.here` is `present` then `hidden`); `json.dump` re-indented their inline arrays.
- Smoke (headless, no model credentials in the container; a live turn was not played, and the
  game page was not rendered): every shipped scenario begins a game and renders the three
  views; the four save fixtures restore; a 24XX campaign takes a job (`install_scene` with a
  `JobDraft`, THE JOB in the master's sections), `settle(True, "")` finishes it, the return
  closes it, the ledger lists it and the note is filed; `enter` on someone hidden here is
  refused "already here" and `reveal_hidden` makes them present; a Tunnel Goons job taken,
  walked, visited home mid-job (still open) and reported "left open" shows in the ledger, and a
  job taken but not walked is swapped by taking another.
- Implemented by three Sonnet implementers in sequence (A: 3.1, B: 3.2, C: 3.3 and 3.4),
  briefs in `/tmp/phase-3/`. Reviews: the Fable reviewer and a second Opus reviewer (no
  `codex` on the machine); the fold is recorded below.
- PLAN's done-when grep still finds `Counter.current`, `TunnelWorld.current` (3.2 deletes the
  scene world's `current` only) and the prose "Stop here" in `turn/prompts/master.md`.

### Decisions off-plan

- `TunnelWorld.job_open` is an open job **with** `started` (PLAN 3.1.4 wrote `open_job() is not
  None`): a job taken at the tavern but not yet walked would otherwise block every other intent
  ("report the open job first") while its report is refused at commit (`check_jobs`: a debrief
  needs `started`), and PLAN's own "taking a job pops a last job whose `started` is `None`"
  would be unreachable. `install_extension`'s return branch refuses "no job is open to report"
  for an unwalked job too, so the refusal lands at the tool, not at commit (Opus #7).
- `job_runs()`/`job_visits()` start at the open job's `started`, the first run away from the
  hub, as PLAN 3.1.2 spells it: the hub run in which the job was taken is no longer in RECENT
  PLAY, SCENES SO FAR or the Trail during the job (the old walk started at the last debriefed
  hub run). Known and accepted; PLAN's literal text.
- `new_world[W: SceneWorld[Any, Any]](world_type: type[W], canon: SceneCanon[Any], player: Person) -> W`
  (PLAN 3.3.1 wrote `type[SceneWorld[C, P]] -> SceneWorld[C, P]`): the literal shape cannot
  return `LonerWorld` or the seam test's subclass, so part C had `cast(...)` at two call sites;
  both reviewers asked for the signature to carry the subclass instead. Their spelling
  (`W: SceneWorld[C, P]`) is one basedpyright rejects, and `C`/`P` used once each are refused
  too, so the world-generic `Any` bound CLAUDE.md allows is the one left.
- `check_jobs(hub, jobs, walked)` refuses a `started` past the runs or visits (both reviewers:
  a stale index made `job_runs()` silently empty). `SceneCanon` refuses an opening with
  `exchanges`, `left` or `recap` (both reviewers: `opening` is a `SceneRun` now). `check_hub`
  refuses hub runs after the first that the closed jobs do not account for (Fable #3: every
  return closes exactly one job; PLAN 3.1.2 had dropped every run-to-job rule).
- The stored boards (`SceneCanon`, `SceneWorld`, `MapCanon`, `TunnelWorld`) are typed
  `Board | tuple[()]` (Opus #1): PLAN 3.4.1 relaxed `check_board` to the no-hub case, which left
  a one-offer campaign file loadable; the rule still lives once, on the `Board` type, and the
  file boundary keeps it.
- `hub.py` gains `open_job_of`, `closed_jobs_of` and `since_start` and the two worlds' six job
  methods are one-liners over them (Opus #2: PLAN 3.1.4's "as the scene world's" made two
  copies; two worlds need it). `move`, `level_up` and `install_extension` read `open_job()`
  instead of re-deriving it from `jobs[-1]` (both reviewers). `SceneWorld.job_terms()` serves
  `scene_rows` and `render_worldsmith` (Opus cut). `scenes/views.py` drops the dead `known`
  filters over `here()` (both). `run_of(draft, here)` takes the list and passes it through.
- `tests/core/test_scenes.py` 76 to 90 tested shapes 3.1 deletes (a debrief on a run,
  `job_done` on a run) and are rewritten on the nearest surviving rule: `check_hub` refusing an
  opening away from the hub, and `settle` refusing `job_done` with no job open.
- Three tests of the "hidden but known / already met" rule 3.2 removes are deleted
  (`tests/loner3e/test_world.py` two, `tests/twentyfourxx/test_world.py` one); the boundary the
  third guarded is now `require_here`'s refusal of an unmet entity, tested as
  `test_someone_hidden_here_cannot_be_acted_on_before_the_reveal`. PLAN 3.2.4's "set `known`
  on the entity" would have made that fact told.
- `NEXT-SPECS.md` line 159 (G.4's phase list) says `AfterJob.raises` too; PLAN 3.4.4 named G.2
  and the done-when only. `with_entity`'s docstring says `known` alone decides.

### Refuted findings

- "Add a Tunnel Goons test that a fact about an unmet npc here is not told" (Opus #5): every
  Tunnel Goons tool that admits an npc through `require_npc_here` (`action_roll`, `kill`)
  calls `world.reveal(npc)` before it files a fact, so no such fact exists to test.
- "Inline `check_hub`" (Opus cut): `SceneCanon` and `SceneWorld` both call it, and the fold
  gave it a fourth rule. "Drop the `job_done` property" (Opus cut): PLAN 3.1.2 names it. "Fold
  `check_board` into `check_jobs`" (Opus cut): `MapCanon` has a board and no jobs; PLAN 3.4.1
  names it.
- "`src` is over the target" (both): no named cut is missing; recorded, not padded. The
  `Board` annotations, `check_jobs`'s bound, the opening check and the hub-run rule are the
  fold's additions.

## Phase 4 — the chores

- `src` lines: 9,257 before, 9,243 after (target about 8,960). PLAN's table expected about 90
  fewer lines from this phase; 49 of the lines it deletes are the three `worldsmith.md`, which
  the `.py` count never held, and the three panel builders replace about 35 duplicated lines
  with 22 shared ones. No named cut is missing; recorded, not padded. Tests: 472 after (472
  before: one `here_panel` test added, one wiring test removed in the fold).
- Goldens: every fixture unchanged. The 24XX and Breathless worldsmith prompts lose the "cast
  carries no dice" paragraph; the Loner prompt carries "Every scene bears on the player's
  `goal`, or brings their `nemesis` nearer." and "Give a door or a storm the `skills` and
  `frailties` it resists with." in `_AUTHORING`, so they reach every scene write and the
  opening through `guidance()`.
- Smoke (headless, no model credentials in the container; a live turn was not played): the four
  save fixtures restore and every engine's sidebar lists Character first, then Here with the
  player as "(you)" and an icon id on every row, then Trail; `game_page` builds under a NiceGUI
  client for 24XX and Tunnel Goons with no traceback; the shared `WORLDSMITH` holds neither
  deleted paragraph and Loner's `guidance()` holds both moved sentences.
- Implemented by one Sonnet implementer (brief in `/tmp/phase-4/`). Reviews: the Fable
  reviewer and a second Opus reviewer (no `codex` on the machine); the fold is recorded below.

### Decisions off-plan

- `engines/seam.py`'s `directory` comment says "rules.md; a scene engine's packs/; Tunnel
  Goons' worldsmith.md": the scene engines no longer read a `worldsmith.md` from it.
- `NEXT-SPECS.md`'s refusal of a `SceneRules` record no longer names `role` among what
  `SceneEngine` carries on `self` (both reviewers: this phase deleted it).
- Both `player_view`s bind the player's `Subject` once and pass it to `PlayerView.player` and
  `here_panel` (both reviewers). `here_panel` has no docstring: "(you)" is on the next line and
  the icon id's reason is the comment on `PanelRow.icon_id` (both).
- `tests/breathless/test_views.py::test_the_player_views_here_panel_lists_the_player_first_then_known_cast`
  is deleted (both reviewers): with the panel built once, it asserted `here_panel`'s own test
  through a view; `tests/core/test_views.py` keeps the scene view's Here membership, icon ids
  and the hidden entity's absence.
- PLAN's done-when `ls src/aidm/engines/*/worldsmith.md` lists `scenes` and `tunnelgoons`: the
  shared file PLAN 4.1.1 creates sits under `engines/scenes/`, which the glob matches. Its
  grep checks hold.

### Refuted findings

- "Delete the `role` parameter of `write_next` and `render_opening`; move `WORLDSMITH` into
  `scenes/worldsmith.py`" (Opus cut): PLAN 4.1.1 spells the shape as the engine's constant that
  "`author` and `advance` pass"; one value at one call site makes it a pass-through, so it is a
  cut. Awaiting the maintainer's call.
- "One `subject_of` in `engines/core.py` for both views" (Opus cut): `Goon` and `Npc` are
  `Mutable`, not `Person`, and the `Entity` protocol has no `brief`, so the shared function
  needs a new protocol for one three-field constructor. Awaiting the maintainer's call.

## The plan, closed

- `src` lines: 9,742 at `4fa8d4f`, 9,243 after phase 4 (PLAN's table: 8,960). Every cut PLAN
  names is taken; the gap is PLAN's estimates (phase 2 about 80, phase 3 about 200 including
  the fold's checks, phase 4 the `.md` lines), recorded per phase above. `engines/scenes/world.py`
  is 666 lines (PLAN: under 600). Tests: 472.
- Cuts deferred across the four phases, each awaiting the maintainer's call: `render_master`'s
  `recent` default (phase 1), inlining `apply_to_draft` and dropping `Fact.entity_id` (phase 1),
  inlining Tunnel Goons' module `record` (phase 2), the `role` parameter and a shared
  `subject_of` (phase 4).
- Known and accepted: `job_runs()`/`job_visits()` start at the open job's `started` (phase 3);
  the phase 3 done-when grep still finds `Counter.current`, `TunnelWorld.current` and the prose
  "Stop here"; the phase 4 `ls` lists `scenes` beside `tunnelgoons`.

## Fold after the maintainer's review

- Cuts taken: `apply_to_draft` is inlined into `_apply`, and the `Validate` alias is gone with
  it; `Fact.entity_id` is dropped, along with the one `entity_id=entity.id` that set it in
  `entity_fact`; Tunnel Goons' module-level `record` and `history` are inlined into
  `TunnelGoonsEngine.record` and `.history`; the `role` pass-through is gone — `WORLDSMITH` now
  lives in `scenes/world.py` beside the `render_worldsmith` method that used to take it as an
  argument, and `render_worldsmith` and `worldsmith_prompt` both read the module constant
  directly instead of carrying a `role` parameter.
- The `render_master` `recent` default, deferred in phase 1, was already gone by the time of
  this fold — phase 2's history rewrite had removed it without anyone flagging the cut as taken.
- Left as is: the shared `subject_of` in `engines/core.py`. `Goon` and `Npc` are `Mutable`, not
  `Person`, and the `Entity` protocol carries no `brief`, so sharing the constructor needs a new
  three-field protocol in `core` built for it alone. Not worth adding for one caller.
- Removed the scene `secret`: the field on `SceneRun` and `SceneDraft`, the worldsmith paragraph
  that described it, the "THE SCENE'S SECRET" row in the three scene engines' master sections,
  and the `opening.secret` key in the six scenarios that still carried one. The game master
  conjures what a scene hides at the table; a stored secret was prose nobody validated, sitting
  beside the mechanic — `hidden`/`reveal` — that already does that job.
- `src` lines: 9,243 before this fold, 9,205 after.
