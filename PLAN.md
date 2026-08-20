# Plan

The phased plan for what is built next, in order. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. A save names no version: a stale save fails validation and
   is refused, never converted.
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

## Phase 2 — the locked cuts

Four decided deletions. Everything here removes plumbing that serves the developer or acts over
the model's head; nothing that helps a weak model perform is touched. Saves are disposable until
release-point, so no step bumps a save version — step 1 deletes the concept (the version alone:
`SaveShell` and the byte-golden fixtures stay, they cost nothing recurring and catch drift).
Order matters: step 1 first, and within step 2 the scenario JSON converts in the same commit as
the code — a removed field refuses the old files at load.

### Step 1 — save versioning leaves

Strict validation is the compatibility gate. A stale save now fails at resume (`SavedGame`'s
`extra="forbid"` refuses its `save_version` key) rather than at listing — acceptable until
release-point.

- `src/aidm/state/base.py`: delete `SAVE_VERSION`.
- `src/aidm/content/store.py`: `SavedGame` and `SaveShell` each lose their `save_version` field;
  `FileStore.shell` loses the version check. `SaveShell` itself stays: the launcher's cheap
  listing and tolerant partial read are worth its ten lines.
- `tests/core/test_golden_state.py`: delete `FIXTURE_SAVE_VERSION` and
  `test_the_save_version_the_fixtures_were_cut_at_has_not_moved`; keep the serialization golden
  and both fixture families — they are the reviewed diff when step 2 moves persisted bytes.
- `tests/core/test_store.py`: delete `test_a_save_from_another_build_is_refused`; drop
  `| {"save_version"}` from the field-parity test.
- `tests/ui/test_launcher.py`: delete the wrong-version save test and the `SAVE_VERSION` import;
  fold its `controller.new_game().slug == slug` assertion into
  `test_one_corrupt_save_does_not_hide_the_others_and_stays_readable`.
- Regenerate `state/` and `save/` fixtures: exactly one `save_version` line vanishes from each.
- This file, working rule 1: delete from "Any phase that changes persisted bytes" through "the
  suite catches you"; add "A save names no version: a stale save fails validation and is refused,
  never converted."

Done when: `grep -rn "SAVE_VERSION\|save_version" src tests` returns nothing.

### Step 2 — hooks leave; consequences become authored text

The hook subsystem fires deterministically on discovery, which times narrative beats wrong
(IDEAS.md). The consequence moves into `detail.when_reached` on the triggering entity, and the Director
now reads `detail` for every entity it is shown — hidden, present, elsewhere, and carried — so a
consequence stays visible until acted on, not for one turn. The Narrator stays blind by
construction: `VisibleScene` strips `detail` (`_undetailed`). Threads and clocks are untouched.

- Convert scenario JSON in this same commit. For each hook: append its `note` — plus "then reveal
  <ids>" for `reveals` and "advance thread <thread_id> to <stage>/<status>" for `advance_thread` —
  to the `detail.when_reached` of the `on_discover` entity, then delete the `hooks` array.
  `EntityDetail.description` is required: when creating a `detail`, write a one-line description
  too. Example, drowned-road `key-discovered` → `bronze_key.detail.when_reached`: "The bronze key removes
  the lock on the crypt entrance: reveal that way and unlock it once Kael works this out." Do both
  `scenarios/*/world.json`.
- Delete `src/aidm/state/hooks.py`.
- `src/aidm/state/world.py`: delete `Hook`, `WorldState.hooks`, `WorldState.fired_hooks`,
  `WorldState.hook()`, and the hook lines in `_consistent_fiction`. `AdvanceThread` stays.
- `src/aidm/engines/transact.py`: drop the `fire_hooks` import and call (`landed = resolution`);
  `apply_to_draft`'s docstring drops "hooks and".
- `src/aidm/content/authored.py`: delete `ScenarioWorld.hooks`, `_hooks_name_authored_ids`, the
  hooks line in the `world` property, and the `Hook` import.
- `src/aidm/turn/expansion.py`: delete `ExpansionPatch.hooks`, `_authored`, the hook lines in
  `apply_patch` and `written`, and the `Hook` import.
- `src/aidm/turn/pipeline.py`: drop `"hooks"` from `TURN_STEPS`; delete the `announce("hooks")`
  block and its `StepTrace`.
