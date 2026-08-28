# Drastic simplification plan

Goal: the core stops being an RPG framework. An engine is a folder with state models, one tool per
SRD procedure, and a `director.md`. Adding engine #4 touches nothing outside `engines/<id>/`.

Line counts below are estimates. The bar is the one already in use: smaller, or break-even but
more maintainable, measured after the phase lands. Re-measured on 2026-08-28 after Phase 1:
phases 1–6 sum to about −780 lines, not −1650.

## Rules for every phase

1. Work on a branch per phase. Commit in small steps; every commit passes `uv run ruff check`,
   `uv run ruff format --check`, `uv run basedpyright`, `uv run pytest`.
2. Golden fixtures: run `AIDM_GOLDEN_REGEN=1 uv run pytest` once at the end of the phase, then
   read `git diff tests/core/fixtures` line by line. A diff you cannot explain is a bug.
3. Eval gate: `uv run python evals/turn_eval.py run` then `compare --baseline <previous>`. Ship at
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

Measured 2026-08-28: −30 lines as written; the deletion was counted but not the rebuild. Extra
cuts landed the same day: Game.mechanics deleted (twist on the Loner sheet), Advancement ABC
collapsed, 24XX _check_skills gone, check_sheet folded into rules(), describe overrides folded
into Engine.describe.

## Phase 2 — Cards are one string, not a struct

Every resolver writes a trace and a `MechanicEvent(title, badges, dice, outcome, effects, icon)`.
The struct is half the resolver. The leak guarantee stays: a card is engine text, never Director
text.

1. First, in its own commit: rewrite `evals/turn_eval.py` to read the new shape (it reads
   `fact.event.outcome`, `fact.event.badges`, `history[0].events` today). The eval must run
   before and after the phase.
2. `Fact(kind, trace, told, entity_id, card: str = "", dice: tuple[DiceEvent, ...] = ())`.
   A non-empty `card` is the player's line. `trace` is the Director's line and may name canon;
   it never reaches the player. Delete `MechanicEvent`, `EventBadge`, `explained_fact`'s event,
   `player_events`, `_absorbed`, every `_badges`.
3. Each resolver writes the card as one f-string: `card=f"Attempt: {outcome} — {skill} d{face}"`.
   Dice ride on the same fact.
4. `Exchange.events` → `Exchange.cards: tuple[Fact, ...]` (told facts with a card).
   `Game.turn_events` same. Callers: `Game.record`, `close_segment`, `play_action`,
   `TurnRecord.landed`, `ui/game.py` chat and live turn, `codemode._picture`.
5. `ui/game.py::_mechanic_event` renders card text + dice. Icons go.
6. Delete `tests/core/test_player_events.py`. Regenerate goldens.

Measured estimate: −85 lines (the struct is 12 lines; 33 build sites ≈ 53 lines). Worst
lines-per-risk in the plan: every card is player-facing text. Optional; do only if card-as-string
is wanted for its own sake.

## Phase 3 — Flat tool ladder, engine as a value

Order matters: 3.1 removes the only reader of `DirectorContext.answered`, so it comes first.

1. Options-only decisions. `PendingDecision.allows_text: bool`. Defence, Loot and stake-proceed
   are options-only. `consume_answer` raises on `Answer(text=...)` when `allows_text` is false;
   `ui/game.py` disables the composer then; `codemode.start_turn` gets the same refusal. Delete
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

Measured estimate: −80 lines (3.2 ≈ −25, 3.5 ≈ −40, 3.6 −8). Half a day.

## Phase 4 — Packs are engine-shipped creation menus, nothing more

Decided: keep the user directory `packs/<engine>/` (one glob). Delete every scenario-level pack
concept.

1. Each engine constructor loads `{stem: Pack}` from `engine_dir / "packs"` then
   `settings.packs_dir / engine.id` (later wins). Delete `engines/sources.py` and
   `engines/packs.py`; `pack_options`, `find_entry`, `picked_entry`, `PackCreation` move next to
   their callers (two engines use `pack_options` → core).
