# Plan

The phased plan for what is built next, in order. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted. `tests/core/test_golden_state.py` pins `FIXTURE_SAVE_VERSION` —
   bump both or the suite catches you.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 1 — simplification

No gameplay change except a faster turn. Concepts are removed before files are moved, so steps 1-5
delete and steps 6-7 reorganise what is left. Out of scope: the Interpreter, which the evals
measure as an improvement (0.900 without it, 0.967 with).

### Step 1 — delete stale eval results

`evals/results/` holds eleven runs, ten of them historical. Git keeps them.

- Delete every file in `evals/results/` except `step-11-baseline.json`, which is the current tree's
  reference run.

Done when: `evals/results/` holds one file and `uv run pytest` is green.

### Step 2 — delete the memory system and the Worldkeeper

A memory is 0-2 sentences per turn bought with a whole model round-trip, and the conversation
window carries the same continuity. The window becomes unbounded in exchange.

Delete, in this order (leaves first):

- `src/aidm/state/world.py`: the `Memory` model, `WorldState.memories`, and the memory-owner check
  inside `_consistent_fiction`.
- `src/aidm/content/authored.py`: `ScenarioWorld.memories` and its line in the `world` property.
- `scenarios/whispering-vault/world.json`, `scenarios/drowned-road/world.json`: the `"memories"`
  arrays (2 entries each). If a line is worth keeping, fold it into the owning entity's `brief`.
- `src/aidm/turn/scene.py`: `SceneSnapshot.memories` and the block that builds it.
- `src/aidm/turn/prompts.py`: `render_worldkeeper`, `_memories`, `_memory_line`, the `WORLDKEEPER`
  constant, and the `("MEMORIES", ...)` entry in `_direction_sections`.
- `src/aidm/turn/prompts/worldkeeper.md`.
- `src/aidm/turn/reports.py`: `MemoryProposal` and `WorldkeeperReport`. `MechanicStep` and
  `TurnInterpretation` stay — the file keeps its name.
- `src/aidm/turn/agents.py`: `worldkeeper_agent`, the `worldkeeper` field on `TurnAgents`, and its
  line in `build_turn_agents`.
- `src/aidm/turn/pipeline.py`: the `remember` function, the whole `announce("worldkeeper")` block,
  and `"worldkeeper"` from `TURN_STEPS`.
- `src/aidm/app/authoring/draft.py`: `ScenarioPatch.memories`, `WorldDraft.memories`, and the
  memory dedupe block inside `apply` (drop `memories` from the `wrote` tuple too).
- `src/aidm/app/prompts/scenario_world.md`: the paragraph instructing the author to write memories.
- `src/aidm/app/views.py`: `JournalView.memories` and its comprehension.
- `src/aidm/ui/panels.py`: the "What is remembered" block in `journal_panel`.
- `src/aidm/config.py`: `max_memories`, `history_window`, and `"worldkeeper"` from the `Role`
  literal.

Then, in `src/aidm/turn/pipeline.py`, replace the history slice with the whole history:

```python
history = exchanges_to_messages(state.history)
```

Tests and fixtures:

- Delete `tests/core/test_worldkeeper.py`.
- Delete `tests/core/fixtures/instructions/*/worldkeeper.txt` and
  `tests/core/fixtures/schemas/worldkeeper_report.json`.
- `tests/core/core_test_support.py` and `tests/ui/ui_test_support.py`: drop `max_memories`,
  `history_window`, and the worldkeeper stub role.
- `tests/core/test_golden_prompts.py`, `test_golden_schemas.py`, `test_context_boundary.py`,
  `test_expansion.py`, `test_golden_turn.py`: drop every worldkeeper entry.
- `tests/core/test_views.py` and `test_pipeline.py`: delete the two memory tests.
- Bump `SAVE_VERSION` 81 -> 82 and `FIXTURE_SAVE_VERSION` in `tests/core/test_golden_state.py`,
  then regenerate with `AIDM_GOLDEN_REGEN=1 uv run pytest`. Expect movement in `save/`, `state/`,
  `turn/`, and in `prompts/*/director.txt` and `prompts/*/interpreter.txt` (the MEMORIES section
  is gone). Read the diff.

Docs, in the same commit:

- New `docs/MEMORY-SYSTEM.md`: what was deleted, why, and what a re-implementation looks like —
  a durable fact per entity, written by a role that runs after narration, shown only to roles that
  may see canon, deduped on text. Keep it to a page.
- `docs/ROADMAP.md`: under "Direction", a line saying the memory system is deliberately gone and
  will return per `docs/MEMORY-SYSTEM.md` once the conversation window stops carrying continuity.

Done when: a turn runs Interpreter -> Director -> hooks -> Narrator, three roles instead of four.

### Step 3 — delete `Resolution`

