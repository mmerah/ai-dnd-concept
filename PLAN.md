# PLAN: simplification

Three phases fold the fifteen accepted simplification proposals into the code: fewer concepts
(a pack list is never optional, one word per thing, one home per model-facing string), less
machinery (the pack editor's private text format, the `G` type parameter, the launcher's second
resume rule, a third of the test suite), and the code rules written as the code lives them.
Every step below was implemented once by a subagent in a throwaway worktree with the four checks
green, then the plan was reviewed adversarially once; the shapes, the gotchas and the numbers
come from those runs and that review, not from estimates.

Decided on 2026-09-17 and not re-opened by any phase:

- `packs` is a required `tuple[Slug, ...]` on every model and every engine ships an SRD pack; the
  `PackSelection` class goes. Pack choice is one select on both create pages, not a `multiple`
  creation step. The pack editor shows one JSON box per pack field; the worldsmith's ask models
  (`PackHead`/`PackBody` and the engine `*Head`/`*Body`) stay as they are.
- `Engine[P, M, W, K]`: the world type is the parameter; `world_of` is concrete in the base.
  The room family stays, with one rule: no new room-only hook until a second room engine lands.
- Kept for structure, not size, measured at about +70 lines together: the meanwhile clock on the
  world with the tool resolving ids; `Gate` + `Busy` + `check_resumes` in the app; one home per
  model-facing string; the `ui/transcript.py` split.
- Dropped after measuring: lifting `narrator_view`/`player_view`/`author` into `Engine` (+36 and a
  room-page panel move); `Game.close`/`open_chapter` and a base `kill` skeleton (+16); a
  `Presentation` object and a shared `_tell` in `GameService` (+35 each to absorb 20); deleting
  `GameService.speaking` (three lines of property for five of test helper); a
  `GameService.version` counter (needs a `step()` method and loses the partial refresh); static
  media mounts (needs a root table and a startup `mkdir`); lambdas for every two-line tool method
  (+6 at 100 columns); dropping a decode pass in `restore` (all three guard something pinned);
  folding `PackStore` into `PackSet` (a wash that puts a file write in `engines`); `PackSet.
  installed` as a property (a built collection is a method, and every reader wants an attribute);
  the hire flag and its raising `write_sheet` default stay.

Measured before any step, at `951ceb9`: `src` **10,904** Python lines, `tests` **12,403**, `qa`
**2,005**, `scripts` **390**, 795 tests collected. Targets below are sums of the measured runs,
corrected for what each phase actually contains. A phase whose target is beyond ±100 lines and
lands outside it by more than 20% stops and says why; a target within ±30 of zero is judged by
the full check alone.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the phases in order and the parts of a phase in the order the phase states. Every part is
   one implementer's work on the files it names; parts that share a file run one after the other.
   Each step is one action. Symbol names are as of `951ceb9`; where an earlier step renamed or
   moved one, follow the name the earlier step gave it.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted
   behaviour is deleted with it. A golden is regenerated only when the step says so, with
   `AIDM_GOLDEN_REGEN=1 uv run pytest`, and the phase names which files moved. The type checker
   does not see a keyword inside a dict literal or a `tool_call(...)` helper; the test run does,
   so a rename is done only when pytest is green, not when basedpyright is.
