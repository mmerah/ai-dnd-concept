# PLAN: human code

Four phases make `src/aidm/engines` read like code one person wrote, and make a pack what it is
at a real table: one setting per adventure. One class per thing, its fields written out. One
place per tool, its description beside its method. One pack on a scenario, none on a character.
A type parameter only where a container holds the engine's own kind of thing. Plain words for
what the code holds.

Folded from `NEXT-PLAN.md` (seven steps, each prototyped green on `3ebf53f`) and
`TABLETOP-STRUCTURE-SPECS.md` (option 1), with the decisions below. Both documents are deleted
with this plan's first commit. Line targets here are estimates, not measured runs, and every
phase is judged by the full check and its "Done when" line.

Decided on 2026-09-18 and not re-opened by any phase:

- **Facts are returned, not accumulated.** NEXT-PLAN step 2 (`World.facts` and `World.tell`) is
  cut. A method that changes the world returns the facts it wrote; the caller sees the data
  leave and arrive. No hidden list, no clearing sites.
- **`SceneEngine` stays as the scene loop; `RoomEngine` goes.** Two engines share the scene loop
  (`next_scene`, `act`, `depart`, `complicate`, `install`, `write_next`, `author`), and a fix to
  how a crossing is written is made once. Its hooks (`sheet_sections`, `panels`,
  `opening_sections`) go: 24XX writes its `master_sections` and `player_view` whole. One engine
  plays rooms, so `RoomEngine`'s body becomes `TunnelGoonsEngine`'s; the `rooms/` world, tools
  and worldsmith checks stay as the family's shared code.
- **A character carries no pack.** The pack is chosen on the creation page to offer tables; the
  sheet then carries labels and needs no pack. A scenario carries one `pack`; a game plays the
  scenario's. Any character of an engine plays any scenario of that engine.
- **The saved shape changes once, in phase 3.** `payload` becomes `world` on a game, `opening`
  on a scenario, `sheet` on a character; `SceneRun` becomes `Scene`. A stale save is invalid
  by the standing rule; the launcher skips it with a warning. The shipped scenarios and
  characters are edited in the same commit.
- **Names.** `Generation` → `Commission` (an engine commissions the worldsmith), `Engine.land` →
  `Engine.commit`, `Turn.picture` → `Turn.master_prompt`, `family_sections` →
  `worldsmith_sections`, `Loner3eCast` → `Loner3eFigure`, `engines/seam.py` →
  `engines/engine.py`. `WorldsmithJob` was rejected: `job` is 24XX's own word.
- **`Engine[W, K]`.** The world and the pack are the two containers an engine holds, so both
  stay typed on the seam; `P` and `M` go. `PackSet[K]` keeps its parameter. No `isinstance`
  reads a pack.
- **A tool is a method marked `@tool`; its docstring is what the master reads.** Descriptions
  leave `tools.py` and sit beside the behaviour they describe; the argument models and their
  field descriptions stay in `tools.py`.
- **Copies are fine.** Two engines each carrying ten plain lines beat one base carrying a hook,
  a flag or a renamed accessor to share them. Shared model-facing strings keep one home.
- **Two rules beyond CLAUDE.md**, for every phase: no `# type: ignore`, no `cast`. A step that
  cannot type without one stops and says so in `PROGRESS.md`.

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
   Each step is one action. Symbol names are as of `4b72270`; where an earlier step renamed or
   moved one, follow the name the earlier step gave it.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted
   behaviour is deleted with it. A golden is regenerated only when the step says so, with
   `AIDM_GOLDEN_REGEN=1 uv run pytest`, and the phase names which files moved. A rename the type
   checker cannot see (a keyword inside a dict literal or a `tool_call(...)` helper) is done only
   when pytest is green, not when basedpyright is.