`Resolution` wraps one field that every caller immediately unwraps, and sits beside a differently
shaped `Resolved` in `engines/transact.py`. Two names, one of which carries nothing.

- In `src/aidm/engines/transact.py`, change the alias to
  `type Play = Callable[[Game, Random], tuple[Fact, ...]]`, and read `resolution` directly where
  `resolution.facts` was read.
- Move `check_draft` from `src/aidm/state/resolution.py` into `src/aidm/engines/transact.py`, then
  delete `src/aidm/state/resolution.py`.
- Update the eleven construction sites: `Resolution(facts=tuple(x))` becomes `tuple(x)`. They are
  in `turn/tools.py`, `turn/expansion.py`, `turn/agents.py`, `app/session.py`, both engines'
  `actions.py` and `tools.py`.
- `state/hooks.py` and `engines/advancement.py` import `check_draft` from its new home.

Watch the import direction: `state` must not import `engines`. `check_draft` moving up into
`engines` is the direction that keeps `tests/core/test_package_boundary.py` green.

Done when: `grep -rn "Resolution" src` returns nothing.

### Step 4 — delete `TurnLog.fired`

Three call sites accumulate `fired` in parallel with `facts`; one line reads it. A fact fired by a
hook already carries `kind="hook_fired"` or `"hook_failed"`.

- `src/aidm/engines/engine.py`: drop the `fired` field from `TurnLog`.
- `src/aidm/engines/transact.py`: drop `Resolved` entirely — `apply_to_draft` returns
  `tuple[Fact, ...]` (resolved facts followed by fired ones, which is what `Resolved.facts`
  already gave). Drop the `deps.log.fired.extend(...)` line in `act`.
- `src/aidm/turn/agents.py`: drop the same line in `expand_world`.
- `src/aidm/turn/pipeline.py`: build the hooks `StepTrace` by filtering
  `fact.kind.startswith("hook_")` over `log.facts`.

Done when: `grep -rn "\.fired" src` matches only `world.fired_hooks`.

### Step 5 — the trace leaves the save format

The trace is developer instrumentation. Version-gating it makes every prompt-shaped change a save
compatibility event, and resume reads an unbounded file.

- `src/aidm/state/trace.py`: drop `save_version` from `TraceEntryBase`. `Turn`, `Applied` and
  `StepTrace` stay — the Trace tab and `evals/turn_eval.py` both read `turn.steps`.
- `src/aidm/content/store.py`: delete `TRACE_ADAPTER`, `append_trace`, `load_trace`,
  `_trace_path`, `_line_version`, and the trace unlink in `discard`. Inline the remaining
  `_require_save_version` call at its one save site.
- `src/aidm/app/session.py`: `_commit` no longer appends to disk, and `__post_init__` no longer
  loads `self.entries` — the list starts empty each session.
- `tests/core/test_store.py`: delete the trace round-trip tests.

No `SAVE_VERSION` bump: the save file's own bytes do not change.

Done when: playing a turn writes only `<slug>.json` under `saves/`.

### Step 6 — `begin_game` leaves `app/session.py`

It is the only reason `app/authoring/playability.py` imports the session module, and it is used by
the app, the evals and the tests alike.

- New `src/aidm/app/newgame.py` holding `begin_game` and `build_engine`, moved verbatim.
- Update the importers: `app/session.py`, `app/authoring/playability.py`, `evals/turn_eval.py`,
  `tests/core/core_test_support.py`.

Done when: nothing under `app/authoring/` imports `app.session`.

### Step 7 — each engine folds to six modules

`tools.py` is a thin adapter over `actions.py` and the two change together every time.

For each of `src/aidm/engines/loner3e/` and `src/aidm/engines/twentyfourxx/`:

- Append the contents of `tools.py` to `actions.py`, then delete `tools.py`. `rules.py` imports
  `director_toolset` from `.actions`.
- Order the merged `actions.py` in one pass: wire models (`Question`, `Attempt`, `LuckTest`) first,
  then module constants, then pure helpers, then resolvers, then `director_toolset` last.

`mechanics.py` stays where it is. It is the leaf every other module reads, and merging it into
`rules.py` would make `actions.py` and `rules.py` import each other.

Leaves six files per engine: `mechanics.py`, `actions.py`, `rules.py`, `create.py`, `advance.py`,
`pack.py`.

Done when: both engine directories hold six modules and the golden tool schemas have not moved.

### Verifying the phase

- `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright` after
  every step.
- After step 2, one live run of `uv run python evals/turn_eval.py run --label phase1-no-memory`
  against `step-11-baseline`. A drop of one case at n=9 is noise; a drop across cases is not.
- `uv run aidm`: start a game, play three turns, resume it. Steps 2 and 5 both touch what a resume
  reads.
