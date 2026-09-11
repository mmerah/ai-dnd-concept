# PLAN: the accepted proposals in two phases

Phase 1 is every accepted proposal but D4: the fixes, the decided requirements that leave the
save format alone, and the sweep. D3 B is infeasible without a new `Any` (basedpyright: a bound
cannot be generic); the three `world_of` overrides stay. Phase 2 is D4 alone — it changes the
scenario and save format, and lands with pack authoring, which this plan does not design.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each names its files and symbols; there are no line numbers, so find
   the symbol. Where a step gives a signature or a class, that is the exact shape. The tag that
   opens a step says who may run it beside what: `[part A]` and `[part B]` steps touch disjoint
   files and run in parallel; `[sequential after N]` runs once every step up to and including N
   has landed.
2. A rename or a deletion applies across `src`, `tests` and `qa` in the same step. Change a shape
   and its tests in the same step. One test per new behaviour, in the file the step names. A test
   of a deleted behaviour is deleted with it.
3. Golden files live in `tests/core/fixtures/`. No phase 1 step changes one: if a golden drifts,
   the step is wrong, so stop. Phase 2 rebuilds them in the step that says so:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   then read every changed fixture line against that step's list.
4. `PROGRESS.md` gets one entry per phase: `src`, `tests` and `qa` line counts before and after
   (`find src -name '*.py' | xargs cat | wc -l`, the same for `tests` and `qa`; at the start
   9,990 / 9,498 / 1,788), decisions made off-plan, and refuted review findings with the reason.
   Phase 1 creates the file.
5. Delete, do not preserve. No compatibility path reads an old save. No constant, helper or test
   stays for a caller that is gone.
6. `CLAUDE.md` is not edited by any step.
7. The standing rules hold: imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond
   the `Game[P]` bound; `__init__.py` files stay empty; tests never start a process; `Refusal` is
   the one message-bearing exception; only code changes state or rolls dice; the narrator reads
   revealed facts only. `ruff format --check` formats the Python fences in this file, so run
   `uv run ruff format PLAN.md` after editing it. The game stays playable at the end of every
   phase: `uv run aidm`, open each shipped scenario, take a turn.

## Phase 1: the fixes, the decided requirements, the sweep

About three days.

### Steps

1. **[part A] N8 and the optional section (Q4).** In `core/prompt.py`, `type Pairs` becomes
   `type Sections = tuple[tuple[str, str], ...]`; `core/views.py` declares
   `type Rows = tuple[tuple[str, str], ...]` of its own and drops
   `from aidm.core.prompt import Pairs`. `core/prompt.py` also gains, under `sections`:

   ```python
   def section_if(title: str, body: str) -> Sections:
       """One prompt section, or none when the body is empty."""
       return ((title, body),) if body else ()
   ```

   `-> Sections` (heading, body): `sections(parts)` (`core/prompt.py`); `_picture`
   (`app/roles.py`); `party_section` and `render_worldsmith`'s `family` parameter
   (`engines/base.py`); `master_sections`, `family_sections` and `_render`'s `family` parameter
   (`engines/seam.py`); `master_sections`, `sheet_sections`, `glossary`, `family_sections`
   (`scenes/engine.py`); `scene_sections` (`scenes/worldsmith.py`); `family_sections`,
   `master_sections` (`rooms/engine.py`); `map_sections` (`rooms/worldsmith.py`);
   `sheet_sections` (`breathless/engine.py`); `sheet_sections` (`twentyfourxx/engine.py`);
   `glossary` (`loner3e/engine.py`); `render_master`'s `engine_sections` parameter
   (`turn/run.py`); `FifthEngine.master_sections` (`tests/engines/test_seam.py`).

   `-> Rows` (label, value): `Thing.rows`, `Thing.line`'s and `Sheeted.line`'s `rows` parameter,
   `World.sheet_rows`, `character_panel`'s `rows` parameter (`engines/base.py`);
   `preview_character` (`engines/seam.py`, `breathless/engine.py`, `tunnelgoons/engine.py`,
   `twentyfourxx/engine.py`); `SurvivorSheet.rows`, `Survivor.rows` (`breathless/world.py`);
   `CrewSheet.rows`, `Crewmate.rows`, `TwentyfourxxWorld.sheet_rows` (`twentyfourxx/world.py`);
   `GoonSheet.rows`, `Adventurer.rows`, `Npc.rows`, `TunnelGoonsWorld.sheet_rows`
   (`tunnelgoons/world.py`); `Loner3eCast.rows`, `twist_pairing`'s `twists` parameter,
   `pack_meanings` (`loner3e/world.py`); `_meanings`, `twist_table` (`loner3e/engine.py`);
   `NarratorView.sheet`, `Companion.sheet` (`core/views.py`); `_companion`'s `sheet` parameter
   (`tests/app/test_roles.py`).

   Every file that imports the alias changes its import line, `Rows` coming from `core.views`:

   - `engines/base.py`: `from aidm.core.prompt import Sections, sections` and
     `from aidm.core.views import Chattiness, Panel, PanelRow, Rows, Subject`.
   - `engines/seam.py`: `from aidm.core.prompt import Sections` and
     `from aidm.core.views import Companion, Look, NarratorView, PlayerView, Rows`.
   - `breathless/engine.py`: `from aidm.core.prompt import Sections, lines_of, sentence` and
     `from aidm.core.views import DiceLook, Look, Panel, PanelRow, Rows`.
   - `twentyfourxx/engine.py`: `from aidm.core.prompt import Sections, lines_of, sentence` and
     `from aidm.core.views import DiceLook, Look, Panel, PanelRow, Rows`.
   - `loner3e/engine.py`: `from aidm.core.prompt import Sections` and
     `from aidm.core.views import DiceLook, Look, Rows`.
   - `tunnelgoons/engine.py`: the prompt import goes; `from aidm.core.views import DiceLook, Look,
     Rows`.
   - `breathless/world.py`, `twentyfourxx/world.py`, `tunnelgoons/world.py`, `loner3e/world.py`:
     the prompt import becomes `from aidm.core.views import Rows`.
   - `scenes/engine.py`, `scenes/worldsmith.py`, `rooms/engine.py`, `rooms/worldsmith.py`,
     `app/roles.py`, `turn/run.py`: `Pairs` becomes `Sections` in the existing
     `from aidm.core.prompt import ...` line.
   - `tests/app/test_roles.py`: the prompt import goes; `from aidm.core.views import Companion,
     NarratorView, Rows, Subject`.
   - `tests/engines/test_seam.py`: `from aidm.core.prompt import Sections`.

   Then `section_if` replaces the starred idiom at its four section sites: `_picture`
   (`app/roles.py`), `SceneEngine.master_sections` twice (`scenes/engine.py`),
   `TwentyfourxxEngine.sheet_sections` (`twentyfourxx/engine.py`). The fifth site is rows, not
   sections: `TwentyfourxxWorld.sheet_rows` (`twentyfourxx/world.py`) ends instead with

   ```python
   rows = self.player.rows()
   return (*rows, ("Gear", gear)) if gear else rows
   ```