3. Count lines at the start and the end of each phase and write both in `PROGRESS.md`, one entry
   per phase, with the decisions taken off-plan and the review findings refuted and why:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   ```
4. Every phase commits once, as one, after the full check.

## Phase 1: one pack

Parts A then B: both touch `engines/seam.py` and `ui/create.py`. Target: `src` about −120,
`tests` about −150; judged by the full check. Three worldsmith goldens are regenerated and
expected to show no text change.

### Part A: the model, the pack set, the seam and the engines

1. **One pack on a scenario, none on a character.** `core/model.py`: delete `Packs` and
   `_distinct_packs`; `Scenario.pack: Slug` and `Game.pack: Slug` replace `packs`; `Character`
   and `CharacterHeader` lose `packs`. `app/launch.py`: `CatalogEntry` loses `packs`.
2. **`PackSet` reads one pack.** `engines/packs.py`: delete `MAX_SUPPLEMENTS`, `supplements`,
   `chosen`, `select`, `check_addable`, `Pack.defined_ids` and its two overrides
   (`loner3e/worldsmith.py`, `twentyfourxx/worldsmith.py`). Add
   `require(pack_id: Slug) -> K` (refusal `f"pack {pack_id!r} is not installed for
   {self.engine!r}"`), `played(pack_id: Slug) -> tuple[K, ...]` (`(srd,)` when `pack_id ==
   SRD_PACK`, else `(srd, chosen)`: the packs a creation table is read from, the SRD once),
   `options() -> tuple[DecisionOption, ...]` over `installed` (id, `pack.name`; the SRD is one of
   them). `guidance(pack_id, *, opening) -> str` renders one `PACK:` block or `""`;
   `rules_sections(selection)` → `rules_section(pack_id) -> Sections`; `seeds(pack_id)`.
   `installing` and `read_packs` stay.
3. **The seam.** `engines/seam.py`: delete `supplement_options`, `select_packs`, `seeds`,
   `admit`. `guidance(pack_id, *, opening)`. `creation_steps(pack_id, picks)`,
   `create_character(name, brief, pack_id, picks)`, `build_character(name, brief, pack_id,
   picks)`, `sheet_character(name, sheet)`, `build_scenario(meta, pack_id, draft, source,
   premise)`, `author(meta, source, pack_id, worldsmith, check)`. `begin`: `self.packs.require
   (scenario.pack)` where `admit` was, and `"pack": scenario.pack`. `restore`: `self.packs.
   require(state.pack)` replaces `select`. `validate`: the `SRD_PACK in state.packs` check goes.
   `scenes/engine.py` and `rooms/engine.py`: `self.packs.rules_section(state.pack)`,
   `self.guidance(draft.pack, ...)`, `self.guidance(pack_id, opening=True)`.
4. **The engines read SRD then pack.** `loner3e/engine.py`: `creation_steps` and
   `master_sections` iterate `self.packs.played(pack_id)` / `played(state.pack)`; `spend_luck`
   refuses unless `self.packs.require(draft.pack).spends_luck` (message `"this pack does not
   spend luck"`). `twentyfourxx/engine.py`: `_offered(pack_id)` and `write_sheet` iterate
   `played`; `skills` and `starting_kit` stay `srd()`. `tunnelgoons/engine.py`: the item hint
   iterates `played`. `app/runtime.py`: `new_scenario(engine_id, meta, document, pack_id,
   character_id)` calls `engine.packs.require(pack_id)` where `admit` was; `rewrite_pack` loses
   its `check_addable` line (the shipped-id refusal above it stays; `edited` already parses).
