# PLAN: a smaller core

This file is self-standing; a session needs nothing else. Phases 1, 2 and 3 have shipped
(`c47e1d1`, `f40c646`, `3b7157d`) and their step lists are deleted; the git log is the record.
What remains is Phase 3.5 and Phase 4.

## Why Phase 3.5 exists

Phases 1–3 were meant to make the codebase smaller. Measured against `f37ba99`, the last
commit before the refactor, they did the opposite:

| | before | after Phase 3 |
|---|---|---|
| `src/**/*.py` | 8956 | 9363 (**+407**) |
| modules | 52 | 60 |

Two independent external reviews of Phases 1–3 agree on the cause, and on what won.

**What won, and must not be undone.** `Fact` absorbing `MechanicEvent`/`EventBadge`; a pending
decision as a deferred tool call, which killed the `Decision` hierarchy, `payload`,
`Engine.resume`, `check_pending` and `_decision`; the `world/` boundary, with
`WorldState._consistent_fiction` reduced to containment integrity and `validate_rooms` owning
topology; `Scene`/`VisibleScene`, whose Narrator type has nowhere to store Director-only text;
flat `Character`; `Draft` on `WorldState`, which deleted the second world representation.

**What lost.**

1. `Engine` became a 16-field service catalogue, and most built-in values are the *same* room
   policy written three times: `over=player_over`, `growth_due=rooms_growth_due`,
   `scene=rooms_scene(...)`, the same nine world tools, `TAKE_OVER`, the same
   `authoring_brief` lambda. Every hook has a caller; the waste is the repeated assembly.
2. Moving mechanics into engines copied procedures core used to share. Loner and 24XX hold
   near-identical `complete_chapter` and `advances_owed`.
3. The mechanics blob did not buy type safety — the old `Entity.rules` was runtime-validated
   JSON too. It is kept because Loner's twist counter is game-wide and a non-rooms engine needs
   somewhere to put state, but its `Engine` surface is two fields wide and should be one.
4. **A non-rooms engine cannot be written today.** The blockers are in shared code (step 3.5.5).

Phase 3.5 is the correction. It cuts before it adds.

### The honest arithmetic

Both reviews measured the steps below. Expected delta, midpoints:

| step | delta |
|---|---:|
| 3.5.1 `rooms_tools` | −42 |
| 3.5.2 one mechanics operation | −8 |
| 3.5.3 shared chapter/advance | −8 |
| 3.5.4 turn trace, `ToolCall`, `DiceEvent.result`, eval split | −128 |
| 3.5.5 non-rooms blockers | ~0 |
| 3.5.6 the deletion pass | −155 |
| **total** | **≈ −340** |

That lands near **9020**, not 8900, and not under the pre-refactor 8956. Two further cuts
would close the gap and are deliberately *not* scheduled:

- Converting `ClaudeDriver` into an `ExecDriver` subclass (−80, and drops the
  `claude_agent_sdk` dependency). `harness/claude.py:28` already records the condition: it is
  right "the day it bills like the API", and that day has not come. Do not do it early. Do not
  do its inverse either — folding `exec.py` into `codex.py` saves ~15 real lines and destroys
  the abstraction this conversion needs.
- Replacing `config.py`'s `Roles.for_name` / `Providers.for_name` `match` blocks (−12). This
  would reintroduce the string-keyed dispatch already killed once, on purpose.

So: **the target is 8900, the measured estimate is ~9020, and the gap is known.** Record the
actual count after every step. If the running total is tracking above the estimate by 3.5.4,
stop and re-scope rather than inventing cuts to hit a number.

## Invariants

1. The model proposes; Python decides. Tools return typed proposals; resolver code mutates.
2. The Narrator sees only revealed canon: `VisibleScene.revealed_from` refuses any listed id
   that is not known and carries only player text; `render_narrator` accepts only
   `VisibleScene`; `apply_to_draft` refuses a told fact about an unknown entity.
3. One pending decision at a time (`apply_to_draft` check).
4. `kill` is the only way to record a death: it drops what the dead carried and opens the
   succession decision, so `add_trait` refuses the reserved `dead` trait id.
5. Draft/commit round-trip: every mutation runs on `Game.draft()`, commit is
   `model_validate(model_dump())`. Dict writes on a `WorldState` skip validation; that is why.
6. Both harnesses (`turn/run.py` and `harness/codemode.py` + `harness/mcp.py`) share
   `render_director` and `Turn`. Never add a second turn loop.
7. The builtin loop commits every turn whole (`close_segment`); code mode commits per accepted
   tool call, and each commit is a legal state.
