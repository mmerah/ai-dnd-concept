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