2. **[part A] N7: `Rolled` carries its dice once.** In `core/facts.py`, drop the `rolled` field
   from `Rolled`; `kept` and `total` read `self.event.rolled`; `_rolled` returns
   `Rolled(event=event, fact=fact)`; add

   ```python
   @property
   def face(self) -> int:
       """The one die of a single roll."""
       if len(self.event.rolled) != 1:
           raise ValueError(f"{self.event.label} rolled {len(self.event.rolled)} dice, not one")
       return self.event.rolled[0]
   ```

   `rolled.rolled[0]` becomes `rolled.face` at: `luck_test` twice (`engines/base.py`),
   `BreathlessEngine.catch_breath` and `loot_check` (`breathless/engine.py`),
   `TwentyfourxxEngine._find` and `_finish`'s payout (`twentyfourxx/engine.py`). The one pool
   site, `Loner3eEngine._twist`, reads both dice instead:
   `subject_face, action_face = rolled.event.rolled`. In `tests/core/test_dice.py` the five
   `rolled.rolled` reads, on four lines, become `rolled.event.rolled`, and one new test asserts
   `face` gives the single die and raises `ValueError` on a two-die pool. `DiceEvent.rolled` is
   untouched, so the dice widgets and the engine tests that read `dice[0].rolled` need no
   change.

