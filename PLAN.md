# PLAN: simplification

Three phases fold the fifteen accepted simplification proposals into the code: fewer concepts
(a pack list is never optional, one word per thing, one home per model-facing string), less
machinery (the pack editor's private text format, the `G` type parameter, the launcher's second
resume rule, a third of the test suite), and the code rules written as the code lives them.
Every step below was implemented once by a subagent in a throwaway worktree with the four checks
green; the line numbers and the gotchas come from those runs, not from estimates.

Decided on 2026-09-17 and not re-opened by any phase:

- `packs` is a plain `tuple[Slug, ...]` on every model and every engine ships an SRD pack; the
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
  `Presentation` object and a shared `_tell` in `GameService` (+35 each to absorb 20); a
  `GameService.version` counter (needs a `step()` method and loses the partial refresh); static
  media mounts (needs a root table and a startup `mkdir`); lambdas for every two-line tool method
  (+6 at 100 columns); dropping a decode pass in `restore` (all three guard something pinned);
  folding `PackStore` into `PackSet` (a wash that puts a file write in `engines`); the hire flag
  and its raising `write_sheet` default stay.

Measured before any step, at `951ceb9`: `src` **10,904** Python lines, `tests` **12,403**, `qa`
**2,005**, `scripts` **390**. Targets below are the sums of the measured runs; a phase that lands
outside its target by more than 20% stops and says why.

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
   `AIDM_GOLDEN_REGEN=1 uv run pytest`, and the phase names which files moved.
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
−395 (10,904 → about 10,510), `tests` about −140, content +10, one prompt golden.

### Part A: the seam

1. **`G` becomes `W`.** In `engines/seam.py`: `class Engine[P: Person, M: Person,
   W: World[Any, Any], K: Pack]`, `game: type[Game[W]]`, and one concrete
   `def world_of(self, state: Game[W]) -> W: return state.payload`. Every `G` in the file becomes
   `Game[W]` (`MasterTool[Game[W]]`, `Request[Game[W]]`, `begin` returns `Game[W]`).
   `engines/scenes/engine.py`: `class SceneEngine[C: Person, W: SceneWorld[Any], K: Pack]
   (Engine[C, C, W, K])` with `world: type[W]`; `engines/rooms/engine.py`: `class RoomEngine[P:
   Person, N: Dweller, W: RoomWorld[Any, Any], K: Pack](Engine[P, N, W, K])`. Delete the five
   `world_of` overrides (two families, three engines). The `Loner3eGame = Game[Loner3eWorld]`
   aliases stay. Tests: `tests/support/fifth.py` and `sixth.py` subclass `Game[...]`; make them
   aliases (`FifthGame = Game[FifthState]`), because `Game[W]` is not assignable to a subclass.
   `tests/app/test_master_tools.py` passes `lambda built: engine.begin(...)` where a
   `Callable[[AnyScenario], None]` is wanted; it typechecked only because `begin` returned `Any`.
   Make it a three-line `def`.
2. **The meanwhile clock lives on the world.** `engines/base.py`: `World.tempo: ClassVar[int]`
   (no default: an unset one is an `AttributeError` at first tick, so every concrete world sets
   it), `World.tick(*, counted: bool) -> None` replaces `count_turn(tempo)` (count, and at the
   tempo start over and arm `meanwhile_due`). `scenes/world.py`: `SceneWorld.tempo = 6`.
   `tunnelgoons/world.py`: `TunnelGoonsWorld.tempo = 4`. `rooms/world.py`: `RoomWorld.tick`
   overrides: return without counting when not armed and `can_move_offscreen()` is false; after
   `super().tick`, if it was armed and `counted`, `disarm()`. `engines/seam.py`: delete
   `meanwhile_turns`; `Engine.tick(draft, *, counted)` is `self.world_of(draft).tick(counted=counted)`;
   keep `Engine.disarm`. The tempo floor check in `Engine.__init__` becomes `if
   self.world.tempo < 2: raise ValueError(...)` (the base can read `self.world` after step 1;
   declare `world: type[W]` on `Engine`, not on the families). Delete `RoomEngine.tick` and
   `TunnelGoonsEngine.meanwhile_turns`. Tests: `tests/support/sixth.py` sets `tempo = 6`;
   `tests/engines/test_seam.py`'s tempo floor test keeps passing against a world class with
   `tempo = 1`.
