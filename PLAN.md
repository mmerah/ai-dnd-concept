# PLAN: fold the ten decided simplifications into three commits

This plan lands the nine accepted proposals from the four reads of the codebase: one id type, one request dict that is never saved, the worldsmith's draft as the scenario payload, one hiring rule, a thinner seam, one role runner, one worldsmith renderer, and tests and qa that state each rule once.
Scope is the decisions as recorded: proposals 1, 2 with option a, 3 in full with `source` on the envelope, 4 option c only, 5, 6 all eight items, 7 steps 1 to 3 with the `turn` layer kept, 8 renderer and prose, and 9 items 1 and 2 with qa option a.
Not built: the 3D dice stack stays exactly as it is, proposal 10 was refused; the `turn` layer stays; the pack mechanism stays; no save or scenario file is migrated.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each is one action on the files it names. Every `file.py:line` anchor is as of `56ec76e`; where an earlier step moved the code, find the named symbol and ignore the number.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. Count lines at the start and end of each phase and write both in `PROGRESS.md`, one entry per phase. At the start `src` is 10,199 lines, `tests` 9,462 and `qa` 2,433:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   ```
   If a phase runs half again past its target, stop and say so. Never pad.
4. Golden files live in `tests/core/fixtures/`. Rebuild them only where a phase says so:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed fixture line against the phase's "Done when". Any other change is a bug.
5. One commit per phase, full check green, reviewed adversarially against the staged diff first. Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the staged tree: CI runs exactly that, and `ruff format --check` also formats the Python fences in this file, so `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of every phase: `uv run aidm`, open each shipped scenario, take a turn.
6. Delete, do not preserve. No compatibility path reads an old save or scenario file. No constant, helper, prompt line or test stays for a caller that is gone.
7. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles. No `Any` beyond the `Game[P]` bound. Every `__init__.py` stays empty. Tests never start a process and stub roles with `ScriptedSpawner`. `Refusal` stays the one message-bearing exception and any other exception is a bug. A bad model answer is re-prompted once with the error, then raises. Only code changes state or rolls dice. The narrator reads revealed facts only. Data is validated at each boundary with strict Pydantic models. Names must explain themselves and a comment is one line, only where the reason is not visible in the code.

## Phase 1: one id, a thinner seam, one role runner

Proposals 1, 6 and 7. Mechanical: no file on disk changes shape.

### Steps

1. `src/aidm/core/entities.py:12-16`: delete the two comments, `EntityId` and `CheckedEntityId`. Keep `EngineId` and `Slug`. `Slug` is now the one id type for entities, places and scenes.
2. Replace every `EntityId` and `CheckedEntityId` annotation in `src` with `Slug` and drop the dead imports. `grep -rn "EntityId" src` lists them: `core/model.py:10,92`, `core/play.py:6,14,26`, `core/views.py:6,23,27,68,70,116`, `engines/base.py:7,24,100,142,149,225`, `engines/hiring.py:7,30,32,38,66,74,82,137`, `engines/scenes/world.py`, `engines/scenes/drafts.py:3,25`, `engines/scenes/tools.py`, `engines/rooms/world.py`, `engines/rooms/tools.py`, `engines/loner3e/tools.py`, `engines/tunnelgoons/tools.py`, `engines/tunnelgoons/world.py`, `engines/tunnelgoons/engine.py`, `engines/breathless/world.py`, `engines/breathless/tools.py`, `engines/breathless/engine.py`, `engines/twentyfourxx/world.py`, `engines/twentyfourxx/tools.py`, `engines/twentyfourxx/engine.py`, `app/runtime.py:17,252`, `app/media.py:13,43`, `app/speech.py:12,85`, `ui/game.py:15,680`, and `core/model.py:94` returns `Slug`. A `dict[EntityId, C]` becomes `dict[Slug, C]`, so its keys are now pattern-checked on parse; the shipped data already satisfies the pattern.
3. Delete the 13 casts in `src`: `engines/base.py:12` becomes `PLAYER_ID: Slug = "player"`; `engines/scenes/world.py:297,299` return `wanted` and `matches[0]`; `engines/tunnelgoons/world.py:67`; `engines/breathless/world.py:134,143,144,145`; `engines/breathless/engine.py:155,227`; `engines/twentyfourxx/world.py:129,168`; `engines/twentyfourxx/engine.py:519`.
4. Delete the 134 casts in `tests`: `EntityId("x")` becomes `"x"`, the constants in `tests/support/breathless.py:19-21`, `tests/support/tunnelgoons.py:9-18` and `tests/support/twentyfourxx.py:18-20` become `NAME: Slug = "name"`, and every `from aidm.core.entities import EntityId` goes; the files are the 74 that `grep -rln EntityId tests` prints. `tests/engines/test_integrity_boundaries.py:86` still passes: the grammar now rides `Slug`.
5. `src/aidm/engines/seam.py`: delete `check_scenario` at `:165-167` and its callers `engines/scenes/engine.py:114` and `engines/rooms/engine.py:73`; delete `check_character` at `:58-62`; `player_of` at `:161-163` keeps only the sheet check and the copy:
   ```python
   def player_of(self, character: AnyCharacter) -> P:
       if character.payload.id != PLAYER_ID or not character.payload.known:
           raise Refusal("a character sheet is the player's: id 'player', known")
       return deepcopy(character.payload)
   ```
   The engine-id half is already refused by `begin` at `:137-147` with a better message, and `tests/engines/test_integrity_boundaries.py:94` proves it for both. Delete the two duplicates `tests/twentyfourxx/test_engine.py:97-109`. `preview_character` at `:64-65` loses the engine-id check with it; its one caller, `ui/create.py:126`, previews on the engine that built the sheet, so nothing changes.
6. `seam.py`: replace the abstract `family_rules` at `:191-194` with a declared attribute `family_prompt: Path` beside `directory` at `:43`, and read it once in `__init__` at `:46-53`:
   ```python
   self.instructions = f"{read_prompt(self.directory / 'rules.md')}\n{read_prompt(self.family_prompt)}"
   ```
   `engines/scenes/engine.py:96-97` becomes `family_prompt = RULES_PROMPT`; `engines/rooms/engine.py:56-57` the same. `tests/engines/test_seam.py:140` asserts `engine.instructions.endswith(read_prompt(engine.family_prompt))`.