5. **Content and docs.** `scenarios/*/world.json` (three): `"packs": ["srd"]` → `"pack":
   "srd"`. `characters/kael/*.json` (three): the `"packs"` line goes. README paragraph 54 ("A
   pack is the whole SRD kit…"): a scenario plays one pack, chosen when it is written, and the
   SRD pack is the engine's own tables; paragraph 56: "Pick it when you make a character or a
   scenario." `docs/24XX.md` lines 36 to 38 and `docs/TUNNEL-GOONS.md` line 46: "selected on the
   scenario". `docs/LONER-3E.md` deviation 4 gains one sentence: a creation table is the SRD's
   entries followed by the chosen pack's, so the starter tables are offered beside an Adventure
   Pack's.

### Part B: the create pages, qa and the tests

6. **One select.** `ui/create.py`: `CharacterForm.pack: Slug = SRD_PACK` and
   `ScenarioForm.pack` replace `packs`; `_pack_select(engine, chosen, on_change) -> ui.select`
   (label `"Pack"`, options `engine.packs.options()`, not `multiple`) replaces `_packs_select`;
   `choose_pack(event)` sets `self.pack = content_id(event.value)` and, on the character form,
   calls `answered()`; delete `_selected_packs`, `_offered`, `choose_packs`,
   `follow_supplements`, `follow_character_id`, `ScenarioForm.supplements`. `ScenarioForm.seeds()`
   reads `engine.packs.seeds(self.pack)`; the seed button's visibility is set in `choose_pack`
   and after `character_fields` builds. `new_scenario(..., self.pack, character_id)`.
   `qa/s_create.py` lines 87 to 94: `select(page, "Pack", "AP01 Fantasy")`; the
   `loner-supplements` shot is retaken as `loner-pack`; the SRD picks "Quiet Hands" and "Pry
   Bar" still exist beside AP01's.
7. **Tests.** `tests/engines/test_packs.py`: delete the two `new_game_*_character_*` tests,
   `select_refuses_two_packs_that_define_the_same_id`, `check_addable_refuses_*`,
   `select_refuses_more_than_max_supplements_*`, `the_seam_admits_a_character_*`; add
   `require_refuses_an_uninstalled_pack`; `seeds_lists_*` and `pack_set_guidance_*` read one
   pack. `tests/engines/test_seam.py`: `validate_refuses_a_game_that_does_not_play_the_srd` →
   `restore_refuses_a_save_naming_an_uninstalled_pack`; `admit_refuses_a_pack_*` →
   `begin_refuses_a_scenario_naming_an_uninstalled_pack`.
   `tests/engines/test_integrity_boundaries.py` (lines 126, 159, 167) and
   `tests/engines/test_scene_bar.py` (338, 345): the duplicate, missing and uninstalled cases
   become one uninstalled-pack case. `tests/loner3e/test_tools.py` (163, 174): `draft.pack =
   "ap01-fantasy"`. `tests/loner3e/test_prompt_budget.py`: the worst case is the largest AP file
   alone; the `MAX_SUPPLEMENTS` import goes. `tests/ui/test_create.py`: one select, no
   character-to-scenario follow. Field renames in `tests/support/fifth.py`, `sixth.py`,
   `tunnelgoons.py` (119), `twentyfourxx.py` (53), `tests/app/test_launcher.py`,
   `test_pack_authoring.py`, `test_pack_editing.py`, `test_master_tools.py` (257),
   `tests/twentyfourxx/test_worldsmith.py` (11). Goldens: regenerate
   `tests/core/fixtures/prompts/*/worldsmith.txt` and diff; the `PACK:` blocks read the same.

Done when: the full check is green; `grep -rn "packs=\|\.packs\b\|MAX_SUPPLEMENTS\|
defined_ids\|check_addable\|select_packs\|supplement" src tests qa` finds only `engine.packs`
(the `PackSet`), `PackSet.shipped/written/installed` reads and `Settings.packs_dir`; the two
create pages show one `Pack` select each.

## Phase 2: things and hire

Parts A then B: both touch `engines/base.py`, `tunnelgoons/world.py` and the two hiring engines.
Target: `src` about +40, `tests` about −20. Two `master_tools.json` goldens move (see step 5).

### Part A: one class per thing

1. **`base.py` keeps `Gauge`, `Thing`, `Person`, `World`.** Delete `Sheet`, `Sheeted`,
   `Person.hired`, `Person.hireable`, `World._player_carries_a_sheet`, `World.require_actor`,
   `World.require_hireable`. `Person` keeps `alive`, `chattiness`, `headline`, `required`,
   `changed_tags`. Inherited fields are never redeclared.
2. **Tunnel Goons: `Goon` and `Npc` written out.** `tunnelgoons/world.py`: `GoonSheet(Mutable)`
   as it is. `Goon(Person)`: `hp: Gauge` (default full), `sheet: GoonSheet` (required: the
   player always carries dice), `kit`; methods `rows(*, carried=None)`, `level(ability, boost)
   -> list[Fact]`, `level_decision()`, `unpack_kit`. `Npc(Dweller)`: `hp: Gauge`, `sheet:
   GoonSheet | None = Field(default=None, description="Leave empty.")`; `hired` property (`self.
   sheet is not None`), `require_sheet()` (refusal `f"{self.name} carries no dice"`),
   `sign_on`, `rows` (the Difficulty Score row when unhired), `level`, `level_decision`,
   `required` (adds `"no sheet"` and `"health above zero"` over `super()`). `Adventurer` goes;
   `level` and `level_decision` are a copy each. `TunnelGoonsWorld`: `require_actor(actor_id)
   -> Goon | Npc` (the player, or a hired member here in the party), `require_hireable(id) ->
   Npc`, `sheet_of(actor: Goon | Npc) -> GoonSheet` (the one `isinstance`, so `roll` and
   `level_up` read one sheet the same way), `next_to_level(actor: Goon | Npc)`. The character
   file and the golden do not move: `Goon.sheet` was always written.
3. **24XX: `Crewmate` written out.** `twentyfourxx/world.py`: `CrewSheet(Mutable)`;
   `Crewmate(Person)`: `sheet: CrewSheet | None = Field(default=None, description="Leave
   empty.")`, `require_sheet`, `hired`, `carried`, `line` (carries `carried()` into `detail`
   for a member), `rows`, `required` (adds `"no sheet"`). `TwentyfourxxWorld` gains
   `_player_carries_a_sheet` (the one validator the base lost, three lines), `require_actor
   (actor_id) -> Crewmate`, `require_hireable(id) -> Crewmate`. `loner3e/world.py`: nothing
   changes. Tests: `tests/engines/test_engines_base.py::test_a_sheeted_person_with_no_sheet_
   has_no_rows` and `test_sheeted_required_names_the_missing_state_not_the_carried_one` become
   `Npc` tests in `tests/tunnelgoons/test_world.py`.

### Part B: the hire flow belongs to the engines that hire

4. **The seam stops knowing about hires.** `engines/seam.py`: delete `Engine.hires`,
   `Engine.hire`, `Engine.write_hire`, `Engine.write_sheet`, `Engine.worldsmith_requests`,
   `Engine.requests`, `Request`. `Written` stays. `Engine.unwritten: dict[Slug, Fact]` is a
   class attribute naming the fact filed when a request fails: `SceneEngine.unwritten =
   {DEPARTURE: WAY_UNWRITTEN, COMPLICATION: COMPLICATION_UNWRITTEN}`; `TwentyfourxxEngine.
   unwritten = {**SceneEngine.unwritten, HIRE: HIRE_UNWRITTEN}`; `RoomEngine.unwritten =
   {EXTEND: MAP_UNWRITTEN}` and `TunnelGoonsEngine.unwritten = {**RoomEngine.unwritten, HIRE:
   HIRE_UNWRITTEN}`. `validate` checks `request.operation in self.unwritten`. `advance(draft,
   request, worldsmith) -> Written` is abstract; each is one `match request.operation`:
   `SceneEngine` (`DEPARTURE` → `depart`, `COMPLICATION` → `complicate`), `TwentyfourxxEngine`
   (`HIRE` → `write_hire`, else `super().advance`), `RoomEngine` (`EXTEND` → `extend`),
   `TunnelGoonsEngine` (`HIRE` → `write_hire`, else `super()`); the fall-through raises
   `ValueError` (validate refused it first). `app/runtime.py` `_grow` reads
   `self.engine.unwritten[request.operation]`.
5. **`hire` and `write_hire`, a copy each.** `TunnelGoonsEngine` and `TwentyfourxxEngine` each
   carry `hire(draft, args: Hire, _rng) -> list[Fact]` (as `Engine.hire` reads today, through
   their world's `require_hireable`) and `async write_hire(draft, request, worldsmith) ->
   Written`, with today's `write_sheet` body inlined: the prompt, the worldsmith call, the
   `sign_on`, then the join and the signs-on fact. `master_tools` lists `hire` after
   `leave_party`… which the tuple cannot do without rebuilding the base's, so `hire` comes after
   the family's tools: regenerate `tests/core/fixtures/schemas/tunnelgoons/master_tools.json`
   and `twentyfourxx/master_tools.json` and confirm the only change is `hire`'s position.
   `HIRE`, `HIRE_TOOL`, `Hire`, `SIGNED_ON`, `HIRED`, `UNWRITTEN_CAST`, `HIRE_UNWRITTEN` stay in
   `engines/tools.py`: one home per model-facing string. Tests: `tests/engines/test_hire_tool.py`
   holds (both engines still hire); `tests/engines/test_scenes.py::test_a_scene_engine_refuses_
   to_write_an_operation_not_its_own` holds through `unwritten`; `tests/app/test_game_service.py`
   overrides `advance`; `tests/core/test_golden_turn.py` iterates `engine.unwritten`.

Done when: the full check is green; `grep -rn "Sheeted\|class Sheet\b\|hireable\|\.hires\b\|
worldsmith_requests\|Request\b" src tests qa` finds nothing but `Request` inside
`twentyfourxx` words and the `mcp` module; `Npc` and `Goon` each read top to bottom with every
field on the class.

## Phase 3: the seam

Parts A, B, C, one after the other: all three touch `engines/seam.py`. Target: `src` about −180
(the deleted `rooms/engine.py` class header and hooks, `world_of` and its 65 calls, the test
engines' support), `tests` about −120. No prompt or turn golden moves; the saved shape does.

### Part A: what a game holds is called what it is

1. **`payload` → `world`, `opening`, `sheet`.** `core/model.py`: `Game[W: BaseModel].world: W`;
   `Scenario[O: BaseModel].opening: O`; `Character[S: BaseModel].sheet: S`;
   `CharacterHeader.sheet: SheetHeader`. `core/io.py` line 131 and `app/launch.py` read
   `header.sheet`. `engines/seam.py`: delete `world_of`, `tick`, `disarm`; every `self.world_of
   (draft)` in `src` becomes `draft.world`; `turn/run.py` `Turn.finish` calls `self.draft.world.
   tick(...)`; `app/runtime.py` `_resumed` calls `state.world.disarm()`. `player_of` reads
   `character.sheet`; `new_game` reads `scenario.opening`; `begin` writes `"world"`.
   Content: `scenarios/*/world.json` `"payload"` → `"opening"`; `characters/kael/*.json`
   `"payload"` → `"sheet"`. Tests follow (44 files mention `payload` or `packs`; the type checker
   sees all but the JSON literals in `tests/engines/test_integrity_boundaries.py` and
   `tests/app/test_launcher.py`).
2. **`SceneRun` → `Scene`.** `scenes/world.py`: `class Scene(Mutable)`; `SceneWorld.scenes:
   list[Scene]`; the `run` property → `scene`. Every `world.run` in `engines`, `tests/support/
   golden_turn.py` (`draft.world.scenes.insert(0, Scene(...))`) and the tests follows.

### Part B: one engine plays rooms; the scene loop has no hooks

3. **`RoomEngine` becomes `TunnelGoonsEngine`.** Delete `engines/rooms/engine.py`. Its methods
   move onto `TunnelGoonsEngine` (`tunnelgoons/engine.py`): `new_game` (with `starting_items`
   inlined: `self.world.opening(draft, player, player.unpack_kit(taken))`), `family_sections`,
   `master_sections`, `narrator_view`, `player_view`, `author`, `act`, `extend`, `advance`,
   `master_tools` (one tuple: the seam's, then `move_item`, `unlock_way`, `move`, `meanwhile`,
   `hire`, `rest`, `roll`, `level_up`, in today's published order), `move_item`, `meanwhile`,
   `write_next`, `install`; `family_dir = Path(__file__).parents[1] / "rooms"`. `EXTEND`,
   `MORE_MAP` and `MAP_UNWRITTEN` move to `rooms/tools.py`; `opening_sections` becomes
   `OPENING_SECTIONS` in `rooms/worldsmith.py` beside `MAP_ASK`. `rooms/rules.md` and
   `rooms/worldsmith.md` are read as today, so the prompt goldens hold.
4. **`SceneEngine` keeps the loop.** `scenes/engine.py`: delete `sheet_sections`, `panels`;
   `opening_sections` → `OPENING_SECTIONS` in `scenes/worldsmith.py` beside `OPENING`.
   `TwentyfourxxEngine.master_sections` and `player_view` are written whole, in the golden's
   order (GEAR, THE JOB, THE SHIP after YOU PLAY FOR; the Job and Ship panels after the
   character panel); Loner keeps the family's. The prompt goldens hold.

### Part C: type parameters on the two containers

5. **`Engine[W, K]`.** `engines/seam.py`: `class Engine[W: World[Any, Any], K: Pack](ABC)`;
   delete the class attributes `member`, `game`; `world: type[W]`, `pack: type[K]` stay;
   `restore` and `begin` parse `Game[self.world]`. `player_of(character: AnyCharacter) -> Person`
   is abstract; each engine's narrows with one `isinstance` on `character.sheet` (the file
   boundary's one runtime check) and refuses `"a character sheet is the player's: id 'player',
   known"` as today. `SceneEngine[W: SceneWorld[Any], K: Pack]` with `member: type[Person]` for
   `NextProposal[self.member]` and `SceneProposal[self.member]`; `check_scene`, `check_map`,
   `check_extension` lose their parameters. `MasterTool[G]` stays until phase 4. `AnyEngine =
   Engine[Any, Any]`. The `Loner3eGame = Game[Loner3eWorld]` aliases stay.
6. **The test engines go.** Delete `tests/support/fifth.py` and `sixth.py`.
   `tests/engines/test_seam.py` runs on the shipped engines through `support/table.py`
   (`test_a_fifth_scene_engine_begins_a_playable_game` goes; `test_a_game_with_no_chapter_open_
   is_refused` uses `game(LONER3E)`; the tempo tests subclass `TunnelGoonsWorld`).
   `tests/support/tunnelgoons.py` gains `keep()` building the sixth keep's map (gate, yard,
   cellar, well; the locked yard→well way; the lantern in the yard; the warden as `Npc(hp=…)`)
   so `tests/engines/test_rooms.py` keeps its ids and counts; its three construction tests
   subclass `TunnelGoonsEngine` with `directory = tmp_path` over `install_engine_dir`.
   `tests/engines/test_scene_bar.py`: `AnySceneEngine` → `Loner3eEngine | TwentyfourxxEngine`.

Done when: the full check is green; `grep -rn "payload\|world_of\|SceneRun\|RoomEngine\|
sheet_sections\|def panels\|opening_sections\|fifth\|sixth" src tests qa` finds nothing;
`engines/rooms/` holds `world.py`, `tools.py`, `worldsmith.py`, `rules.md`, `worldsmith.md`
and nothing else; `uv run aidm` starts, and a game begun from each shipped scenario saves a
file with a `"world"` key.

## Phase 4: tools and words

Parts A then B: both touch every `engine.py`. Target: `src` about −60 (the `*_TOOL` constants
and the `master_tools` tuples against the docstrings), `tests` about +40. Two `master_tools.json`
goldens may move by order; the plan says where.

### Part A: a tool is a marked method

1. **`@tool` and `tools_of`.** `core/tools.py`: `MARKED: set[Callable[..., object]]`; `def
   tool[F: Callable[..., Sequence[Fact]]](method: F) -> F` adds `method` to `MARKED` and returns
   it unchanged, refusing (`ValueError`) a method with no docstring. `def tools_of(engine:
   object) -> dict[str, MasterTool]` walks `reversed(type(engine).__mro__)` and each class's
   `vars()` in order, so the base's tools come first and an override keeps the base's slot; for
   each marked name it binds `getattr(engine, name)` (an unmarked override such as
   `TwentyfourxxEngine.kill` is bound too, and reads the marked base's docstring), takes the
   args model from the annotation of the third parameter of `inspect.signature` (`isinstance
   (annotation, type) and issubclass(annotation, BaseModel)`, else `ValueError`), reads the
   description from the marked method's `__doc__` with `inspect.cleandoc`, and refuses a model
   field without a description as `master_tool` does today. `MasterTool` loses its parameter:
   `call: Callable[[AnyGame, JsonValue, Random], tuple[Fact, ...]]`. Delete `master_tool`.
2. **Every tool moves onto its method.** `engines/seam.py`: `self.tools = tools_of(self)` in
   `__init__` (the twice-named check stays); `Engine.tool(name)` → `require_tool(name)`.
   Delete `master_tools` and every override; each `*_TOOL` and one-line tool constant in
   `engines/tools.py`, `scenes/tools.py`, `rooms/tools.py`, `loner3e/tools.py`,
   `tunnelgoons/tools.py`, `twentyfourxx/tools.py` becomes the docstring of its method; each
   lambda becomes a two-line method (`reveal`, `enter`, `leave`, `unlock_way`, `move`,
   `take_lead`, `rest`). Definition order is the published order: `Loner3eEngine.spend_luck`
   below `roll`; `TwentyfourxxEngine.take_lead` between `spend` and `ship_upgrade`, `hire` where
   phase 2 put it. Regenerate the three `tests/core/fixtures/schemas/*/master_tools.json` and
   confirm no change but a description that `cleandoc` reflowed. Tests: `tests/core/test_tools.
   py` tests `tools_of` (order across the MRO, an unmarked override, a missing docstring, a
   third parameter that is no model); `tests/turn/test_decisions.py` builds its ad-hoc tools as
   one small marked class.

### Part B: plain words

3. **Renames.** `git mv src/aidm/engines/seam.py src/aidm/engines/engine.py`, imports follow.
   `Generation` → `Commission`; `Game.generation` → `Game.commission` (excluded from saves, so
   no file moves); `Engine.land` → `Engine.commit`; `Turn.picture` → `Turn.master_prompt`;
   `family_sections` → `worldsmith_sections` on every engine; `Loner3eCast` → `Loner3eFigure`.
   Prompt text and traces do not change: the goldens hold.
4. **CLAUDE.md.** Replace the `Any` rule with: "Do not use `Any`. The one exception: `Game[Any]`,
   `Engine[Any, Any]`, `World[Any, Any]`, `Scenario[Any]`, `Character[Any]` where the app holds
   every engine at once or a class is generic on the game state." Replace the engine tool rule
   with: "A tool is an engine method marked `@tool`; its docstring is what the master reads. It
   resolves ids and rolls dice, and the world or entity method it calls changes fields and
   returns the facts." In "How the game is built", after "The engine owns the world": "An engine
   is one class with its fields and tools written out; `SceneEngine` is the scene loop two
   engines share, and `rooms/` is the world shape and tools one engine plays."
5. **The docs.** README paragraph 29: the sentences naming `SceneEngine` say that `SceneEngine`
   is the scene loop Loner and 24XX share, and that Tunnel Goons is one class over the `rooms/`
   world. `docs/24XX.md` line 106 and `docs/LONER-3E.md` line 141 keep their `SceneEngine`
   sentence; `docs/TUNNEL-GOONS.md` names `TunnelGoonsEngine` over `engines/rooms/`.

Done when: the full check is green; `grep -rn "master_tool\|_TOOL\b\|Generation\|\.land(\|
picture()\|family_sections\|Loner3eCast\|engines.seam" src tests qa` finds nothing; every
`engine.py` under `engines/` defines its tools in published order, each with a docstring and no
constant beside it; the counts are in `PROGRESS.md`.

## Accepted and left as is

`RoomWorld`'s two validators and its `entity()`/`require()` unions over `Person | Prop |
Place`; the `rows(carried=...)` keyword; the pack `head`/`body` authoring split; Loner's SRD
starter tables offered beside an Adventure Pack's (cosmetic, this repo's own tables); a written
pack edited under a running game changes its tables in play, and deleted, breaks its saves at
the next `restore`.