3. **[part A] Q3, N4, N10 and the rest of Q4 in the engines.** Helpers that mutate become
   methods:

   - `Loner3eWorld.strike(self, actor: Loner3eCast, opponent: Loner3eCast, outcome: Outcome) ->
     Struck` (`loner3e/world.py`) replaces `_strike`, with

     ```python
     @dataclass(frozen=True, slots=True)
     class Struck:
         """One exchange of a conflict: what it cost, and who lost it, if anyone."""

         facts: list[Fact]
         loser: str = ""
     ```

     The world writes no note: `Loner3eEngine.roll` adds
     `draft.note(DEFEAT_NOTE.format(name=struck.loser))` when `struck.loser`, and opens the
     conflict `PendingDecision` when it is empty.
   - `Loner3eWorld.check_conflict(self, actor, opponent: Loner3eCast | None) -> None` replaces
     the free `_check_ready`.
   - `Roll.faces(self) -> tuple[tuple[int, ...], tuple[int, ...]]` on the loner3e `Roll`
     (`loner3e/tools.py`, which already imports from `loner3e/world.py`) replaces `_pair`: it
     returns the chance faces and the risk faces, and `Loner3eEngine.roll` calls `roll_pool`
     twice with the same reasons and labels as today.
   - `BreathlessEngine._pool` becomes a method and stops spending the stunt;
     `BreathlessEngine.roll` calls `actor.require_sheet().spend_stunt(actor.name)` under
     `if args.stunt:` immediately after `_pool` and before `roll_pool`, so the refusal still
     fires before any die is rolled.
   - `Adventurer.level_decision(self) -> PendingDecision` (`tunnelgoons/world.py`) replaces the
     free `_level_decision`; `level_options` moves from `tunnelgoons/tools.py` to
     `tunnelgoons/world.py` (a public function after the classes) because `tools.py` imports
     `world.py`, and the engine's import of it goes.
   - `Turn.landed(self) -> bool` (`turn/run.py`, beside `told`, `handed_over` and `narrates`)
     replaces `_landed` in `app/roles.py`; `Roles.master` calls `turn.landed()`.

   N4: `engines/base.py` gains, above `Sheeted`:

   ```python
   class Sheet(Mutable):
       """What a person's dice are written on."""

       def rows(self) -> Rows:
           return ()
   ```

   `Sheeted[S: BaseModel]` becomes `Sheeted[S: Sheet]` and gains
   `def rows(self) -> Rows: return self.sheet.rows() if self.sheet is not None else ()`;
   `ItemSheet[I: Item]` and `GoonSheet` (`tunnelgoons/world.py`) inherit `Sheet`; `Survivor.rows`
   (`breathless/world.py`) and `Crewmate.rows` (`twentyfourxx/world.py`) are deleted.
   `Adventurer.rows` keeps its override (Health then the sheet's rows) and `Npc.rows` keeps its.
   The bound is a model, not a protocol, because pydantic cannot build a schema for a field whose
   type parameter is bound by a `Protocol`. One new test in `tests/engines/test_engines_base.py`:
   a `Sheeted` person with no sheet has no rows.

   N10, option B: `Hiring` stays the callable alias and `hiring()` stays the factory; only its
   `check` default stops being a lambda returning a lambda. Above the factory in
   `engines/hiring.py`:

   ```python
   def _no_check[A: BaseModel](_draft: object) -> Check[A]:
       """A write whose only bar is its own schema."""

       def unchecked(_answer: A) -> None: ...

       return unchecked
   ```

   and the parameter becomes `check: Callable[[G], Check[A]] = _no_check`. The `_draft` parameter
   is `object`, not `G`: a type parameter used once in a signature is an error under
   basedpyright's strict mode.

   Q4 in `twentyfourxx/engine.py`: `create_character` builds the kits as a list appended in named
   steps (`kits = [*pack.starting_kit, *specialty.kit]`, then `if weapon is not None:` and
   `if body is not None and body.kit is not None:`) and passes it to `items_from_kits`, which
   takes a `Sequence[Kit]`. `_finish`'s three-way diff becomes one comparison and one message:

   ```python
   owed = [None, *(member.id for member in world.sheeted_members())]
   expected = sorted(_named(actor_id) for actor_id in owed)
   given = sorted(_named(raise_.actor_id) for raise_ in raises)
   if given != expected:
       raise Refusal(
           "`job` `finish` names the player and every living hired member once each: "
           f"expected {', '.join(expected)}; given {', '.join(given) or '(nobody)'}"
       )
   ```

   where `_named(actor_id)` is "the player" for `None` and the id otherwise, a private function
   under the classes, and `Counter` leaves the module if nothing else uses it. In
   `tests/twentyfourxx/test_tools.py`, `test_finish_job_refuses_raises_that_name_the_player_twice`
   matches "given the player, the player" instead of "repeated the player"; the missing-member
   test's match still holds.

   N14: `Engine._render` (`engines/seam.py`) is deleted; `render_request` and `render_opening`
   call `render_worldsmith` directly with the same arguments.

4. **[part A] N5: one retry constant, one timeout idiom.** `Roles.master` (`app/roles.py`) loops
   `for attempt in range(RETRIES + 1)` with `if attempt == RETRIES: raise`, importing `RETRIES`
   from `app/spawn.py` alongside what it already imports. `_spawn` (`app/spawn.py`) renames its
   `timeout: float` parameter to `seconds: float` and uses `async with timeout(seconds):` around
   `process.communicate()`, matching `run_builtin` (`app/builtin.py`); `wait_for` is dropped from
   the imports and the refusal text keeps its shape.

5. **[part A] D5: pin the shallow freeze.** One test per family, asserting the authored scenario
   payload is unchanged after the world begun from it is mutated: in `tests/engines/test_scenes.py`
   for the scene family and `tests/engines/test_rooms.py` for the rooms family. Each begins a
   game, mutates the world on the state (a cast or dweller field), and asserts the `Scenario`
   object's `payload` still reads as it did. No source change; `validate_assignment` stays off.

6. **[part B] F3, F4 and F1: one publication, one `except` per boundary, one claim helper.** In
   `core/io.py`, beside `write_text`:

   ```python
   def publish(path: Path, write: Callable[[Path], None]) -> None:
       """Write beside, then replace: a reader never sees a partial file."""
       staged: Path | None = None
       try:
           path.parent.mkdir(parents=True, exist_ok=True)
           fd, name = mkstemp(dir=path.parent, prefix=f".{path.name}.")
           os.close(fd)
           staged = Path(name)
           write(staged)
           staged.replace(path)
       except OSError as broken:
           raise Refusal(f"{path.name} cannot be written: {broken}") from broken
       finally:
           if staged is not None:
               staged.unlink(missing_ok=True)
   ```

   The `mkdir` and the `mkstemp` are inside the `try`, so an unwritable directory still refuses
   rather than raising a bare `OSError`, which is what `write_text` gives today.
   `write_text(path, body)` becomes `publish(path, lambda staged: staged.write_text(body,
   encoding=ENCODING))` and keeps no `except` of its own. `_write` in `app/media.py` becomes
   `publish(path, lambda staged: staged.write_bytes(data))`. `Reader.read` (`app/speech.py`)
   passes a `write` that opens the wave file on the staged path, and its own
   `self.saves.mkdir(...)` and `.part` handling go.

   The boundary rules, one `except` each: `_read_text` (`core/io.py`) catches
   `(OSError, UnicodeDecodeError)` and refuses naming the file; `whole_text` (`core/source.py`)
   catches `(OSError, UnicodeDecodeError, PyPdfError)`; `FileStore.discard` (`core/io.py`)
   catches `OSError` and refuses; `Illustrator.illustrate` (`app/media.py`) catches
   `(HTTPError, OSError, Refusal)` and logs `LOGGER.warning("image generation failed: %s",
   failed)`; `Reader.read` (`app/speech.py`) catches `(HTTPError, OSError, Refusal, wave.Error)`
   and logs `LOGGER.warning("speech generation failed: %s", failed)` — `LOGGER.exception` leaves
   both modules. `Illustrator._generate` therefore loses its own `try`/`except` and returns
   `GeneratedImage`, not `GeneratedImage | None`; `_draw` and `_drawn_icon` drop their `is None`
   checks on it. A failed reference icon now ends the whole attempt, and the next turn retries.
   `PlaceholderIllustrator._generate` (`qa/art.py`) already returns `GeneratedImage`.

   In `app/providers.py`, `Claims` gains

   ```python
   @contextmanager
   def hold(self, key: str) -> Iterator[bool]:
       """Yields whether this caller won the claim; releases only what it won."""
       won = self._claim(key)
       try:
           yield won
       finally:
           if won:
               self._release(key)
   ```

   `Illustrator.illustrate` becomes `with self.claims.hold(key) as drawing:`, then awaits
   `self._drawn_icon(player)` (the chat avatar wants the player's icon even when the scene is
   cached), then draws when `drawing and _existing(self.saves, key) is None`.
   `Illustrator._drawn_icon` and `Reader.read` use `hold` in place of their `claim`/`release`
   pairs; `hold` is then the only caller of either, so both become `_claim` and `_release`. The
   two `claims.held` assertions in `tests/app/test_media.py` still read the set.

   Tests: in `tests/app/test_media.py`, one test cancels `illustrate` at the icon await and
   asserts a second call draws the scene; in `tests/core/test_store.py`, one test asserts a write
   that raises midway leaves the old file intact and no staged file behind, and one asserts a
   scenario whose file cannot be read is skipped rather than raised; in
   `tests/core/test_documents.py`, one asserts an unreadable document refuses with its name.

7. **[part B] N13: the CSS leaves `theme.py`.** The body of `STATIC_CSS` moves verbatim into a new
   `src/aidm/ui/theme.css`, and the constant goes. `install()` (`ui/theme.py`) reads it with
   `read_prompt(Path(__file__).parent / "theme.css")`, which caches, and keeps building the
   `:root` palette line from `NEUTRAL_PALETTE` in Python. `pyproject.toml` ships the file
   already: `[tool.hatch.build.targets.wheel] packages = ["src/aidm"]` takes every file under the
   package, as it does for `ui/dice_assets/` and `app/prompts/*.md`.

8. **[part B] Q2: one upload directory per form.** In `ui/create.py`, `ScenarioForm` gains
   `self.uploads: Path | None = None` beside `self.document`. `uploaded` creates the directory
   lazily on the first upload (`self.uploads = Path(mkdtemp())`), unlinks the previous document,
   saves the new one under it and keeps the "source reader opens a path" comment. `write` drops
   `_discard_upload` from its `finally` (the button's `remove="loading"` stays) and calls a new
   `_discard_uploads` after a successful `new_scenario`, which `shutil.rmtree`s the directory and
   sets both attributes to `None`, with the one-line reason that an abandoned page leaves one
   temp directory to the OS. A refused write keeps the document for the retry. No unit test:
   `qa/s_create.py` drives the page.

9. **[sequential after 8] D1: strict validation.** `Frozen`, `Mutable` and `Loose`
   (`core/entities.py`) gain `strict=True`, and beside `parse`:

   ```python
   def parse_json[T: BaseModel](model: type[T], raw: str | bytes) -> T:
       """Strict mode reaches a tuple field only from JSON, so text is validated as text."""
   ```

   Its body is `model.model_validate_json(raw)` under the same `except ValidationError` that
   `parse` uses to build the refusal. `decode` keeps the duplicate-key check and is still called
   wherever duplicate keys must be refused; `parse_json` does not replace it.

   Each text boundary: `_read` (`core/io.py`) reads the text, calls `decode(raw)` for the
   duplicate-key check and returns `parse_json(model, raw)`; `Library.read_scenario`
   (`core/io.py`) becomes `raw = _read_text(path)` then `parse_json(routed(decode(raw), models),
   raw)`; `read_packs` (`engines/scenes/packs.py`) reads each pack the same way as `_read`;
   `ask` (`app/spawn.py`) calls `decode(spoken.text)` then `parse_json(model, spoken.text)`;
   `ClaudeDriver.read_result` (`app/spawn.py`) uses `parse_json(_ClaudeResult, output)`;
   `_complete` (`app/builtin.py`) uses `parse_json(_Completion, raw)`; `Illustrator._generate`
   (`app/media.py`) uses `parse_json(_ImageReply, content)`.

   `Engine.restore` (`engines/seam.py`) takes the raw text, because the game has tuple fields:
   `def restore(self, raw: str) -> G`, whose body decodes once for the header and the
   duplicate-key check and then `state = parse_json(self.game, raw)`. Call sites:
   `GameService.__post_init__` (`app/runtime.py`, which passes the text it already read; step 10
   moves that line into `GameService.resume`), `_save_option` (`app/launch.py`), `Table.saved`
   (`tests/support/table.py`), and `engine.restore(decode(...))` in `tests/core/test_store.py`,
   `tests/engines/test_integrity_boundaries.py` (three), `tests/engines/test_seam.py`,
   `tests/loner3e/test_engine.py`, `tests/turn/test_decisions.py`, all of which pass the text.

   A master's tool call arrives already decoded, so `master_tool`'s `call` (`core/tools.py`)
   re-encodes it once: `parse_json(args, json.dumps(raw))`. Everything else keeps `parse`:
   `Game.commit`, `routed`, `SceneWorld.opening`, `RoomWorld.opening`, `BreathlessEngine.answer`'s
   `TakeLoot` (its option args carry no tuple).

   `Settings` is a `BaseSettings` and stays lax, but its six nested models inherit `Frozen` and
   read env strings, so `config.py` imports `from pydantic import ConfigDict, Field, SecretStr,
   model_validator` and gains, above `ProviderConfig`:

   ```python
   class Configured(Frozen):
       """Settings arrive as env strings, so these read them lax; every other model is strict."""

       model_config = ConfigDict(strict=False)
   ```

   `ProviderConfig`, `RoleConfig`, `MediaConfig`, `SpeechConfig`, `RoleSettings` and `Providers`
   inherit `Configured`.

   Tests that fake a JSON round trip in Python mode are the ones that break, and each becomes a
   real one: `stub_worldsmith` (`tests/support/table.py`) validates
   `model.model_validate_json(json.dumps(answer))`; `"packs": [SRD_PACK]` becomes a tuple in
   `tests/engines/test_scene_bar.py`; `TwentyfourxxWorld.model_validate(world.model_dump(...))`
   becomes `model_validate_json(world.model_dump_json())` in `tests/twentyfourxx/test_world.py`;
   the two `model_validate` calls in `tests/app/test_master_tools.py` become
   `model_validate_json`; the refusal text asserted in `tests/app/test_builtin.py` is now "Input
   should be an object", and the one in `tests/turn/test_decisions.py` is "Extra inputs are not
   permitted". Two new tests in `tests/engines/test_integrity_boundaries.py`: a `Frozen` model
   refuses `"4"` for an int and `"false"` for a bool, and a JSON array reaches a tuple field
   through `parse_json`. This step was tried end to end before it was written: with exactly these
   changes the suite is green.

10. **[sequential after 9] N1, N2, F2, F5 and N14: how a session is built and guarded.** In
    `app/runtime.py`:

    - `GameService` loses `__post_init__`; `state: AnyGame` becomes a plain field, after `store`
      and before the defaulted fields, and a classmethod builds it:

      ```python
      @classmethod
      def resume(
          cls,
          target: LaunchTarget,
          scenario: AnyScenario,
          character: AnyCharacter,
          engine: AnyEngine,
          roles: Roles,
          store: FileStore,
          *,
          media: Illustrator | None = None,
          reader: Reader | None = None,
          interjections: bool = True,
      ) -> Self:
          """The filed save if there is one, else a fresh opening."""
      ```

      Its body reads `store.read(target.slug)` and takes either
      `engine.begin(target.scenario_id, scenario, character)` or
      `_resumable(engine.restore(saved), target, scenario, character)`, where `_resumable` is a
      private module function carrying today's two refusals. `GameService._begin` and
      `_resumable` as methods go; `restart` calls `self.engine.begin(self.target.scenario_id,
      self.scenario, self.character)`.
    - `GameService.stop` and `settled` are replaced by
      `async def close(self) -> None`, which calls `hush()`, cancels a snapshot of `_background`
      and awaits `gather(*tasks, return_exceptions=True)`. `_retain`'s done callback becomes a
      `_settled(task)` method that discards the task, ignores `CancelledError`, and logs anything
      else with `LOGGER.exception`.
    - `GameService.open` drops its `if not self.unopened(): return` guard (`Runtime.open` below
      holds it); `unopened` stays, because `GamePage.build` reads it to decide whether to schedule
      the opening.
    - `Runtime` loses `__post_init__`, `playing`, `busy_refusal`, `play_refusal` and
      `scenario_models`, and becomes:

      ```python
      @dataclass(slots=True)
      class Runtime:
          settings: Settings
          spawn: Callable[[Settings], Spawner] = RoleRunner
          admitted: GameService | None = field(default=None, repr=False)
          _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
          engines: dict[EngineId, AnyEngine] = field(init=False)
          spawner: Spawner = field(init=False)
          library: Library = field(init=False)
          store: FileStore = field(init=False)

          @classmethod
          def start(cls, settings: Settings, spawn: Callable[[Settings], Spawner] = RoleRunner) -> Self:
              """Reads every engine's prompts and packs, then mounts the library and the saves."""
      ```

      `start` builds the instance, sets `engines = build_engines()` and calls `_mount()`;
      `_mount` sets `spawner = self.spawn(self.settings)`, `library` and `store`, so
      `reload_settings` can no longer forget the injected spawner.
    - Admission:

      ```python
      @asynccontextmanager
      async def admit(self, session: GameService) -> AsyncIterator[None]:
          """One writer at a time: two turns on one save is the only failure that costs a game."""
      ```

      It refuses with "The settings changed. Reload this page before you play on." when
      `self._sessions.get(session.slug) is not session`, refuses with
      `f"A turn is in flight in {self.admitted.slug!r}."` when `admitted` is not `None`, sets
      `admitted` and clears it in `finally`. The public entry points each enter it before their
      first await: `async def open(self, session)` (returning at once when
      `not session.unopened()`), `async def play(self, session, answer: Answer)`,
      `async def act(self, session, action: Slug, words: str)`,
      `async def restart(self, session)`. `async def reload_settings(self)` raises the same
      in-flight refusal when `admitted` is not `None`, then re-reads the settings, re-mounts,
      awaits `session.close()` for every session and clears `_sessions`.
    - `published_tools` and `call` read `self.turn`, a property returning
      `None if self.admitted is None else self.admitted.turn`.
    - `_open` builds the session through `GameService.resume(...)`, `Illustrator.open(...)` and
      `Reader.open(...)`, and derives the scenario models itself:
      `{engine_id: engine.scenario for engine_id, engine in self.engines.items()}`.

    `open_illustrator` and `open_reader` become classmethods on their own classes:
    `Illustrator.open(cls, settings: Settings, store: FileStore, slug: str, *, style: str,
    icon_dirs: tuple[Path, ...]) -> Self | None` (`app/media.py`) and
    `Reader.open(cls, settings: Settings, store: FileStore, slug: str, *, voice: str) -> Self |
    None` (`app/speech.py`), each returning `None` when the feature is off and `cls(...)`
    otherwise. Their tests in `tests/app/test_media.py` and `tests/app/test_speech.py` call the
    classmethods.

    `LauncherCatalog.read(cls, library, store, engines)` (`app/launch.py`) drops its
    `scenario_models` parameter and derives the mapping from `engines[id].scenario` itself;
    callers `home_page` (`ui/app.py`), `scenario_page` (`ui/create.py`) and `_catalog`
    (`tests/app/test_launcher.py`) drop the argument.

    In `ui/game.py`: `refuse_play` is deleted; `GamePage.play(self, answer: Answer) -> bool` sets
    `own_move` and returns `await self._run(lambda: self.runtime.play(self.session, answer))`;
    `answered(self, option_id: str) -> None` is the decision widget's callback and awaits
    `self.play(Answer(option_id=option_id))`; the `accept` closure becomes
    `on_click=partial(self.play, Answer(text=proposed.proposal))`; `_send` is deleted, and
    `submit` and `act` each read the composer, return on empty, and clear it through a new
    `_clear_box()` (the two lines and the Quasar comment `_clear_spent_draft` already carries) when
    the call returned true; `act` calls `self.runtime.act(self.session, action.id, typed)`;
    `restart` runs through `_run` so an admission refusal still reaches the player —
    `await self._run(partial(self.runtime.restart, self.session))`, then `self.poll_turn()`, then
    `await self._open()`; `_open` becomes
    `await self._run(lambda: self.runtime.open(self.session))` with its own guard gone. `Observed`
    becomes `@dataclass(frozen=True, slots=True, kw_only=True)`, and its two construction sites
    (`Observed.of` and `GamePage.__init__`) pass keywords.

    In `ui/app.py`: `start()` calls `Runtime.start(settings)`; `apply_settings` becomes
    `async def apply_settings() -> str | None` that awaits `runtime.reload_settings()` and returns
    `str(refused)` from `except Refusal`; the shutdown hook also registers `runtime.close`, a new
    `async def close(self) -> None` on `Runtime` that awaits every session's `close`. In
    `ui/settings.py`, `SettingsForm.apply` is `Callable[[], Awaitable[str | None]]`,
    `SettingsForm.save` is `async` and awaits it, and `settings_page`'s parameter follows.

    In `qa/`: `QaRuntime` is deleted — `server.py` builds `Runtime.start(settings, lambda _:
    agents)`, which keeps the scripted roles across a reload; `_draw_offline` sets
    `runtime_module.Illustrator = PlaceholderIllustrator` and its `open_placeholder` goes;
    `agents.py`'s `_engine_id` reads `self._runtime().turn` instead of `playing()`.

    Every `Runtime(` in `tests` becomes a `Runtime.start(...)` with a factory:

    - `tests/support/table.py` `open_table`: `Runtime.start(settings, lambda _: spawner)`.
    - `tests/app/test_launcher.py`, four sites: `Runtime.start(settings, lambda _:
      ScriptedSpawner()).session(TARGET)` in `_opening_state`; `Runtime.start(settings, lambda _:
      spawner)`; and `Runtime.start(offline_settings(tmp_path, scenarios), lambda _: spawner)`
      twice.
    - `tests/app/test_mcp.py`: `Runtime.start(offline_settings(tmp_path), lambda _: master)`.
    - `tests/app/test_game_service.py`, two sites: `Runtime.start(updated(offline_settings(),
      saves_dir=tmp_path), lambda _: ScriptedSpawner())` and the same with `lambda _: spawner`.

    The rest of the tests: `tests/support/table.py`'s `play_turn` and `take` go through
    `table.runtime.play(table.service, ...)` and `table.runtime.act(table.service, action,
    words)`, and `drain` awaits `service.close()`. `tests/app/test_game_service.py` opens through
    `await table.runtime.open(table.service)` (including the twice-opened test) and awaits
    `reload_settings`. `tests/app/test_mcp.py` plays through `runtime.play(service, Answer(...))`.
    The two admission tests move out of `tests/ui/test_settings.py` into
    `tests/app/test_game_service.py` and are rewritten against `admit`: a page holding an evicted
    session is refused, and a reload under a turn in flight is refused. Three new tests there: two
    concurrent `runtime.play` calls on different sessions cannot both open a turn; a background
    task that fails is logged and `close` leaves no live task; `reload_settings` keeps the injected
    spawner.

11. **[sequential after 10] D2 and N3: the dice and the event loop.** `Turn.begin` (`turn/run.py`)
    stores `rng=deepcopy(rng)`, so a failed turn spends none of the game's dice. In
    `app/runtime.py`, `GameService._turn` sets `self.rng.setstate(turn.rng.getstate())`
    immediately after its `self.save(state)`, with the one-line reason that the dice advance with
    the turn. `GameService` gains `chatter: Random = field(default_factory=Random)` and `_speaks`
    rolls it instead of `rng`, so companion chatter cannot move gameplay rolls.
    `Runtime.new_scenario` awaits `asyncio.to_thread(given_text, meta.premise, document,
    self.settings.source_max_chars)`.

    Tests: in `tests/app/test_game_service.py` the six tests that seed an interjection
    (`test_a_member_who_passes_the_d10_speaks_after_the_turn`,
    `test_nobody_passing_the_d10_spawns_no_narrator`,
    `test_a_turn_that_lands_first_drops_the_interjection`,
    `test_an_answer_with_no_lines_records_nothing`,
    `test_a_new_turn_silences_the_member_still_speaking`,
    `test_reload_settings_cancels_an_evicted_sessions_background_task`) set
    `service.chatter = Random(...)` with the seed they used to give `rng`. Re-seed
    `tests/tunnelgoons/test_play.py`'s `FIGHT_SEED` if its second turn's dice move: it is the one
    play test that leaves interjections on across two turns. One new test: a turn whose narrator
    fails leaves `service.rng` where it was.

12. **[sequential after 11] N11: the comment and naming sweep.** Shorten to one line each: the
    comment above `create_button` in `CharacterForm.build` (`ui/create.py`); the scroll-area
    comment in `GamePage.build`, the scene-art comment in `scene_header` and the portrait comment
    in `sidebar` (`ui/game.py`); the two-line comment above the palette in `install()`
    (`ui/theme.py`). `Refusal`'s docstring (`core/entities.py`) becomes one line. Rename the
    single-letter names: `n, f` in `_shown` (`ui/settings.py`); `p` in `read_scenarios` and
    `read_characters` (`core/io.py`); `e` in `sound_state`, `scrolled`, `dictated`,
    `dictation_failed` and the tabs lambda in `build` (`ui/game.py`); `e` in `RoomWorld.map_so_far`
    (`rooms/world.py`); `n` in `creation_steps` and `create_character`
    (`tunnelgoons/engine.py`). `core/io.py` imports `re` and calls `re.fullmatch`, like every
    other module.

## Phase 2: D4, one explicit pack selection

About a day, alongside pack authoring.

### Steps

1. **The selection value.** `core/model.py` gains, above `Scenario`:

   ```python
   class PackSelection(Frozen):
       """The table sets one game plays by: the primary first, then what supplements it."""

       primary: Slug
       supplements: tuple[Slug, ...] = ()

       def ids(self) -> tuple[Slug, ...]:
           return (self.primary, *self.supplements)
   ```

   It lives in `core/model.py`, not in `engines/scenes/packs.py`, because `core` owns the
   scenario envelope and may not import an engine family; `engines/scenes/packs.py` imports it.
   A validator refuses a supplement equal to the primary or repeated.
   `Scenario.packs: PackSelection | None = None` and `Game.packs: PackSelection | None = None`
   replace the two `tuple[Slug, ...]` fields; `Scenario._unique_packs` and `Game._playable_game`
   go, because the selection's own validator is the uniqueness check now. `None` is what an engine
   that ships no packs stores, which today is the tunnelgoons scenario, so the field stays
   optional at the seam: `Engine.author`'s and `Engine.build_scenario`'s `packs` parameters
   (`engines/seam.py`) become `PackSelection | None`, and `RoomEngine.author`
   (`engines/rooms/engine.py`) passes what it was given.

2. **The engine reads one selection.** In `scenes/engine.py`:

   - `SceneEngine.selected(self, packs: PackSelection | None) -> PackSelection` refuses `None`
     with "a {self.id!r} game needs a table set" and is the one narrowing point; it replaces
     `first_pack`, whose callers (`BreathlessEngine.hire_prompt`, `TwentyfourxxEngine.hire_prompt`
     and `hire_check`) become `self.packs[self.selected(draft.packs).primary]`.
   - `SceneEngine.validate` refuses a `None` selection and refuses ids the engine does not
     install, naming them.
   - `pack_content(self, selection: PackSelection, *, include=..., exclude_defaults=...)` takes
     the selection in place of `picks` and dumps `selection.ids()`.
   - `guidance(self, selection: PackSelection | None, /) -> str` keeps the seam's optional, and
     the two implementations that read packs (`Loner3eEngine.guidance`,
     `BreathlessEngine.guidance`) open with `chosen = self.selected(selection)` and pass `chosen`
     to `pack_content`; `TwentyfourxxEngine.guidance` ignores its parameter as it does today.
   - `SceneEngine.select(self, primary: Slug, supplements: Sequence[Slug]) -> PackSelection`
     builds one at authoring time, refusing an uninstalled pack and refusing an id that two
     selected packs both define.
   - `TwentyfourxxEngine.resolve_skill` searches the selected packs only, and its refusal names
     them.

   The chain, page to prompt: `ScenarioForm.write` (`ui/create.py`) builds the `PackSelection`
   from its two selects, or `None` for an engine that offers no packs, and passes it to
   `Runtime.new_scenario(engine_id, meta, document, packs: PackSelection | None, character_id)`
   (`app/runtime.py`), which hands it to `engine.author(meta, source, packs, ...)`;
   `SceneEngine.author` passes it to `self.guidance(packs)` and on to `build_scenario`. Mid-game the selection comes from the state instead:
   `SceneEngine.render_next` calls `self.guidance(draft.packs)`, and `Loner3eEngine.glossary`
   calls `self._meanings(self.selected(state.packs), member)`, whose signature becomes
   `_meanings(self, selection: PackSelection, sheet: Loner3eCast) -> Rows`.

   `Engine.begin` (`engines/seam.py`) keeps `"packs": scenario.packs`: it hands the model
   instance straight to `parse`, which strict Python mode accepts.

3. **The character carries its pack.** `Character.pack: Slug | None = None` (`core/model.py`);
   each scene engine's `create_character` fills it from `picked(picks, "pack")`, and
   `TunnelGoonsEngine.create_character` leaves it `None`. `SceneEngine.new_game` refuses a
   character whose `pack` is not in the scenario's selection, naming both. One test per scene
   engine, in the file that engine already has: `tests/loner3e/test_create.py`,
   `tests/twentyfourxx/test_create.py`, and `tests/breathless/test_engine.py` and
   `tests/tunnelgoons/test_engine.py`, which have no `test_create.py`. One more in
   `tests/engines/test_scenes.py` for the refusal.

4. **The create page picks one primary and any supplements.** In `ui/create.py`,
   `ScenarioForm.form` replaces the single multi-select with a `ui.select` for the primary
   (defaulting to the SRD pack) and a `multiple=True` select for the supplements, which excludes
   the primary; `write` builds the `PackSelection` and hands it to `Runtime.new_scenario`, and
   refuses with a notification when no primary is chosen.

5. **Every reader of the field.** Beyond step 2's engine sites:
   `tests/twentyfourxx/test_engine.py` and `tests/breathless/test_engine.py` assert
   `state.packs == PackSelection(primary=SRD_PACK)` in place of `== (SRD_PACK,)`;
   `tests/engines/test_scene_bar.py` passes `"packs": PackSelection(primary=SRD_PACK)` — a model
   instance, because strict Python mode takes no dict for a model field;
   `tests/app/test_master_tools.py` needs no change, since it already passes `table.state.packs`
   straight into `engine.author`, whose parameter is now the same type.

   The shipped content is rewritten in the new shape: `scenarios/buried-keep/world.json`
   (tunnelgoons), `scenarios/drowned-road/world.json` (breathless),
   `scenarios/silent-relay/world.json` (twentyfourxx), `scenarios/whispering-vault/world.json`
   (loner3e), and the four `characters/kael/<engine>.json`. There is no source document to
   re-author them from, so each file is edited in place: `"packs": ["srd"]` becomes
   `"packs": {"primary": "srd", "supplements": []}`, the tunnelgoons scenario's empty list becomes
   `null`, and each scene-family character gains `"pack": "srd"`. Then run `uv run aidm`, write
   one new scenario through the create page and start it, to prove the authored path.

6. **Rebuild the goldens.** Regenerate as "How to work" says. Expected: only the pack lines of
   the four `tests/core/fixtures/prompts/<engine>/master.txt` and of any worldsmith prompt that
   renders `SELECTED PACK CONTENT`; the four `tests/core/fixtures/turn/*.json` and every
   `narrator.txt` and `interjection.txt` are byte-identical. Any other change is a bug. Four new
   tests: two packs that both define one id are refused at selection; a character from an
   unselected pack is refused at launch; a skill installed but not selected is refused by
   `resolve_skill`; a save naming a pack the engine no longer installs is refused on resume — the
   first three in `tests/engines/test_scenes.py`, the last in
   `tests/engines/test_integrity_boundaries.py`.
