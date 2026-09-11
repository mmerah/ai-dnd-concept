# PLAN: the 41 accepted proposals in three phases, four commits

Phase 1 renames and respells (no behaviour change). Phase 2 fixes the edges and the layers.
Phase 3 reshapes the engines, as two commits: part A the seam and the families, part B the rules
code. Deviations from the proposals as decided, each because the tools refused the letter of the
proposal or the letter did not fit the code:

- 27: a narrowing `world_of` override per engine instead of a fourth type parameter
  (basedpyright rejects a bound that names another parameter).
- 13: `ItemSheet` stays generic; `Survivor` and `Crewmate` get a two-line `drop_item` each (the
  same rule blocks a shared carrier class).
- 7: a `field_validator` for `ChangeStress.amount` (`Field` has no `ne`).
- 12: `_generate(words="")` becomes one `_grow(*, words, mark)` with both values explicit, not
  two methods; the flag is gone either way.
- 28: `kill` by id on `RoomWorld` means the master can kill the player in tunnelgoons through
  the `kill` tool, as it already can in the scene engines. The tunnelgoons roll needed the by-id
  path for the player at 0 Health anyway.
- Names: `finish_job` → `close_job`, `maimed()` → `maim()`, `rested()` → `catch_breath()`; the
  hire description stays `HIRE_TOOL` because `HIRE` names the request; `drop_item` is listed by
  the two backpack engines rather than detected from the member class.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset, after `uv sync --all-groups --locked`
once:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each names its files and symbols; there are no line numbers, so find
   the symbol. Where a step gives a signature or a class, that is the exact shape.
2. A rename applies across `src`, `tests` and `qa` in the same step. Change a shape and its tests
   in the same step. One test per new behaviour. A test of a deleted behaviour is deleted with it.
3. Golden files live in `tests/core/fixtures/`. Rebuild them only in the step that says so:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   then read every changed fixture line against the step's list. Any other change is a bug.
4. One commit per phase (two for phase 3), full check green, reviewed adversarially against the
   staged diff first. `ruff format --check` formats the Python fences in this file, so run
   `uv run ruff format PLAN.md` after editing it. The game stays playable at the end of every
   commit: `uv run aidm`, open each shipped scenario, take a turn.
5. `PROGRESS.md` gets one entry per commit: `src`, `tests` and `qa` line counts before and after
   (`find src -name '*.py' | xargs cat | wc -l`; at the start 9,827 / 9,146 / 1,786), decisions
   made off-plan, and refuted review findings with the reason. Phase 1 creates the file.
6. Delete, do not preserve. No compatibility path reads an old save. No constant, helper or test
   stays for a caller that is gone.
7. The standing rules hold: imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond
   the `Game[P]` bound; `__init__.py` files stay empty; tests never start a process; `Refusal` is
   the one message-bearing exception; only code changes state or rolls dice; the narrator reads
   revealed facts only.

## Phase 1: names and spelling

No behaviour changes. About a day, mostly mechanical.

### Steps