3. Count lines at the start and the end of each phase and write both in `PROGRESS.md`, one entry
   per phase, with the decisions taken off-plan and the review findings refuted and why:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   find scripts -name '*.py' | xargs cat | wc -l
   ```
4. Every phase commits once, as one, after the full check.

## Phase 1: engines and packs

Parts A, B, C, one after the other: all three touch `engines/seam.py`. Target: `src` about
−395 (10,904 → about 10,510), `tests` about −140, content +10, one prompt golden, 783 tests
collected.

### Part A: the seam

1. **`G` becomes `W`.** In `engines/seam.py`: `class Engine[P: Person, M: Person,
   W: World[Any, Any], K: Pack]`, class attributes `world: type[W]` and `game: type[Game[W]]`
   (the families' own `world: type[SceneWorld[C]]` / `world: type[RoomWorld[P, N]]` declarations
   go), and one concrete `def world_of(self, state: Game[W]) -> W: return state.payload`. Every
   `G` in the file becomes `Game[W]` (`MasterTool[Game[W]]`, `Request[Game[W]]`, `begin` returns
   `Game[W]`). `engines/scenes/engine.py`: `class SceneEngine[C: Person, W: SceneWorld[Any],
   K: Pack](Engine[C, C, W, K])`; `engines/rooms/engine.py`: `class RoomEngine[P: Person,
   N: Dweller, W: RoomWorld[Any, Any], K: Pack](Engine[P, N, W, K])`. Delete the five `world_of`
   overrides (two families, three engines). The `Loner3eGame = Game[Loner3eWorld]` aliases stay.
   Tests: `tests/support/fifth.py` and `sixth.py` subclass `Game[...]`; make them aliases
   (`FifthGame = Game[FifthState]`), because `Game[W]` is not assignable to a subclass.
   `tests/app/test_master_tools.py` passes `lambda built: engine.begin(...)` where a
   `Callable[[AnyScenario], None]` is wanted; it typechecked only because `begin` returned `Any`.
   Make it a three-line `def`.
2. **The meanwhile clock lives on the world.** `engines/base.py`: `World.tempo: ClassVar[int]`
   (no default) and `World.tick(*, counted: bool) -> None` replacing `count_turn(tempo)` (count,
   and at the tempo start over and arm `meanwhile_due`). `scenes/world.py`: `SceneWorld.tempo =
   6`. `tunnelgoons/world.py`: `TunnelGoonsWorld.tempo = 4`. `rooms/world.py`: `RoomWorld.tick`
   overrides: return without counting when not armed and `can_move_offscreen()` is false; after
   `super().tick`, if it was armed and `counted`, `disarm()`. `engines/seam.py`: delete
   `meanwhile_turns`; `Engine.tick(draft, *, counted)` is `self.world_of(draft).tick(counted=
   counted)`; keep `Engine.disarm`; the tempo floor check in `Engine.__init__` reads `self.world.
   tempo` (so a world that forgot its tempo fails at engine construction, not at the first tick).
   Delete `RoomEngine.tick` and `TunnelGoonsEngine.meanwhile_turns`. Tests: `tests/support/
   sixth.py` sets `tempo = 6`; in `tests/engines/test_seam.py`, `test_the_tempo_floor_refuses_a
   _tempo_below_two` subclasses the engine with `meanwhile_turns = 1` and must instead subclass
   `FifthState` with `tempo = 1` and point an engine subclass's `world` at it; `test_the_clock_
   arms_on_reaching_the_tempo_and_starts_over` reads `scene_engine.meanwhile_turns` twice and
   reads `FifthState.tempo` instead.
3. **The tool resolves the ids; the world changes fields.** `rooms/tools.py` gains
   `NOTHING_OFFSCREEN`, `MOVES_OFFSCREEN`, `MOVED_CARD` from `rooms/world.py` now (phase 2 would
   otherwise move them and make the world import the tools again). `rooms/world.py`: replace
   `RoomWorld.meanwhile(args: Meanwhile)` with `walk_offscreen(npc: N, place: Place) -> Fact`
   (keeps the "stands with the player; that is not offscreen" refusal and the unlocked-way
   check), `drift_item(item: Prop, place: Place) -> Fact`, `shut_way(start: Place, end: Place)
   -> Fact`, and `spend_meanwhile() -> None` which only `disarm()`s; `_offscreen_place` becomes
   public `offscreen_place`. Each keeps its refusals in the order the tests expect (resolve the
   destination before the state check that follows it). `rooms/engine.py`: `RoomEngine.
   meanwhile(self, draft, args: Meanwhile, _rng) -> list[Fact]` refuses `NOTHING_OFFSCREEN` when
   not `meanwhile_due`, resolves the three pairs (`npcs.get` → `UNKNOWN_ID`, then `IS_DEAD`;
   `items.get` → `UNKNOWN_ID`, then "is here with the player"; `require_place` twice), calls the
   three world methods, appends `Fact(trace=MOVES_OFFSCREEN, told=True, card=MOVED_CARD)` and
   calls `spend_meanwhile()`. `rooms/world.py` no longer imports `rooms/tools.py`. Tests: every
   refusal in `tests/engines/test_rooms.py` passes unchanged.
4. **`World.leave_party` is concrete; the proposals are frozen.** `engines/base.py`: delete the
   abstract `leave_party`; add a concrete one below the abstract block: `member =
   self.member_of(entity_id)`, refuse `UNKNOWN_ID` when `None`, `return self.part(member)`.
   Delete `SceneWorld.leave_party` and `RoomWorld.leave_party`. `scenes/tools.py`:
   `SceneDraft(Frozen)`, `NextDraft` follows. No test pins the changed refusal (scenes
   `leave_party("player")` now says unknown id).
5. **`Game.source`.** `core/model.py`: `Game.source: str = ""`. `engines/seam.py`: `begin` fills
   it from `scenario.source`; `render_request` reads `draft.source` and drops its `world` local.
   `engines/base.py`: delete `World.source`. Both `opening` classmethods (`scenes/world.py`,
   `rooms/world.py`) lose the `source` parameter; both `new_game` calls follow. Tests: three
   one-line reads become `state.source` (`tests/app/test_launcher.py` ×2,
   `tests/loner3e/test_prompt_budget.py`); `tests/tunnelgoons/test_world.py` calls
   `TunnelGoonsWorld.opening` directly and loses the argument. No golden moves.
6. **Small cuts on the seam and the engines.** `Engine.tool(name) -> MasterTool[Game[W]]` with
   one refusal, `f"{name!r} is not a tool of the {self.id!r} engine."`, used by `Engine.answer`
   and `Turn.call`; `tests/turn/test_decisions.py` pins the old "no tool ... to play option"
   message and follows. `Loner3eEngine.__init__` computes `self.twists` once; `twist_table()`
   goes. `items_from_kits` builds `Gear(**kit.model_dump())`. `CrewSheet.gear_text(*, ids: bool
   = False) -> str` shared by `Crewmate.carried()` (`ids=True`), `TwentyfourxxWorld.sheet_rows()`
   and `preview_character` (names, each followed by its `notes()` in parentheses where
   non-empty); `tests/twentyfourxx/test_create.py::test_preview_character_ends_with_gear_row`
   pins the three bare names and follows that rule. `GoonSheet.rows(*, carried: int | None =
   None)` so `TunnelGoonsWorld.sheet_rows` passes the count instead of patching the Inventory row
   by label; `Adventurer.rows` and `Npc.rows` carry the keyword through. Docstrings:
   `PendingOption` ("not every name is a tool" is false: `Engine.answer` refuses any non-tool);
   `Game.generation` (`exclude=True`, so `restore`'s refusal fires only on a hand-edited file).

### Part B: packs are never optional, and one pack select

7. **The Tunnel Goons SRD pack.** Create `src/aidm/engines/tunnelgoons/packs/srd.json`: `name`
   `"Tunnel Goons SRD"`, `source` `"https://tunnelgoons.com/"`, `license` `"Tunnel Goons is ©
   Nate Treme (Highland Paranormal Society), CC BY 4.0."`, `items` = the eighteen names of
   `STARTING_ITEM_LIST` (`tunnelgoons/engine.py`), every other field empty. Change the
   `.gitignore` line `packs/` to `/packs/` (it hides `src/aidm/engines/*/packs/` too; the two
   existing pack directories only predate the rule). Delete `STARTING_ITEM_LIST`; the create
   page's item hint reads `pack.items` from the chosen packs, as it already does for supplements.
   `tests/support/sixth.py` gets a `packs/srd.json` beside its `rules.md`, as `fifth.py` has.
