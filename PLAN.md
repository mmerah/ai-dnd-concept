# Drastic simplification plan

Goal: the core stops being an RPG framework. An engine is a folder with state models, one tool per
SRD procedure, and a `director.md`. Adding engine #4 touches nothing outside `engines/<id>/`.

Line counts below are estimates. The bar is the one already in use: smaller, or break-even but
more maintainable, measured after the phase lands. Re-measured on 2026-08-28 after Phase 1:
phases 1–6 sum to about −780 lines, not −1650. Audited the same day for extra cuts: phases 2–6
now estimate about −700; Phase 7 as decided about −265 more. Player-facing behaviour is the
bar above lines: a cut that plays worse is out.

## Rules for every phase

1. Work on a branch per phase. Commit in small steps; every commit passes `uv run ruff check`,
   `uv run ruff format --check`, `uv run basedpyright`, `uv run pytest`.
2. Golden fixtures: run `AIDM_GOLDEN_REGEN=1 uv run pytest` once at the end of the phase, then
   read `git diff tests/core/fixtures` line by line. A diff you cannot explain is a bug.
3. Eval gate: `uv run python evals/turn_eval.py run --label <phase> --concurrency 16` then
   `compare --baseline <previous>`. High concurrency: the default of 4 is slow. Ship at
   or above the current baseline (96/99). Below it: revert the phase, do not patch.
4. Saves are invalid after every phase. No compatibility code, no version field.
5. Shipped content is migrated by hand in the same phase: `scenarios/*/world.json`,
   `characters/kael/*.json`. `extra="forbid"` means a deleted field must leave those files too.
6. Delete first. A helper stays in core only if two engines call it. A helper one engine calls
   moves into that engine's folder.
7. Keep every `Field(description=...)` the model reads. Changing one is a prompt change and needs
   the eval.

Decided and not up for re-litigation: no discriminated-union mega-tools (`world(change)`,
`rules(move)`). Union schemas lost twice (RuleCall, TurnPlan) and schema size was the measured
failure variable for weak models. One Director tool per SRD procedure stays.

## Phase 1 — Rules live on the entity, sheets mirror deleted

Today an entity's authored `rules` dict is copied into `mechanics.sheets[id]` /
`mechanics.items[id]` and kept in sync by `seed`, `validate`, `uses_sheet`, `uses_item_sheet`,
`_check_items`, `opening_mechanics`, `overlay_rows`, `require_sheet`, `Mechanics.of_game`.
After this phase `Entity.rules` is the only copy.

Design: `Entity.rules` stays `dict[str, JsonValue]`. That keeps `Scenario`, `CharacterProfile`,
`ScenarioPatch`, `read_scenarios` and the authoring JSON schema unchanged. Engines read and write
the dict through one helper, and `engine.validate` parses every entity's rules as the commit
gate.

Steps, in order:

1. Add to `engines/core.py`:
   ```python
   @contextmanager
   def rules[M: Mutable](entity: Entity, model: type[M]) -> Iterator[M]:
       """Parsed on entry, written back on exit; the one way an engine touches `entity.rules`."""
       parsed = model.model_validate(entity.rules)
       yield parsed
       entity.rules = parsed.model_dump(mode="json")
   ```
   Read-only callers use it the same way. No `of()` classmethod anywhere.
2. Add `Engine.rules_types: ClassVar[Mapping[Kind, type[Mutable]]]`. Engine `validate` does
   `for entity in state.world.entities: rules_types[entity.kind].model_validate(entity.rules)`
   plus its own checks (Breathless carry limit). Kinds with no rules map to a model with no
   fields.
3. `Game.mechanics` is deleted; Loner `twist` lives on the player `Sheet`; `completed` becomes
   `SheetBase.chapters` per entity.
4. Advancement ledger: delete `SheetEngine.seed`'s levelling. Replace with the SRD reading:
   `complete_chapter` increments `chapters` on the sheet of the player and every party member
   present. Owed = `sheet.chapters.current - sheet.<spent>.current`. Nobody is owed chapters they
   did not play. This is a behaviour change; note it in `docs/24XX.md` and `docs/LONER-3E.md`.
