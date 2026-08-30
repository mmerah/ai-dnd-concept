# PROGRESS

Branch `core-slim`. **Phase 3.5 is complete**, staged not committed. Baseline before the phase:
**9363** `src/**/*.py` lines (`288497c`). Target below 8900; the plan's own estimate was ~9020.

## Line ledger

| step | before | after | delta | estimate |
|---|---:|---:|---:|---:|
| 3.5.1 `rooms_tools` | 9363 | 9323 | −40 | −42 |
| 3.5.2 one mechanics operation | 9323 | 9313 | −10 | −8 |
| 3.5.3 shared advance procedure | 9313 | 9311 | −2 | −8 |
| 3.5.4 turn trace, `ToolCall`, `DiceEvent.result` (src) | 9311 | 9168 | −143 | −128 |
| 3.5.6 items 4-7 | 9168 | 9118 | −50 | |
| 3.5.5 non-rooms blockers | 9118 | 9116 | −2 | ~0 |
| 3.5.6 item 2 (shared scenario form) | 9116 | 9102 | −14 | −30/−40 |
| 3.5.6 item 1 (prose) | 9102 | 9085 | −17 | −45/−60 |
| 3.5.6 item 3 (`Rules` constants) | 9085 | 9066 | −19 | −18/−22 |
| review fixes (correctness) | 9066 | 9076 | +10 | — |
| **total** | **9363** | **9076** | **−287** | **≈ −340** |

Full check green after every step: **281 pytest, ruff check, ruff format --check, basedpyright
0 errors**. Modules 60 -> 59. Goldens were regenerated exactly once, inside 3.5.4.

