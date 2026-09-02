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