5. Migrate 24XX first (largest), then Loner, then Breathless. In each: replace
   `Mechanics.of_game(draft).sheets[actor.id]` with `with rules(actor, Sheet) as sheet:`;
   `overlay_rows` → `Sheet.model_validate(rules).rows()`; `describe`/`sheet_rows` → `rows()` on
   the parsed model; `check_scenario` sheet checks → `validate`.
6. Breathless: a rules-less item parses as `ItemSheet()` (d10) because every field has a default,
   so the `seed` refusal goes. Loner: an actor with empty rules parses as `Sheet()`. This widens
   Loner deviation 2 to authored actors; update `docs/LONER-3E.md` to say so.
7. `create.py` preview: `engine.overlay_rows(created.rules)` →
   `engine.rules_types["actor"].model_validate(created.rules).rows()`. `load_character`'s
   `check_overlay` callback becomes the same one-liner.
8. Delete `engines/sheets.py`. `complete_chapter`/`chapter_command` are called by two engines, so
   they move to `engines/core.py` (rule 6).
9. `parse_save` special case goes with `Game.mechanics`.
10. Hand-edit nothing: the JSON shape of `rules` is unchanged.

Follow-up (decided 2026-08-28): the Loner widening in step 6 was a downgrade. Loner `validate`
refuses an actor with empty rules again; `_sheeted` applies to items only ("Everything is a
Character" is for things, not for an actor nobody wrote). Restore deviation 2 in
`docs/LONER-3E.md` to its Phase 0 wording.

Measured 2026-08-28: −30 lines as written; the deletion was counted but not the rebuild. Extra
cuts landed the same day: Game.mechanics deleted (twist on the Loner sheet), Advancement ABC
collapsed, 24XX _check_skills gone, check_sheet folded into rules(), describe overrides folded
into Engine.describe.

## Phase 2 — Cards keep their shape, the helpers around them go

Decided 2026-08-28: `MechanicEvent(title, badges, dice, outcome, effects, icon)` stays as is.
The card is the fun part of a turn. Only the ceremony around it goes.

1. Fold `explained_fact` into its callers: `entity_fact(e, kind, f"{trace} ({why})")`.
2. Four join helpers (`trace_lines`, `traced`, `narrator_lines`, `narrator_evidence`) become
   two; `NOTHING_MECHANICAL` and `NOTHING_CHANGED` become one constant.
3. `chapters`, `jobs`, `milestones` only count up: `int`, not `Counter`. `counter_fact` is for
   pools with a maximum; a ledger step is a plain `entity_fact`.
4. Loner `_absorbed` and the three `_badges` builders stay: they are card content.

Measured estimate: −30 lines. One hour. No eval needed: no prompt text changes.

## Phase 3 — Flat tool ladder, engine as a value

Order matters: 3.1 removes the only reader of `DirectorContext.answered`, so it comes first.

1. Options-only decisions. `PendingDecision.allows_text: bool`. Defence and Loot are
   options-only: the SRD gives the player a pick, and the buttons are that pick. Stake-proceed
   keeps text: "Proceed, or change your plan" is how the player revises. Conflict (Loner) keeps
   text. `consume_answer` raises on `Answer(text=...)` when `allows_text` is false; `ui/game.py`
   disables the composer then; `codemode.start_turn` gets the same refusal. Delete
   `settle_defence`, `DirectorContext.answered`. Keep `suspended_at_start` and
   `during_suspension`: a turn that opened re-suspended still develops the answer with core tools.
2. One constructor `director_tool(name, description, Args, resolve: (draft, args, rng) -> facts,
   *, during_suspension=False)`. Delete `command`, `rule`, `action`, `_world_command`.
   The name avoids `pydantic_ai.Tool`.
3. Advancement is already per-engine after Phase 1; nothing left here.
4. `Engine.director_tools` is the complete list. Engines compose `(*CORE_TOOLS, ...)` themselves.
   Breathless drops `gain_improvised_item` and its "never call" line in `breathless/director.md`.
   The core `director.md` line "Create only ordinary incidental objects, with
   `gain_improvised_item`" moves into the 24XX and Loner `director.md`.
5. Engine as a value. After 1–4 every abstract method is data or one function. `Engine` becomes a
   frozen dataclass: `id, badge, engine_dir, rules_types, director_tools,
   player_actions, creation, validate, owed_notes, authoring_instructions`. Each
   `engines/<id>/engine.py` ends with `ENGINE = Engine(...)` or a `build(settings) -> Engine`.
   `registry._declared` becomes `import_module(...).ENGINE`. Delete `engine_class` reflection.
6. `CreatedCharacter` and `Character` are the same two fields plus an id: one model.
7. MCP tool list: authoring tools are listed only while an authoring run is open; director tools
   are listed as soon as a game is open (unchanged). The Claude SDK lists tools once at connect,
   so nothing may depend on a later `list_changed`.
8. Regenerate `tests/core/fixtures/schemas/*/director_tools.json`; read the diff.
9. After 3.1 no tool reads `deps` (`_settle_defence` was the only reader). Delete
   `DirectorContext`; `apply_play` and `run_command`'s suspension gate become `Turn.call`.
   `TurnRecord` stays: `on_event` streams cards to the page.
10. `CharacterCreation.rolls` is never `True`. Delete it, the Reroll button, `seed`, and the
    `rng` parameter of every `create` (all three `del rng`).
11. `TurnResult` is a tuple. Loner `PackEntry` is `CreationOption`; 24XX `Specialty`, `Origin`,
    `SkillGrant`, `GearItem` subclass it, so `pack_options` goes.
12. `mcp.py`: the `AUTHORING`/`AUTHORING_TOOLS` module constants go with 3.7; `call` routes by
    `name in run.toolset`.

Measured estimate: −145 lines (3.2 ≈ −25, 3.5 ≈ −40, 3.6 −8, 3.9 ≈ −25, 3.10 −15, 3.11 −17,
3.12 −10). One day.

## Phase 4 — One pack list per scenario, no scenario-shipped packs

Decided 2026-08-28: a scenario still chooses which installed packs it plays with (a Loner
scenario picks its table sets), and the authoring prompt still shows their content. What goes is
the second layer: packs a scenario ships in its own folder, and a pack list on every sheet.

1. Each engine constructor loads `{stem: Pack}` from `engine_dir / "packs"` then
   `settings.packs_dir / engine.id` (later wins). A broken file raises. Delete
   `engines/sources.py` (`PackSources`, `drafted`, the warn-and-skip) and `engines/packs.py`;
   `pack_options`, `find_entry`, `picked_entry`, `PackCreation` move next to their callers.
2. `Scenario.packs` stays and is copied to a new `Game.packs` in `begin_game`. Delete
   `SheetBase.packs`, `_packs_include_srd`, `character_packs`, the per-entity installed-pack
   check in `validate`; `validate` checks `state.packs` against the installed packs once. Loner
   keeps `twist_pack` and checks it is in `state.packs`; `meanings` reads `state.packs`.
3. Delete scenario-shipped packs: `write_pack`, `pack_refusal`, `PlaytestCheck.shipping`,
   `PlaytestCheck.sources`, `ScenarioDraft.packs`, `scenario_packs`, `AuthoringBrief.writes_packs`,
   `PACKS_DIR`, the `packs` argument of `write_scenario`, the `(engine, scenario)` memo key. The
   pack multiselect on both authoring pages, `selected_packs`, `installed_pack_ids`,
   `BeginScenario.packs` and the "SELECTED PACK CONTENT" dump stay. Update the 24XX
   `authoring_instructions` string (it says "set packs" per actor). Grep `packs` under
   `.claude/skills/` and fix the skills.
4. Delete the "How much to author" select: `scenario_run` derives the brief from `grows`.
   Delete `AuthoringBrief.label`, `BRIEFS`, `brief_named`.
5. `Runtime` builds every engine once at start: `engines: dict[EngineId, Engine]`. Delete
   `build_engine`, `engine_class`, `engine_ids`, `as_engine_id`. Callers: `runtime.py`,
   `create.py`, `draft.py`, `launch.py`, `ui/app.py`.
6. `PlaytestCheck` keeps `engine`, `character`, `packs`; `playing` is never `None`: the MCP tool
   listing uses any built engine, so both "no engine is loaded" branches go.
7. `ScenarioDraft.grows` moves to `ScenarioRun`; `NOT_PATCHED` and the `exclude=` go.
   `ScenarioRun.art_style` goes: the form seeds `draft.art_style` before the run.
8. `AuthoringConfig.worked_example` goes: `_example` takes the first scenario for the engine.
   `Pack.source` and `Pack.license` are never read; keep them only if the JSON needs them.
9. Hand-edit: remove `"packs"` from every `rules` in `characters/kael/*.json` and
   `scenarios/*/world.json`; the top-level `"packs"` of each `world.json` stays. Delete
   `tests/core/test_sources.py`.

Measured estimate: −175 lines. Half a day.

## Phase 5 — Fewer fields for the Director

Each item is one eval run (`run`, then `compare --baseline`). Land what holds the baseline; drop
what does not. Regenerate prompt goldens after each.

1. One id syntax: `name[id]`. Change `_label` and `_exit_line` in `turn/context.py` and the
   sentence in `turn/prompts/director.md` that says `name[id=...]`.
2. Delete `Thread.clock`, `AdvanceThread.tick`, `ThreadSummary.clock`, both `_thread_line`
   clock branches, the clock words in `world.py`'s `advance_thread` description. Hand-edit:
   remove `"clock": null` from every thread in `scenarios/*/world.json`.
3. Flatten `Entity.detail` into `Entity.description: str = ""` and `Entity.when_reached: str =
   ""`. Touch `_undetailed` (strip both), `_detail`, `_reached`, `_bar_unmet`, and the prompts
   `scenario_world.md`, `scenario_bar.md`, `scenario_opening.md`, `scenario_extend.md`,
   `director.md`. Hand-edit every entity in the three scenarios.
4. Dropped 2026-08-28: `Attempt.luck_test` stays. A riding luck test is one call for the
   Director; a second tool call is one more thing a weak model forgets.
5. `ThreadSummary`, `thread_summaries` and `_thread_line` are a UI projection of `Thread`; the
   panels read `Thread`. No eval needed.
6. Eval candidate: `Thread.stage`. The Director invents free slugs; `note` carries the same.
   Delete `AdvanceThread.stage`, the `_thread_line` stage branch, `_thread_card`'s stage part.

Measured estimate: −70 lines (5.5 −25, 5.6 −15). This phase is four prompt experiments, scored
in eval runs, not lines.

## Phase 6 — Dict-keyed world, creation through the decision panel

1. `WorldState.entities: dict[EntityId, Entity]`, `threads: dict[Slug, Thread]`. `Entity.id`
   stays; a `WorldState` validator checks `key == entity.id`. `exits` stays a list.
   Delete only the entity/thread `require_unique` calls and `find` scans (`require_unique` still
   guards traits, party, options, 24XX gear ids). Callers to update: `WorldState.find/require/
   of_kind/children/all_ids/thread`, `Game.add`, `frontier`, `_walk`, `_reachable_hidden`,
   `SceneSnapshot.from_game`, `begin_game`, `draft.py` `_index/_upsert/_drop/_require_location`,
   `extension_patch`, `apply_patch`, `ScenarioDraft.from_scenario/from_game/scenario`.
   Hand-edit: entities and threads become objects keyed by id in the three scenarios and in
   `characters/kael/base.json` items.
2. Character creation through the decision panel. `engine.creation_steps(picks)` yields steps of
   the same shape as `PendingDecision` (`prompt`, `options` or free text). A choose-N step
   becomes N single-choice steps. The character page is name + brief inputs plus the existing
   decision widget; delete the bespoke widgets in `ui/create.py` (the character half, ~275
   lines; the scenario pages stay). This is also the path to a new character on death (24XX
   deviation 1): a succession option "new character" starts the same loop. Once choose-N is N
   steps, delete `CreationStep.choose`/`repeats`, `TextStep.count`/`max_length`, and
   `_check_chosen`/`_check_written`: `check_picks` is "every step answered with a legal option
   or non-empty text".
3. `turn/context.py`: replace `placements`/`exit_names` dicts and `_placements/_placement` with
   one `placement(world, entity, nameable)` function; fold `BaseScene` into the two scenes.
4. `state/play.py`: delete `TraceEntryBase`, `WorldExtended`, the `TraceEntry` union and the
   `match` in `ui/panels.py`; the dev tab shows `TurnTrace` only. Growth logs a line.

Measured estimate: −275 lines; 6.2 alone is −205. 6.1 is ≈ −20 lines and is kept for the
key==id invariant and the end of O(n) scans, not for lines.

## Phase 7 — Optional cuts, each needs the maintainer's say

1. Refused 2026-08-28: player actions stay. The "You can" buttons are a player feature.
2. Refused 2026-08-28: live-turn streaming stays. Cards landing during the turn is the feel of
   the game.
3. Decided 2026-08-28: keep `claude.py`, `codex.py` and `external`; delete `opencode.py` and
   `pi.py` (both play through `external`). `Settings.harness` becomes
   `"builtin" | "external" | "claude" | "codex"`; drop the pi `limit=2**20` note in `exec.py`.
   −75 lines.
4. Decided 2026-08-28. Launcher: replace `LauncherController` and its four option models with
   `load_catalog` plus `launch_target(catalog, scenario_id, character_id)`. `codemode._target`
   uses the same function. A save that does not parse as `Game` is skipped with a log line,
   like `read_scenarios`: delete `SaveHeader`, `UnreadableSave`, `SaveOption.problem`,
   `_save_refusal`, `_short_reason` and the unreadable cards. `LauncherCatalog.badge` reads
   `runtime.engines[id].badge`. −125 lines.
5. Journal export (`journal_markdown`, `write_journal`, the export button): the journal tab
   already shows the chronicle. −24 lines.
6. Authoring `write` takes the whole draft; delete `ScenarioPatch`, `connect`, `patch_refusal`.
   Only after an authoring eval exists. −65 lines.

Refused 2026-08-28, do not re-propose: narration as one string (NPC bubbles stay), deleting
media (always played on), deleting the settings page, player actions, live streaming, card as a
string, per-scenario pack choice, the riding 24XX luck test, options-only stake.

## Phase 8 — Close the eval gaps

The Director is the bar a weak model must clear. After Phase 7 the code is as small as it gets;
what is left is the cases the model still fails. This phase is measurement first, then the
cheapest fix that closes each gap.

1. Measure: `uv run python evals/turn_eval.py run --label phase8-base --repeats 27 --concurrency
   27`. Nine repeats hide a 4-in-9 case behind the backend lottery (`swing-the-fire-axe` scored
   17% and 28% on the same code, same day). Twenty-seven gives the number a floor. Check the
   OpenRouter backend before reading any number (memory: eval-conditions-closure).
2. List every expectation under 90% with its failing runs' tool calls and refusals. At the
   Phase 6 baseline that is `breathless/swing-the-fire-axe` (axe-rolled 2/9, axe-in-hand 6/9),
   `breathless/mend-the-floodlight` (think-rolled 6/9), `breathless/no-improvised-brick`
   (shoot-rolled 8/9). Read the failing runs, not the score: a refusal, a missing call and a
   wrong argument are three different gaps.
3. Close each gap with the cheapest rung that holds, one gap per eval run, `--case <id>
   --repeats 27` first and the full run after:
   1. Instruction text: one sentence in the core or engine `director.md` (memory:
      load-bearing-director-lines lists the four lines that are already known to carry weight).
   2. Tool description: the `director_tool(description=...)` string.
   3. Field description: a `Field(description=...)` on the tool's args.
   4. Tool schema: a field's shape, a default, an enum. Schema size was the measured failure
      variable for weak models: a schema change must shrink or hold the size of
      `tests/core/fixtures/schemas/*/director_tools.json`.
   5. Refusal text: what `ModelRetry` says back. A refusal the model recovers from on the next
      call is a closed gap at one extra call.
   6. A resolver rule: the engine does what the model forgot (a `take` folded into an item roll,
      say). Only where the SRD allows it and only after 1–5 lost.
4. A rung is kept only when the case moves and the full run holds at or above the baseline
   (score, errors, and `director_calls`). Regenerate prompt and schema goldens after each kept
   rung and read the diff.
5. Stop when every expectation is at or above 90% over 27 repeats, or when the remaining gap has
   lost all six rungs; then record it in the case as a known limit with the rung that came
   closest.

Reasonably closed means 90%, not 100%: below that, the backend lottery owns the number.

## Deviations

- Loner 2 (unauthored characters get a blank sheet) widens to authored actors in phase 1; the
  doc is updated, the rule is unchanged.
- 24XX 1 (new character on death): phase 6.2 provides the loop; the feature is a succession
  option plus `take_over`.
- Breathless "Before We Start": a `Scenario.content_note` text field shown at game start. Any
  time.
- Loner 3 (twist timing) is inherent to Director → Narrator and stays documented.

Delete this file after phase 8. The git log is the record.
