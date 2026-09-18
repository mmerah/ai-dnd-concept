# NEXT-PLAN: human code

Done after `PLAN.md`. The target: the engines, the tools and the world read like code one person
wrote in an afternoon. No generics, no family layer, one class per thing an engine plays, one
place per tool, and a world that writes its own facts. Nothing the player sees changes: the
prompts, the tool schemas, the saves and the pages come out byte-identical, so every golden holds
unless a step says otherwise.

Symbol names are as of `PLAN.md` phase 3 done. Measured then: `src` about 10,510 lines, `tests`
about 12,000, 748 tests collected. Each phase writes its start and end counts in `PROGRESS.md`.

Rules for both phases:

- Run the full check (`uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
  `uv run basedpyright`, `UV_CACHE_DIR` unset) before calling a step done.
- Change a shape and its tests in the same step. Delete a test with the behaviour it pinned. Add
  no test for a move that kept behaviour.
- No `# type: ignore`, no `cast`, no `Any` beyond the one CLAUDE.md allows. A step that cannot
  type without one stops and says so in `PROGRESS.md`.
- Duplication across the three engines is accepted when the shared version needed a generic, a
  hook or a flag to exist. Three plain copies of ten lines beat one clever copy of thirty.

## Phase 1: shape

Steps 1 to 4, in order; 1 and 2 touch disjoint files and may run in parallel.

1. **A tool is a decorated method.** `core/tools.py`: `def tool(description: str)` marks a
   method `(self, draft, args, rng) -> None` with the description and the args model read from
   its annotation; `def tools_of(engine) -> dict[str, MasterTool]` walks `type(engine).__mro__`
   in definition order, the base's tools first, and refuses a name defined twice. `MasterTool`
   keeps `name`, `description`, `args`, `call`; `master_tool(...)` goes. `Engine.__init__` sets
   `self.tools = tools_of(self)`; `master_tools()` and its overrides go. Every `*_TOOL`
   description constant in a `tools.py` moves into the decorator at the method, and each lambda
   in a `master_tools()` becomes a two-line method. Tool methods return nothing; see step 3 for
   where the facts go. The MCP list, the master prompt and `tests/core/fixtures/schemas/*/
   master_tools.json` do not move. `tests/core/test_tools.py` swaps its `master_tool` tests for
   one on `tools_of` (order, duplicate name, missing description).
2. **A world writes its own facts.** `engines/base.py`: `World.facts: list[Fact] = Field(
   default_factory=list, exclude=True)` and `World.tell(trace, *, told=False, card="", dice=())`
   that appends one. Every method that returned `list[Fact]` or `tuple[Fact, ...]` (about 70,
   under `src/aidm/engines`) appends through `tell` and returns `None`; a `Thing.fact`,
   `Thing.change`, `Thing.reveal` becomes `world.tell(...)` at the call site with the same text.
   `turn/run.py` `Turn.apply`: clear `candidate.payload.facts`, run the call, take the list.
   `Engine.answer`, `Engine.advance`, `Written.facts` and the `Request.write` return follow. The
   traces do not change, so `tests/core/fixtures/turns/*` hold. Tests that read a tool's return
   read `world.facts` instead.
3. **No generics.** `engines/seam.py`: `class Engine(ABC)` with no type parameters; `world:
   type[World]`, `member: type[Person]`, `pack: type[Pack]`; `world_of(state) -> World`. Each
   engine narrows once: `def world_of(self, state: Game) -> TunnelGoonsWorld` returning
   `state.payload` after `isinstance`, which is the one runtime check and reads as one. `Game`,
   `World`, `PackSet`, `MasterTool`, `Request`, `Sheeted`, `Dungeon`, `SceneWorld`,
   `MapProposal`, `RegionProposal`, `SceneProposal`, `NextProposal` lose their parameters; a
   field typed by a parameter is typed by the base (`player: Person`, `npcs: dict[Slug,
   Dweller]`) and the engine's own class overrides it with its own type. `TunnelGoonsGame`,
   `Loner3eGame`, `TwentyfourxxGame` aliases go; the tests and `qa/` that name them say `Game`.
   The `Any` count under `src/aidm` drops to the `Game` bound CLAUDE.md allows, or to zero.
4. **No family layer.** `engines/rooms/engine.py` and `engines/scenes/engine.py` go. What they
   held moves: the tool methods onto `TunnelGoonsEngine` (rooms) and onto both scene engines
   (scenes, a copy each); the view builders (`master_sections`, `narrator_view`,
   `player_view`, `family_sections`) become free functions in `engines/rooms/views.py` and
   `engines/scenes/views.py` that take the world and return the view, called by the engine's own
   method of the same name; `author`, `act`, `extend`/`next_scene`, `write_next`, `install`
   become free functions beside them or methods on the one engine that uses them. `RoomWorld`
   and `SceneWorld` stay as the two world shapes; `Dungeon` folds into `RoomWorld`. `family_dir`
   goes: each engine directory holds its own `worldsmith.md` and `rules.md` (the family's text
   appended to the engine's, one file each). `Engine.__init__` reads one `rules.md`. The
   worldsmith prompt goldens under `tests/core/fixtures/prompts/*` do not move.

Done when: the full check is green; `grep -rn "master_tool\|-> list\[Fact\]\|-> tuple\[Fact" src`
finds nothing; `grep -rn "^class .*\[" src/aidm` finds nothing; `engines/rooms/engine.py` and
`engines/scenes/engine.py` are gone; the counts are in `PROGRESS.md`.

## Phase 2: things

Steps 5 to 7, in order.

5. **One class per thing.** `engines/base.py` keeps `Gauge`, `Thing` (`id`, `name`, `brief`,
   `known`) and `Person` (`Thing` + `alive`, `chattiness`), with the one-line reads (`tag`,
   `mention`, `headline`, `subject`). `Sheet`, `Sheeted`, `hired`, `hireable`, `required`,
   `carried`, `changed_tags`, `line`, `rows` leave the base. Each engine spells its own two
   classes with every field written out: Tunnel Goons `Goon` and `Npc` (with `place`, `hp`,
   `abilities: dict[Ability, int] | None`, `inventory`, `level`); Loner `Loner3eCast`; 24XX
   `Crewmate`. `rows()`, `line()`, `sign_on`, `level`, `level_decision` are methods on the
   engine's own class; `hired` is `self.abilities is not None` (or the engine's own field) where
   the engine hires, and the engine that does not hire has no such word. `Dweller`, `Prop`,
   `Place`, `Way` stay in `rooms/world.py`. Saves keep every field name, so no character or
   scenario file changes; `tests/twentyfourxx`, `tests/loner3e`, `tests/tunnelgoons` build the
   flat classes.
6. **The hire flow is one engine's.** `Engine.hires`, `Engine.hire`, `Engine.write_hire`,
   `Engine.write_sheet`, `Engine.worldsmith_requests` and `HIRE*` in `engines/tools.py` go.
   Tunnel Goons and 24XX each carry a `hire` tool method, a `write_hire` and their own
   `requests` dict entry, written out. `Request`, `Written`, `Generation` and `Engine.advance`
   stay: the platform runs a worldsmith request the same way for every engine. Loner has none.
7. **Plain words.** Rename, with every caller and test: `engines/seam.py` → `engines/engine.py`;
   `Engine.land` → `Engine.check_and_commit`; `Engine.close` → `Engine.end_turn`;
   `World.disarm` → `World.clear_clock`; `Generation` → `WorldsmithJob`; `Written` →
   `WorldsmithResult`; `Request` → `JobHandler`. Saved field names (`meanwhile_due`,
   `turns_played`, `pending`) do not change: a rename there would invalidate every save. The
   README paragraph on the engine seam names the new file.

Done when: the full check is green; `grep -rn "Sheeted\|hireable\|family_dir\|seam" src` finds
nothing; every engine's `world.py` has its two entity classes with fields written out; the
counts are in `PROGRESS.md`.