7. `seam.py`: delete `record`, `history` and `scenes` at `:172-179`; `close` at `:130` calls `self.world(draft).record(exchange)`. Every caller reads the world: `app/launch.py:111,117` take `world = engine.world(state)` and use `world.records()` and `len(world.exchanges())`; `app/runtime.py:97,245,272` use `self.engine.world(self.state).records()` and `.exchanges()`; `app/roles.py:89,104,110` use `self.engine.world(draft).records()` and `.exchanges()`; `turn/run.py:100` uses `self.engine.world(self.draft).records()`. In tests, every `engine.history(state)` becomes `engine.world(state).exchanges()`: `tests/app/test_game_service.py:104,109,118,239,347,361,372,378,383`, `tests/app/test_master_tools.py:223,404,409,434,452,462,474`, `tests/app/test_speech.py:161`, `tests/app/test_launcher.py:259`, `tests/engines/test_seam.py:186`, `tests/turn/test_turn.py:63,225,366`, `tests/breathless/test_play.py:47,59`, `tests/twentyfourxx/test_play.py:43,55`, `tests/tunnelgoons/test_play.py:93,102,120,124`; `tests/app/test_context_boundary.py:38` becomes `_engine().world(state).records()`. Delete `_CountingLoner3e` and `test_turn_picture_walks_the_history_through_scenes_alone` at `tests/turn/test_turn.py:296-318`: they counted the wrappers.
8. `seam.py:89-110`: `compose` builds twice and drops the `nonlocal` cache:
   ```python
   def refusal(answer: M) -> str | None:
       try:
           return playable(build(answer))
       except Refusal as unbuildable:
           return str(unbuildable)


   return build(await worldsmith(prompt, model, refusal))
   ```
   Delete `test_compose_builds_the_accepted_answer_once` at `tests/engines/test_seam.py:146-160`.
9. `app/roles.py:52-73`: `Roles.master` becomes two explicit tries with the same outcome as the loop: a failure after something landed is logged and returns; a failure with nothing landed is logged once and spawns again; a second failure with nothing landed raises.
   ```python
   async def master(self, turn: Turn) -> None:
       """A crashed game master still played the turn, if it applied anything legal first."""
       prompt = turn.picture()
       try:
           await self.spawner.run("master", prompt, None, turn)
           return
       except (OSError, Refusal) as failed:
           if self._landed(turn, failed):
               return
           LOGGER.warning("the game master landed nothing, spawning it again: %s", failed)
       try:
           await self.spawner.run("master", prompt, None, turn)
       except (OSError, Refusal) as failed:
           if not self._landed(turn, failed):
               raise


   def _landed(self, turn: Turn, failed: Exception) -> bool:
       if not turn.facts and turn.draft.pending is None:
           return False
       LOGGER.warning("the game master failed after applying %d facts: %s", len(turn.facts), failed)
       return True
   ```
   The fourth argument to `run` is step 15.
10. `turn/run.py:102`: `notes=self.notes`. `draft.notes` is always empty there: `begin` at `:48` swapped it out and nothing writes a note before `picture()` runs at `roles.py:58`.
11. Merge `engines/scenes/drafts.py` into `engines/scenes/tools.py`: move `SceneDraft` and `NextDraft` from `drafts.py:7-41` to the end of `tools.py`, delete `drafts.py`, and repoint the imports at `engines/scenes/world.py:20`, `engines/scenes/worldsmith.py:10`, `engines/scenes/engine.py:34`, `tests/twentyfourxx/test_worldsmith.py:8`, `tests/breathless/test_worldsmith.py:9`, `tests/app/test_master_tools.py:40`, `tests/engines/test_scenes.py:13`, `tests/loner3e/test_world.py:10`. `tools.py` imports only `engines/base.py`, so `world.py` importing it makes no cycle.
12. `engines/base.py`: add one band reader after `check_filing`:
    ```python
    def banded(face: int, low: str, mid: str, high: str) -> str:
        """The three bands of a six-sided read: 1 to 2, 3 to 4, 5 and up."""
        return low if face <= 2 else mid if face <= 4 else high
    ```
    Delete `outcome` at `engines/breathless/tools.py:102-107` and `engines/twentyfourxx/tools.py:180-185`. `engines/breathless/engine.py:267,364` call `banded(face, "fail", "success-but", "success")`; `engines/twentyfourxx/engine.py:377` calls `banded(face, "disaster", "setback", "success")`; the inline bands at `engines/twentyfourxx/engine.py:405-409` and `:429-433` become one `banded(...)` call each with the three strings they hold today. Drop the `outcome` imports at `breathless/engine.py:25` and `twentyfourxx/engine.py:34`.
13. `app/spawn.py`: move the `Tools` protocol from `app/builtin.py:22-24` to beside `Spawner` at `:129-130`, and give `Spawner.run` a fourth parameter:
    ```python
    class Tools(Protocol):
        def published_tools(self) -> Sequence[MasterTool[AnyGame]]: ...
        def call(self, name: str, raw: JsonValue) -> str: ...


    class Spawner(Protocol):
        async def run(
            self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
        ) -> RunResult: ...
    ```
    Replace the `CliSpawner` dataclass at `:133-160` with a free function that no longer reads the settings or guards the role:
    ```python
    async def run_cli(
        role: Role, config: RoleConfig, driver: Driver, port: int, prompt: str, session: str | None
    ) -> RunResult:
    ```
    Its body is `CliSpawner.run` from `:143-160` with `url = f"http://localhost:{port}/mcp/"`.
14. `app/builtin.py`: replace the `BuiltinSpawner` dataclass at `:57-117` with a free function; `_converse` and `_answer` take `tools` as a parameter instead of `self`, and the guard at `:64-66` goes:
    ```python
    async def run_builtin(
        role: Role, config: RoleConfig, provider: ProviderConfig, prompt: str, tools: Tools | None
    ) -> RunResult:
    ```
    `run_builtin` passes `tools if role == "master" else None` to `_converse`, which computes `published = () if tools is None else [_declared(tool) for tool in tools.published_tools()]`; the check at `:101` becomes `if tools is None:` with the same refusal, so `_answer(tools, call)` takes a `Tools`, never an optional.