**Phase 3.5 lands at 9076, not the 8900 target and not the ~9020 estimate.** The plan says to say
so and stop rather than reach for the two cuts it rules out (`ClaudeDriver` -> `ExecDriver`, and
`config.for_name`'s `match` blocks). Both stay unbuilt. The 46-line gap against the estimate is
one item: the prose pass returned −17 where the plan projected −45/−60.

## Step notes

### 3.5.1 `rooms_tools` — done
`world/tools.py:rooms_tools(validate, *extra, improvised=True)`. All three engines call it; the
tuple order is unchanged, so `schemas/*/director_tools.json` did not move. Breathless passes
`improvised=False`. The ~12-name `from aidm.world.tools import (...)` block per engine collapsed
to one import. No `rooms_engine` factory was built, per the plan.

### 3.5.2 one mechanics operation — done
`Engine.mechanics_merge` + `Engine.mechanics_without` -> one `Engine.mechanics_patch`, typed
`MechanicsPatch` in `state/model.py` so `world/authoring.py:diff` can name it without importing
`aidm.engines`. Shared body `engines/core.py:mechanics_patched`, bound per engine with
`partial(..., entity_maps=("sheets",))` / `("sheets", "items")`. The three `_without` functions
are gone. The merged blob is validated **before** removed ids drop, so a patch cannot hide a bad sheet by
adding and removing the same id. The second guarantee the plan asked for — a rejected patch
leaving nothing behind — took a review to actually land; see below.

### 3.5.3 shared advance procedure — done, half of it abandoned on its own floor
- `advances_owed` **is** shared: `engines/core.py:owed_notes(state, sheets, is_owed)`. Loner and
  24XX each keep a 3-line wrapper naming their tally (`milestones` / `jobs`). The duplicated
  owed-advance prompt string now has one definition.
- `complete_chapter` **stays duplicated**, deliberately. Sharing it needs `sheet.chapters += 1`
  through a `Chaptered` Protocol — which the step forbids — and measured out at ~12 shared lines
  against ~14 removed, i.e. net −2 for an extra indirection and a mutable-protocol typing fight.
  The step's floor says keep the duplication and say so. This is that.

Net −2 against a −8 estimate. Running total −52 of the ~−340 the plan projects.

### 3.5.5 the non-rooms blockers — done, line-neutral (+1 of its own)
1. `Draft.scenario`'s unconditional null-`player_parent_id` refusal deleted; `_start_unmet` added
   to `world/authoring.py` and called from `_bar_unmet` and `_opening_unmet`.
2. The companion co-location rule moved out of `content/model.py:_playable_canon` into
   `_start_unmet`. Not into `validate_rooms` — that runs on live state, where `_move_actor`
   legally lets a party member be witnessed moving away.
3. `_HOW_TO_WORK` no longer names `connect`.
5. `patch_refusal` says "with your tools"; the `connect` steer moved out of the shared
   `scenario_example.md` into `world/prompts/scenario_world.md`, so only rooms briefs carry it.
6. The growth limit is a one-line comment at `authoring/draft.py:75`. No fix built.
4. **Packs: `min_length=1` stays.** Relaxing it would also have to fix
   `loner3e:twists` (`state.packs[0]` → `IndexError`) and the pack select's `options[:1]`
   default. A pack is how an engine ships the content its rules read, and "no content" is one
   trivial pack. Phase 4.2 pays one dict entry, test-side.

**Where the plan was wrong, verified in code.** Item 1's stated benefit does not land:
`scenario_refusal` runs `playing.check(scenario)` *before* `brief.unmet(scenario)`, and
`validate_rooms` refuses a floating player first. So a rooms draft with a null start still gets
"actor 'player' is not in a valid location", not the new line. The line is kept because it is the
correct statement of the bar, but reordering `scenario_refusal` — the only way to surface it —
would change what a failed playtest reports for every engine, which the plan never asked for.

### 3.5.4 delete the turn trace — src and tests done, eval split in flight
Deleted: `StepTrace`, `TurnTrace`, `TurnResult`, `TurnRecord`, `retry_prompts`, `ToolCall`,
`DiceEvent.result`, `GameSession.entries`, `trace_panel` and the dev-tab trace expansion.
`run_segment -> Game`, `Turn.finish(lines) -> Game`, `GameSession.submit -> None`,
`GameSession.commit(state)`. `TurnRecord` folded into `Turn`, which is now a mutable dataclass
carrying `facts` and `on_fact`; `consume_answer(turn, player_input)` and `_apply(turn, play)`
take it. `PendingOption` carries `name`/`args` directly. Illustration narration now comes from
`state.history[-1].narration`.

Tests: `played -> Game`; `shown` deleted; `Recorder.prompt()` added, so golden prompts come from
the recorder. `test_golden_turn` writes the facts seen through `on_fact` plus the committed save.
Assertions that read `turn.steps` now read the `on_step` announcements.

**Goldens regenerated once, every diff read:**
- `prompts/**` did **not** move — the recorder reproduces the old `StepTrace.prompt` exactly.
- `save/*.json`: only the `"result"` line dropped from each dice event.
- `turn/*.json`: shape change from a trace object to the fact list; same facts, same order.
- `state/*.json`: unchanged — neither fixture holds an open decision, so no flattened option
  call appears there. The plan expected one; there was nothing to move.

Saves written before this step are invalid by policy: any save holding an open decision or a
stored dice card. No migration, by design.

### 3.5.4 eval rework and the `evals/cases/` split — done
`evals/turn_eval.py` 1708 -> 346 lines, holding **no engine name**; `evals/cases/shared.py`
(`Canon`, `cases_for`) plus one module per engine, loaded by `import_module`. `evals/` overall
is 1783 against 1708 — the four module headers cost ~90 lines; the trace deletion itself cut.
That growth is outside the `src/**` number this phase is judged by.

The four semantics the plan named:
1. `director_calls` counts Director **segments**, from `on_step`, not model requests.
2. Retries come from `capture_run_messages()` around each `run_segment`, filtered by the literal
   body of the deleted `retry_prompts`. Only the Director is captured, which is what the old
   director-only `StepTrace.refusals` recorded.
3. Facts are collected per segment and folded in **only after `run_segment` returns**, so a
   failed narrator records nothing the loop rolled back. Verified with an always-failing narrator.
4. **Diagnostic loss accepted in part**: a failed case keeps the Director's prompts, not the
   stage outputs. Recording request/response pairs would need a model wrapper and a second
   serialized blob for a field nothing ever read.

All 55 case ids and every expectation name are unchanged, in order.

Two calls I reversed after the agent reported them:
- **`Run`'s `extra="ignore"` deleted.** It existed so results files written before this phase
  still loaded. That is shaping a field around old data, which this project does not do — the
  same policy that makes pre-3.5.4 saves invalid. Old eval labels die with the fields.
- **`Played.narration` deleted.** The plan lists it, but no expectation reads it and the prose
  already lives in `state.history[-1].narration`.

### 3.5.6 item 1, the prose pass — −17, not −45/−60
All 178 docstring lines and 183 comments in `src/` were read in context. Eight docstrings, two
section dividers and one comment came out. The rest state a why, a constraint, or an SRD/tooling
reason, so the estimate simply did not survive the file: the corpus was already at the bar
earlier phases set. Nothing was left uncut out of caution — going further meant deleting real
*why*. No golden fixture moved, which is the proof that no runtime text was touched.

### 3.5.6 item 3 — `Rules` dataclasses to module constants, −19
The three frozen `Rules` classes and their `RULES = Rules()` singletons are gone. The worry was
that wider imports would eat the saving; measured, only **7** names cross a module boundary
(loner3e 2, 24XX 1, breathless 4), so the import cost is ~+4 against the class scaffolding
removed. Two names were made readable outside their own module: `floor` -> `DIE_FLOOR`,
`carry` -> `CARRY_LIMIT`. Nothing moved to `Settings` — this is not the rejected
constants-into-config move.

## Adversarial review, and what it caught

An independent review read the whole staged diff against `PLAN.md` and `CLAUDE.md`. Three of its
findings were real and are fixed; the rest of the diff it cleared.

**1. `Draft.apply` was not atomic, and this file claimed it was.** The blob was written once, but
the entity and thread pops still ran before it, so two paths left a half-applied patch: a
`mechanics_patch` that refused after entities had landed, and an unknown id in `patch.remove`
that raised after earlier pops. The second was a **regression** against `f37ba99`, where each pop
dropped that entity's sheet immediately — orphan sheets could have reached a written `world.json`,
since no engine's `validate` refuses one. Fixed by moving every refusal ahead of the first write:
`_require_held` finds each removal target (and raises), `mechanics_patch` runs on the gathered
ids, and only then does anything mutate. `_remove` now only pops and cannot raise.
`tests/core/test_authoring.py` gains the regression test, confirmed to fail without the fix.
Cost +10 lines, which is why the phase total moved from −297 to −287.

**2. `PLAN.md` step 4.2's `Scene` snippet was a trap for the next session.** It showed
`director_sections` as an addition to `sections`, but the shipped shape is the Director's
complete list. A Phase 4.2 built from the plan as written would have hidden the journal's own
section from the Director. `PLAN.md` is fixed and now states the rule.

**3. The null-start unmet line was dead code.** `_start_unmet`'s
"a start location: set `player_parent_id`" can never be seen: `scenario_refusal` runs
`playing.check` first, `validate_rooms` refuses a floating player, and `world/authoring.py` is
reached by rooms briefs alone. The plan asked for that line on a premise that does not hold. It
is gone; the function is now `_party_unmet`, which is the half that is live and tested.

Also cut: `_ScenarioForm.widgets()` (one caller, inlined) and the `director_sections` parameter
in `rooms_scene` that shadowed the field it fills (now `engine_sections`).

The review independently confirmed the parts most at risk: the Narrator boundary holds
(`VisibleScene` has no field for director text, the render-twice stands, golden prompts
byte-identical), `DiceEvent.result` -> `max(die.rolled)` is exactly equivalent (`keep_highest` was
its only writer), every `PendingOption` constructor and reader is consistent,
`state.history[-1].narration` is always populated, and no dead code is left anywhere in `src`.
It also re-read all 181 comments and 161 docstrings in `src/` and confirmed the prose pass's −17
was honest: the estimate was made from raw counts and did not survive the corpus.

## Done-when, checked

- [x] Full check green: pytest 281, ruff check, ruff format --check, basedpyright 0 errors.
- [x] `tests/core/test_package_boundary.py` passes.
- [x] `grep -rn "TurnTrace\|StepTrace\|TurnResult\|ToolCall\|mechanics_without\|SceneSection\|
      sheet_rows" src/` is empty.
- [x] `advances_owed` has one definition. `complete_chapter` keeps two, with the measurement
      recorded above — the step's own floor allows it.
- [x] Goldens regenerated once, inside 3.5.4, every diff read.
- [x] `evals/cases/<engine>.py` exists per engine; `evals/turn_eval.py` is 346 lines and holds
      no engine name.
- [ ] **`src/**/*.py` below 8900** — it is 9076. Reported, not chased.
- [x] **Evals: all three named cases pass at their prior score.** Run as label `phase3-5`
      (`evals/results/phase3-5.json`), 9 repeats each, 191s:

      | case | score | errors | director_calls | prior |
      |---|---|---|---:|---|
      | `loner3e/walk-and-look` | 9/9 (100%) | 0/9 | 1.0 | 100% |
      | `loner3e/fight-the-rat` | 9/9 (100%) | 0/9 | 1.0 | 100% |
      | `twentyfourxx/fight-the-wrecker` | 9/9 (100%) | 0/9 | 2.7 | 100% |

      Every expectation at 100%, no refusals. The prior score is 100% for all three in every
      recorded baseline (`baseline`, `phase1-baseline`, `phase3`, `phase5`, `phase6`,
      `phase8-base`, `phase8-r1-full`, `step-2.5`), read from the result files directly.

## Next

- Run the three named eval cases, if the spend is wanted.
- 3.5.6 items 4-7 done; 1-3 wait for the in-flight agents to release their files.
  - **item 7**: threads deleted from the sheet panel; the journal panel already shows them.
  - **item 6**: `check_tool_names` inlined into `Engine.__post_init__`; `Harness._picture`
    folded into `Harness.scene`; `state/threads.py` (27 lines) merged into `state/tools.py`.
  - **item 4**: `Engine.sheet_rows` and its three engine functions deleted. The sheet panel had
    duplicated what the scene header already draws — `world/scene.py` renders the player's
    mechanics and inventory in `PLAYER CHARACTER`, so the panel's row block is simply gone
    rather than re-derived. `tests/core/test_sheet_rows.py` deleted; the two succession
    assertions now read the scene.
  - **item 2** (−18): `_scenario_form` extracted — slug, premise, upload, grows, engine and packs are
    built once for both scenario pages. **Not** the single page with a submission branch the plan
    asked for: after the shared form the two pages diverge completely (two-column chat and
    readback versus one card and an agent log), so one function would have carried a large
    `if driver is None` branch and read worse than two. Measured −18 against the plan's −30/−40;
    the rest of that estimate was only reachable by merging layouts that have nothing in common.
  - **item 5**: `SceneSection` deleted. `Scene` now carries two flat tuples: `sections` (the
    player's blocks, non-empty only) and `director_sections` (the Director's complete list).
    `VisibleScene` copies `sections` and has nowhere to hold director text, so the
    `Scene`/`VisibleScene` boundary is untouched. **The render-twice stands**: `rooms_scene`
    still makes a separate `blocks(shown=True)` pass for the player rather than stripping the
    Director's — only the `director=None if text == full` dedup went, which never changed a
    rendered byte. Proof: the golden prompt fixtures did not move.
    `director_sections` is required, not defaulted: an engine that forgets it fails loudly
    instead of silently hiding its world from the Director. This differs from the snippet in
    PLAN 4.2, which reads as if `director_sections` were additive — under this shape the
    journal engine passes `director_sections=(*sections, ("COUNTER", ...))`.