3. **The tool resolves the ids; the world changes fields.** `rooms/world.py`: replace
   `RoomWorld.meanwhile(args: Meanwhile)` with four methods that take resolved entities:
   `walk_offscreen(npc: N, place: Place) -> Fact`, `drift_item(item: Prop, place: Place) -> Fact`,
   `shut_way(start: Place, end: Place) -> Fact`, `spend_meanwhile() -> Fact` (the "Elsewhere,
   something moves" card plus `disarm()`); `_offscreen_place` becomes public `offscreen_place`.
   Each keeps its refusals in the order the tests expect (resolve the destination before the
   state check that follows it). `rooms/engine.py`: `RoomEngine.meanwhile(self, draft, args:
   Meanwhile, _rng) -> list[Fact]` refuses when not `meanwhile_due`, resolves the three pairs
   (`npcs.get` → `UNKNOWN_ID`, alive, not at the current place; `items.get`; `require_place`
   twice) and calls the four methods. `rooms/world.py` no longer imports `rooms/tools.py`. Tests:
   every refusal in `tests/engines/test_rooms.py` passes unchanged.
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
   one refusal, used by `Engine.answer` and `Turn.call` (`tests/turn/test_decisions.py` pins the
   old message; update it). `Loner3eEngine.__init__` computes `self.twists` once; `twist_table()`
   goes. `items_from_kits` builds `Gear(**kit.model_dump())`. `CrewSheet.gear_text(*, ids: bool)`
   shared by `Crewmate.carried()` (ids) and `TwentyfourxxWorld.sheet_rows()` /
   `preview_character` (names with notes; the character preview now shows notes such as
   "(bulky)", name it in the test). `GoonSheet.rows(*, carried: int | None = None)` so
   `TunnelGoonsWorld.sheet_rows` passes the count instead of patching the Inventory row by
   label; `Adventurer.rows` and `Npc.rows` carry the keyword through. Docstrings:
   `PendingOption` ("not every name is a tool" is false: `Engine.answer` refuses any non-tool);
   `Game.generation` (`exclude=True`, so `restore`'s refusal fires only on a hand-edited file).

### Part B: packs are never optional, and one pack select

7. **The Tunnel Goons SRD pack.** Create `src/aidm/engines/tunnelgoons/packs/srd.json`: `name`
   "Tunnel Goons SRD", `source`/`license` from `docs/TUNNEL-GOONS.md`, `items` = the eighteen
   names of `STARTING_ITEM_LIST` (`tunnelgoons/engine.py`), every other field empty. Change the
   `.gitignore` line `packs/` to `/packs/` (it hides `src/aidm/engines/*/packs/` too; the two
   existing pack directories only predate the rule). Delete `STARTING_ITEM_LIST`; the create
   page's item hint reads `pack.items` from the chosen packs, as it already does for supplements.
   `tests/support/sixth.py` gets a `packs/srd.json` too (`install_engine_dir` in phase 3 will
   own it; here, add it beside `fifth.py`'s).
8. **`packs: tuple[Slug, ...]`.** `core/model.py`: delete `PackSelection`; `packs: tuple[Slug,
   ...] = ()` on `Scenario`, `Character`, `Game`, `CharacterHeader`. `engines/packs.py`:
   `PackSet.select(ids: Sequence[Slug]) -> tuple[Slug, ...]` runs `check_unique`, the installed
   check, the two-supplement cap and the defined-id overlap; `chosen`, `guidance`,
   `rules_sections`, `seeds` take a tuple and lose their `None` branch; delete `require`;
   `installed` becomes a `@property` (`{**self.shipped, **self.written}`; drop the
   `field(init=False)` and `object.__setattr__`). `engines/seam.py`: `pack_ids` prepends
   `SRD_PACK` for every engine; `select_packs(supplements) -> tuple[Slug, ...]`; `admit`
   compares sets with no unwrapping; `guidance(selection, *, opening)` takes a tuple;
   `Engine.__init__` calls `self.packs.srd()` (an engine that ships no SRD pack is a bug);
   `validate` keeps one check, `if SRD_PACK not in state.packs: raise Refusal(...)`, so a save
   that omits the SRD is still refused, and moves the `self.packs.select(state.packs)` overlap
   scan out of `validate` into `restore` and `begin` (it ran on every tool call). Delete the four
   `SceneEngine` overrides (`pack_ids`, `validate`, `guidance`, `admit`) and its `__init__`.
   `app/launch.py`: `packs=header.packs`. Content: `"packs": {"ids": [...]}` → `"packs": [...]`
   in `scenarios/*/world.json` (three) and `characters/kael/*.json` (three; `buried-keep` and
   the Tunnel Goons character gain `["srd"]`). Tests: the SRD-required tests
   (`test_select_refuses_a_selection_without_the_srd`, `test_a_scenario_with_no_packs_is_refused
   _by_check_packs`) stay and now run against every engine; three tests that called `validate`
   directly for the overlap rule go through `restore`; `tests/engines/test_packs.py`,
   `tests/tunnelgoons/test_engine.py`, `tests/app/test_launcher.py`, `tests/engines/
   test_scene_bar.py` drop their `PackSelection` spellings. Golden:
   `tests/core/fixtures/prompts/tunnelgoons/worldsmith.txt` gains a `PACK: Tunnel Goons SRD`
   block; regenerate it and nothing else.
9. **One pack select.** `core/creation.py`: delete `MANY`, `picked_many`, `CreationStep.multiple`
   and the `multiple` branch of `check_picks`; `tests/core/test_creation.py` loses its three
   `multiple` tests and keeps the single-answer rule. `engines/seam.py`: `creation_steps(packs:
   tuple[Slug, ...], picks)`, `create_character(name, brief, packs, picks)`, `build_character
   (name, brief, packs, picks)`; delete `supplement_steps`, `picked_packs`, `chosen_packs`,
   `SUPPLEMENTS`, `SUPPLEMENTS_LABEL`; engines read `self.packs.chosen(packs)` where they read
   `chosen_packs(picks)`, and `sheet_character(name, sheet, packs)`. `ui/create.py`: one
   `_packs_select(offered: Iterable[DecisionOption], chosen: Iterable[Slug], on_change)` (the UI
   may not import `aidm.engines`, so it takes options, not an engine) used by `CharacterForm`
   and `ScenarioForm`, and one `_selected_packs(runtime, engine_id, picked) -> tuple[Slug, ...]`
   that calls `select_packs`, alerts on a `Refusal` (the two-pack cap is reachable from the page:
   Loner offers twelve) and keeps the previous selection; both forms hold `self.packs`. Delete
   `choose_many` and the `multiple` branch of `_drop_stale`. Tests: every `create_character`
   call site gains `packs` (`tests/loner3e/test_create.py`, `tests/twentyfourxx/test_create.py`,
   `tests/tunnelgoons/test_engine.py`, `tests/engines/conftest.py`, `tests/twentyfourxx/
   test_tools.py`, `tests/ui/test_create.py`, `tests/support/fifth.py`, `sixth.py`).

### Part C: the pack editor reads and writes JSON

10. **One JSON box per pack field.** `engines/packs.py`: `Pack.boxes` (a property) returns
    `tuple[tuple[str, str], ...]` of `(field, json.dumps(value, indent=2, ensure_ascii=False))`
    for every field of `model_dump(mode="json")` except `name`, `source`, `license`.
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
    renders with them. `ui/packs.py`: one monospace textarea per box, `rows=12`. `Runtime.
    rewrite_pack` is unchanged but for the call. Tests: delete `tests/engines/test_pack_text.py`
    (the thirteen codec tests); in `tests/app/test_pack_editing.py` the two edit tests write JSON
    (`json.dumps(SETTING)`; the collision test writes an explicit `{"id": "quiet-hands", ...}`,
    because ids are now edited directly, not re-minted from labels) and one new test edits one
    field, saves, builds a second `Runtime` over the same directory and asserts every other
    field comes back unchanged.

Done when: the full check is green; `uv run aidm` opens a Tunnel Goons game and the home page
lists the Tunnel Goons SRD pack read-only; a written pack opens as JSON boxes and saves; the
counts land in the target.

## Phase 2: names and homes

Parts A then B: both touch every `tools.py` and `worldsmith.py`. Target: `src` about −1,
`tests` about +13, three schema goldens, two `rules.md`, CLAUDE.md +2.

### Part A: one home per model-facing string

1. **Per family and engine.** Move every model-facing constant to `worldsmith.py` (what the
   worldsmith reads) or `tools.py` (what the master reads: tool descriptions, and the `Fact`
   traces that are instructions); nothing model-facing stays in `world.py` or `engine.py`.
   `scenes/engine.py` → `OPENING`, `MEANWHILE_NUDGE` to `scenes/worldsmith.py`, `MOVING_ON` to
   `scenes/tools.py`; `scenes/world.py` → `WAY_OFFERED`, `SCENE_LEFT` to `scenes/tools.py`;
   `rooms/engine.py` → `ELSEWHERE` to `rooms/tools.py`; `rooms/world.py` → `NOTHING_OFFSCREEN`,
   `MOVES_OFFSCREEN`, `MOVED_CARD` to `rooms/tools.py`; `loner3e/engine.py` → `TWIST_NOTE`,
   `DEFEAT_NOTE` to `loner3e/tools.py`; `engines/tools.py` → `DROP_ITEM`, `DropItem`, `AskWorld`
   to `twentyfourxx/tools.py` (`ACTOR` stays: Tunnel Goons reads it). Text unchanged; no golden
   moves.
2. **App: the roles own the role logic.** `app/roles.py` gains `OPENING_NARRATION` (from
   `runtime.py`), `ask`, `RETRIES`, `worldsmith` (from `spawn.py`). `core/tools.py` gains the
   `Tools` protocol (it is a protocol over `MasterTool[AnyGame]`; `builtin.py` imports from
   `spawn.py`, so `RoleRunner` cannot move into `spawn.py` while `spawn.py` needs `builtin`
   unless `Tools` sits below both). `app/spawn.py`: the `Driver` and `Spawner` protocols move to
   the top, before the classes; `RoleRunner` moves here beside `Spawner` and owns the one
   `async with timeout(config.timeout)`, the one `Refusal(f"the {role} answered nothing in
   {seconds:.0f}s")` and the one info log line (`"%s answered: provider=%s model=%s effort=%s %s
   in %.1fs"` with a detail string, "cold" / "resumed" / "over N rounds"); `run_cli` returns
   `(RunResult, detail)` with no timeout of its own (`_spawn`'s `finally: await _kill(process)`
   still kills a cancelled spawn); `run_builtin` returns `(text, detail)` and the runner applies
   `final_message`; `builtin.py` loses its `LOGGER`. `master.md` and `render_master` stay in
   `turn/`. Tests: the six files that import `Tools` from `spawn` import it from `core.tools`;
   `test_the_whole_run_is_held_to_the_roles_timeout` still drives the builtin path.

### Part B: one word per thing

3. **Proposals, not drafts.** Rename the worldsmith's answer classes: `SceneDraft` →
   `SceneProposal`, `NextDraft` → `NextProposal`, `MapDraft` → `MapProposal`, `RegionDraft` →
   `RegionProposal`, `SheetDraft` → `SheetProposal`, `AbilitiesDraft` → `AbilitiesProposal`,
   `SpecialtyDraft` → `SpecialtyProposal`, `OriginDraft` → `OriginProposal` (about 25 files; no
   class name reaches a prompt or a file). `SceneProposal`/`NextProposal` move from
   `scenes/tools.py` to `scenes/world.py` beside `MapProposal`'s place in `rooms/world.py`.
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
5. **Methods and rules.** `line()` is a method on `Loner3eBlock`, `TunnelGoonsBlock`,
   `TwentyfourxxBlock` (it renders). `Gear.broken_message`/`harmless_message` become module
   constants `ALREADY_BROKEN`/`BREAKS_HARMLESSLY` formatted at the raise sites. `Thing.headline`
   returns `self.subject().headline`. `core/io.py`: `parse_unique` → `parse_text`, with one
   docstring line: the entry for our own files and model answers; a caller that already decoded
   uses `parse_json`. `Engine.pack_of(..., origin=...)` (the on-disk field stays `source`).
   `GameService.interject` → `let_party_speak`. CLAUDE.md, under "Code", two sentences: "A
   property is a scalar or attribute-like read; anything that renders text or builds a
   collection is a method." and, replacing the `id`/`label`/`detail` rule: "`id`, `label`,
   `detail` for a pick, an option or a panel row, on disk too; `name` and `brief` for an entity;
   `title` for a scene, a scenario, an engine. Tool arguments: `actor_id` for who acts,
   `target_id` for who is acted on, `to_id` for a destination, `_id` on every id."

Done when: the full check is green; `grep -rn "Draft" src/aidm` finds no worldsmith answer
class; no `engine.py` or `world.py` under `src/aidm/engines` defines a string a model reads;
the counts land in the target.

## Phase 3: app, UI and tests

Parts A, B, C, one after the other: A and B share `ui/game.py`; B and C share `tests/ui`.
Target: `src` about −20, `tests` about −410, `scripts` −390, `tests/fixtures` −420.

### Part A: the app

1. **`Gate` and `Busy`.** `app/runtime.py`: `class Busy(Refusal)` with `elsewhere: bool`
   (`IN_FLIGHT_HERE`/`IN_FLIGHT_ELSEWHERE` become its two messages); `@dataclass(slots=True)
   class Gate` with `admitted: GameService | None`, `turn` property, `require_turn()`, and the
   `admit(session)` context manager, raising `Busy(elsewhere=self.admitted is not session)`.
   `Runtime.gate: Gate = field(default_factory=Gate)`; `Runtime.turn`, `require_turn`, `admit`,
   `admitted` go. `GameService.gate: Gate`. `app/mcp.py`: `endpoint(gate: Gate)`; the module no
   longer imports `Runtime`. `ui/game.py`: `except Busy as busy: if busy.elsewhere: alert(...)`
   in `_run`, `except Busy: blocked = True` in `_opened`; the string compares go. `Runtime
   (settings, spawner: InitVar[Spawner | None] = None)` with the stored attribute `roles`
   (`self.roles = spawner or RoleRunner(settings)`; `GameService.spawner` stays); the fifteen
   test lambdas become `spawner=...`. Delete `GameService.speaking` (tests read `_speaking`
   through a helper) and `ScriptedSpawner.resumed`; `Tasks.settled` stays with one docstring
   line saying it is the test hook. `qa/agents.py` and `tests/support/table.py` reach
   `require_turn` through `.gate`; two UI tests raise `Busy(elsewhere=...)`.
2. **One resume rule.** `app/launch.py`: `check_resumes(state: AnyGame, target: LaunchTarget,
   meta: ScenarioMeta) -> None` (ids match, `check_drift`), called by `_save_option` (which keeps
   its "filed under another name" slug rule) and by `Runtime._resumed`, which becomes
   begin-or-restore plus `check_resumes` plus `disarm`. Keep the wording `"save is
   'x'/'y', selected is ..."` that `test_resume_refuses_a_save_that_is_not_this_game` pins.
3. **Small cuts in app and config.** `config.py`: `RoleSettings.for_name` and
   `Providers.for_name` become one-line `getattr` returns; delete `Settings.source_max_bytes`
   (the `AIDM__SOURCE_MAX_BYTES` env key stops working) and add `SOURCE_MAX_BYTES = 48_000` to
   `core/source.py`, read by `given_text`'s two callers; `description=` on
   `RoleConfig.max_rounds` ("read only over a completion API") and `timeout` ("bounds the whole
   process on a CLI"), shown by `ui/settings.py`'s `_label` as a hint. `turn/run.py`:
   `Turn.narrates` and `Turn.landed` become properties; three call sites drop the parentheses.

### Part B: the UI

4. **No engine knowledge above the seam.** `engines/seam.py`: `Engine.seeds(supplements:
   Sequence[Slug]) -> tuple[str, ...]`; `ScenarioForm.seeds` calls it. `core/creation.py`:
   `drop_stale(steps, picks)` moves here from `ui/create.py`, its two tests from
   `tests/ui/test_create.py` to `tests/core/test_creation.py`. `core/views.py`: `Panel.portrait:
   bool = False`; `engines/base.py`: `character_panel` sets it; `GamePage.sidebar` reads it and
   the `enumerate`/`index == 0` go; one parametrized test over every engine asserts exactly one
   panel carries the portrait.
5. **One file per job.** `ui/app.py`: public `register_pages(runtime)` built from
   `ui.page(route)(partial(page, runtime))`; only the game page (it awaits
   `client.connected()`) and the pack page (the refusal page) keep a small module-level
   function; the seven pyright ignores go; `qa/server.py` imports the public name.
   `ui/create.py`: `_form_page(runtime, engine_id, *, eyebrow, title, lead)` context manager
   yielding inside the card, used by the three forms; `DocumentUpload.build` registers its own
   `on_delete`. New `ui/transcript.py`: the pure renderers as free functions (`exchange_block`,
   `live_block`, `card`, `dice_group`, `bubble`, `status_ticker`, `clock`, `MARK_LABELS`,
   `STEP_COPY`, plus `can_type` and `standing_proposal`, which the renderers call);
   `GamePage.chat`, `live_turn`, `journal` become short refreshables. `Observed` and the
   partial refresh stay; `media_url` stays. `ui/game.py` lands near 545 and `ui/transcript.py`
   near 175. `tests/ui/test_game.py` imports the moved names from `transcript`.
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
   the fixtures. `tests/app/test_launcher.py`: the six bad-save tests become one parametrized
   test over writers returning `(settings, engines, stem)` and the expected log text (three make
   the only save bad, one needs a second engine map). `tests/app/test_spawn.py`: one
   `_StubDriver(argv: tuple[str, ...])` replaces the three stub drivers. `tests/test_config.py`:
   the five `base_url` tests become one parametrized test.
9. **Support and the converter.** `tests/support/engine_dir.py`: `install_engine_dir(tmp_path,
   *, srd: bool) -> Path` writing `rules.md`, `look.json` and, when asked, `packs/srd.json`;
   `fifth.py` and `sixth.py` call it. Delete `take()` (its two callers call
   `table.service.act(...)` directly); `open_game = partial(open_table, engine_id=LONER3E,
   state_type=Loner3eGame)`. Delete `scripts/srd_packs.py`, `tests/scripts/`,
   `tests/fixtures/srd/`, the three `scripts` entries in `pyproject.toml` (pytest `pythonpath`,
   basedpyright `include` and `extraPaths`), and rewrite the `docs/LONER-3E.md` paragraph that
   documents the converter (the twelve packs are checked in; their source is the SRD site named
   in each pack's `source`). `qa/agents.py` stays as it is.

Done when: the full check is green; `uv run aidm` plays one turn on each engine, resumes a save,
and shows a refusal toast when a second tab plays the same game; `tests` is about 765
collected; the counts land in the target.