15. `app/roles.py:35-44`: replace `RoleSpawner` with the one runner. It reads the role's config once and branches on the provider:
    ```python
    @dataclass(frozen=True, slots=True)
    class RoleRunner:
        settings: Settings

        async def run(
            self, role: Role, prompt: str, session: str | None, tools: Tools | None = None
        ) -> RunResult:
            config = self.settings.roles.for_name(role)
            match config.provider:
                case "claude" | "codex":
                    driver = DRIVERS[config.provider]
                    return await run_cli(
                        role, config, driver, self.settings.server_port, prompt, session
                    )
                case "openrouter" | "local":
                    provider = self.settings.providers.for_name(config.provider)
                    return await run_builtin(role, config, provider, prompt, tools)
    ```
    `Roles.master` passes the turn as `tools`, as step 9 shows. Delete `RoleConfig.cli` at `config.py:37-43`: its only callers were `spawn.py:141,143`. `RoleConfig.api` stays for `config.py:142`.
16. `turn/run.py`: `Turn` satisfies `Tools` by gaining, beside `call` at `:105`:
    ```python
    def published_tools(self) -> tuple[MasterTool[AnyGame], ...]:
        return tuple(self.engine.tools.values())
    ```
    No import of `Tools`: the protocol is structural and `turn` stays below `app`.
17. `app/runtime.py`: `Runtime` takes its spawner. Delete the `stub` InitVar at `:320-321`, `_spawner` at `:334-336` and `lock` at `:324`; `spawner: Spawner` becomes an ordinary init field after `settings`; `__post_init__` at `:329-332` keeps `self.engines = build_engines()` and `self._mount()`; `reload_settings` at `:380` sets `self.spawner = RoleRunner(self.settings)`; the imports at `:10,13,14` become `from aidm.app.roles import RoleRunner, Roles` and `from aidm.app.spawn import Spawner`. `playing` at `:351-358` becomes one line and loses the guard and its comment:
    ```python
    def playing(self) -> GameService | None:
        return next((session for session in self._sessions.values() if session.turn is not None), None)
    ```
    `ui/app.py:109` builds `Runtime(settings, RoleRunner(settings))`. `published_tools` at `:346-349` returns `() if playing is None else playing.turn.published_tools()` once step 16 lands.
18. `app/mcp.py:70-88`: `_build_server` holds `lock = Lock()` from `asyncio` in its closure and `on_call_tool` at `:81` enters `async with lock:`. The comment at `:80` stays.
19. Tests and qa follow the runner: `tests/support/table.py:123` and `qa/agents.py:70` give `run` the fourth parameter `tools: Tools | None = None`, importing `Tools` from `aidm.app.spawn`; `tests/app/test_builtin.py` replaces its seven `BuiltinSpawner(_settings(...), tools)` constructions with `RoleRunner(_settings(...)).run(role, prompt, None, tools)` and `:235` with `RoleRunner(settings).run("narrator", "BRIEF", None)`; `tests/app/test_master_tools.py:529` calls `RoleRunner(settings).run("master", "go", None)`.

### Done when

- `grep -rn "EntityId" src tests qa` prints nothing. `PLAYER_ID` is a `Slug`.
- `Engine` has no `record`, `history`, `scenes`, `check_scenario`, `check_character` or `family_rules`; `app`, `turn` and the tests read `engine.world(state).exchanges()` and `.records()`.
- A game master that fails with nothing landed is spawned once more; a second failure with nothing landed raises; a failure after a fact or a decision landed returns with a warning.
- `Runtime(settings, spawner)` is the only constructor; `Runtime.lock`, `Runtime.stub`, `RoleSpawner`, `CliSpawner` and `BuiltinSpawner` are gone; the MCP `tools/call` handler serialises calls with a lock inside `app/mcp.py`; `qa/server.py` still builds `QaRuntime(settings, agents)`.
- `engines/scenes/drafts.py` is gone; `outcome` is gone from both `tools.py`; `banded` lives in `engines/base.py`.
- `src` is about 10,090 lines, at most 10,110. The id casts are inline, so proposal 1 removes annotations, not lines.
- No golden regenerates. If `tests/core/fixtures/` drifts, that is a bug.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn. Saves keep their shape: a save from before this phase restores as before.

## Phase 2: the request, the draft as the scenario, one hiring rule

Proposals 2 with option a, 3 in full, and 5. Reordered from the suggested order because option a deletes `Hiring.validate` and proposal 5 builds on proposal 2, so all three reshape models together. This phase rewrites the four `scenarios/*/world.json`.

### Steps

1. `core/model.py:107`: `generation: Generation | None = Field(default=None, exclude=True)`. The request lives in memory for one turn and is never written: `Game.draft()` deep-copies it and `Game.commit()` re-parses the instance, so the field survives both, and `model_dump_json` leaves it out.
2. `engines/seam.py:44`: replace `operations: tuple[Slug, ...]` with `unwritten: dict[Slug, Fact]`, the requests this engine writes and what the player reads when one could not be written. Delete the `unwritten` method at `:181-183`. `validate` at `:199-201` stops being abstract and holds the one check; a family adds its own after `super()`:
   ```python
   def validate(self, state: G) -> None:
       """Refuse a state this engine cannot play; a family adds its check after `super()`."""
       request = state.generation
       if request is not None and request.operation not in self.unwritten:
           raise Refusal(f"the {self.id!r} engine writes no {request.operation!r}")
   ```