1. Renames, old → new, with every call site:
   - `Sheeted.dice()` → `require_sheet()` (`engines/base.py`).
   - The `roll` tool's args: `Question` (`loner3e/tools.py`), `Check` (`breathless/tools.py`),
     `ActionRoll` (`tunnelgoons/tools.py`) → `Roll`; the loner3e resolver's parameter
     `action: Question` → `args: Roll`.
   - `Loner3eSheet` → `Loner3eCast` (`loner3e/world.py`); `Sheet` → `CrewSheet`
     (`twentyfourxx/world.py`); `Abilities` → `GoonSheet` (`tunnelgoons/world.py`).
   - `engines.base.Counter` → `Gauge`; `core/entities.py` imports `collections.Counter` under its
     own name (drop `as Tally`).
   - `Library` (`core/io.py`): the `name: Slug` parameter of its public methods → `scenario_id`
     or `character_id`; `_check_filed`'s third parameter → `filed_under`; `FileStore.load/save`
     → `read/write`.
   - `Objection` → `Check` (`core/model.py`); every parameter `refusal: Objection[..]` → `check:
     Check[..]` (`WorldsmithAnswer`, `spawn.ask`); `playable` → `check` (`Engine.author`,
     `compose`, `Runtime.new_scenario`); `Hiring.hire_bar` → `hire_check`; the word "bar" leaves
     the docstrings of `scene_unmet`, `Engine.build_scenario` and `RoomWorld.attach`.
   - `PlayerView.prompt` → `decision`; `CreationStep.prompt` → `label`; `Exchange.prompt`,
     `Turn.prompt` and the `prompt=` keyword of `Engine.close` → `words`. `PendingDecision.prompt`
     and the model prompt keep their name.
   - `Generation.brief` → `detail`; `Outcome.name` → `id`; `SaveOption.scenario_title` /
     `character_title` → `scenario_label` / `character_label`.
   - `ScenarioForm.took` → `uploaded` (`ui/create.py`); `RoomWorld.begin` → `opening`;
     `TwentyfourxxEngine.kill(..., _rng)` → `rng`; `BreathlessEngine.complications` →
     `_complications`; `Loner3eEngine.meanings` → `_meanings`; `_meanings` and `twist_table`
     return `Pairs`.
   - `SceneEngine.leaving(self, _state: G)` → `_draft` (the base body uses nothing; ruff `ARG`)
     and `Loner3eEngine.leaving(self, state)` → `draft`; the docstring on the hook says it may
     change the draft.
   - Delete `Thing.fact(narrate=...)`: `told=self.known`.
   - Delete `GameService.engine_title` and `engine_id`; `ui/game.py` and `tests/ui/test_game.py`
     read `session.engine.title` and `session.engine.id`.
2. Property rule. CLAUDE.md "Code" gains: "A property takes no argument, has no side effect and
   reads its own fields; anything else is a method." `Person.hired` and `hireable` (and the
   `Sheeted` overrides) become properties, call sites drop the `()`; `Gear.detail()` →
   `Gear.notes()`.
3. Facts as lists in rules code: `SceneEngine.leaving`, `Engine.answer` and
   `BreathlessEngine.answer` return `list[Fact]`; `SceneEngine.depart` builds
   `facts = [*self.leaving(draft), *self.install(draft, scene)]` and returns `tuple(facts)`;
   `Turn._consume` wraps the `Play` boundary: `tuple(engine.answer(copy, option, dice))`.