8. **`packs: tuple[Slug, ...]`, required.** `core/model.py`: delete `PackSelection`; `packs:
   tuple[Slug, ...]` with no default on `Scenario`, `Character`, `Game`, `CharacterHeader` (a
   file without it is refused at the boundary; a character file without it is skipped with the
   launcher's warning). `engines/packs.py`: `PackSet.select(ids: Sequence[Slug]) -> tuple[Slug,
   ...]` runs `check_unique("selected pack ids", ids)`, the installed check, the two-supplement
   cap and the defined-id overlap; `chosen`, `guidance`, `rules_sections`, `seeds` take a tuple
   and lose their `None` branch; delete `require`; `check_addable` selects `(SRD_PACK, pack_id)`
   unconditionally. `engines/seam.py`: `pack_ids` prepends `SRD_PACK` for every engine;
   `select_packs(supplements) -> tuple[Slug, ...]`; `admit` compares sets with no unwrapping;
   `guidance(selection, *, opening)` takes a tuple; `Engine.__init__` calls `self.packs.srd()`
   (an engine that ships no SRD pack is a bug); `validate` keeps one pack check, `if SRD_PACK
   not in state.packs: raise Refusal(f"a {self.id!r} game plays the {SRD_PACK!r} tables")`, and
   the `self.packs.select(state.packs)` overlap scan moves out of `validate` (it ran on every
   tool call) into `begin` (after `admit`, before `parse(self.game, ...)`) and `restore` (after
   `validate`). Delete the four `SceneEngine` overrides (`pack_ids`, `validate`, `guidance`,
   `admit`) and its `__init__`. `app/launch.py`: `packs=header.packs`. Content: `"packs": {"ids":
   [...]}` → `"packs": [...]` in `scenarios/*/world.json` (three) and `characters/kael/*.json`
   (three; `buried-keep` and the Tunnel Goons character gain `["srd"]`). Tests, seventeen files
   in the measured run; the sites the type checker does not see: raw `{"ids": [...]}` literals in
   `tests/engines/test_integrity_boundaries.py` and `tests/app/test_launcher.py`; `tests/
   tunnelgoons/test_engine.py` builds a `PackSet` without an SRD (add `SRD_PACK: engine.packs.
   srd()`) and asserts `state.packs is None` twice (now `== ("srd",)`). `test_select_refuses_a_
   selection_without_the_srd` moves to `tests/engines/test_seam.py` parametrized over
   `ENGINE_IDS` and matches the base message; `tests/engines/test_scene_bar.py::test_a_
   scenario_with_no_packs_is_refused_by_check_packs` uses `packs=()` instead of `None` and
   matches the base message. Three tests that called `validate` directly for the overlap rule go
   through `restore`. Golden: `tests/core/fixtures/prompts/tunnelgoons/worldsmith.txt` gains a
   `PACK: Tunnel Goons SRD` block; regenerate it and nothing else.
9. **One pack select.** `core/creation.py`: delete `MANY`, `picked_many`, `CreationStep.multiple`
   and the `multiple` branch of `check_picks`; `tests/core/test_creation.py` loses its three
   `multiple` tests and keeps the single-answer rule. `engines/seam.py`: `creation_steps(packs:
   tuple[Slug, ...], picks)`, `create_character(name, brief, packs, picks)`, `build_character
   (name, brief, packs, picks)`; delete `supplement_steps`, `picked_packs`, `chosen_packs`,
   `SUPPLEMENTS`, `SUPPLEMENTS_LABEL`; engines read `self.packs.chosen(packs)` where they read
   `chosen_packs(picks)`, and `sheet_character(name, sheet, packs)`. `ui/create.py`: one
   `_packs_select(offered: Iterable[DecisionOption], chosen: Iterable[Slug], on_change)` (the UI
   may not import `aidm.engines`, so it takes options, not an engine) used by `CharacterForm`
   and `ScenarioForm`, and one `_selected_packs(runtime, engine_id, picked) -> tuple[Slug, ...]
   | None` that calls `select_packs`, alerts on a `Refusal` and returns `None` (the two-pack cap
   is reachable from the page: Loner offers twelve); both forms hold `self.packs` and leave it
   alone on `None` (`if (packs := ...) is not None: self.packs = packs`).
   `ScenarioForm.follow_character_id` also sets `self.packs = engine.select_packs(chosen)`.
   Delete `choose_many` and the `multiple` branch of `_drop_stale`. Tests: every
   `create_character` call site gains `packs` (`tests/loner3e/test_create.py`,
   `tests/twentyfourxx/test_create.py`, `tests/tunnelgoons/test_engine.py`, `tests/engines/
   conftest.py`, `tests/twentyfourxx/test_tools.py`, `tests/ui/test_create.py`, `tests/support/
   fifth.py`, `sixth.py`).

### Part C: the pack editor reads and writes JSON

10. **One JSON box per pack field.** `engines/packs.py`: `Pack.boxes() -> dict[str, str]` (a
    method: it builds a collection) mapping every field of `model_dump(mode="json")` except
    `name`, `source`, `license` to `json.dumps(value, indent=2, ensure_ascii=False)`.
    `engines/seam.py`: `Engine.edited(pack, values: Mapping[str, str]) -> K` decodes each box
    with `decode`, lays it over `pack.model_dump(mode="json")`, and re-parses through
    `json.dumps` + `parse_json(self.pack, ...)` (strict mode reaches tuple fields only from JSON;
    `parse(model, dict)` rejects the lists `model_dump` produces). Delete `EditField`,
    `PROSE_ROWS`/`NAME_ROWS`/`LIST_ROWS`, `NAME_LABELS`, `Pack.head_fields`/`body_fields`,
    `table_text`, `parse_table`, `parse_list`, `blocks_text`, `parse_blocks`, `block_fields`,
    `block_values`, `head_values`, `body_values`, `_blocks`, `_block_text`, `_printed`,
    `_field_value`, `_key_label`, `Engine.edit_fields`/`engine_fields`/`engine_values`,
    `_asked`, and the three engines' `engine_fields`/`engine_values` plus `Loner3eEngine.edited`.
    `DASH` and `SEPARATOR` stay: `Labelled` and `Names` validate with them and `Pack.sections`
    renders with them. `ui/packs.py`: one monospace textarea per box, `rows=12`, labelled by
    `_label(field_id) = field_id.replace("_", " ").capitalize()`. `Runtime.rewrite_pack` is
    unchanged but for the call. Tests: delete `tests/engines/test_pack_text.py` (the thirteen
    codec tests); in `tests/app/test_pack_editing.py` the two edit tests write JSON
    (`json.dumps(SETTING)`; the collision test writes an explicit `{"id": "quiet-hands", ...}`,
    because ids are now edited directly, not re-minted from labels) and one new test edits one
    field, saves, builds a second `Runtime` over the same directory and asserts every other
    field comes back unchanged.

Done when: the full check is green; `uv run aidm` opens a Tunnel Goons game and the home page
lists the Tunnel Goons SRD pack read-only; a written pack opens as JSON boxes and saves; the
counts land in the target.

## Phase 2: names and homes

Parts A then B: both touch every `tools.py` and `worldsmith.py`. Target: `src` about −5,
`tests` about +13, three schema goldens, two `rules.md`, CLAUDE.md +3. Judged by the full check.

### Part A: one home per model-facing string

1. **Per family and engine.** Move every model-facing constant to `worldsmith.py` (what the
   worldsmith reads) or `tools.py` (what the master reads: tool descriptions, and the `Fact`
   traces that are instructions); nothing model-facing stays in `world.py` or `engine.py` except
   the three `*_UNWRITTEN` facts and the two page actions (`MOVE_ON`, `MORE_MAP`), which are
   player-facing and stay where they are. `scenes/engine.py` → `OPENING`, `MEANWHILE_NUDGE` to
   `scenes/worldsmith.py`, `MOVING_ON` to `scenes/tools.py`; `scenes/world.py` → `WAY_OFFERED`,
   `SCENE_LEFT` to `scenes/tools.py`; `rooms/engine.py` → `ELSEWHERE` to `rooms/tools.py` (the
   three room strings phase 1 step 3 moved are already there); `loner3e/engine.py` →
   `TWIST_NOTE`, `DEFEAT_NOTE` to `loner3e/tools.py`; `engines/tools.py` → `DROP_ITEM`,
   `DropItem`, `AskWorld` to `twentyfourxx/tools.py` (`ACTOR` stays: Tunnel Goons reads it).
   Text unchanged; no golden moves. Tests importing a moved name follow: `tests/engines/
   test_rooms.py`, `tests/loner3e/test_engine.py`, `tests/twentyfourxx/test_tools.py`.
2. **App: the roles own the role logic.** `app/roles.py` gains `OPENING_NARRATION` (from
   `runtime.py`), `ask`, `RETRIES`, `worldsmith` (from `spawn.py`). `core/tools.py` gains the
   `Tools` protocol (it is a protocol over `MasterTool[AnyGame]`; `builtin.py` imports from
   `spawn.py`, so `RoleRunner` cannot move into `spawn.py` while `spawn.py` needs `builtin`
   unless `Tools` sits below both). `app/spawn.py`: the `Driver` and `Spawner` protocols move to
   the top, before the classes; `RoleRunner` moves here beside `Spawner`, split in two:
   `run(role, prompt, session, tools)` owns `started = monotonic()`, the one `async with
   timeout(config.timeout)`, the one `Refusal(f"the {role} answered nothing in {config.timeout:
   .0f}s")` and the one info log line (`"%s answered: provider=%s model=%s effort=%s %s in
   %.1fs"` with a detail string, "cold" / "resumed" / "over N rounds"); `_answered(role, config,
   prompt, session, tools) -> tuple[RunResult, str]` is the provider `match`, wrapping
   `run_builtin`'s text with `final_message`. `run_cli` returns `(RunResult, detail)` with no
   timeout of its own (`_spawn`'s `finally: await _kill(process)` still kills a cancelled spawn);
   `run_builtin` returns `(text, detail)`; `builtin.py` loses its `LOGGER`. `master.md` and
   `render_master` stay in `turn/`. Tests: `Tools` is imported from `core.tools` in `tests/app/
   test_mcp.py`, `test_roles.py`, `test_spawn.py`, `tests/support/table.py`, `qa/agents.py`;
   `RoleRunner` from `spawn` in `tests/app/test_master_tools.py`, `test_builtin.py`; `ask` from
   `roles` in `tests/app/test_spawn.py`; `test_the_whole_run_is_held_to_the_roles_timeout` still
   drives the builtin path.

### Part B: one word per thing

3. **Proposals, not drafts.** Rename the worldsmith's answer classes: `SceneDraft` →
   `SceneProposal`, `NextDraft` → `NextProposal`, `MapDraft` → `MapProposal`, `RegionDraft` →
   `RegionProposal`, `SheetDraft` → `SheetProposal`, `AbilitiesDraft` → `AbilitiesProposal`,
   `SpecialtyDraft` → `SpecialtyProposal`, `OriginDraft` → `OriginProposal` (about 25 files; no
   class name reaches a prompt or a file). `SceneProposal`/`NextProposal` move from
   `scenes/tools.py` to `scenes/world.py`, where `rooms/world.py` keeps `MapProposal`.
4. **One vocabulary for tool arguments.** Tool argument models only (a `World` lookup keeps
   `entity_id`, about 90 sites; a saved field such as `Way.to` keeps its name). Who acts →
   `actor_id`: Loner `ChangeTags`, `Drive`, `RestoreLuck`, `SpendLuck`; 24XX `TakeLead`. Who is
   acted on → `target_id`: seam `Reveal`, `Kill`, `JoinParty`, `LeaveParty`, `Hire`; scenes
   `Enter`, `Leave`; Loner `Roll.opponent_id`; Tunnel Goons `Roll.against`. Destination →
   `to_id`: `MoveItem.to`. `_id` on every id field: `Meanwhile.dweller_to_id`, `item_to_id`,
   `shut_from_id`, `shut_to_id`; Tunnel Goons `Roll.item_ids`; 24XX `Staked`/`Helper`
   `defend_with_id` (and `check_risk`'s keyword). Update `loner3e/rules.md` (`opponent_id` ×3),
   `twentyfourxx/rules.md` (`defend_with` ×3), and the `Roll.difficulty` description ("Null when
   `against` is set"). The 24XX `take_lead` `PendingOption` is built as a dict in
   `twentyfourxx/engine.py` and only a play test catches its key. Tests and `qa/`: about 73
   lines build calls as `tool_call("reveal", entity_id=...)` or dicts; the test run finds them,
   the type checker does not. Regenerate the three `tests/core/fixtures/schemas/*/
   master_tools.json`; the prompt and turn goldens do not move.
5. **Methods and rules.** CLAUDE.md, under "Code", replacing the `property` rule: "A property is a
   scalar, or a one-line reading of the object's own fields; anything that renders a block,
   joins other objects or builds a collection is a method." Make the code true to it: `line()` a
   method on `Loner3eBlock`, `TunnelGoonsBlock`, `TwentyfourxxBlock`; `Pack.counts()`,
   `Names.listed()`, `Exchange.narration()`, `Exchange.transcript()`, `RoomWorld.holders_here()`
   become methods with their call sites (`Pack.summary`, the three `counts` overrides, the
   `Names` validator, `Pack.sections`, `core/prompt.py`, `runtime.py`, `rooms/world.py`);
   `Thing.tag`/`mention`/`headline`, `Subject.headline`, `SpokenLine.said`, `Pack.summary`,
   `Rolled.*`, `Gauge.shortfall` are one-line reads and stay. `Gear.broken_message`/
   `harmless_message` become module constants `ALREADY_BROKEN`/`BREAKS_HARMLESSLY` formatted at
   the raise sites. `Thing.headline` returns `self.subject().headline`. `core/io.py`:
   `parse_unique` → `parse_text`, with one docstring line: the entry for our own files and model
   answers; a caller that already decoded uses `parse_json`. `Engine.pack_of(..., origin=...)`
   (the on-disk field stays `source`). `GameService.interject` → `let_party_speak`. CLAUDE.md,
   replacing the `id`/`label`/`detail` rule (the plan's own wording; the code already lives it):
   "`id`, `label`, `detail` for a pick, an option or a panel row, on disk too; `name` and `brief`
   for an entity; `title` for a scene, a scenario, an engine. Tool arguments: `actor_id` for who
   acts, `target_id` for who is acted on, `to_id` for a destination, `_id` on every id."

Done when: the full check is green; `grep -rn "Draft" src/aidm` finds no worldsmith answer
class; the only model-facing strings left in an `engine.py` or `world.py` under
`src/aidm/engines` are the three `*_UNWRITTEN` facts; the counts land in the target.

## Phase 3: app, UI and tests

Parts A, B, C, one after the other: A and B share `ui/game.py`; B and C share `tests/ui`.
Target: `src` about +25 (9d +17, UI trims +24, `Panel.portrait` +1, small cuts −17; judged by
the full check), `tests` about −395, `scripts` −390, `tests/fixtures` −420, 756 tests collected.

### Part A: the app

1. **`Gate` and `Busy`.** `app/runtime.py`: `class Busy(Refusal)` with `def __init__(self, *,
   elsewhere: bool): super().__init__(IN_FLIGHT_ELSEWHERE if elsewhere else IN_FLIGHT_HERE);
   self.elsewhere = elsewhere` (the two constants keep their names: `tests/app/
   test_game_service.py` matches the text); `@dataclass(slots=True) class Gate` with `admitted:
   GameService | None`, `turn` property, `require_turn()`, and the `admit(session)` context
   manager raising `Busy(elsewhere=self.admitted is not session)`. `Runtime.gate: Gate =
   field(default_factory=Gate)`; `Runtime.turn`, `require_turn`, `admit`, `admitted` go.
   `GameService.gate: Gate`. `app/mcp.py`: `endpoint(gate: Gate)`; the module no longer imports
   `Runtime`; `ui/app.py` and `tests/app/test_mcp.py` pass `runtime.gate`. `ui/game.py`: `except
   Busy as busy: if busy.elsewhere: alert(str(busy))` in `_run`, `except Busy: blocked = True` in
   `_opened`; the string compares go. `Runtime(settings, spawner: InitVar[Spawner | None] =
   None)` with the stored attribute `roles` (`self.roles = spawner or RoleRunner(settings)`);
   `GameService.spawner` stays and its three `self.spawner` reads inside `GameService` are not
   rewritten; the fourteen `Runtime(settings, lambda _: ...)` call sites in eight files, `qa/
   server.py` included (keep its comment about surviving a reload), become `spawner=...`.
   `GameService.speaking` stays. Delete `ScriptedSpawner.resumed` (`tests/support/table.py`).
   `Tasks.settled` stays with one docstring line saying it is the test hook. `qa/agents.py` and
   `tests/support/table.py` reach `require_turn` through `.gate`; two UI tests raise
   `Busy(elsewhere=...)`.
2. **One resume rule.** `app/launch.py`: `check_resumes(state: AnyGame, target: LaunchTarget,
   meta: ScenarioMeta) -> None` (ids match, `check_drift`), called by `_save_option` (which keeps
   its "filed under another name" slug rule) and by `Runtime._resumed`, which becomes
   begin-or-restore plus `check_resumes` plus `disarm`. Keep the wording `"save is
   'x'/'y', selected is ..."` that `test_resume_refuses_a_save_that_is_not_this_game` pins.