3. `engines/scenes/engine.py:90`: `unwritten = {DEPARTURE: WAY_UNWRITTEN, COMPLICATION: COMPLICATION_UNWRITTEN}`; `validate` at `:105-111` calls `super().validate(state)` first and loses `:110-111`; delete the `unwritten` method at `:207-212`. `engines/rooms/engine.py:54`: `unwritten = {EXTEND: MAP_UNWRITTEN}`; `validate` at `:66-70` calls `super().validate(state)` first and loses `:69-70`; delete `:166-169`. `RoomEngine.advance` keeps its own `ValueError` at `:181-182`: it guards its parameter, not the state.
4. `engines/hiring.py`: delete `__init_subclass__` at `:94-97`, `unwritten` at `:108-109` and `validate` at `:111-115`. Each hiring engine merges the hire entry by hand in its class body: `engines/breathless/engine.py` and `engines/twentyfourxx/engine.py` get `unwritten = {**SceneEngine.unwritten, HIRE: HIRE_UNWRITTEN}` beside `hire_answer`; `engines/tunnelgoons/engine.py:89` gets `unwritten = {**RoomEngine.unwritten, HIRE: HIRE_UNWRITTEN}`.
5. `app/runtime.py:227`: `self.engine.unwritten[request.operation]`. The one-line clear at `:313` stays and loses its comment: `Game` still parses a `generation` key, so a save written before this phase mid-write would otherwise play its stale request on the next turn. `tests/app/test_game_service.py:278` becomes `test_a_save_never_carries_a_request`: it saves a game whose draft holds a request and asserts the file has no `generation` key, without the `model_copy` indirection.
6. Tests: `tests/engines/test_scenes.py:183` matches `"writes no 'hire'"`. Delete the tests of the deleted `Hiring.validate`: `tests/breathless/test_engine.py:128-135`, `tests/tunnelgoons/test_tools.py:414-420`, `tests/twentyfourxx/test_tools.py:470-489`. The renamed test at `tests/app/test_game_service.py:278` proves the exclusion.
7. `core/model.py:59-70`: `Scenario` gains `source: str = ""` between `packs` and `payload`. The payload is the worldsmith's accepted draft, so the file is the draft plus the envelope.
8. `engines/scenes/world.py`: delete `SceneCanon` at `:52-65`, `begin` at `:97-109` and `run_of` at `:315-323`. One free function settles a draft for a world that may not exist yet, and `apply_scene` at `:265-275` and a new `opening` both use it:
   ```python
   def settled[C: Person](
       draft: SceneDraft[C], player: C, cast: dict[Slug, C], party: Sequence[Slug]
   ) -> tuple[dict[Slug, C], SceneRun]:
       """Free: it marks the present met and files the run, for a world that may not exist yet."""
       everyone: Mapping[Slug, Thing] = {player.id: player, **cast}
       present = resolve_ids(draft.present, everyone, "present")
       hidden = resolve_ids(draft.hidden, everyone, "hidden")
       for entity_id in present:
           cast[entity_id].known = True
       run = SceneRun(
           place=draft.place,
           title=draft.title,
           focus=draft.focus,
           situation=draft.situation,
           here=[*party, *present, *hidden],
       )
       return cast, run
   ```
   ```python
   @classmethod
   def opening(cls, draft: SceneDraft[C], player: C, source: str) -> Self:
       """The player is added by code and never authored, so no scenario can claim their id."""
       cast, run = settled(draft, player, dict(draft.cast), ())
       return parse(
           cls, {"player": player, "cast": cast, "runs": [run], "arc": draft.arc, "source": source}
       )


   def apply_scene(self, draft: SceneDraft[C]) -> None:
       self.cast, run = settled(draft, self.player, self.merged_cast(draft.cast), self.party)
       if isinstance(draft, NextDraft):
           self.run.recap = draft.recap
       self.arc = draft.arc or self.arc
       self.runs.append(run)
   ```
9. `engines/scenes/engine.py`: `new_game` at `:113-116` copies the payload, runs the bar and opens the world; `build_scenario` at `:268-278` files the draft itself with `source=source` on the envelope; delete `opening_canon` at `:280-295` and the `SceneCanon`, `run_of` and `resolve_ids` imports at `:37-43`.
   ```python
   def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> SceneWorld[C]:
       draft: SceneDraft[C] = scenario.payload.model_copy(deep=True)
       if (refused := scene_refusal(draft)) is not None:
           raise Refusal(refused)
       return self.world_type.opening(draft, self.player_of(character), scenario.source)
   ```
   The bar in `build_scenario` stays: authoring and the file are two boundaries.
10. `engines/rooms/world.py`: delete `RoomCanon` at `:121-129`; `begin` at `:152-165` takes the draft and the source: `begin(cls, draft: MapDraft[N], player: P, items: Iterable[Prop], source: str) -> Self`, reading `draft.places`, `draft.ways`, `draft.npcs`, `draft.items` and `draft.start`. `engines/rooms/engine.py`: `new_game` at `:72-77` runs `map_refusal` on the payload, which is what `RoomCanon._startable` checked, then calls `begin` with `scenario.source`; `build_scenario` at `:252-262` files the draft with `source=source`; delete `opening_canon` at `:264-276` and the `RoomCanon` import at `:34`.
    ```python
    def new_game(self, scenario: AnyScenario, character: AnyCharacter) -> RoomWorld[N, P]:
        draft: MapDraft[N] = scenario.payload
        if (refused := map_refusal(draft)) is not None:
            raise Refusal(refused)
        player = self.player_of(character)
        taken = (*draft.places, *draft.npcs, *draft.items)
        return self.world_type.begin(draft, player, self.starting_items(player, taken), scenario.source)
    ```