4. Tool descriptions as constants beside their args model, named after the tool: `ROLL` in the
   four `tools.py`; `CATCH_BREATH`, `LOOT_CHECK`, `TEST_LUCK` (`breathless/tools.py`); `LEVEL_UP`
   (`tunnelgoons/tools.py`); `TEST_LUCK`, `JOB` (`twentyfourxx/tools.py`). Text byte for byte as
   today. `HIRE_TOOL` stays. `core/tools.py` gains `class NoArgs(Frozen): pass` (no docstring:
   pydantic would publish it as the schema's `description`); `rest` uses it.
5. `loner3e/tools.py` keeps args models and descriptions only: `TOLD`, `AND_AT`, `BUT_AT`,
   `Outcome`, `outcome_for`, `twist_pairing`, `pack_meanings` move to `loner3e/world.py` (public
   functions after the classes); `twist_note` and `defeat_note` become the format strings
   `TWIST_NOTE` and `DEFEAT_NOTE` in `loner3e/engine.py`.
6. Spelling:
   - `type TagKind`, `type Ability`, `type Boost`, `type AbilityScores`; `Slug` stays
     `Annotated[...]` with the comment "assignment, not `type`: pydantic reads the metadata".
   - `Game.notes` and `PendingOption.args` use `Field(default_factory=...)`.
   - `LOGGER` is the first line after the imports in `core/io.py`, `app/spawn.py`, `ui/game.py`.
   - The seven underscored constants (`_STEP_COPY`, `_DICTATION_FAILURES`, `_STATIC_CSS`,
     `_EVENT`, `_BLANK_LINE`, `_LINE_BREAK_HYPHEN`, `_SAVE_SLUG_PATTERN`) lose the underscore.
   - `->` → `→` in `Gauge.change`, `luck_test` and `TwentyfourxxEngine._finish`.
   - `Pairs` moves to `core/prompt.py`; `core/views.py` imports it from there.
7. Docstrings: `TwentyfourxxWorld.take_lead` reads "The new lead keeps their id; the dead lead is
   filed in the cast under theirs."; the "Free:" / "free because" clauses leave `settled`,
   `check_scene`, `post_bearer` and `scene_key`.
8. Ceremony:
   - `Engine.compose` becomes a free `compose(...)` in `engines/seam.py`, under the classes.
   - `render_master` drops `scenes`; it reads `state.log`.
   - `run_builtin` passes `tools` through; the `role == "master"` test goes.
   - `Roles.master` is one `for attempt in (1, 2)` loop; `_landed` no longer logs, the loop does.
   - `turn/run.py`: `PAUSED_TO_ASK = 'The rules paused play to ask the player: "{prompt}" '`.
   - `ui/theme.py`: `_install` → `install()`, no `@cache`; `start()` in `ui/app.py` calls it once
     before `ui.run`; `apply()` no longer installs. (NiceGUI's `add_css(shared=True)`,
     `add_head_html(shared=True)` and `default_props` need no page context.)
   - `LauncherCatalog.read`: the save loop body becomes `_save_option(slug, raw, engines, titles,
     played_by) -> SaveOption | None`.
   - `Engine` gains `family_dir: Path`; `__init__` reads `family_dir / "rules.md"` and
     `family_dir / "worldsmith.md"`; `RoomEngine` and `SceneEngine` set `family_dir =
     Path(__file__).parent`; delete `WORLDSMITH_PROMPT`, `RULES_PROMPT`, `family_prompt`,
     `worldsmith_prompt`.
9. Regenerate the goldens. Expected: `turn/breathless.json`, `turn/tunnelgoons.json`,
   `prompts/breathless/narrator.txt` and `prompts/tunnelgoons/narrator.txt` change on `->` → `→`
   only. Everything else, the schemas included, is byte-identical.

### Done when

- `grep -rn "dice()\|Loner3eSheet\|class Sheet(\|class Abilities\|Counter(Mutable)\|Objection\|hire_bar\|\.took\b\|engine_title\|narrate=\|hired()\|hireable()\|_STEP_COPY" src tests qa` prints nothing; `grep -rn "\.prompt\b" src` prints only `PendingDecision.prompt` reads; `grep -n "@cache" src/aidm/ui/theme.py` prints nothing.
- Full check green; goldens changed as step 9 says; `PROGRESS.md` exists with the phase 1 entry.

## Phase 2: edges and layers

About a day.

### Steps

1. `app/spawn.py` `_spawn`: `create_subprocess_exec` under `except OSError as failed: raise
   Refusal(f"the {role} could not be started: {failed}") from failed`; `wait_for` under
   `except TimeoutError: raise Refusal(f"the {role} answered nothing in {timeout:.0f}s")`.
   `app/builtin.py` `run_builtin`: the same `TimeoutError` conversion around `timeout(...)`.
   Then every `except (OSError, Refusal)` (`app/roles.py` three, `app/runtime.py` two,
   `ui/create.py`, `ui/game.py`) becomes `except Refusal`; `ui/game.py` `_run` shows
   `str(error)` without the type name.
2. `core/source.py` `whole_text`: `except (UnicodeDecodeError, PyPdfError) as broken: raise
   Refusal(f"{path.name} cannot be read: {broken}") from broken` (`from pypdf.errors import
   PyPdfError`).
3. `Refusal` docstring: "A message a role or the player is meant to read. Any other exception is
   a bug. A `ValueError`, so a check helper may raise it inside a validator too." `check_filing`
   raises `Refusal`. CLAUDE.md "Code": "Inside a validator raise `ValueError` or call a check
   helper; `parse` turns either into the refusal."
4. `core/entities.py`: `def parse_json[T: BaseModel](model: type[T], raw: str | bytes) -> T`
   beside `parse`, same `except ValidationError`. `app/media.py` `_generate` uses it for
   `_ImageReply`; `app/spawn.py` `ClaudeDriver.read_result` uses it for `_ClaudeResult` (its
   refusal text becomes `parse`'s). `media._decode` wraps `b64decode` with `except binascii.Error
   as broken: raise Refusal(...)`. The two `except ValueError` in `spawn.py` (`final_message`,
   `_decodes`) become `except json.JSONDecodeError`. Media catches `(HTTPError, Refusal)`;
   speech catches `(HTTPError, OSError, Refusal, wave.Error)` with the one-line reason "a full
   disk is not a bug" on `OSError`.
5. `SceneEngine.__init__`: after `read_packs`, `if SRD_PACK not in self.packs: raise
   ValueError(f"the {self.id!r} engine ships no {SRD_PACK!r} pack")`; `srd_pack()` returns
   `self.packs[SRD_PACK]`. `Loner3eEngine.__init__`: after `super().__init__()`, `ValueError`
   when the SRD pack has `twist_subjects is None`; `twist_table` no longer refuses.
6. Argument-shape rules move onto the args models: `model_validator`s on `NextScene` ("a pursuit
   or a complication, not both"), `LevelUp` ("both an ability and a boost, or neither"),
   `ChangeTags` ("at least one gained or lost tag"), `Drive` ("a goal, a motive or a nemesis");
   `@field_validator("amount")` on `ChangeStress` ("a non-zero amount"). The same checks leave
   `SceneEngine.next_scene`, `TunnelGoonsEngine.level_up`, `Loner3eCast.change_tags` and `drive`,
   `Survivor.change_stress`.
7. Boundaries: `read_packs` returns `dict[Slug, P]` keyed by `content_id(path.stem)`;
   `SceneEngine.packs: dict[Slug, K]`. `ScenarioForm.write` narrows `packs = tuple(content_id(pick)
   for pick in self.packs.value)` and `character_id = content_id(self.character.value)` before
   the runtime call; after `new_scenario` returns or refuses, it removes the upload directory
   (`shutil.rmtree(self.document.parent)`) and sets `self.document = None`, so a retry does not
   read a deleted file.
8. `SceneDraft` and `NextDraft` become `Mutable`; `SceneEngine.new_game` keeps its one
   `model_copy(deep=True)` (comment: "a restart reopens the same scenario file");
   `SceneEngine.install` installs the draft as handed and its comment goes.
9. `app` stops importing `engines.base`. `core/views.py`: `type Chattiness = Literal["quiet",
   "normal", "chatty"]` moves here from `engines/base.py` (`Person.chattiness` imports it from
   `core.views`), and
   ```python
   class Companion(Subject):
       """A party member as the app sees them: what they show, and how readily they speak."""

       sheet: Pairs
       chattiness: Chattiness
   ```
   `Engine` (seam): `def companions(self, state: G) -> tuple[Companion, ...]` built from
   `self.world(state).members()` (`id`, `name` → `label`, `brief` → `detail`, `rows()`,
   `chattiness`). `Roles.interject(self, engine, state, member: Companion)` passes `member` and
   `member.sheet` to `render_interjection`; `GameService.interject` picks from
   `engine.companions(self.state)`; `_speaks(candidate: Companion)`; `INTERJECTION_ODDS` keys
   the core `Chattiness`.
10. The engine carries its look. `core/views.py`: `DiceLook` moves here from `ui/theme.py`
    (`ui/dice.py` imports it from `core.views`), and
    ```python
    class Look(Frozen):
        """An engine's palette overrides and dice, read by the pages."""

        palette: dict[str, str] = Field(default_factory=dict)
        dice: DiceLook
    ```
    `Engine.look: Look` is declared on the seam and set on each of the four engines from today's
    `THEMES` entry. `ui/theme.py` deletes `Theme`, `THEMES`, `NEUTRAL_DICE`, `dice_look`;
    `set_engine(look: Look | None)` merges `look.palette` over `NEUTRAL_PALETTE`;
    `page_header(..., *, look: Look | None = None)`; `DiceTray(session.engine.look.dice)`;
    `CatalogEntry.look: Look` so `LaunchForm` can call `theme.set_engine(scenario.look)`;
    `ui/create.py` passes `self.runtime.engines[self.engine_id].look`.
11. Flags in `app` and `ui`:
    - `Roles.narrate` loses `fatal` and always raises. `GameService.open` and the worldsmith
      path wrap the `narrate` call alone (not the whole write, or a failed arrival narration
      would count as an unwritten scene): `except Refusal as failed: LOGGER.warning("the arrival
      went unnarrated: %s", failed); lines = ()`.
    - `GameService._generate(words="")` → `async def _grow(self, *, words: str, mark: Mark) ->
      bool`; `act` calls `_grow(words=words, mark="")`, `_turn` calls `_grow(words="",
      mark="story")`.
    - `GamePage.submit(acting=False)` → `submit()` and `act()` over `async def _send(self, typed:
      str, playing: Callable[[], Awaitable[None]]) -> None`.
    - `mcp._content(body, *, error: bool = False)`.
12. `app/media.py`: `class Claims` with `claim(key: str) -> bool` and `release(key: str) ->
    None` over one `set[str]`; `Illustrator.claims` and `Reader.claims` replace `generating` and
    the `claim(...)` / `discard` pairs; `app/providers.py` keeps `post_bearer` only.
    `Runtime.scenario_models(self) -> dict[EngineId, type[AnyScenario]]` used by `_open` and
    passed into `LauncherCatalog.read`.
13. Tests stop reaching private state: `GameService.settled(self) -> Awaitable[None]` (gathers
    `_background`), `GameService.speaking` property (`_speaking is not None`), `Turn.apply`
    public, `ui/settings.refusal_text` public (it is unit-tested on its own); the
    `reportPrivateUsage` ignores in `tests/` go.
14. Goldens: none change. Run the full check and confirm `git status` shows no fixture.

### Done when

- `grep -rn "except (OSError\|except ValueError\|except (HTTPError, ValueError\|from aidm.engines" src/aidm/app src/aidm/ui` prints only the `engines.registry` and `engines.seam` imports; `grep -rn "EngineId(\"" src/aidm/ui` prints nothing.
- A missing CLI binary, a timeout, a Latin-1 upload and a broken PDF each reach the page as a
  `Refusal` message (one test each, with `ScriptedSpawner` or a fixture file).
- Full check green; no fixture changed; `PROGRESS.md` entry written.

## Phase 3: the engines

Part A (steps 1 to 8) reshapes the seam and the families, about a day and a half, one commit.
Part B (steps 9 to 16) the rules code, the same, a second commit. B starts when A is committed.

### Steps

1. One npc type. `Engine[P: Person, M: Person, G: Game[Any]]` with `member: type[M]`;
   `type AnyEngine = Engine[Any, Any, Any]`; `SceneEngine[C: Person, G: Game[Any], K:
   ScenePack](Engine[C, C, G])`; `RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[P, N,
   G])`. Delete `cast` and `dweller`; `NextDraft[self.cast]`, `SceneDraft[self.cast]` and
   `MapDraft[self.dweller]` read `self.member`. The four engines set `member` once.
2. One way to the world. The seam declares `@abstractmethod def world_of(self, state: G) ->
   World[M, P]`; `SceneEngine.world_of -> SceneWorld[C]` and `RoomEngine.world_of ->
   RoomWorld[N, P]` return `state.payload`; `Loner3eEngine` and `TwentyfourxxEngine` override
   with the exact type (`def world_of(self, state: Loner3eGame) -> Loner3eWorld: return
   state.payload`); breathless and tunnelgoons inherit. The attribute `world_type` → `world`.
   Every `draft.payload` / `state.payload` in the four engines → `self.world_of(...)`; `payload`
   is then read in the two family `world_of` bodies and `Engine.player_of` only.
3. Hiring without a mixin. `engines/hiring.py` imports nothing from `engines.seam` any more (the
   seam imports it); it keeps `HIRE`, `ACTOR`, `SIGNED_ON`, `HIRE_TOOL`, `DROP_ITEM`,
   `HIRE_UNWRITTEN`, `Hire`, `DropItem` and gains
   ```python
   @dataclass(frozen=True, slots=True)
   class Hiring[G: Game[Any], M: Person]:
       """The worldsmith's write of one sheet: prompt, check and install over one answer type."""

       write: Callable[[G, M, str, WorldsmithAnswer], Awaitable[str]]


   def hiring[G: Game[Any], M: Person, A: BaseModel](
       answer: type[A],
       prompt: Callable[[G, M, str], str],
       install: Callable[[M, A], str],
       check: Callable[[G], Check[A]] = lambda _draft: lambda _answer: None,
   ) -> Hiring[G, M]:
       async def write(draft: G, member: M, terms: str, worldsmith: WorldsmithAnswer) -> str:
           answered = await worldsmith(prompt(draft, member, terms), answer, check(draft))
           return install(member, answered)

       return Hiring(write)
   ```
   The seam gains `def hiring(self) -> Hiring[G, M] | None: return None`, and the `hire` tool,
   `write_hire` request and `hireable(draft, entity_id) -> M` move onto `Engine` from the mixin.
   `Engine.worldsmith_requests` becomes concrete (`{HIRE: Request(HIRE_UNWRITTEN,
   self.write_hire)}` when `self.hiring()` is not `None`, else `{}`) and both families spread
   `super()` first; `Engine.master_tools` lists `hire` on the same condition (step 4 gives the
   full order). `BreathlessEngine`, `TwentyfourxxEngine` and `TunnelGoonsEngine` override
   `hiring()` with `hiring(SheetDraft, self.hire_prompt, self.install_sheet)` (24XX adds
   `self.hire_check`); `hire_prompt`, `install_sheet`, `hire_check` are plain methods. Delete the
   `Hiring` class from the engine bases; `hire_answer` goes.
4. Shared tools on the seam. `Reveal`, `Kill`, `REVEAL`, `KILL` move to `engines/base.py` beside
   `JoinParty` (texts: scenes' "A hidden entity here becomes known to the player." / "Someone
   here dies."; fields "Exact id of something hidden here." / "Exact id of who here died.").
   `World` declares `reveal_hidden`, `kill`, `join_party`, `leave_party` abstract, all
   `(self, entity_id: Slug) -> list[Fact]`; `RoomWorld.kill` takes the id (the player's id names
   the player, any other goes through `require_member_here`). `Engine.master_tools` returns
   `reveal`, `kill`, `join_party`, `leave_party` (wrappers written once on the seam), then
   `hire` when hiring; the families spread `super()` first and list only their own; each engine
   lists its own after the family's.
5. `World` gains `sheet_rows(self) -> Pairs: return self.player.rows()` (`RoomWorld`'s moves up;
   `TunnelGoonsWorld` keeps its override); `SceneEngine.narrator_view` and `player_view` read
   `world.sheet_rows()`.
6. `World` gains the shared party validator: `@abstractmethod def member_of(self, member_id:
   Slug) -> M | None` (`npcs.get` / `cast.get`) and a `model_validator` that every party id is
   unique (`check_unique("party", ...)`), known ("`{id!r}` travels with the player but is not
   known") and alive ("`{id!r}` is dead and cannot travel with the player"); the families keep
   only their "with the player" check. Pydantic runs the base validator first, so an unknown
   party id is now reported before the family's own checks.
7. `Engine.open_chapter`: `if draft.log and not draft.log[-1].exchanges: draft.log.pop()` before
   appending (`begin` calls it on an empty log); `RoomEngine.move` loses its pop.
8. `SceneEngine.pack_content(self, picks: Sequence[Slug], *, include: set[str] | None = None,
   exclude_defaults: bool = False) -> str` builds the "SELECTED PACK CONTENT" text for breathless
   and loner3e; `SceneEngine.first_pack(self, draft: G) -> K` replaces `self.packs[draft.packs[0]]`
   in breathless and `_pack` in 24XX. Then regenerate the goldens for part A. Expected:
   `schemas/*/master_tools.json` reorder to seam (`reveal`, `kill`, `join_party`, `leave_party`,
   `hire` where hiring), family, engine, and the rooms `reveal`/`kill` texts change; nothing else.
9. Dice results as one object. `core/facts.py`:
   ```python
   class Rolled(Frozen):
       faces: tuple[int, ...]
       rolled: tuple[int, ...]
       event: DiceEvent
       fact: Fact

       @property
       def kept(self) -> int:
           return max(self.rolled)

       @property
       def total(self) -> int:
           return sum(self.rolled)
   ```
   `roll(faces, reason, rng, *, label: str = "") -> Rolled` (no highlight) and `roll_pool(faces,
   reason, rng, *, label: str = "") -> Rolled` (highlights the kept die); an empty label is the
   notation, and `_notation` spells one die `d10`, not `1d10`, so the card labels keep their
   spelling and the traces follow it. The five hand-built `DiceEvent`s go; loner3e `_pair`
   returns `tuple[Rolled, Rolled]`. `engines/seam.py`: `@dataclass(frozen=True, slots=True)
   class Written: facts: tuple[Fact, ...]; telling: str | None` replaces the alias.
10. The owner writes the fact. `Gauge` moves above `Thing` in `engines/base.py` and keeps
    `adjust`; `Thing.change(self, gauge: Gauge, amount: int, label: str, why: str) ->
    list[Fact]` replaces `Gauge.change(owner, ...)`. `ItemSheet.drop_item(item_id, owner)` →
    `ItemSheet.remove_item(self, item_id: Slug, owner: str) -> I` (refuses, deletes, returns the
    item); `Person.drop_item(self, item_id: Slug) -> list[Fact]` refuses "carries no items";
    `Survivor.drop_item` and `Crewmate.drop_item` are the two-line override over `remove_item`
    and `self.fact`; the `drop_item` tool wrapper is written once on the seam and listed by
    breathless and 24XX after the family's tools. `Sheeted.take_sheet(self, sheet: S) -> None`
    (refuses when one is carried) is what the three `install_sheet` methods call.
    `GoonSheet.rows(hp)` → `rows()` without Health; `tunnelgoons/world.py` gains `class
    Adventurer(Sheeted[GoonSheet]): hp: Gauge` with `rows()` (`("Health", str(self.hp))` first,
    then the sheet's: a deliberate reorder) and `level(ability, boost)`; `Goon(Adventurer)`
    keeps its default `hp` and `kit`, `Npc(Adventurer, Dweller)` keeps its unhired `rows()`;
    `next_to_level(actor: Adventurer)`.
11. No field write in an engine. CLAUDE.md "Code" gains: "An engine tool method resolves ids and
    rolls dice; a world or entity method changes fields and writes the facts." New methods, each
    owning the fields it writes: `SurvivorSheet.wear(skill: Skill) -> None`,
    `Survivor.wear_item(item_id: Slug) -> list[Fact]` (the "gone" fact at d4),
    `SurvivorSheet.spend_stunt() -> None` (refuses when spent), `Survivor.catch_breath() ->
    list[Fact]`, `SurvivorSheet.step_loot() -> None`; `Adventurer.level(ability, boost) ->
    list[Fact]`; `Crewmate.maim() -> list[Fact]`, `Crewmate.raise_skill(label: str) ->
    list[Fact]`, `Crewmate.earn(credits: int, event: DiceEvent) -> list[Fact]`,
    `TwentyfourxxWorld.take_job(terms: str) -> list[Fact]`, `TwentyfourxxWorld.close_job() ->
    None`; `Loner3eWorld.tick_twist() -> bool` (true when the counter turns over). Every
    assignment in the four `engine.py` files to a sheet, gauge or world field goes through one
    of these.
12. One shape for `roll`. In each engine: `_pool(world, actor, args)` returns a frozen `Pool`,
    then the roll, then `_line(...)` for the card text, then `_consequence(...)`. `Pool` fields:
    breathless `die, label, item: Supply | None, helper: tuple[Survivor, Die] | None`, with
    `_wear(sheet, pool)` owning the second branch; tunnelgoons `faces, label, items, npc,
    difficulty, penalty`; 24XX `faces, label, die, helped_by: str`; loner3e two `Rolled` from
    `_pair`. Loner3e builds the oracle fact after computing the exchange, keeping today's fact
    order (asked, oracle, exchange) so `turn/loner3e.json` and the narrator's WHAT HAPPENED do
    not move.
13. `SceneWorld.require_here(entity_id, *, alive=False)` → `require_here(entity_id)` and
    `require_living_here(entity_id)`; `require_member_here` calls the second.
14. Inventory shown once. `Item.notes(self) -> str` returns `""`; `Supply.notes` returns
    `f"d{self.die}"`; `Gear.notes` is step 1.2's. `Sheeted.carried(self) -> str` returns `""`,
    `Survivor.carried` and `Crewmate.carried` spell their items (`name[key] notes`, breathless
    adds ", med kit"); `Sheeted.line` appends `carried()` to the caller's `detail`, `; `-joined,
    for anyone but the player, and `Survivor.line` is deleted. `Crewmate.rows()` loses the Gear
    row; `TwentyfourxxEngine.panels` adds `Panel(title="Gear", rows=...)` before Job and Ship;
    `TwentyfourxxEngine.preview_character` appends `("Gear", ...)` like breathless does.
15. `TwentyfourxxEngine._finish`: `_operators_unmet(expected: Sequence[Slug | None], got:
    Sequence[Slug | None]) -> str` returns the refusal text or `""`. `scene_unmet` splits into
    `_listing_unmet`, `_cast_unmet`, `_hidden_unmet`, concatenated.
16. Regenerate the goldens for part B. Expected: `turn/*.json` change on dice traces and labels
    (`1d10` → `d10`) only; `prompts/tunnelgoons/master.txt` and `narrator.txt` on the Health row
    coming first; `prompts/twentyfourxx/master.txt`, `narrator.txt` and `interjection.txt` on the
    Gear row leaving the sheet; nothing else.

### Done when

- `grep -rn "\.payload\b" src/aidm/engines` prints the two family `world_of` bodies,
  `Engine.player_of` and the worldsmith drafts only; `grep -rn "class Hiring\[.*Engine\|world_type\|hire_answer" src` prints nothing; `grep -rn "DiceEvent(" src/aidm/engines` prints nothing.
- `grep -rnE "(sheet|world|actor|member|npc|player)\.[a-z_]+(\[.*\])? *(=|\+=|-=)|del (sheet|world)\." src/aidm/engines/*/engine.py` prints nothing.
- Full check green; goldens changed as steps 8 and 16 say; `uv run aidm` plays a turn with a
  roll in each of the four shipped scenarios; `PROGRESS.md` entries for A and B written.