2. Delete `Scenario.packs`, `SheetBase.packs`, `character_packs`, the `check_scenario` pack
   checks, the `validate` installed-pack checks, 24XX `_check_skills` (already deleted in Phase
   1's extra cuts; the SRD leaves skills open). `_packs_include_srd` is on `SheetBase` in core.
   Loner keeps `twist_pack`; `meanings` reads every installed pack.
3. Delete `write_pack`, `pack_refusal`, `PlaytestCheck.shipping`, `PlaytestCheck.sources`,
   `ScenarioDraft.packs`, `engine_packs`, `installed_pack_ids`, `selected_packs`,
   `scenario_packs`, `AuthoringBrief.writes_packs`, `BeginScenario.packs`, the pack multiselect
   on both authoring pages, the "SELECTED PACK CONTENT" dump and workflow step 4 in
   `scenario_world.md`. Update the 24XX `authoring_instructions` string (it points at pack skill
   names). Grep `packs` under `.claude/skills/` and fix the skills too.
4. Also delete the "How much to author" select: `scenario_run` derives the brief from `grows`.
   Delete `AuthoringBrief.label`, `BRIEFS`, `brief_named`.
5. `Runtime.engine(engine_id)`: one instance per engine. Callers: `runtime.py`, `create.py`,
   `draft.py`.
6. Hand-edit: remove `"packs"` from `characters/kael/*.json` and from every `rules` in
   `scenarios/*/world.json`; remove `"packs"` from each `world.json` top level. Delete
   `tests/core/test_sources.py`.

Measured estimate: −230 lines; the authoring side is the real win. Half a day.

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
4. Delete `Attempt.luck_test` (24XX): `roll_luck_test` is the one place. Remove the riding path
   in `resolve_attempt` and the two `director.md` sentences about it.

Measured estimate: −46 lines. This phase is four prompt experiments, scored in eval runs, not
lines.

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
   deviation 1): a succession option "new character" starts the same loop.
3. `turn/context.py`: replace `placements`/`exit_names` dicts and `_placements/_placement` with
   one `placement(world, entity, nameable)` function; fold `BaseScene` into the two scenes.
4. `state/play.py`: delete `TraceEntryBase`, `WorldExtended`, the `TraceEntry` union and the
   `match` in `ui/panels.py`; the dev tab shows `TurnTrace` only. Growth logs a line.

Measured estimate: −250 lines; 6.2 alone is −180. 6.1 is ≈ −20 lines and is kept for the
key==id invariant and the end of O(n) scans, not for lines.

## Phase 7 — Optional cuts, each needs the maintainer's say

1. Player actions. `Offer`, `PlayerAction`, `player_action`, `offered`, `play_action`, the
   Breathless `breathers`/`med_kit_holders`, the "You can" panel, the MCP `player_action` tool.
   `use_med_kit` is already both a Director tool and a player action. Make `catch_breath` a
   Director tool the player asks for, delete the rest. −105 lines. Shipped in 7d9afeb, so this
   reverses a recent decision.
2. Live-turn streaming: `TurnRecord.on_event`, `on_step`/`on_event` plumbing, `_STEP_COPY`,
   `live_turn`, `_inline_status`, `_clock`, `tick_elapsed`, `GameView.live_*`. One spinner with the
   step name. Keep `Game.turn_events` for the external viewer. −110 lines.
3. One `ExecDriver` with `HARNESS_COMMAND` in `.env`; the dev log shows raw lines. Delete
   `codex.py`, `opencode.py`, `pi.py`. Keep `claude.py`. `Settings.harness` becomes
   `"builtin" | "external" | "claude" | "exec"`. −125 lines.
4. Launcher: replace `LauncherController` and its four option models with `load_catalog` plus
   `launch_target(catalog, scenario_id, character_id)`. `codemode._target` uses the same
   function. −80 lines.
5. Journal export (`journal_markdown`, `write_journal`, the export button): the journal tab
   already shows the chronicle. −24 lines.
6. Authoring `write` takes the whole draft; delete `ScenarioPatch`, `connect`, `patch_refusal`.
   Only after an authoring eval exists. −65 lines.

## Deviations

- Loner 2 (unauthored characters get a blank sheet) widens to authored actors in phase 1; the
  doc is updated, the rule is unchanged.
- 24XX 1 (new character on death): phase 6.2 provides the loop; the feature is a succession
  option plus `take_over`.
- Breathless "Before We Start": a `Scenario.content_note` text field shown at game start. Any
  time.
- Loner 3 (twist timing) is inherent to Director → Narrator and stays documented.

Delete this file after phase 6 (or 7). The git log is the record.