11. The scenario aliases name the draft: `engines/loner3e/world.py:118` is `Scenario[SceneDraft[Loner3eSheet]]`, `engines/breathless/world.py:172` `Scenario[SceneDraft[Survivor]]`, `engines/twentyfourxx/world.py:237` `Scenario[SceneDraft[Crewmate]]`, `engines/tunnelgoons/world.py:118` `Scenario[MapDraft[Npc]]`; fix the imports at `loner3e/world.py:11`, `breathless/world.py:13`, `twentyfourxx/world.py:11`, `tunnelgoons/world.py:11`. `World.source` at `engines/base.py:99` stays: the save keeps the source.
12. `core/io.py`: delete `SOURCE_STEM` at `:17`, the `shutil` import at `:3`, and the `source` parameter with `:136-137` from `write_scenario` at `:131-137`. `SOURCE_SUFFIXES` stays for `ui/create.py:226`. `app/runtime.py:410` calls `self.library.write_scenario(name, scenario)`. `test_a_scenario_written_from_a_document_keeps_it_beside_the_world` at `tests/app/test_launcher.py:293` becomes `test_a_scenario_written_from_a_document_carries_its_text`: drop only the `source.md` assertion, keep the `SOURCE DOCUMENT:` and premise-fallback checks, which no other test covers. Rename `test_a_directory_holding_no_canon_is_skipped` at `:84` to `test_a_directory_holding_no_world_is_skipped`.
13. Rewrite the four `scenarios/*/world.json` by hand. A scene scenario is the envelope `meta`, `engine`, `packs`, `source`, `payload`, where `source` holds the string that was `payload.source` and `payload` is a `SceneDraft`: `place`, `title`, `focus`, `situation` from the old `opening`; `present`, the old `opening.here` ids whose cast entry had `known: true`; `hidden`, those whose entry had `known: false`; `cast`, every old cast entry with its `known` key removed; `arc: ""`. So `whispering-vault` has `present: ["mara"]` and `hidden: ["vault-map"]`; `drowned-road` has `present: ["ovid-sarn", "ivo-casks"]` and `hidden: ["drowned-marta"]`; `silent-relay` has `present: ["vessa-rune", "harl-odum"]` and `hidden: ["warden-six"]`. The room scenario `buried-keep` keeps its payload `places`, `ways`, `npcs`, `items`, `start` with every `known` flag as it is, loses `payload.source`, and gains `"source": ""` on the envelope.
14. Tests that built a canon build a draft or use the engine: `tests/twentyfourxx/test_engine.py:75-94` and `tests/breathless/test_engine.py:74-108` file a `SceneDraft[...]` with `cast={PLAYER_ID: decoy}` and keep expecting `"the player is in the cast"` from `new_game`, which the world's own validator raises when `settled` files the decoy; `tests/engines/test_seam.py:34,109-129` uses `Scenario[SceneDraft[Person]]` and a draft with `present=("keeper",)`; `tests/engines/test_rooms.py:37,92-115` uses `Scenario[MapDraft[Dweller]]`; delete `test_a_canon_opening_with_play_in_it_is_refused` at `tests/engines/test_scenes.py:53-56`; `tests/tunnelgoons/test_world.py:11-18` builds a `MapDraft[Npc]` and calls `TunnelGoonsWorld.begin(draft, world.player, (), "")`; `tests/twentyfourxx/test_worldsmith.py:242-249` becomes `test_new_game_marks_present_known` through `ENGINE.new_game(_built(draft), character)` with the character read as at `tests/twentyfourxx/test_engine.py:96`. The `tests/support/*.py` builders build worlds, not canons, and read the shipped scenarios through `Library`, so the rewritten files serve them unchanged.
15. `README.md:55`: "the engine's starting world" becomes "the worldsmith's accepted opening, with its source beside it".
16. `engines/base.py`: `Person` at `:80-94` gains the two questions a world asks of anyone, and `Sheeted` moves here from `engines/hiring.py:44-54` with the answers:
    ```python
    class Person(Thing):
        ...

        def hired(self) -> bool:
            """Whether they carry a sheet. A kind that never does answers no."""
            return False

        def hireable(self) -> bool:
            """Whether a sheet could still be written for them."""
            return False


    class Sheeted[S: BaseModel](Person):
        sheet: S | None = Field(default=None, description="Leave empty.")

        def dice(self) -> S: ...  # as today
        def forbidden(self) -> str: ...  # as today

        def hired(self) -> bool:
            return self.sheet is not None

        def hireable(self) -> bool:
            return self.sheet is None
    ```
17. `engines/base.py:97-126`: `World` takes the member type and holds the one rule. `M` appears only in return positions, so `World[Person, P]` accepts every family world.
    ```python
    class World[M: Person, P: Person](Mutable):
        player: P
        source: str = ""
        party: list[Slug] = Field(default_factory=list)

        @model_validator(mode="after")
        def _player_carries_a_sheet(self) -> Self:
            if self.player.hireable():
                raise ValueError("the player carries no sheet")
            return self

        @abstractmethod
        def records(self) -> tuple[SceneRecord, ...]: ...
        @abstractmethod
        def record(self, exchange: Exchange) -> None: ...
        @abstractmethod
        def members(self) -> Sequence[M]: ...
        @abstractmethod
        def require_member_here(self, entity_id: Slug) -> M:
            """Alive and here with the player."""

        def require_actor(self, actor_id: Slug | None) -> M | P:
            if actor_id is None or actor_id == self.player.id:
                return self.player
            member = self.require_member_here(actor_id)
            if member.hired() and member.id in self.party:
                return member
            raise Refusal(f"{member.name} is not the player or a hired party member")

        def require_hireable(self, entity_id: Slug) -> M:
            member = self.require_member_here(entity_id)
            if member.hired():
                raise Refusal(f"{member.name} already carries a sheet")
            if not member.hireable():
                raise Refusal(f"{member.name} takes no sheet")
            return member
    ```
    `join` and `part` stay as they are. `engines/seam.py:196-197` and `:203-204` return `World[Person, P]`.