3. **Small cuts in app and config.** `config.py`: `RoleSettings.for_name` and
   `Providers.for_name` return from a dict literal keyed by the `Literal` (`{"master": self.
   master, ...}[name]`; `getattr` would be `Any`); delete `Settings.source_max_bytes` (the
   `AIDM__SOURCE_MAX_BYTES` env key stops working). `core/source.py`: `SOURCE_MAX_BYTES = 48_000`;
   `whole_text(path)` reads it and `given_text(premise, document)` loses the parameter; the two
   `runtime.py` callers drop the argument; `tests/core/test_documents.py` drops its own
   `MAX_BYTES` and its nine `whole_text(path, MAX_BYTES)` arguments, and the "too large" test
   writes `SOURCE_MAX_BYTES + 1` bytes. `description=` on `RoleConfig.max_rounds` ("read only
   over a completion API") and `timeout` ("bounds the whole process on a CLI"), shown by
   `ui/settings.py`'s `_label` as a hint. `turn/run.py`: `Turn.narrates` and `Turn.landed`
   become properties (scalar reads); three call sites drop the parentheses.

### Part B: the UI

4. **No engine knowledge above the seam.** `engines/seam.py`: `Engine.seeds(packs: tuple[Slug,
   ...]) -> tuple[str, ...]: return self.packs.seeds(packs)` (no `select_packs` inside: the form
   already holds a full selection and `pack_ids` would prepend the SRD twice);
   `ScenarioForm.seeds` is `self.runtime.engines[self.engine_id].seeds(self.packs)`.
   `core/creation.py`: `drop_stale(steps, picks)` moves here from `ui/create.py`, its two tests
   from `tests/ui/test_create.py` to `tests/core/test_creation.py`. `core/views.py`:
   `Panel.portrait: bool = False`; `engines/base.py`: `character_panel` sets it;
   `GamePage.sidebar` reads it and the `enumerate`/`index == 0` go; one parametrized test over
   `ENGINE_IDS` asserts exactly one panel carries the portrait.
5. **One file per job.** `ui/app.py`: public `register_pages(runtime)` built from
   `ui.page(route)(partial(page, runtime))`; only the game page (it awaits
   `client.connected()`) and the pack page (the refusal page) keep a small module-level
   function; the seven pyright ignores go; `qa/server.py` imports the public name.
   `ui/create.py`: `_form_page(runtime, engine_id, *, eyebrow, title, lead)` context manager
   yielding inside the card, used by the three forms; `DocumentUpload.build` registers its own
   `on_delete`. New `ui/transcript.py`: the pure renderers as free functions, `chat`, `live_turn`,
   `journal`, `card`, `dice_group`, `bubble`, `inline_status`, `clock`, with `MARK_LABELS`,
   `STEP_COPY`, `can_type` and `standing_proposal` (the renderers call them); `GamePage.chat`,
   `live_turn`, `journal` become short refreshables. `Observed`, `whole_page`, the partial
   refresh and `media_url` stay. `ui/game.py` lands near 570 and `ui/transcript.py` near 175.
   `tests/ui/test_game.py` imports the moved names from `transcript`.
6. **`Look` is one palette.** `core/views.py`: `Look` keeps one field, `palette: Mapping[str,
   str]`; `DiceLook` goes. The three `look.json` spell `game-die-body`, `game-die-ink`,
   `game-die-glow` directly; `ui/theme.py`: `set_look` is one merge, `dice_variables` goes.
   `tests/support/fifth.py`/`sixth.py` write the flat shape; `tests/ui/test_dice.py` walks the
   engine's palette for the three `game-die-*` keys against `theme.css`.

### Part C: the tests

7. **Delete what the goldens pin.** `tests/app/test_context_boundary.py`: delete
   `..._names_the_party_and_leaves_a_member_out_of_who_is_here`, `..._carries_the_players_
   own_sheet`, `test_the_master_prompt_shows_the_scope_right_after_the_scenario`,
   `test_the_master_prompt_ends_on_the_action_with_no_empty_waiting_section`.
   `tests/app/test_roles.py`: delete `test_render_interjection_prints_the_members_own_sheet_
   or_none`, `test_render_narrator_asks_for_the_narration_shape_not_the_interjections`,
   `test_render_interjection_asks_for_the_interjection_shape_not_the_narrations`, and the
   `_view`/`_companion` helpers that go dead with them. The leak tests in both files stay.
8. **Parametrize the copies.** `tests/ui/conftest.py`: a `page` fixture that yields a builder
   entering the NiceGUI client in the test's own asyncio task (NiceGUI keys its slot stack by
   task id; a `with client:` entered in the fixture leaves the test outside any slot) and pops
   that task's `Slot.stacks` entry at teardown; a `notified` fixture that monkeypatches
   `ui.notify`. `tests/ui/test_game.py`: the five toast tests become one parametrized test over
   `(exception, expected notifications)`; the 24 `spy_notify`/`Client`/`try…finally` blocks use
   the fixtures; `tests/ui/test_settings.py` moves onto `notified` too. `tests/app/
   test_launcher.py`: the six bad-save tests become one parametrized test over writers returning
   `(settings, engines, stem)` and the expected log text (three make the only save bad, one needs
   a second engine map; this file is line-neutral). `tests/app/test_spawn.py`: one
   `_StubDriver(argv: tuple[str, ...])` replaces the three stub drivers. `tests/test_config.py`:
   the five `base_url` tests become one parametrized test.
9. **Support and the converter.** `tests/support/engine_dir.py`: `install_engine_dir(tmp_path:
   Path) -> None` writing `rules.md`, the flat `look.json` (the three `game-die-*` keys) and
   `packs/srd.json`; `fifth.py` and `sixth.py` call it. Delete `take()` (its two callers call
   `table.service.act(...)` directly); `open_game = partial(open_table, engine_id=LONER3E,
   state_type=Loner3eGame)`. Delete `scripts/srd_packs.py`, `tests/scripts/`,
   `tests/fixtures/srd/`, the three `scripts` entries in `pyproject.toml` (pytest `pythonpath`,
   basedpyright `include` and `extraPaths`), and rewrite the `docs/LONER-3E.md` paragraph that
   documents the converter (the twelve packs are checked in; their source is the SRD site named
   in each pack's `source`). `qa/agents.py` stays as it is.

Done when: the full check is green; `uv run aidm` plays one turn on each engine, resumes a save,
and shows a refusal toast when a second tab plays the same game; the counts land in the target.