- `src/aidm/turn/prompts.py`: pass `detail=True` in `_direction_sections`' hidden `_entities`
  call and in `_scene_sections`' two `_entities` calls, and render `_detail(item)` on inventory
  lines in `_character` (a carried item's hook must not vanish). Safe for the Narrator: its
  entities carry `detail=None`.
- `src/aidm/app/authoring/draft.py`: drop hooks from `ScenarioPatch`, `WorldDraft`, `apply`, and
  `_remove`; narrow the three generic bounds to `[T: Entity | Thread]` and drop the `Hook` import.
- `src/aidm/app/authoring/agents.py`: drop the hooks count in `summarize`.
- `src/aidm/app/authoring/playability.py` `_bar_unmet`: replace the hook item with "at least one
  unknown entity whose `detail.when_reached` carries a consequence" (check
  `entity.detail is not None and entity.detail.when_reached and not entity.known`).
- Prompts: `turn/prompts/expander.md` deletes its `hooks` bullet and extends the entity bullet —
  a consequence new canon carries is written into its `detail.when_reached` as an instruction to the
  Director. `app/prompts/scenario_world.md` replaces the `hooks` collection bullet the same way:
  what to reveal, which thread to advance and to where, written into `detail.when_reached` of the entity
  that triggers it. `app/prompts/scenario_bar.md` rewords its hook item likewise.
  `turn/prompts/director.md` gains one sentence: an entity's `hook` line is authored
  consequence — when the fiction reaches it, reveal and advance what it names yourself; written
  as standing instructions, a hook already acted on reads as done.
- Tests: `tests/core/test_actions.py` — delete the three hook tests and the `state.hooks` import.
  `test_pipeline.py` — delete the hook test (~line 249); in the narrator-filter test drop
  `hook_fired` AND `thread_advanced` from the expected kinds and replace the
  `len(outcomes) < len(result.turn.facts)` assertion (all remaining facts narrate; assert
  `outcomes == tuple(fact.trace for fact in result.turn.facts)` or script one un-narrated fact).
  `test_integrity_boundaries.py` — delete the two hook tests and the `Hook` import.
  `test_expansion.py` — drop hooks entries. `test_golden_turn.py` — update `TURN_STEPS`.
  `test_authoring.py` — update the wanted-words list. `test_context_boundary.py` — the Director
  now sees `detail`/`hook:` for known and hidden entities alike: flip those assertions; keep the
  Narrator assertions (never shown) exactly as they are.
- Regenerate golden fixtures (`AIDM_GOLDEN_REGEN=1 uv run pytest`). Expect movement in
  `prompts/*/{director,interpreter}.txt` (detail lines appear), `instructions/*/director.txt`,
  `turn/`, `state/`, and `save/` (hooks and fired_hooks leave the world). No `schemas/` fixture
  moves. Read the diff.
- Docs: `README.md` pipeline diagram drops `hooks` (and the stale `WORLDKEEPER` label left from
  phase 1) and the "committed Facts fire the scenario's authored hooks" sentence is rewritten.
  `docs/ROADMAP.md` (~line 23) drops its hooks/`MAX_HOOK_ROUNDS` paragraph.
  `docs/MEMORY-SYSTEM.md` (~line 12) drops "hooks" from its pipeline line. Delete the answered
  hook complaint in `IDEAS.md` (line 18).

Done when: `grep -rn "on_discover\|fire_hooks\|fired_hooks" src tests scenarios` returns nothing
and a turn's steps are interpreter, director, narrator.

### Step 3 — scenario overlays become optional

An NPC without authored mechanics gets a default sheet — `actor_sheets` already validates `{}` —
exactly as play-created entities do via `new_sheet`. Every scenario plays under every engine; an
overlay file becomes optional enrichment. Character overlays stay mandatory: the player's own
sheet is the point of creation.

- `src/aidm/content/store.py`: `load_scenario` reads `<engine>.json` when present, else uses
  `ScenarioOverlay()`. `read_scenarios` offers any directory holding `world.json` under every
  engine — and skips, with a log line, a directory whose `world.json` does not read (catch
  `ValidationError`/`ValueError` per directory: a half-written scenario must not take down the
  home page). `read_characters` keeps the per-engine overlay probe; split `_playable` accordingly
  and rewrite its docstring, whose overlay rationale is gone.