18. `engines/scenes/world.py:68`: `class SceneWorld[C: Person](World[C, C])`. Every `C | P` in `require` at `:145`, `require_here` at `:153`, `here` at `:166` becomes `C`; add `require_member_here(self, entity_id: Slug) -> C: return self.require_here(entity_id, alive=True)`. `engines/scenes/worldsmith.py:39-49`: `scene_refusal` and `scene_unmet` take `world: SceneWorld[C] | None`. `engines/scenes/engine.py:85`: `class SceneEngine[C: Person, G: Game[Any], K: ScenePack](Engine[C, G])` with `world_type: type[SceneWorld[C]]`, `world` returning `SceneWorld[C]`, `shared_change(self, world: SceneWorld[C], ...)`.
19. `engines/hiring.py`: delete `SheetedWorld` at `:57-78` and `member_noun`. `Hiring[P, M, G, A]` keeps its four parameters: the seam's `world()` erases the member type to `Person`, and `install_sheet` reads the answer's own fields, so `M` and `A` are what type `hireable` and `install_sheet`. Delete the `Sheeted` class from here and import it from `engines/base.py` where `engines/breathless/world.py:12`, `engines/twentyfourxx/world.py:10` and `engines/tunnelgoons/world.py:11` need it.
20. Scene worlds: `engines/breathless/world.py:166-167` becomes the alias `BreathlessWorld = SceneWorld[Survivor]`; `engines/twentyfourxx/world.py:163-164` becomes `class TwentyfourxxWorld(SceneWorld[Crewmate])` without `member_noun`; `engines/loner3e/world.py:104` becomes `class Loner3eWorld(SceneWorld[Loner3eSheet])`. Engines: `engines/breathless/engine.py:55` is `SceneEngine[Survivor, BreathlessGame, Pack]`, `engines/twentyfourxx/engine.py:55` is `SceneEngine[Crewmate, TwentyfourxxGame, Pack]`, `engines/loner3e/engine.py:39` is `SceneEngine[Loner3eSheet, Loner3eGame, Pack]`.
21. `engines/rooms/world.py:132`: `class RoomWorld[N: Dweller, P: Person](Dungeon[N], World[N, P])`; rename `require_npc_here` at `:185-193` to `require_member_here` and its callers at `:215`, `:247`, `engines/rooms/engine.py:194`, `engines/tunnelgoons/engine.py:190`.
22. `engines/tunnelgoons/world.py`: `class Npc(Sheeted[Abilities], Dweller)` loses its own `sheet` field at `:46`; `class Goon(Sheeted[Abilities])` loses `sheet: Abilities` at `:56` and its `rows` at `:60-61` reads `self.dice().rows(self.hp)`; `TunnelGoonsWorld.sheet_rows` at `:77` reads `self.player.dice().inventory`; delete `require_actor_and_sheet` at `:83-91` and `require_hireable` at `:93-97`; `next_to_level` at `:110` filters with `member.hired()`. `engines/tunnelgoons/engine.py`: `roll` at `:188` and `level_up` at `:234,239` become `actor = world.require_actor(args.actor_id)` then `sheet = actor.dice()`.
23. Tests follow the shapes: `tests/engines/test_seam.py:26,42` use `SceneWorld[Person]` and `SceneEngine[Person, FifthGame, ScenePack]`; `tests/engines/test_scenes.py:26-28` use `SceneWorld[Person]`; `tests/twentyfourxx/test_world.py:114` and `tests/breathless/test_world.py:102` match `"not the player or a hired party member"`; `tests/tunnelgoons/test_tools.py:393-398` calls `world.require_actor(MIRA)`.

### Done when

- A save written by this build has no `generation` key: `grep -L '"generation"' saves/*.json` lists every save after a hire. `test_a_save_never_carries_a_request` is green.
- `scenarios/*/world.json` parse as `Scenario[SceneDraft[...]]` for the three scene engines and `Scenario[MapDraft[Npc]]` for Tunnel Goons; each scene payload has `present`, `hidden` and a `cast` without `known` keys; `source` sits on the envelope; `new_scenario` writes no `scenarios/<id>/source.*`.
- A scenario file of the old shape is skipped on the home screen with a warning, and any save that plays it is skipped with it.
- `grep -rn "SceneCanon\|RoomCanon\|opening_canon\|run_of\|SheetedWorld\|member_noun\|require_actor_and_sheet\|require_npc_here\|\.operations\|__init_subclass__" src tests qa` prints nothing. `Hiring.validate` is gone.
- The refusal messages read: "already carries a sheet", "is not the player or a hired party member", and "the 'loner3e' engine writes no 'hire'".
- Tunnel Goons hires with a sheet written by the worldsmith, rolls for a hired member, and refuses an unsheeted one, through the one `World.require_actor`.
- `src` is about 9,980 lines, at most 10,000.
- No golden regenerates: the opening run and the marking of the present are the same as before, so the master, narrator and turn fixtures are unchanged. `Npc` now inherits `sheet`'s "Leave empty." description, which changes the Tunnel Goons worldsmith schema; no golden covers it until phase 3 step 1.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn. Saves keep their shape and a save from before this phase restores as before, its request cleared on reload as today.

## Phase 3: one worldsmith renderer, packs, tests and qa

Proposals 8, 4 option c, and 9 with qa option a.

### Steps

1. Golden first. `tests/core/test_golden_turn.py` gains a worldsmith golden per engine, before any renderer changes:
   ```python
   @pytest.mark.parametrize("engine_id", ENGINE_IDS)
   async def test_a_worldsmith_request_renders_unchanged(engine_id: EngineId) -> None:
       engine, state = game(engine_id)
       prompts: list[str] = []

       async def recording[M: BaseModel](prompt: str, _model: type[M], _refusal: Objection[M]) -> M:
           prompts.append(prompt)
           raise Refusal("recorded")

       request = Generation(
           operation=next(iter(engine.unwritten)), brief="Deeper in, toward the sound."
       )
       with pytest.raises(Refusal, match="recorded"):
           await engine.advance(state.draft(), request, recording)
       golden(FIXTURES / "prompts" / engine_id / "worldsmith.txt", prompts[0])
   ```
   `golden` and `FIXTURES` come from `tests/support/golden.py`, `game` and `ENGINE_IDS` from `tests/support/table.py`; the snippet also imports `Generation` and `Objection` from `aidm.core.model`, `Refusal` from `aidm.core.entities` and `BaseModel` from `pydantic`. Run the regeneration once here so `tests/core/fixtures/prompts/<engine>/worldsmith.txt` exists for all four engines, then read the four files once.
2. `engines/base.py`: add the one renderer after `banded`, with `sections` from `core/prompt.py` and `schema_text` from `core/tools.py`. The order is the room family's order. Define `SOURCELESS = "(none — write from the cast)"` beside it, the placeholder from `engines/scenes/worldsmith.py:138`; the room family's own placeholder at `rooms/worldsmith.py:25` goes with its renderer:
   ```python
   def render_worldsmith(
       *,
       role: str,
       source: str,
       scope: str,
       family: Pairs,
       intent: str,
       guidance: str,
       answer: type[BaseModel],
   ) -> str:
       return sections(
           (
               ("YOUR ROLE", role),
               ("SOURCE MATERIAL", source or SOURCELESS),
               ("THE SCOPE OF PLAY", scope),
               *family,
               ("WHAT COMES NEXT", intent),
               ("ENGINE GUIDANCE", guidance),
               ("ANSWER WITH", schema_text(answer)),
           )
       )
   ```
