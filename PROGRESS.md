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

## Phase 2: the request, the draft as the scenario, one hiring rule

Counts (`find <dir> -name '*.py' | xargs cat | wc -l`):

| tree  | before | after  | target           |
| ----- | ------ | ------ | ---------------- |
| src   | 10,111 | 10,020 | ~9,980, ≤ 10,000 |
| tests | 9,360  | 9,307  |                  |
| qa    | 2,435  | 2,435  |                  |

Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine). Three
sequential Sonnet implementers: steps 1 to 6, 7 to 15, 16 to 23.

Decisions off the plan:

- `World.require_hireable` (step 17) has no `takes no sheet` branch: every member a hiring engine
  hires is `Sheeted`, where `hired()` and `hireable()` are complements, so the branch had no
  caller and no test. `Person.hireable()` stays for the player check in the `World` validator.
- `resolve_ids` in `scenes/world.py` is `_resolve_ids` in the private section: `settled` is its
  one caller once `opening_canon` went.
- `Engine.validate` on the seam sits beside `over()`, not inside the abstract block, now that it
  has a body.
- `SceneEngine.new_game` carries a one-line why on the deep copy: a restart opens the same
  scenario again, and `settled` marks the present met on the copy.
- `TwentyfourxxWorld.sheeted_members` and `Npc.rows` ask `hired()` (and `dice()`), the question
  this phase added, instead of `sheet is not None`.
- README line 55 keeps the plan's words and gains a colon and "played with" so the sentence has
  one `with` clause per thing it says.

Refuted findings:

- "`settled` should return only the `SceneRun`, since it mutates the cast it is handed": step 8
  gives the tuple shape; the mutation is on the cast entries (`known`, state models are mutable
  by CLAUDE.md), which the dict return neither hides nor exposes; the deep copy in `new_game`
  stays either way.
- "`Goon` should re-declare `sheet: Abilities`, since the optional field lets a sheetless
  character file parse": step 22 removes the field; `Survivor` and `Crewmate` are already
  `Sheeted` with the same optional at the file boundary, and the `World` validator refuses a
  sheetless player at launch, as `test_twentyfourxx_world` proves; narrowing a mutable field is
  a basedpyright error.
- "rename `unwritten` to `writes`": step 2 names it `unwritten`, and phase 3 step 1 reads
  `engine.unwritten` in the worldsmith golden.
- "delete the three `hireable` overrides by making `Hiring.hireable` concrete": step 19 keeps
  `Hiring[P, M, G, A]` with `hireable` typed by `M` because the seam's `world()` erases the
  member type to `Person`.
- "`dict(draft.cast)` in `opening` copies a dict `new_game` already deep-copied": no line saved,
  and the copy keeps the draft's own dict from aliasing the world's.

- `state.generation = None` in `GameService._resumable` is deleted (both reviews; the
  maintainer's call): `Game.generation` is excluded from every dump this build writes, so the
  line only served saves from before this phase, which PLAN "How to work" 6 forbids reading and
  which no longer load anyway, since their scenario files changed shape. PLAN step 5 said it
  stays.

Known and accepted:

- `src` ends 20 lines over the cap (10,020 vs 10,000). The remaining lines are the shapes the
  plan spells out (`Sheeted` and the one hiring rule moved into `base.py`); nothing was padded
  and nothing was compressed to hit the number. Well under the "half again" stop rule.
- The smoke (`uv run aidm`, port 8765, saves in a scratch dir) opened the four shipped scenarios
  and took one turn on each with the CLI roles; every save landed without a `generation` key
  (`grep -L '"generation"'` lists all four). One narrator answer on Whispering Vault was not
  JSON and surfaced as a refusal notification; no page error.
