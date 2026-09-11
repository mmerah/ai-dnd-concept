# PROGRESS

One entry per commit. Line counts are `find <dir> -name '*.py' | xargs cat | wc -l`.

## Phase 1: names and spelling

| dir   | before | after |
| ----- | ------ | ----- |
| src   | 9,827  | 9,798 |
| tests | 9,146  | 9,119 |
| qa    | 1,786  | 1,788 |

Full check green; app smoke green (home, settings, create and scenario pages serve). Reviewed by
two adversarial readers (Fable and Opus; no Codex on the machine).

### Decisions off-plan

- Step 6, `type TagKind` / `type Ability` / `type Boost` / `type AbilityScores`: not done. Measured
  on pydantic 2.13.4: a PEP 695 `type` alias becomes a `$defs` entry and a `$ref` in every schema
  that reads it, so the four would have changed `schemas/loner3e/master_tools.json`,
  `schemas/tunnelgoons/master_tools.json` and two `worldsmith.txt` goldens, against step 9 and
  the phase's "no behaviour changes". They stay assignments, each group with a one-line comment.
  **Awaiting the maintainer's call**: keep as is, or spell them `type` and accept the schema change.
- Step 9's prediction was wrong on the worldsmith prompts: pydantic keys `$defs` by class name, so
  the step 1 renames (`Loner3eCast`, `GoonSheet`, `Gauge`, `CrewSheet`) rename and re-sort `$defs`
  keys in the four `prompts/*/worldsmith.txt`. Verified identical modulo rename and reorder;
  regenerated. The `schemas/*` goldens are byte-identical.
- Step 8, `_save_option` takes `store: FileStore`, not `raw`: the read's own refusal (a save that
  is not UTF-8) is still skipped with a warning, as the loop did.
- Step 8, `theme.install()`: `qa/server.py` is a second entry point that mirrors `start()`, so it
  calls `install()` before `ui.run` too (review finding).
- Step 1, `GameService.engine_title` / `engine_id` deleted: `ui/game.py` now reads
  `session.engine.title` and `session.engine.id`, which
  `tests/core/test_package_boundary.py::test_no_ui_module_reaches_through_a_session_into_the_engine`
  forbade. The test guarded exactly the facade the plan removes (phase 2 step 10 reads
  `session.engine.look.dice` too), so it is deleted with it.
- Step 8, `run_builtin` passes `tools` through: the two `tests/app/test_builtin.py` cases that
  handed a narrator run a `Tools` and asserted the gate dropped it now run the narrator as
  production does, with no tools (`ask` passes none). The refusal on a tool call is still tested.
- `tests/turn/test_decisions.py` uses the new `core.tools.NoArgs` instead of its own stand-in
  (review cut).

### Refuted review findings

- "`Engine.answer` returns a list only for `Turn._consume` to re-tuple it": PLAN step 3 asks for
  exactly this; rules code returns lists, the `Play` boundary stays a tuple.
- "`Pairs` belongs in `core/views.py`, the dependency now points the wrong way": PLAN step 6 moves
  it to `core/prompt.py`; `views` importing from `prompt` makes no cycle.
- "Fold `apply` and `set_engine` into one function": `set_engine` has three callers
  (`ui/app.py`, twice in `ui/create.py`) beside `apply`.
- "Inline `_landed`": PLAN step 8 keeps it and moves only the logging into the loop.
- "Drop the `facts` local in `SceneEngine.depart`": PLAN step 3 spells that shape.

### Known and accepted

- `Hiring.hire_check(self, _draft: G)` keeps the underscore: the base body reads nothing (ruff ARG).
- `dice_look`, `THEMES`, `Theme`, `NEUTRAL_DICE`, `HIRE_TOOL` and `AbilitiesDraft` stay for phase 2.