3. `engines/scenes/worldsmith.py`: delete `worldsmith_prompt` at `:123-148`; move the four sentences of `SURPRISE` at `:32-36` into `engines/scenes/worldsmith.md` as one paragraph placed before its last two paragraphs, "Everything you need is below" and "Answer with one JSON object", and delete the constant. Add the family's middle, with the placeholders from `engines/scenes/engine.py:260-262` when there is no world yet:
   ```python
   def scene_sections[C: Person](world: SceneWorld[C] | None) -> Pairs:
       if world is None:
           return (("SCENES SO FAR", ...), ("THE WHOLE CAST", ...), ("THE SCENE NOW", ...))
       return (
           ("SCENES SO FAR", render_history(world.records())),
           ("THE WHOLE CAST", world.cast_lines()),
           ("THE SCENE NOW", world.scene_lines()),
       )
   ```
   `engines/scenes/engine.py`: `render_request` at `:228-242` keeps its signature and calls `render_worldsmith(role=read_prompt(WORLDSMITH_PROMPT), source=world.source, scope=draft.scenario.scope, family=scene_sections(world), intent=intent, guidance=guidance, answer=answer)`; `render_opening` at `:255-266` calls it with `family=scene_sections(None)`, `intent=OPENING` and `answer=SceneDraft[self.cast]`.
4. `engines/rooms/worldsmith.py`: delete `worldsmith_prompt` at `:10-34` and add `map_sections(world: RoomWorld[N, P] | None) -> Pairs` returning `MAP SO FAR`, `SCENES SO FAR`, `THE PLAYER` with the placeholders from `engines/rooms/engine.py:210-212` when there is no world. `engines/rooms/engine.py`: `render_request` at `:218-237` takes the same signature as the scene family, `render_request(self, draft: G, *, intent: str, guidance: str, answer: type[BaseModel]) -> str`, reading `self.world(draft)` and `draft.scenario.scope`; `write_next` at `:241-243` and `engines/tunnelgoons/engine.py:172-178` call it that way; `render_opening` at `:205-216` calls `render_worldsmith` with `family=map_sections(None)`.
5. Regenerate the goldens and read the four `worldsmith.txt` diffs: the three scene prompts move `ENGINE GUIDANCE` after `WHAT COMES NEXT` and carry the surprise paragraph under `YOUR ROLE` instead of a `STANDING INSTRUCTION` section; the Tunnel Goons prompt changes on the `SOURCE MATERIAL` placeholder line only, since `buried-keep` has an empty source. Anything else is a bug.
6. Prose. `engines/scenes/rules.md` and `engines/rooms/rules.md` each gain a final section `## The party` with the five shared sentences that open every engine's party section today, "from scene to scene" in scenes and "from place to place" in rooms, ending with the "Never volunteer" sentence. In each engine's `rules.md` replace the `## The party` section, at `breathless:42-47`, `loner3e:76-82`, `tunnelgoons:50-55`, `twentyfourxx:63-68`, with `## A member's help` holding only that engine's own sentence or two. Append the sentence "A sheet is for someone hired to work, never for one who only comes along." to `HIRE_TOOL` at `engines/hiring.py:17-21`, and delete that sentence and "Call `hire` when the player takes someone on to work." from the `## Hiring` sections at `breathless:49-52`, `tunnelgoons:57-60` and `twentyfourxx:70-73`; the rest of each section stays.
7. Regenerate the goldens: the four `master.txt` and the three `master_tools.json` of the hiring engines change; nothing else does.
8. Proposal 4 option c: delete the pack refusal at `engines/rooms/engine.py:67-68` and its test `tests/tunnelgoons/test_engine.py:28-31`. That leaves `RoomEngine.validate` as a bare `super().validate(state)`, so delete the override; the seam's check serves. `pack_options` stays on the seam: `ui/create.py:191` reads it through `AnyEngine`, and `ui` may not import `engines`.
9. `tests/engines/test_hiring.py`, new, parametrized over the three hiring engines with one case each:
   ```python
   @dataclass(frozen=True, slots=True)
   class HireCase:
       engine: AnyEngine
       game: Callable[[], AnyGame]  # support.breathless / twentyfourxx / tunnelgoons small_world
       member: Slug  # MIRA, KESTREL, MIRA
       sheeted: Callable[[AnyGame], AnyGame]  # the game with `member` already carrying a sheet
       answer: dict[str, JsonValue]  # the worldsmith's sheet, as in the three deleted tests
   ```
   The three tests, written once: `test_hire_sets_the_generation_and_ends_the_turn` through `case.engine.tools["hire"].call(draft, {"entity_id": case.member, "terms": "Watch our backs"}, Random(0))`; `test_hire_refuses_a_sheeted_member` matching `"already carries a sheet"`; `test_advance_on_a_hire_installs_the_sheet_and_joins_the_party` through `await case.engine.advance(draft, Generation(operation=HIRE, brief=..., target=case.member), stub_worldsmith(case.answer))`, asserting `engine.world(draft).require_member_here(case.member).hired()`, membership in `party`, and the `SIGNED_ON` line. Delete the originals: `tests/breathless/test_engine.py:111-157`, `tests/tunnelgoons/test_tools.py:401-431`, `tests/twentyfourxx/test_tools.py:458-467,492-502`. Move `test_restored_round_trips` once into `tests/engines/test_seam.py`, parametrized over `ENGINE_IDS` through `game(engine_id)`, and delete it from `tests/breathless/test_engine.py:69`, `tests/tunnelgoons/test_engine.py:34` and `tests/twentyfourxx/test_engine.py:70`.
