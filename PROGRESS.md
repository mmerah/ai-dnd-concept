# PROGRESS

One entry per PLAN.md phase: the line counts before and after, decisions taken off the plan,
refuted review findings and why, and anything known and accepted.

## Phase 1: one id, a thinner seam, one role runner

Counts (`find <dir> -name '*.py' | xargs cat | wc -l`):

| tree  | before | after  | target            |
| ----- | ------ | ------ | ----------------- |
| src   | 10,199 | 10,111 | ~10,090, ≤ 10,110 |
| tests | 9,462  | 9,360  |                   |
| qa    | 2,433  | 2,435  |                   |

Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).

Decisions off the plan:

- `Runtime.playing()` returns `Turn | None`, not `GameService | None` (step 17): both callers,
  `published_tools` and `call`, only wanted the turn and each re-narrowed `playing.turn`;
  `qa/agents.py` reads `playing.engine.id` off the turn instead.
- `_landed` (step 9) is a private free function at the end of `app/roles.py`, not a `Roles`
  method: it reads only `Turn` state and `turn` sits below `app` (CLAUDE.md, first rule).
- Two tests went with the behaviour they proved, beyond the ones the plan names:
  `test_a_second_game_in_flight_crashes_the_call_rather_than_routing_it` (the `playing` guard,
  step 17) and `test_preview_character_refuses_foreign_character_type` (the engine-id half of
  `check_character`, step 5).

Refuted findings:

- "`preview_character` should keep an engine-id refusal; a non-`Person` payload now raises
  `AttributeError`": step 5 says it loses that check; its one caller, `ui/create.py`, previews on
  the engine that built the sheet, and `Library.read_character` types every payload by engine, so
  no path hands it a foreign payload.
- "`_landed` logs, so its name hides a side effect": step 9 gives that shape; moving the warning
  into `master` writes the same warning on two exit paths.
- "`"fail", "success-but", "success"` is spelled twice in `breathless/engine.py`": step 12
  gives both calls inline; a constant would be one more name per engine for three words.

Known and accepted:

- `src` ends one line over the cap (10,111 vs 10,110). The remaining lines are the shapes the
  plan spells out; nothing was padded and nothing was compressed to hit the number.
- The smoke (`uv run aidm`, port 8765, saves in a scratch dir) opened the four shipped scenarios
  and took one turn on Buried Keep with no model credentials: the master timed out, was spawned
  once more, and the second failure raised, with no page error. The narrator's opening went
  unnarrated as designed. The two fold edits after the smoke (`playing`, `_landed`) are covered
  by `tests/app/test_master_tools.py` and `tests/app/test_game_service.py`.