8. `aidm/world/` is rooms policy and may not import `aidm/engines/`. **A non-rooms engine
   imports nothing from it directly.** `authoring/` reaches `world.authoring.diff` and
   `world.topology.player_location` on growth-only paths; step 3.5.5 decides whether that stays.
9. Core never reads inside `WorldState.mechanics`. Only `engines/` opens the blob, and an
   engine names the keys it treats as entity-keyed rather than assuming every map is.

## What not to collapse

Both reviews tested this list independently and upheld it. Do not re-propose:

- **`Fact` and `DiceEvent`** stay separate. A fact is an occurrence with an audience policy; a
  dice event is one visual group, and a fact may carry several.
- **`Scene` and `VisibleScene`** stay separate. The conversion is invariant 2 made structural.
  (`SceneSection` is a different question — step 3.5.6 cuts it.)
- **`DirectorTool` and `AuthoringTool`** stay separate: one mutates a `Game` with an rng and
  returns facts, the other edits a `WorldState` and returns draft feedback.
- **`Draft` and `ScenarioPatch`** stay separate: accumulated mutable state versus the validated
  partial command crossing the model boundary. Whole-draft writes were rejected before.
- **`AuthoringBrief`** stays: the only engine→authoring contract, consumed by builtin authoring
  and MCP publication alike.
- **`state/tools.py:apply_to_draft`**, the single gate every mutation passes.
- **`world/scene.py`'s render-twice-and-diff**, which is what computes `director=None`.
  Simplifying it is how a hidden-canon leak returns.
- **The engine `rules.py` files.** They are the SRDs; sharing across them to save ~20 lines
  would blur "each engine owns all of its mechanics".
- Media, player actions, cards, streaming `on_fact`, the settings page and scenario pack
  choice: all on the recorded keep list.

## Verification

From the repo root with `UV_CACHE_DIR` unset: `uv run pytest`, `uv run ruff check`,
`uv run ruff format --check`, `uv run basedpyright`. "Full check" means all four.

Goldens: `AIDM_GOLDEN_REGEN=1 uv run pytest` rewrites `tests/core/fixtures/**` and reports
failure by design. Read every diff with `git diff tests/core/fixtures` before the next plain
run. Goldens regenerate **once**, inside step 3.5.4.

Evals: only `uv run python evals/turn_eval.py run --label <step> --case <name>` on named cases,
never a full run.

**Every step records `find src -name '*.py' | xargs cat | wc -l` before and after.** Except
3.5.5, which is correctness work and is expected to be line-neutral, a step that adds lines has
failed its own purpose: stop and say so.

---

## Phase 3.5: consolidation

Branch `core-slim`. 3.5.1 to 3.5.3 are independent. 3.5.4 changes saves and goldens and must be
atomic. 3.5.5 unblocks Phase 4 and must precede it. 3.5.6 is last so it can also sweep whatever
the earlier steps leave behind.

### Step 3.5.1: `rooms_tools` (−42)

The three engines repeat the same tool list and the same ~12 world imports. New in
`world/tools.py`:

```python
def rooms_tools(
    validate: Validate, *extra: DirectorTool, improvised: bool = True
) -> tuple[DirectorTool, ...]:
    return (
        REVEAL, MOVE,
        *((GAIN_IMPROVISED_ITEM,) if improvised else ()),
        ADD_TRAIT, REMOVE_TRAIT, kill_tool(validate),
        UNLOCK_EXIT, JOIN_PARTY, LEAVE_PARTY, ADVANCE_THREAD,
        *extra,
    )
```

That order reproduces all three engines exactly, so `schemas/*/director_tools.json` must not
move. Breathless alone passes `improvised=False`. The named constants stay exported for a
non-rooms engine that wants some of them.

**Do not build a `rooms_engine(...)` factory.** It was considered and rejected: a 15-parameter
function that re-passes `creation`, `validate`, `sheet_rows`, `describer`, `tools`, `resolvers`
and `player_actions` is `Engine(...)` with renamed keywords, and it costs 55–65 lines to save
~65. The five remaining policy defaults (`over`, `scene`, `growth_due`, `authoring_brief`,
`TAKE_OVER`) are one line each per engine; hiding them costs more than it saves. Revisit only
if a fourth rooms engine appears.

Verify: full check; goldens must not move.
Eval: `--label step-3.5.1 --case loner3e/fight-the-rat`.

### Step 3.5.2: one mechanics operation (−8)

`Engine.mechanics_merge` and `Engine.mechanics_without` become one field:

```python
type MechanicsPatch = Callable[[Mechanics, Mechanics, Sequence[EntityId]], Mechanics]
mechanics_patch: MechanicsPatch   # (blob, added, removed_ids) -> blob
```