10. `tests/engines/test_scene_bar.py`, new, parametrized over the three scene engines:
    ```python
    @dataclass(frozen=True, slots=True)
    class SceneCase:
        engine: AnyEngine
        game: Callable[[], AnyGame]
        bar: Callable[
            [Mapping[str, object]], str | None
        ]  # scene_refusal over the engine's SceneDraft and the game's world
        player: str  # the player's name: Jax, Rook, Kael
        met: Slug  # a known cast member here: mira, kestrel, mara
        unmet: Slug  # a hidden one: dax, sable, vault-map
    ```
    Each case's `bar` builds the engine's draft from the base fields at `tests/breathless/test_worldsmith.py:13-21` and `tests/twentyfourxx/test_worldsmith.py:45-53`, and the Loner case uses `support.game.initialized` with a matching base. The tests, written once: lists the player, matching `"put there by code"`; a cast entry under the player's id, matching `"rewrites the player"`; hides someone met, matching `"already met"`; a dead draft cast member, matching `"may write them"`; a hidden multi-word name in the situation, matching `"does not name what is hidden"`; a scenario whose cast holds the player's id is refused by `new_game`, matching `"the player is in the cast"`; a game with no packs is refused by `validate`, matching `"at least one table set"`; installing a next scene through `engine.advance` with `stub_worldsmith` appends a run and returns a fact whose card starts with `"New scene:"`; the worldsmith prompt names the player first under `THE WHOLE CAST`, read through the recording worldsmith of step 1. Delete the originals: `tests/breathless/test_worldsmith.py:24-84` except `test_sheet_draft_rated_off_the_creation_spread_is_refused`; `tests/twentyfourxx/test_worldsmith.py` at `:92`, `:130`, `:142`, `:167`, `:182`, `:216`, `:230`; `tests/breathless/test_engine.py:63-66` and `:74-108`; `tests/twentyfourxx/test_engine.py:58-62` and `:75-94`; `tests/loner3e/test_world.py` at `:110`, `:133`, `:195`, `:202`.
11. Fold the small files: `tests/breathless/test_views.py` and `tests/breathless/test_create.py` into `tests/breathless/test_engine.py`; `tests/twentyfourxx/test_views.py` into `tests/twentyfourxx/test_engine.py`; `tests/tunnelgoons/test_create.py` into `tests/tunnelgoons/test_engine.py`; delete the four files. While folding, delete the three "nothing hidden" narrator-view tests, `tests/breathless/test_views.py:29`, `tests/twentyfourxx/test_views.py:24` and `tests/tunnelgoons/test_views.py:8`: `tests/app/test_context_boundary.py:44` pins the field set and stays. Delete `test_a_twist_card_lands_only_once_a_twist_fires` at `tests/loner3e/test_tools.py:89`; `tests/loner3e/test_engine.py:116` keeps the priming.
12. qa. Delete `qa/s_mcp.py`, `qa/s_visual.py` and `qa/s_probe.py`; move the markdown and long-word checks at `qa/s_probe.py:28-64` to the end of `qa/s_loner.py` as its two last steps. Shrink `qa/s_goons.py`, `qa/s_breathless.py` and `qa/s_24xx.py` each to: open the game and wait for the opening, one turn that opens the engine's option-only decision, `level_up` in Tunnel Goons, `loot_check` in Breathless and a `risking_death` disaster with a hired member in 24XX, answer it, open the drawer, one screenshot. Delete the MCP transport from qa: `qa/agents.py:23,33,63,127-128,137-153`, `qa/server.py:20,47,72-73`, the `--transport` flag in `qa/serve.sh`; `qa/run_all.sh` lists `home loner goons breathless 24xx settings create mobile`; `qa/README.md` drops the three scenarios and the transport line.
13. `tests/app/test_mcp.py`, new: the master's tools over the MCP endpoint, in process. Build `runtime = Runtime(offline_settings(tmp_path), master)` where `master` is a small spawner defined in the test whose `run` answers the narrator with `narrated("You wait.")` and, for the master, posts JSON-RPC to the endpoint through `httpx.AsyncClient(transport=ASGITransport(app=asgi), base_url="http://localhost:8123")` with `asgi, manager = endpoint(runtime)` and `MountedLifespan(manager)` started before and stopped after; the request bodies and headers are the ones at `qa/s_mcp.py:34-46` before that file goes, and `ui/app.py:175-178` shows how the app mounts it. Assert: `tools/list` between turns is `[]`; `tools/call` between turns is `isError` with "no turn is open"; inside `service.play(Answer(text=...))` the list names `roll` and `change_world`, and a `change_world` reveal of `vault-map` lands as a fact in `engine.world(service.state).exchanges()[-1].facts`.

### Done when

- `tests/core/fixtures/prompts/<engine>/worldsmith.txt` exists for the four engines. The three scene prompts carry `ENGINE GUIDANCE` after `WHAT COMES NEXT` and no `STANDING INSTRUCTION` section; the room prompt is as it was in step 1.
- The four `master.txt` regenerate: `## The party` appears once per prompt, after the engine's rules, `## A member's help` holds one engine's sentence, and the two hiring opener sentences are gone; the three hiring engines' `master_tools.json` carry the sheet sentence in the `hire` description.
- `grep -rn "worldsmith_prompt\|SURPRISE\|STANDING INSTRUCTION" src tests` prints nothing. `render_worldsmith` is the one renderer.
- `engines/rooms/engine.py` refuses no pack; `pack_options` is still on the seam.
- `tests/engines/test_hiring.py` and `tests/engines/test_scene_bar.py` exist; the names `test_restored_round_trips`, `test_advance_on_a_hire_installs_the_sheet_and_joins_the_party`, `test_hire_refuses_a_sheeted_member`, `test_the_bar_refuses_a_scene_that_lists_the_player`, `test_the_bar_refuses_a_draft_cast_entry_under_player_id`, `test_a_dead_draft_cast_member_is_refused`, `test_a_hidden_multi_word_name_in_situation_is_refused`, `test_install_scene_appends_a_run_and_returns_the_opened_fact`, `test_render_worldsmith_lists_the_player_first`, `test_a_player_id_cast_entry_is_refused_by_new_game` and `test_a_scenario_with_no_packs_is_refused_by_check_packs` each occur once under `tests/`. The four folded files are gone.
- `qa/` holds eight scenario scripts and no `transport`; `uv run basedpyright` covers it green. `tests/app/test_mcp.py` proves the four MCP behaviours without a process.
- `src` is about 9,940 lines; `tests` about 9,220; `qa` about 1,730.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn. Saves keep their shape and a save from before this phase restores as before.