- `src/aidm/app/authoring/agents.py`: delete `TypedOverlay`, `overlay_agent`, `authored_overlay`,
  `_overlay_prompt`, `_as_overlay`, `OVERLAY_INSTRUCTIONS`, `ask_until_playable`, `ROUNDS`, and
  the imports they leave unused; `summarize(world)` loses its overlays parameter. Delete
  `app/prompts/scenario_overlay.md`.
- `src/aidm/app/authoring/session.py` `write()`: pass `overlays={}` to `write_scenario` (which
  keeps its signature — hand-authored overlays still load) and drop unused imports.
- `src/aidm/app/authoring/playability.py`: `Playtest.check` drops its `overlay` parameter and the
  `check_overlay` call — its only remaining caller passes an empty overlay; shipped overlay files
  are still validated by `load_scenario`.
- Tests: `tests/ui/test_launcher.py` — `test_content_is_offered_only_for_the_rulesets_it_ships`
  now asserts the world-only scenario IS offered under every engine (rename it); rename
  `test_an_overlay_decides_which_rules_a_scenario_offers` to say it is about characters, the rule
  it still pins. `tests/core/test_authoring.py` — delete the overlay-authoring tests plus
  `test_the_author_is_asked_again_with_the_reason`,
  `test_the_author_gives_up_after_every_round_is_refused`, and the `ask_until_playable` import.
  `test_store.py` — a scenario directory with only `world.json` lists every engine and loads with
  an empty overlay. No `schemas/` fixture moves.
- `README.md`: reword the two sentences saying content plays only under engines it ships overlays
  for (home-page paragraph and the scenarios/characters lines in Layout).

Done when: a scenario directory holding only `world.json` starts and plays under both engines,
and `grep -rn "TypedOverlay\|authored_overlay\|ask_until_playable" src tests` returns nothing.

### Step 4 — expansion policies fold to closed | open

`open` is today's `cited_or_invented` generalized: search the document where one exists, fall
back to the premise where it is silent — which subsumes `cited` (document answers everything)
and `invented` (no document, always the premise). Lost deliberately: the strict `cited` refusal.

- `src/aidm/content/sources.py`: `ExpansionPolicy = Literal["closed", "open"]`. Rename
  `CitedOrInventedSource` to `OpenSource` with a reworded docstring and a default
  `document: RecordSource = RecordSource(records=())`, so no call site builds a null object.
  Delete `WholeSource`. `whole_text` stays for authoring; its too-large error now says "author it
  `open`, which searches the document".
- `src/aidm/content/store.py`: delete `read_source` and `require_source`; `source_file` stays.
- `src/aidm/app/session.py` `open_source`: `closed` returns `None`; `open` returns
  `OpenSource(premise=scenario.meta.premise)` when `source_file(...)` is `None`, else
  `OpenSource(document=ingest(path), premise=...)`. Rewrite its docstring, which names the dead
  policies.
- `src/aidm/app/authoring/session.py` `__post_init__`: delete the cited/cited_or_invented
  document-requirement check.
- `src/aidm/ui/scenario_create.py`: `_EXPANSION_LABELS` shrinks to `closed` and `open` ("the
  document where it speaks, the premise where it is silent"); the select defaults to `"open"`;
  delete the now-redundant `expansion.set_value(...)` line in the upload handler.
- `scenarios/drowned-road/world.json`: `"expansion": "cited"` → `"open"`.
- Tests: `tests/core/test_authoring.py` — delete `test_a_cited_session_needs_a_document`; change
  both `expansion="invented"` sites (and the final assertion) to `"open"`.
  `test_sources.py` — replace `WholeSource` cases with `OpenSource`; rewrite the
  refused-without-document test as: an `open` scenario with a document searches it, one without
  answers from its premise. `test_expansion.py` — replace `read_source`/`WholeSource`
  construction with `OpenSource` and rename the two `cited` tests. `test_store.py` — delete
  `test_a_scenario_expands_from_its_own_source_or_else_from_its_premise`; the behavior now lives
  in `open_source` and is covered in `test_sources.py`.

Done when: `grep -rn "cited_or_invented\|WholeSource\|read_source\|require_source" src tests`
and `grep -rn '"invented"' src scenarios` return nothing.

### Verifying the phase

- `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright` after
  every step, one commit per step.
- `uv run aidm` after steps 2 and 4: play three turns of each scenario, watch a converted
  `detail.when_reached` consequence land at a sensible moment, and see an `open` scenario expand.
- After step 3: launch whispering-vault under 24XX with its loner3e overlay file temporarily
  renamed away, and confirm default sheets play.