One shared body in `engines/core.py`, bound per engine:
`partial(mechanics_patched, Loner3eState, entity_maps=("sheets",))`; 24XX and Breathless pass
`("sheets", "items")`.

**`entity_maps` is not optional and must not be inferred.** "Drop the id from every dict-valued
top-level key" is unsafe: an entity called `winter` would delete `mechanics["seasons"]["winter"]`,
and it would break invariant 9. Each engine declares which maps are entity-keyed.

Validate the merged blob **before** discarding removed ids, so a patch cannot hide an invalid
sheet by adding and removing the same id. Compute the new blob before mutating the draft, so a
rejected patch cannot leave half its entities behind — `Draft.apply` currently mutates in two
places.

If, in implementation, the three-argument form reads worse than two fields (three of four call
sites pass no removals), keep two fields and share only the body. The win being bought is the
deletion of three near-identical `_without` functions, not the field count.

Verify: full check.

### Step 3.5.3: shared chapter and advance procedures (−8, or abandon)

Loner and 24XX hold the same two algorithms with a different ledger field (`milestones` vs
`jobs`). Move both to `engines/core.py`.

Constraint: `complete_chapter` mutates, and only the `rules(...)` context manager writes the
blob back. The `with rules(draft.world, Model) as game:` wrapper therefore stays in the engine;
the shared function takes `game.sheets` and mutates it. `advances_owed` is read-only and takes
the parsed mapping plus an `is_owed` callback. No sheet protocol, no mixin — two plain
functions with explicit arguments.

The identical owed-advance prompt string is the one guaranteed duplicate; make it a shared
constant even if nothing else shares.

**This step has a floor.** If the generic typing and wrappers cost more than the duplication
they remove, keep the duplication and say so. Moving code without deleting it fails this phase.

Verify: full check; goldens must not move.
Eval: `--label step-3.5.3 --case twentyfourxx/fight-the-wrecker`.

### Step 3.5.4: delete the turn trace, atomically (−128 src)

The largest cut. It must be one step: `tests/core/test_golden_turn.py` serializes `TurnTrace`,
so the trace deletion and the golden regeneration cannot be separated. `ToolCall` and
`DiceEvent.result` ride along because they change the same fixtures.

**Delete:**
- `state/play.py`: `StepTrace`, `TurnTrace`.
- `turn/run.py`: `TurnResult`, `retry_prompts`, the `steps` list; `run_segment -> Game`;
  `Turn.finish(lines) -> Game`. Fold `TurnRecord` into `Turn`.
- `app/runtime.py`: `GameSession.entries`; `commit(state)`; **`submit -> None`** — the session
  already owns and commits the state. Illustration narration comes from
  `state.history[-1].narration`, not from a returned trace.
- `ui/panels.py`: `trace_panel`; `ui/game.py` drops the dev tab call.
- `harness/codemode.py:end_turn`: `state = turn.finish(lines)`.
- `state/play.py:ToolCall` — `PendingOption` carries `name` and `args` directly.
- `state/facts.py:DiceEvent.result` — written only by `keep_highest`, always `str(max(rolled))`;
  the UI renders faces, rolled and highlight only. Readers become `max(die.rolled)`.

**Eval side**, replacing the deleted types with an eval-owned record:

```python
class Played(Frozen):
    state: Game
    facts: tuple[Fact, ...]
    narration: str
    director_calls: int
    retry_prompts: tuple[str, ...]
    prompts: tuple[str, ...]
```

Four semantics the drafting must get right, each a real difference from the deleted trace:
1. `director_calls` counts Director **segments**, as today — not `WrapperModel` requests.
2. Record **all** `RetryPromptPart`s of the newly appended final `ModelRequest`, not just the
   last, and do not re-record earlier requests.
3. `on_fact` fires before narration commits. Keep facts per segment and append them only when
   `run_segment` succeeds, or a failed narrator records facts the loop rolled back.
4. Today a failed case keeps its stage outputs. Either record request/response pairs eval-side
   or accept the diagnostic loss explicitly.

**Fold the old Phase 4.1 eval split into this step.** Both passes rewrite the same ~60
predicates; doing them separately means touching every one twice. While the predicates are open:
`evals/turn_eval.py` keeps `Case`, `Expectation`, `Run`, `CaseResult`, `Report`, `begin`,
`Played`, the CLI and `compare`; new `evals/cases/shared.py` holds `Canon` and
`cases_for(engine_id, canon, settings)` for the four parametrized cases; new
`evals/cases/<engine>.py` holds `CANON` and `CASES(settings)`; the runner loads
`evals.cases.<engine_id>` by `import_module`.

`tests/core/core_test_support.py`: `played -> Game`; delete `shown`; golden prompts come from
`recorded(...)`; the golden turn fixture is facts through `on_fact` plus the committed save.

Then regenerate goldens once and read every diff: `turn/*.json` (shape), `save/*.json` and
`state/*.json` (flattened option calls, no `result` on dice).

**Saves written before this step are invalid** — any save holding an open decision or a stored
dice card. That is policy, not a bug; no migration.

Verify: full check.
Eval: `--label step-3.5.4 --case loner3e/walk-and-look`.

### Step 3.5.5: the non-rooms blockers (line-neutral, by design)

Shared code that assumes rooms. Doing this before Phase 4 means no test ever forces a
production change.

1. **`authoring/draft.py:Draft.scenario`** refuses a null `player_parent_id` unconditionally
   while `Scenario` allows it. Delete the refusal — **and** add the explicit unmet line ("a
   start location: set `player_parent_id`") to `world/authoring.py:_bar_unmet` and
   `_opening_unmet`. Without it a rooms draft is refused later, by the playtest, with a worse
   message: `_bar_unmet` currently skips reachability when the start is null.
2. **`content/model.py:Scenario._playable_canon`** enforces that companions stand beside the
   player — a rooms rule in core. Move it into `world/authoring.py`'s unmet functions, which
   receive a `Scenario`. **Not** into `validate_rooms`: that runs on live state, and
   `world/actions.py:_move_actor` deliberately allows a party member to be witnessed moving
   away, with the player pulled along on their next move. A live co-location check would refuse
   legal states.
3. **`authoring/run.py:_HOW_TO_WORK`** hardcodes "join locations with `connect`". Replace it
   with static generic wording naming no tool. Do not generate the sentence from `brief.tools`:
   dynamic prose costs lines for no behaviour change.
4. **Packs.** `Scenario` and `Game` require `min_length=1`, and both `playtest_check` and
   `Harness.blank_authoring` call `next(iter(engine.packs))`. Either relax the requirement or
   accept that every engine ships one pack — decide here, not in the test.
5. **`authoring/draft.py:patch_refusal`** still tells every engine to reach existing places
   "with `connect`", and `authoring/prompts/scenario_example.md` still mandates exits and
   `connect`. Both are shown to non-rooms engines. Fix the wording or scope it to the brief.
6. **`Draft.from_game` calls `player_location`**, so growth is impossible for a non-rooms
   engine. Phase 4's journal has `growth_due` False, so this does not block it — record the
   limit rather than fixing it speculatively.
7. **`Game.player` needs no change.** `begin_game` always constructs the played entity as an
   actor. Do not relax it.

The closing grep must cover `authoring/` and `ui/`, not just `state/` and `content/`.

Verify: full check.

### Step 3.5.6: the deletion pass (−155)

Ranked by lines saved per unit of risk. Take them in order and stop when the target is met.

1. **Non-runtime prose that restates names** (−45/−60, very low risk). There are ~178 docstring
   lines and ~182 comments in `src/`; many say *what*, which the signature already says.
   Preserve every runtime description (Pydantic `description=`, tool descriptions, prompt text)
   and every comment carrying a non-obvious *why*.
2. **Merge `ui/create.py:scenario_page` and `agent_scenario_page`** (−30/−40, medium). They
   duplicate the id, premise, engine, packs, growth and upload form. One page, one small
   builtin-versus-driver branch at submission.
3. **Delete the three frozen `Rules` dataclasses** in the engine `rules.py` files (−18/−22,
   low). Named module constants. These values have no second configuration and never vary.
   This is not the "constants into config" move that was rejected before — nothing moves to
   `Settings`.
4. **Delete `Engine.sheet_rows`** (−15/−20, low-medium). `world/scene.py` already renders the
   player's mechanics and inventory in `PLAYER CHARACTER`. The game page reads the visible
   scene; Phase 4's character preview builds a throwaway game and renders the same section.
   Deletes three engine functions and one contract field.
5. **Delete `SceneSection`** (−14/−20, medium). `Scene.sections: tuple[tuple[str, str], ...]`
   plus `Scene.director_sections: tuple[tuple[str, str], ...]`; `VisibleScene` copies only
   `sections`. This removes a concept **without** collapsing the `Scene`/`VisibleScene`
   boundary — check the render-twice-and-diff still produces the same golden prompts.
6. **Small forwarding and micro-modules** (−8/−12, low): `Harness.scene`/`_picture`,
   `check_tool_names` inlined into `__post_init__`, and `state/threads.py`'s 27 lines moved
   beside the other state tools.
7. **Duplicated right-panel content** (−8/−14, medium): threads appear in both the sheet and
   the journal panel. Keep them in the journal. Reconsider the raw-state expansion only if it
   is no longer used as a diagnostic.

Verify: full check after each numbered item, not once at the end.

---

## Phase 4

### Step 4.1: UI consolidation

- `ui/widgets.py`: `page_header(title, engine_title: str | None = None, home=True)`; delete
  `show_engine_badge`; `ui/app.py`'s two callers render `ui.badge(engine.title)`.
- `ui/create.py`: sheet preview built from a throwaway
  `begin_game(engine, "preview", scenario, character)` when a scenario is selected, else traits
  and items only.
- `ui/game.py`: `_mechanic_event` → `_card(fact)`.
- Do not merge `ui/settings.py` or `ui/theme.py` into anything.

Verify: full check; `uv run aidm` opens and a game page renders.

### Step 4.2: non-rooms proof engine, green

- New `tests/nonrooms/engine.py`: a journal engine built by calling `Engine(...)` directly.
  `id="nonrooms"`, `JournalState(counter: int = 0)` as its mechanics model, one Director tool
  `mark_passage`, a one-step `creation`, a room-free `AuthoringBrief` with no `connect`,
  `growth_due` False, `over=lambda state: None`, its own `mechanics_patch`. `scene` returns
  `Scene(key="journal", label="Journal I", sections=(("JOURNAL", <public text>),),
  director_sections=(("COUNTER", <counter text>),), present_entity_ids={player},
  art_prompt="an open journal ...")`. No import from `aidm.world`; no locations, exits, party,
  threads, death or dice; `player_parent_id` null.
- `tests/nonrooms/test_nonrooms.py` asserts:
  1. `run_segment` with a `FunctionModel` calls `mark_passage`, commits counter `1`, records
     `Exchange.scene == "Journal I"`, leaves `player.parent_id` None.
  2. `Harness` (MCP) does the same through code mode.
  3. Authoring writes the scenario with no start location and no `connect`, and `load_scenario`
     reads it back; the character comes through the normal creation form.
  4. `game_page` renders "Journal I", its section, the composer and the art slot.
  5. A stub illustrator receives the journal art prompt, keyed by `Scene.key`.
  6. A `Scene` whose `public_entity_ids` names an unknown entity is refused by
     `VisibleScene.revealed_from`; the same entity may appear in a director section.

A permanent acceptance test, not a one-off proof. No xfails, and **no production file changes
to make it pass** — 3.5.5 did that work. If one is needed, 3.5.5 was incomplete: fix it there.

Verify: full check.

### Step 4.3: small deletions and docs

- `app/runtime.py:GameSession._resumable`: delete the second `engine.validate` call —
  `engine.restored` already ran it.
- `docs/NEXT-ENGINE-RESEARCH.md`: one line at the top naming what no longer exists.
- `tests/cairn/` is already untracked; remove its stale `__pycache__`.
- `grep -rn "at_boundary\|sheet_of\|EventBadge\|TurnTrace" tests/` is empty.
- Delete this `PLAN.md` in the final commit; the git log is the record.

Verify: full check.

---

## Done when

- [ ] `src/**/*.py` is **below 8900**, with the per-step actuals recorded. The measured estimate
      is ~9020; if the plan lands there instead, say so and stop rather than reaching for the
      two cuts this file rules out.
- [ ] Full check green: pytest, ruff check, ruff format --check, basedpyright.
- [ ] `tests/core/test_package_boundary.py` passes; `engines/core.py` and `state/` import
      nothing from `aidm.world`; `world/` imports nothing from `aidm.engines`.
- [ ] `grep -rn "TurnTrace\|StepTrace\|TurnResult\|ToolCall\|mechanics_without\|SceneSection\|
      sheet_rows" src/` is empty.
- [ ] `complete_chapter` and `advances_owed` each have one definition, or the step recorded why
      sharing them cost more than it saved.
- [ ] Goldens regenerated once, inside 3.5.4, and every diff read.
- [ ] Evals: the named `--case` runs at 3.5.1, 3.5.3 and 3.5.4 pass at their prior score.
- [ ] `evals/cases/<engine>.py` exists per engine; `evals/turn_eval.py` holds no engine name and
      is under 1000 lines.
- [ ] `tests/nonrooms/` is green with no xfail, built by calling `Engine(...)` directly, and it
      required no production change to pass.
- [ ] `PLAN.md` deleted in the last commit.
