# PLAN — one gate, one vocabulary, one seam

Nine phases, in order. **Phase 1** puts the four commands on every push and brings `qa/` under the
linters; nothing runs on push today, so every later phase would otherwise be verified by hand.
**Phase 2** puts tool-argument validation on one site, deletes two dead guards, splits
`core/views.py` and the prompt renderers by owner, evicts the single-family symbols from the shared
engine base, and fixes the five ways the room family diverges from the scene family. **Phase 3**
collapses six spellings of "a thing with a name and a line" into one law. **Phase 4** deletes
`Fact.kind`, of which fifty literals are written and one is read. **Phase 5** moves the per-engine
palettes onto the engine, gives the UI real accessors, computes the view and the history once per
turn, and splits `GameService` into itself, a `Presenter` and a `Roles`. **Phase 6** writes the two
missing playthrough tests and then factors the sheeted person and hiring. **Phase 7** is the
consistency pass: seventeen findings with no other owner. **Phase 8** renames the eight names that
mean more than one thing each. **Phase 9** re-shapes `tests/` to mirror `src/`, a pure move.
Self-standing: an implementer needs this file, `CLAUDE.md` and the code.

What stays, everywhere: one turn is one player input on one draft behind the commit gate; only code
changes state or rolls dice; the narrator reads revealed facts only; the three roles, each a cold
spawn; four shipping engines; every engine self-contained. What is not built: multiplayer, a second
transport, a compatibility path for anything.

Saves have no version field. Phase 4 removes `Fact.kind` from every stored fact, so a save written
before it carries a key the model no longer declares and no longer parses: the launcher logs
`skipping save ...` and shows the rest (`app/launch.py:99-101`). Nothing migrates. No other phase
invalidates a save.

## Decisions

1. **The four engines stay, and so does `engines/rooms/`.** The engines are what keeps the seam
   honest: four resolution systems, four decision kinds, two world topologies, one engine that does
   not hire and one that survives its player's death. `rooms/` is 834 lines with one shipping user
   (`tunnelgoons/`), which is under the bar, but the next map game brings its own world model
   (`IDEAS.md:18`), so the family stays and only its asymmetry against `scenes/` is fixed
   (Phase 2). `MapDraft` and `RoomCanon` stay two types: the compile-time guarantee that a draft is
   not a canon is worth the duplicate shape.
2. **The `Engine` seam is not split.** It declares 11 class attributes, 12 abstract methods and ~15
   concrete ones, but the two families answer 9 of the 12, so a concrete engine writes only
   `master_tools`, `creation_steps`, `create_character` and one family hook. No engine stubs a
   method to satisfy it (`FifthEngine`, `tests/core/test_seam.py:41-71`, is 30 lines). Every public
   member has a caller. Do not propose an interface split again.
3. **`Runtime`, `ui/game.py` and `app/spawn.py` stay whole**, and `turn/` is not merged into
   `app/`. The one property `turn/` earns as a layer is that `Turn` cannot reach a `Spawner`, a
   `Settings` or a `GameService`; merging would also push `app/runtime.py` past 750 lines.
4. **No Null Object for `media`/`reader`.** Five of the six `X | None` guards would go, but
   `ui/game.py:171` asks *is this feature on at all*, not *is it safe to call* — so an `enabled`
   flag comes back and two classes buy four deleted `if`s. A `Presenter` that owns the guards and
   answers `polls` honestly does the job (Phase 5).
5. **The MCP tool surface stays process-global.** `Runtime.playing()` (`app/runtime.py:410`) cannot
   raise: `busy_refusal` (`:424`) stops a second turn opening, `Runtime.lock` (`:383`) serialises
   every tool call, and `app/mcp.py:63` runs `stateless=True`. Phase 7 rewrites the comment above
   that raise in `Runtime.playing()` (`runtime.py:411` today) to say so, and to record the upgrade
   path: if multiplayer or concurrent multi-save play ever becomes real, drop `stateless=True`,
   route by MCP session, and delete `playing()`, `Runtime.lock` and `NO_TURN`. Do that only with a
   JSON-RPC round-trip test in `tests/`; today it exists only in `qa/s_mcp.py`.
6. **`qa/` keeps all eleven scenarios.** Three modules have no test in `tests/` importing them at
   all — `ui/app.py`, `ui/create.py`, `ui/widgets.py` (which holds `decision_widget`, the only way a
   player answers a decision) — and the real MCP transport is exercised nowhere else. Redundancy in
   the only suite that touches the UI is not waste. What was wrong is that it sat outside every
   gate; Phase 1 fixes that.
7. **One labelled-value vocabulary: `id` / `label` / `detail`**, with `icon_id` as the single
   extension. It binds every value type shown to a role, to the player or to the launcher.
   Persisted world entities keep `name` / `brief`: those words are in the character files, the save
   files and the worldsmith's schema, and renaming them would invalidate every document on disk.
   Phase 3 does the rename and writes the law into `CLAUDE.md`. Not covered, and left alone:
   `draft` and `prompt`, which mean three and five things.
8. **`Fact.kind` goes** (Phase 4). Fifty label values are written and exactly one is read
   (`loner3e/engine.py:205`). Lost: a readable label in save files; `trace` already says what
   happened, in better English.
9. **Hiring is a mixin, and hiring is not the party.** `World.join`/`part` and the
   `JoinParty`/`LeaveParty` verbs are used by all four engines, loner3e included
   (`loner3e/tools.py:9,59`), so the mixin must not be called `Party`. What three engines share is
   narrower: bringing in someone whose sheet the worldsmith authors. It is called `Hiring`
   (Phase 6).
10. **`config.py` stays at the top level, in no layer, and the rule is what is wrong.** `turn/`
    imports it nowhere; only `app/{builtin,media,providers,runtime,spawn,speech}.py` and
    `ui/{app,game,settings}.py` do. Phase 2 tightens `CLAUDE.md` and the boundary test to
    `("app", "ui")`.
11. **One tool-argument validation site: `Turn.call`.** Both transports validate separately today
    and neither check earns its place. MCP's own `CallToolRequestParams` declares
    `arguments: dict[str, Any] | None`, so a non-object argument is rejected by the transport before
    `on_call_tool` runs: `_ARGUMENTS` (`app/mcp.py:87`) is dead code, not a hole. The builtin
    transport's `isinstance` check duplicates a refusal the layer below already makes. That refusing
    code is `master_tool`'s inner `call` (`core/tools.py:45` calls `parse`), which answers
    `Input should be a valid dictionary or instance of Attempt` for `[1, 2]`, `'hello'` and `5`
    alike. Phase 2 widens the argument type and deletes both checks.
12. **The unreachable `_apply` guard becomes a `ValueError`, not a deletion.** The invariant is real
    — a tool opening a second decision while one is open would silently lose the player's first
    question — but only an engine bug can cause it, and a `Refusal` is text a model retries from.
    `assert` is refused: it vanishes under `python -O`.
13. **The interjection die stays in `app` and stays outside `core.facts.roll`.** It decides whether
    to spawn a narrator, changes no state and lands no fact; routing it through `roll` would
    manufacture a `Fact` with nothing to record. Phase 7 gives it a name and one line saying it is
    the one die that is not the game's.
14. **Ten proposals were cut and stay cut**, all taste rather than defect: moving the option
    helpers in `core/creation.py`, moving `core/source.py` to `app/`, merging the two
    `Reveal`/`Kill` pairs (their prose reaches the model through `schema_of`), merging the three
    unmet-reason joiners, splitting `LauncherCatalog.read`, splitting `Runtime`, splitting
    `app/spawn.py`, decomposing `ui/game.py`, and three test-suite tidying moves.
15. **`PanelRow` stays stringly-typed** (`core/views.py:39-44`) and `PendingOption.name` keeps its
    two meanings (`core/play.py:68`, widened LSP-safely by `breathless/engine.py:318-322`). One
    producer family, one consumer, each below the two-things bar.
16. **`Loner3eSheet` keeps its name.** It is a `Person` (`loner3e/world.py:20`), while
    `SurvivorSheet` (`breathless/world.py:35`) and `Sheet` (`twentyfourxx/world.py:66`) are dice
    blocks held inside a person: one word, two kinds of thing. Loner3e holds no second sheet type to
    confuse it with and no other engine imports it, so it is below the two-things bar and the
    Phase 8 rename list does not carry it. Recorded as a non-change so nobody re-proposes it.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action on the files it names. Finish it before the next.
   Every `file.py:line` anchor is as of the start of this plan; where an earlier phase moved the
   code, find the named symbol and ignore the number.
2. **Change a shape and its tests in the same step.** One test per new behaviour; no test of prose
   or wiring. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of a phase that says so:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line against the phase's "Done when"; anything else is a bug.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one entry
   per phase. Phase 1 creates the file. `src` is 9,897 lines and `tests` 9,236 at the start.
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs half again past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase**, full check green, reviewed adversarially against the staged diff first.
   Never leave two versions of one thing alive at a commit.
8. **Delete, do not preserve.** No compatibility path reads an old save or character file; no
   constant, helper or prompt line stays for a caller that is gone.
9. **The standing limits hold.** Imports flow `core <- engines <- turn <- app <- ui`; no `Any`
   beyond the `Game[P]` bound; every `__init__.py` empty; tests never start a process
   (`ScriptedSpawner`); `Refusal` stays the one message-bearing exception; a bad model answer is
   re-prompted once, then raises.
10. **The load-bearing list. Every one of these has a silent failure mode; no step below removes,
    weakens or routes around them.** `Refusal` as a `ValueError` subclass (`core/entities.py:35`) —
    it is what lets a validator's failure survive Pydantic and re-emerge through `parse`. `parse`
    (`:56`) as the one `ValidationError` -> `Refusal` funnel, which carries the location string the
    retry prompt depends on. `Game.draft()`/`commit()` with `Mutable`'s `revalidate_instances=
    "always"` (`core/model.py:113-121`, `entities.py:26`): mutate freely, re-check the whole tree on
    landing. `Turn._apply`'s candidate copy **and** its rng deep copy (`turn/run.py:130,136`) — a
    refused call must consume no dice, or a model retrying a refused roll gets different ones.
    `NarratorView` (`core/views.py:67`) having no field that can hold hidden canon: the guarantee is
    the shape of the type, and `tests/core/test_context_boundary.py` is its only enforcement.
    `Fact.told` computed from `known` in `Thing.fact` (`engines/base.py:73-83`). `decode`'s
    duplicate-key rejection (`core/io.py:147-152,183`). `write_text`'s staged rename (`:139-144`).
    `master_tool`'s description check (`core/tools.py:41-42`). `schema_of` (`:50`) as the one schema
    function, so MCP's published schema and every prompt's ANSWER WITH block cannot diverge.
    `routed` + `EngineHeader` (`core/io.py:155`, `core/model.py:42`). `Turn.call`'s pending and
    generation gates (`turn/run.py:104-117`), which **answer** rather than refuse, precisely so no
    retry prompt tells the model to try again. The `Tools` protocol (`app/builtin.py:22`), the one
    genuine inversion breaking the `Runtime`/`BuiltinSpawner` cycle. The `Spawner` and `Driver`
    protocols (`app/spawn.py:129,34`). `MountedLifespan` (`app/mcp.py:21`). `build_engines`
    (`engines/registry.py:9`) as the one composition root. `ScriptedSpawner`
    (`tests/support/table.py:115`). The `AIDM_GOLDEN_REGEN` guard (`tests/conftest.py:5-9`). The
    three boundary tests: `test_package_boundary`, `test_context_boundary`,
    `test_integrity_boundaries`.

---

## Phase 1 — CI and the toolchain

Target: about +40 lines, none of them under `src/`. Nothing runs on push today, so every guarantee
in this file depends on the maintainer running four commands by hand. This phase comes first.

### Steps

1. **Add `.github/workflows/check.yml`.** On `push` and `pull_request`, one job on
   `ubuntu-latest`: checkout, `astral-sh/setup-uv` pinned to a released major, `uv sync`, then the
   four commands as four named steps. Python 3.13, matching `pyproject.toml:5`. Do not set
   `UV_CACHE_DIR`: it breaks the test suite.
2. **Bring `qa/` under the type checker.** `pyproject.toml:41`: `include = ["src", "tests", "qa"]`.
   Fix what it reports, starting with `qa/drive.py:54` `def run(name: str, body) -> None`, whose
   `body` is unannotated — give it the exact callable type its callers in `qa/s_*.py` pass.
3. **Delete the dead suppressions.** `uv run ruff check --extend-select RUF100 --fix qa/` removes 14
   `noqa` directives: ten for `ANN001`/`ANN202`, rule families this repo never enabled, and four
   `E402` at `qa/server.py:20,22,23,24` that suppress nothing.
4. **Align the scenario list.** `qa/run_all.sh:8` defaults to nine scenarios and silently omits
   `visual` and `probe`, which `qa/README.md` lists. Add them.

### Done when

A push runs the four commands in Actions and they are green. `uv run basedpyright` covers `qa/`'s
2,292 lines. `uv run ruff check --extend-select RUF100 qa/` reports nothing. `qa/run_all.sh` with no
arguments names eleven scenarios, the same eleven `qa/README.md` lists. Full check green.

---

## Phase 2 — The gate, the kernel and the room family

Target: about -60 lines. One validation site for tool arguments, two dead guards gone,
`core/views.py` and the prompt renderers split by owner, one prompt reader, `engines/base.py`
honestly shared, one generic `ChangeWorld`, and the room family aligned with the scene family.

### Steps

1. **`turn/run.py` — the dead guard.** Delete `:117` (`decided_before = self.draft.pending`, always
   `None` because `call` early-returns at `:108-113` whenever `pending is not None`) and simplify
   `:121` to `if self.draft.pending is not None:`. Rename `already_pending` (`:116`) to
   `notes_before`: it counts notes, not decisions.
2. **`turn/run.py:131-134` — the unreachable refusal.** Replace `raise Refusal("the rules already
   wait on a decision; they take one at a time")` with a plain `raise ValueError` naming the
   invariant: a tool opened a second decision while one was open. No test references the old string.
3. **Widen tool arguments to `JsonValue`.** `MasterTool.call` (`core/tools.py:32`), the inner `call`
   built by `master_tool` (`:44`), `Turn.call` (`turn/run.py:102`), `Runtime.call`
   (`app/runtime.py:417`) and the `Tools` protocol (`app/builtin.py:24`) all take
   `raw: JsonValue` instead of `Mapping[str, JsonValue]`. `parse(args, raw)` (`core/tools.py:45`)
   already refuses everything else. Widen the test stub with them: `_Tools.call`
   (`tests/core/test_builtin.py:32`) declares `raw: Mapping[str, JsonValue]`, and a narrower
   parameter fails the protocol under basedpyright. `tests/support/table.py:155` needs no edit: a
   `dict` is a `JsonValue`.
4. **Delete both transport checks.** `app/mcp.py`: drop `_ARGUMENTS` (`:17`) — the transport's own
   `CallToolRequestParams` rejects non-object arguments before `on_call_tool` runs, so the check is
   dead code — and pass `params.arguments or {}` straight to `runtime.call` (`:87`).
   `app/builtin.py`: delete the `_arguments` wrapper (`:156-160`) with its `isinstance` check and
   its `Refusal`, and call `decode(text)` at its one call site, `_answer` (`:121`). One test, on the
   builtin transport: a call whose arguments are `'[1, 2]'` comes back as a tool error carrying the
   refusal, not as an escaping exception.
5. **Split `core/views.py`.** Move `SCENE_EXCHANGES`, `WHOLE_SCENES`, `TAIL_EXCHANGES` (`:17-19`),
   `sections` (`:145`), `lines_of` (`:149`), `render_history` (`:153`), `told_history` (`:160`) and
   the private `_block`, `_header`, `_told` into a new `core/prompt.py`. The models stay. It must be
   `core/`, not `turn/`: `engines/` sits below `turn/` and calls `render_history`
   (`scenes/engine.py:240`, `rooms/engine.py:240`). Re-point `turn/context.py:9-18`,
   `scenes/worldsmith.py:7`, `scenes/engine.py:22`, `scenes/world.py:17`, `rooms/engine.py:20-29`,
   `rooms/worldsmith.py:4`, and the three that import `lines_of`: `rooms/world.py:9`,
   `breathless/engine.py:12`, `twentyfourxx/engine.py:12`. Split the test file with the code:
   `tests/core/test_views.py` imports `TAIL_EXCHANGES`, `render_history` and `told_history` at
   `:8-12`, so its `render_history`/`told_history` tests (`:211-278`) move to a new
   `tests/core/test_prompt.py`; it imports `render_interjection` from `aidm.turn.context` at `:16`,
   the module step 7 deletes, so that test (`:197`) moves to a new `tests/core/test_roles.py`, which
   follows `render_interjection` into `app/roles.py`.
6. **One prompt reader.** Add `read_prompt(path: Path) -> str` to `core/io.py`, `@cache`d, reading
   with `ENCODING`. It replaces three mechanisms: the lazy cached `_prompt`
   (`turn/context.py:109-111`); the construction-time read at `engines/seam.py:52`; and the
   import-time reads at `scenes/engine.py:55-56` and `rooms/engine.py:47`, which make an `import`
   statement perform disk I/O and able to raise `OSError`. Delete the `WORLDSMITH` and `SCENE_RULES`
   module constants and call `read_prompt` where they were read.
7. **Split prompt rendering by owner.** Each renderer has exactly one caller. Move `render_master`
   (`turn/context.py:23`) into `turn/run.py` as a module-level function beside `Turn.picture`, which
   keeps calling it: `tests/core/test_context_boundary.py:9,33` imports it and calls it directly, so
   it does not become a method. Move `render_narrator` (`:47`), `render_interjection` (`:60`) and
   `_picture` (`:81`) into a new `app/roles.py`, beside their
   caller `GameService`. Delete `turn/context.py`. `turn/prompts/master.md` stays;
   `turn/prompts/{narrator,interjection}.md` move to `src/aidm/app/prompts/`. Update
   `tests/core/test_context_boundary.py`'s imports; its assertions do not change.
8. **Evict the single-family symbols from `engines/base.py`.** All four are used by scene engines
   only: `SRD_PACK` (`:18`), `Pack` (`:176`) and `read_packs` (`:293`) move to a new
   `engines/scenes/packs.py`; `named_unmet` (`:282`) moves to `engines/scenes/worldsmith.py`, its
   one caller (`:101`). Rename the base class to `ScenePack` at its new home and delete the
   `from ... import Pack as ScenePack` / `class Pack(ScenePack)` shadowing at
   `loner3e/worldsmith.py:6,25`, `breathless/worldsmith.py:7,25`, `twentyfourxx/worldsmith.py:7,47`.
   Move `EXTEND` (`:20`) into `rooms/engine.py`, its only user. Move `keep_highest` (`:271`) to
   `core/facts.py` beside `roll`, which is where a reader looks for it. Re-point the test importers
   in the same step: `tests/core/test_seam.py:14` (`Pack`), `tests/core/test_dice.py:7`
   (`keep_highest`), `tests/core/test_engines_base.py:7` (`named_unmet`), and `SRD_PACK` in
   `tests/loner3e/test_engine.py`, `tests/breathless/test_engine.py`,
   `tests/twentyfourxx/test_engine.py` and `tests/twentyfourxx/test_tools.py`.
9. **One generic `ChangeWorld[C]`.** Add `class ChangeWorld[C](Frozen)` to `engines/base.py` with
   one field, `change: C = Field(description=...)`, whose description is the one the four copies
   share, taken verbatim. The discriminator does not go on the generic:
   `Field(discriminator="verb")` on a type-parameter field raises `TypeError: The core schema type
   'any' is not a valid discriminated union variant` when the class body runs, and bounding
   `C: BaseModel` fails differently. It goes at the use site. Each engine keeps its own
   `type WorldChange = ...` and writes `ChangeWorld[Annotated[WorldChange, Discriminator("verb")]]`,
   so the union stays a written annotation the checker still reads. Delete `loner3e/tools.py:63`,
   `breathless/tools.py:43`, `tunnelgoons/tools.py:22`, `twentyfourxx/tools.py:122` and the fifth
   copy at `tests/core/test_rooms.py:43`. `schema_of` renders the parametrised form exactly as it
   renders the four copies today, so `tests/core/fixtures/schemas/*/master_tools.json` do not move.
10. **The family rules suffix becomes a hook.** `scenes/engine.py:96` appends a family `rules.md` to
    `Engine.instructions`; the room family has none. Add `def family_rules(self) -> str: return ""`
    to `Engine`, called at the end of `Engine.__init__` and appended when non-empty. `SceneEngine`
    overrides it with `read_prompt(scenes/rules.md)` and drops the line at `:96`; `RoomEngine`
    overrides it with a new `engines/rooms/rules.md`: one paragraph, at most 10 lines, covering ways
    and places as `scenes/rules.md` covers scenes. Its text lands in every TunnelGoons master
    prompt, so read it back in the golden diff (step 16).
11. **`MapDraft` comes home.** `rooms/drafts.py` is 10 lines and its one class imports the world
    (`rooms/drafts.py:4`), so the reason for a separate drafts module — that drafts may not import
    the world (`scenes/worldsmith.py:41`) — does not apply. Move `MapDraft` into `rooms/world.py`
    and delete `rooms/drafts.py`. `MapDraft` and `RoomCanon` stay two types.
12. **Align the four room verbs on the scene names.** `render_map` (`rooms/engine.py:213`) ->
    `render_opening`; `render_extension` (`:226`) -> `render_next`; `write_extension` (`:247`) ->
    `write_next`; `install_extension` (`:258`) -> `install`. Update the callers at `:173, 191, 192,
    251` and `tunnelgoons/engine.py:160`.
13. **`rooms/engine.py:62` says `EXTEND`.** It reads `operations = (MORE_MAP.id,)` while `:177`
    reads `request.operation == EXTEND`, and `MORE_MAP.id` **is** `EXTEND` (`:48`) — one value, two
    spellings, one file. Make line 62 `operations = (EXTEND,)`.
14. **`RoomEngine.advance` reads the operation it is handed.** `rooms/engine.py:188-193` never
    checks it, so a second room operation would be silently treated as an extension;
    `scenes/engine.py:331` branches. Add `if request.operation != EXTEND: raise ValueError(...)` in
    the shape of `Engine.unwritten`'s raise (`seam.py:193`) — `validate:74` already bars it, so it
    is a cannot-happen guard, not a refusal.
15. **Fix the settings rule.** `CLAUDE.md`: *"Only `turn`, `app` and `ui` read the settings"* ->
    *"Only `app` and `ui` read the settings"*. `tests/core/test_package_boundary.py:22`:
    `"aidm.config": ("turn", "app", "ui")` -> `("app", "ui")`. `turn/` imports `aidm.config`
    nowhere; both grant a permission nobody uses, and the rule as written weakened on paper the one
    property `turn/` earns as a layer.
16. **Regenerate the goldens.** Step 10 changes a prompt: the room family's rules now render into
    `RoomEngine.instructions`. The only diff is that new block inside
    `tests/core/fixtures/prompts/tunnelgoons/master.txt`, under `THE RULES OF THIS GAME:` (`:26`).
    `tests/core/fixtures/schemas/` does not move.

### Done when

A CLI sending non-object tool arguments over the builtin transport gets a tool error carrying the
refusal, and neither transport validates arguments itself. `turn/context.py` and `rooms/drafts.py`
are gone; `core/prompt.py`, `app/roles.py`, `tests/core/test_prompt.py`, `tests/core/test_roles.py`
and `engines/rooms/rules.md` exist; no module reads a file at import time. `engines/base.py` holds
nothing used by one family. `ChangeWorld` resolves to one type. The room engine refuses an operation
it does not write, and the two spellings of `EXTEND` are one. Full check green; one test per new
behaviour; the only golden that moves is the room-family rules block in
`tests/core/fixtures/prompts/tunnelgoons/master.txt`; `tests/core/fixtures/schemas/` is unchanged.

---

## Phase 3 — One vocabulary

Target: about -25 lines, ~30 mechanical sites. Nothing else is in flight during this phase. Six
spellings of "a thing with a name and a line" collapse to one law: **`id` / `label` / `detail`**,
with `icon_id` as the single extension.

### Steps

1. **Delete `Action`** (`core/views.py:59` today; Phase 2 step 5 lifts three constants out of the
   file, so every anchor here sits about three lines higher). It is field-for-field a
   `DecisionOption` (`core/play.py:62`), which additionally has `min_length=1` on `label` and
   `detail: str = ""`. `PlayerView.action` (`core/views.py:141` today) takes
   `DecisionOption | None`; `MORE_MAP` (`rooms/engine.py:48`) and `MOVE_ON`
   (`scenes/world.py:21`) change type only;
   `Observed.action` (`ui/game.py:56`) follows.
2. **Delete `Named`** (`core/model.py:48`), a class with one use at `:57`. `CharacterHeader` reads
   the two fields itself: `label: str` and `detail: str = ""`, lifted out of the document's
   `payload` by a `model_validator(mode="before")`. Update its three readers: `app/launch.py:82-83`,
   `core/io.py:125` and `tests/core/test_store.py:117`. The files on disk do not change: the payload
   still carries `name` and `brief`.
3. **Collapse `Rows` and `Sections`** (`core/views.py:21-22` today). They are PEP 695 aliases of one
   identical type, distinguished by a comment, so the checker already lets a sheet be passed where a
   prompt section is expected. One survivor, named for what it is: `type Pairs = tuple[tuple[str,
   str], ...]`. Replace both names everywhere: `Rows` at 30 sites, `Sections` at 22.
4. **Rename `Subject.name`/`brief` -> `label`/`detail`** (`Subject`, `core/views.py:25` today).
   Touches `Thing.subject()` (`engines/base.py:92`), the panel builders (`:225-262`),
   `app/media.py:176,193` and the party rendering that becomes `app/roles.py:_picture`. `Thing`
   keeps `name` and `brief`: they are persisted.
5. **Rename the `Thing.label` property to `Thing.mention`** (`engines/base.py:44`). It returns
   `the player [id]` or the tag and is read in ~30 traces; with `Subject.label` in place it would be
   the third meaning of one word in one expression. `mention` says what it is: how a role names this
   thing in a trace.
6. **`CatalogEntry` speaks the law** (`app/launch.py:14`): `id`, `engine`, `label`, `detail`,
   `rules`. This also closes `subtitle` meaning two things — a premise at `:73`, a brief at `:83`;
   both are the line under the name. Update `ui/app.py` and `ui/create.py` where they read it.
7. **Write the law into `CLAUDE.md`**, under `## Code`: *"A value type that names something to a
   role, the player or the launcher spells it `id` / `label` / `detail`, with `icon_id` as the one
   extension. Persisted world entities keep `name` and `brief`: those words are on disk."* Without
   this line the rename will not hold.
8. **Regenerate the goldens.** `tests/core/fixtures/schemas/*/master_tools.json` churn where a
   renamed field reaches a schema. Read every changed line.

### Done when

`Action`, `Named`, `Sections` and `CatalogEntry.subtitle` do not exist. One grep for `label` finds
one concept in value types and `Thing.mention` in traces. `CLAUDE.md` carries the law. Full check
green; the golden diff is field renames and nothing else.

---

## Phase 4 — Facts without kinds

Target: about -70 lines under `src/`, more under `tests/`. Fifty `kind` literals are written and
exactly one is read (`loner3e/engine.py:205`, `fact.kind == "conflict_lost"`). This phase is alone
in its window: it edits ~60 call sites and ~80 test assertions.

### Steps

1. **Make the one reader read a flag.** `_strike` (`loner3e/engine.py:251`) returns
   `tuple[list[Fact], bool]` — the facts and whether the conflict ended. It already knows at `:258`
   (`if hit.luck.current != 0`). The caller unpacks first: `:202` becomes `struck, ended =
   _strike(...)` and then `exchange, effects = _absorbed(struck)`, and `:205` branches on `ended`
   instead of `any(fact.kind == "conflict_lost" for fact in exchange)`. `_absorbed` (`:245`) is not
   touched: it keeps taking `list[Fact]`.
2. **Remove `kind`.** Delete the field from `Fact` (`core/facts.py:35`) and the first parameter from
   `Thing.fact()` (`engines/base.py:73`), then every call site: ~60 `.fact(...)` calls across the
   four engines and the two families, plus 13 direct `Fact(kind=...)` constructions in `src/`.
   `PendingDecision.kind` (`core/play.py:78`) is a different field and stays: its four values are
   `loot`, `conflict`, `level-up` and `succession`.
3. **`roll` stops labelling.** `core/facts.py:55` builds its fact without `kind`; delete `DICE`
   (`:10`), write-only once `kind` is gone. The dice tray already selects facts by *having dice*
   (`ui/dice.py:36`), not by label.
4. **Drop the test assertions that check `kind` and nothing else** (~80). `CLAUDE.md` calls those
   wiring. An assertion that checks `kind` alongside a real behaviour keeps the behaviour half.
5. **Regenerate the four turn goldens** and read the diff: every removed `"kind"` key and nothing
   else.

### Done when

`Fact` has four fields and `Thing.fact()` takes the trace first; no label is written anywhere.
Loner's conflict still suspends on a `conflict` decision and still ends when a side is out of luck,
proved by a test that reads the outcome, not a string. Saves written before this phase are skipped
by the launcher with `skipping save ...`; nothing migrates. Full check green.

---

## Phase 5 — The service's seams

Target: about +40 lines net, `app/runtime.py` down from 511 to about 390. That one number is the
target: `Runtime` (`:376-507`) and the module constants (`:31-55`) are about 190 lines that do not
move, and the extractions take about 135 out. The palettes move onto the engine, the UI stops
reaching through the service into the engine, the view and the history are computed once per turn,
and `GameService` gives up two collaborators.

### Steps

1. **The palettes belong to the engine.** `ui/theme.py:26-73` hardcodes `EngineId("loner3e")`,
   `"tunnelgoons"`, `"breathless"`, `"twentyfourxx"` with a full palette each, which is per-engine
   world knowledge in `ui/`. Add `type Palette = Mapping[str, str]` to `core/views.py` beside
   `DiceLook` (`core/views.py:51` today; Phases 2 and 3 lift about ten lines out above it), and
   `palette: Palette` to `Engine`'s class attributes (`engines/seam.py:42`, beside
   `dice_look` and `art_style`, which are the same class of data). Each of the four engines declares
   its own, moved verbatim. Delete `ENGINE_PALETTES` and `ui/theme.py`'s local `Tokens` alias
   (`:9`), which `Palette` replaces.
2. **Seed the CSS from the registry.** `theme.seed(palettes: Mapping[EngineId, Palette])` stores
   them in a module-level dict and injects `_palette_css() + _STATIC_CSS` once; `apply()` keeps
   `ui.dark_mode` and `set_engine`, and `_palette` reads the seeded dict.
   `seed` is idempotent and overwrites: the dict it fills is module-level state shared by every test
   in a session, so a second call must leave the same result, not add to it.
   `_register_pages` (`ui/app.py:167`) calls `seed` from `runtime.engines` before registering pages.
   Two tests in `tests/ui/test_theme.py` read `ENGINE_PALETTES` and both must change. `:42-53`,
   which asserts the accent and muted colours `set_engine` writes, calls `seed` from `ENGINES_BUILT`
   first and asserts against the seeded palette; without that call it falls back to neutral and
   fails twice over. The hex-value assertion at `:67` is a wiring test over a data table: delete it
   and replace it with one that every built engine has a block in the generated CSS, so a fifth
   engine cannot ship themeless.
3. **Close the boundary test's literal hole.** `tests/core/test_package_boundary.py:76-84` inspects
   `ast.Import`/`ast.ImportFrom` only, which is why four engine ids sat in `ui/` unnoticed. Add a
   test that no module under `src/aidm/ui/` holds an `ast.Constant` string equal to a built engine
   id.
4. **Give `GameService` its accessors** — this comes before the caching below, because six call
   sites fetch the history themselves today. Add `history()`, `engine_title`, `engine_id`,
   `dice_look` and `scene_header()`. `core/views.py` gains `SceneHeader(Frozen)` with `title` and
   `situation`. Repoint `ui/game.py:66, 105, 162, 186, 204, 324, 389, 444, 497`. `:186` reads
   `narrator_view` — a type built for the *narrator* — to draw the scene header; `scene_header()`
   replaces it, and `PlayerView`, already rebuilt eight times per refresh, is not widened.
5. **Forbid the reach.** Extend `tests/core/test_package_boundary.py` to fail on the attribute chain
   `session.engine` or `self.session.engine` inside `src/aidm/ui/`. The AST carries no types, so a
   bare `.engine` ban would false-positive on `scenario.engine` (`ui/app.py:78,88`,
   `ui/create.py:107`). Today the test checks imports only, which is why twelve method calls slipped
   through a passing ban.
6. **Build the narrator's view once per turn.** `app/runtime.py:274` builds a `NarratorView` to
   narrate and `engines/seam.py:124` builds an identical one inside `Engine.close`, purely to turn
   `Line` into `SpokenLine`; each build runs `_everyone_is_a_subject` (`core/views.py:82`) and a
   full entity walk. `_narrate` returns `tuple[SpokenLine, ...]` by calling `view.spoken(...)` on
   the view it already holds; `Engine.close` takes `SpokenLine`s and stops calling `narrator_view`.
   Change all five callers of `Engine.close`: `GameService.open` (`app/runtime.py:106`),
   `GameService.interject` (`:208`), both branches of `GameService._generate` (`:231` and `:236`),
   and `Turn.finish` (`turn/run.py:126`). Two tests call it directly and change with them:
   `tests/core/test_speech.py:149` and `tests/core/test_game_service.py:306`.
7. **Walk the history once in `Turn.picture`.** `turn/run.py:98` calls
   `len(self.engine.history(self.draft))`, which reaches `World.exchanges()`
   (`engines/base.py:125`), rebuilds every `SceneRecord` from scratch, flattens it and discards all
   of it for one integer — on the line after `:96` built the same records. Bind
   `scenes = self.engine.scenes(self.draft)` once and pass
   `played=sum(len(record.exchanges) for record in scenes)`.
8. **One `PlayerView` and one history walk per UI tick.** `poll_turn` (`ui/game.py:374-381`) already
   diffs `Observed` and calls `refresh()` as one unit. Build the view and the history once there,
   hold them on the page, and pass them into the refreshables that call `session.player_view()` at
   `:62, 209, 250, 266, 282, 305, 422, 480` and the history at `:66, 204, 324, 389, 444, 497`.
9. **Extract a `Presenter`** into `app/present.py`: `media`, `reader`, `_background`, `_retain`,
   `_present`, `illustrate`, `speak`, `scene_art`, `icon`, `newest_clip`, `_newest` — about 45
   lines. It answers `polls` (is either feature on at all), `async drain()` (await every retained
   task) and `stop()` (cancel them). `GameService` holds one and delegates the five calls
   `ui/game.py` makes. `ui/game.py:171` asks `session.presents`; `tests/core/test_golden_turn.py:37`
   awaits `drain()` and drops its `# pyright: ignore[reportPrivateUsage]`.
10. **A settings reload actually stops the writing.** `Runtime.reload_settings`
    (`app/runtime.py:435-442`) calls `session.hush()`, which cancels only the interjection task;
    in-flight art and speech keep running and write into the evicted session's folder, though the
    comment at `:440` claims eviction stops it. Call `stop()` on each evicted session's `Presenter`
    and correct the comment. One test: a retained background task belonging to an evicted session is
    cancelled by a reload.
11. **Extract `Roles`** into `app/roles.py`, beside the render functions Phase 2 put there:
    `RoleSpawner` (`app/runtime.py:365`), `_narrate`, `_master` and `_worldsmith` (`:510`), plus the
    prompt-and-ask half of `interject` — about 90 lines. The master's retry rule, the narrator's
    evidence assembly and the interjection prompt then read as three peer role interactions instead
    of three methods buried between `commit` and `scene_art`. `GameService` keeps state, turn flow
    and interjection policy.

### Done when

`ui/` names no engine id and calls no engine method; the boundary test fails if either returns. A
fifth engine without a palette fails a test. One `NarratorView` per turn and one history walk per
`Turn.picture` and per UI tick, each proved by a test that counts calls on a stub. A settings reload
cancels an in-flight illustration. `app/runtime.py` is about 390 lines. Full check green.

---

## Phase 6 — Coverage, the sheeted base and hiring

Target: about -80 lines under `src/`, +120 under `tests/`. The two blocking coverage gaps close
first: `breathless` and `twentyfourxx` have no multi-turn test at all, and 24XX's hire-then-
succession path is untested end to end. Steps 1 and 2 come before every other step in this phase.
Steps 1-2 touch only `tests/` and steps 3-7 only `src/`, which is disjoint enough to look parallel
and is not: **Split: sequential — A (steps 1–2) then B (steps 3–7).**

### Steps

1. **A multi-turn playthrough for Breathless and for 24XX.** `tests/tunnelgoons/test_play.py:45` is
   the only start-to-finish test in the suite; mirror it as `tests/breathless/test_play.py` and
   `tests/twentyfourxx/test_play.py`, driving several turns through `ScriptedSpawner`, never a
   process.
2. **The hire-then-succession test.** `tests/twentyfourxx/test_world.py:124` and
   `test_tools.py:416` cover the mechanism but not the path: hire a member, let the worldsmith write
   their sheet, save and reload the game through the store, kill the lead, and assert `_succession`
   (`twentyfourxx/engine.py:278`) hands the lead to the hired member with their sheet intact. This
   test gates steps 3 to 7.
3. **A sheeted person.** `Survivor` (`breathless/world.py:105`) and `Crewmate`
   (`twentyfourxx/world.py:96`) share four methods character for character — `dice()`
   (`:110-113` / `:101-104`), `require_item` (`:115-119` / `:106-110`), `drop_item`
   (`:121-125` / `:148-152`), `unwritten()` (`:178-184` / `:176-182`) — and declare
   `sheet: X | None = Field(default=None, description="Leave empty.")` identically. Add
   `class Sheeted[S: BaseModel](Person)` carrying `sheet`, `dice()` and `unwritten()`, and
   `class ItemSheet[I: BaseModel](Mutable)` carrying `items: dict[EntityId, I]` with `require` and
   `drop`. Both sheets subclass `ItemSheet[Item]`; each engine's `require_item`/`drop_item` become
   two-line delegations, because `Item` is a different shape in the two engines
   (`breathless/world.py:30` is name+die; `twentyfourxx/world.py:39` is name+bulky+breaks). If
   basedpyright accepts a bound that names an earlier type parameter
   (`Sheeted[I: BaseModel, S: ItemSheet[I]]`), pull `require_item` and `drop_item` up too. The field
   name `sheet` does not change, so no save changes.
4. **One `require_sheeted`.** `require_actor` (`breathless/world.py:194`,
   `twentyfourxx/world.py:203`) and `require_hireable` (`:202`, `:211`) differ only in the noun
   inside the refusal; the `_player_carries_a_sheet` validator (`:188`, `:194`) is byte-identical.
   Add `require_sheeted(entity_id, *, noun: str)` on the world side and one shared validator.
5. **Spike the mixin, then write it.** Confirm in a throwaway that a mixin composes through
   `Engine[P, G]` -> `SceneEngine[C, P, G, K]` -> concrete **and** through `Engine[P, G]` ->
   `RoomEngine[...]` -> concrete under basedpyright: TunnelGoons hires from the room family, so a
   mixin that only composes with `SceneEngine` does not do the job. If it does not, fall back to a
   template method on the seam with the same hooks and say so in `PROGRESS.md`.
6. **`engines/hiring.py`.** `Hiring` owns `HIRE`, `HIRE_TOOL`, `hire_target` (`engines/base.py:215`
   today), `Engine.hire` (`seam.py:180`), the HIRE branch of `Engine.unwritten` (`:191`),
   `Engine.check_request` (`:195`), `World.require_hireable` (`engines/base.py:144` today, a method
   whose whole body is a refusal with its argument unused), `World.sign_on` (`:147` today),
   `Sheeted` and `ItemSheet`. It contributes HIRE to whichever family base it is mixed with —
   `(*super().operations, HIRE)` computed when the class is built, never
   `(*SceneEngine.operations, HIRE)`: TunnelGoons hires from the room family
   (`tunnelgoons/engine.py:74` reads `(*RoomEngine.operations, HIRE)`) and Breathless and 24XX from
   the scene family (`breathless/engine.py:73`, `twentyfourxx/engine.py:76`), all three hand-synced
   today. Its `advance` handles HIRE and delegates everything else to `super().advance`, which is
   why the mixin sits between the family base and the concrete engine in the MRO. It absorbs the
   six-step HIRE block inside `advance`, written three times (`breathless/engine.py:194`,
   `tunnelgoons/engine.py:153`, `twentyfourxx/engine.py:303` today), leaving each engine steps 3 and
   5 — its prompt text and its sheet shape, the two that are genuinely per-ruleset — as hooks. One
   more thing in that block is per-engine and must stay a hook, not be flattened: the bar the
   worldsmith's sheet answer has to clear, which is `lambda _draft: None` in
   `tunnelgoons/engine.py:167` and `breathless/engine.py:214` and a real check,
   `lambda sheet: sheet.refusal(pack)`, in `twentyfourxx/engine.py:317`. The no-op is the mixin's
   default. The three engines opt in; loner3e stops carrying five pieces it never uses.
7. **Delete what the mixin now owns** from `engines/seam.py` and `engines/base.py`, and the three
   `!= HIRE` guards that follow the HIRE branch in each `advance` (`breathless/engine.py:197`,
   `tunnelgoons/engine.py:156`, `twentyfourxx/engine.py:306` today).

### Done when

A Breathless game and a 24XX game each play several turns in a test. A hired 24XX crew member's
sheet survives a save and a succession. Neither `engines/seam.py` nor `engines/loner3e/` names
hiring: it lives in `engines/hiring.py` and the three engines that opt in. The hire flow is written
once. Full check green; goldens unchanged.

---

## Phase 7 — The consistency pass

Target: about -40 lines. Seventeen findings with no other owner. Each is small; none depends on
another; the phase splits cleanly by file.

### Steps

1. **The story marks stop being player input.** `app/runtime.py:34-37` defines `OPENING_MARK`,
   `STORY_MARK` and `INTERJECTION_MARK`, stores them in `Exchange.prompt`, matches them by identity
   in the history panel's `if exchange.prompt in MARKS` (`ui/game.py:212` today, moved by Phase 5
   step 8) — and `core/prompt.py:_told` feeds them verbatim into the master and narrator prompts as
   `f"> {exchange.prompt}"`, so the master reads `> (the story begins)` as a player action. Add
   `type Mark = Literal["", "opening", "story", "interjection"]` and `Exchange.mark: Mark = ""` to
   `core/play.py`; `Engine.close` takes the mark and leaves `prompt` empty for a marked exchange.
   `_told` renders a marked exchange as its transcript alone, except an interjection, which gets a
   prefix naming it as a party member speaking unprompted, never a `>` line. The history panel tests
   `exchange.mark`. Delete `MARKS`. The new field is optional with a default, so a save written
   before this phase still parses; nothing is invalidated. No fixture holds a marked exchange, so no
   golden moves: add one test that a marked exchange renders without a `>` line.
2. **`Refusal` is not for programmer errors.** `engines/registry.py:11` and the `require_unique`
   call in `Engine.__init__` (`engines/seam.py:54` today, moved by Phase 2 step 10) raise `Refusal`
   for what only a code bug can cause — duplicate engine ids, duplicate tool names — both at app
   start, where `app/runtime.py:414`'s bare `ValueError` is the right shape. Raise `ValueError` at
   both, keeping `require_unique` itself as it is: it is genuinely dual-use and is also called at
   tool boundaries.
3. **Module layout, three sites.** `CLAUDE.md` orders a module: imports, constants, classes, public
   functions, private functions. `ui/game.py` — the six public functions `can_type` through
   `placeholder` (`:597-637` today, moved by Phase 5 step 8) sit after the private `_card`,
   `_dice_group`, `_bubble`, `_inline_status` and `_clock` (`:539-592` today). `ui/app.py:60` —
   `class LaunchForm` after the public `start:47`. `loner3e/tools.py:102` — `TOLD` is a plain dict,
   not a constant built from a class, so it belongs at the top. These are the only three in
   `src/aidm`.
4. **Validator helpers raise `ValueError`.** `check_filing` (`engines/base.py:265`) and
   `check_named` (`scenes/world.py:286`) raise `Refusal` from inside validators, while the
   equivalent `check_spread` (`breathless/world.py:220`) raises `ValueError`. It works only because
   `Refusal` subclasses `ValueError` and Pydantic swallows it — which means the `Refusal` type is
   lost and the rule is satisfied by accident. Make all three raise `ValueError` for their own
   checks; the `require_unique` call inside `check_named` stays.
5. **Narrow the two blanket handlers.** `app/media.py:122` and `app/speech.py:63` catch `Exception`
   with a stated reason and a `LOGGER.exception`, but as written a `TypeError` in
   `illustration_request` is swallowed forever. Narrow both to `(OSError, HTTPError, ValueError)`,
   the discipline the rest of `app/` uses (`app/runtime.py:195,232,259,290`, `ui/game.py:516`).
6. **The fourth base config comes home.** `core/entities.py:19-32` establishes `Frozen`, `Mutable`
   and `Loose` as *the* three configs; `app/builtin.py:27-30` declares a fourth, `_Echoed`
   (`extra="allow", frozen=True`) — the missing quadrant of the same 2x2, in another layer. Move it
   to `core/entities.py` as `Echoed`.
7. **`Roles.each` stops enumerating by hand.** `Roles.each` (`config.py:89-94`) lists the three
   roles that `for_name` (`:80-87`) already lists. Write it as
   `tuple((name, self.for_name(name)) for name in get_args(Role.__value__))`. `Role` is a PEP 695
   alias (`config.py:12`), so `get_args(Role)` returns `()` while `get_args(Role.__value__)` returns
   the three names; the shorter spelling would leave `each` empty and silently disable half of
   `_keys_present` (`:137-148`). The exhaustive `match` in `for_name` stays: it type-checks.
   `Providers.for_name` (`:107`) stays as it is.
8. **Declare the `__init__` ordering contract.** `Engine.__init__` (`seam.py:51-55`) calls
   `self.master_tools()`, which for a scene engine reads `self.packs`, so `SceneEngine.__init__`
   must call `read_packs` **before** `super().__init__()`, guarded only by an inline comment
   (`scenes/engine.py:95`). A subclass author who calls `super().__init__()` first gets an
   `AttributeError` at import. Add `def prepare(self) -> None: ...` to `Engine`, called on the first
   line of `Engine.__init__`; `SceneEngine` overrides it with the `read_packs` line and its
   `__init__` disappears.
9. **`Attempt` moves out of `core`.** `core/tools.py:18-25` is game vocabulary — "An attempt at
   something uncertain", with `what` described as "The attempt, in a few words the player reads" —
   in the layer that knows no world shape. Four engines subclass it, so it is earned; move it to
   `engines/base.py`.
10. **Two more ruff rules.** `pyproject.toml:55` selects `["E", "F", "I", "UP", "B", "TID252"]`. Add
    `"N"` and `"ARG"`; basedpyright covers types but neither naming nor unused parameters. Fix what
    they turn up.
11. **Name the two notions of in flight.** `GameService.busy` is `phase is not None`
    (`app/runtime.py:91` today); `Runtime.playing()` filters on `turn is not None` (`:412` today;
    Phase 5 lifts about 135 lines out above both). `busy_refusal` uses the first, the tool surface
    the second, and they diverge during `open()` and `_generate`, which set a phase without a turn.
    Intentional, never stated: one line on each saying which question it answers.
12. **Rewrite the comment above the raise in `Runtime.playing()`** (`app/runtime.py:411` today). It
    reads *"A second turn in flight has no owner: the tool surface is shared"*, which describes a
    state the code prevents elsewhere, so a reader cannot tell the raise is unreachable. Say
    instead: this app is single-player; `busy_refusal` (`:424`) stops a second turn opening and
    `Runtime.lock` (`:383`) serialises every tool call, so this is a cannot-happen guard — and if
    multiplayer or concurrent multi-save play ever becomes real, the answer is to drop
    `stateless=True` (`app/mcp.py:63`), route by MCP session, and delete `playing()`, `Runtime.lock`
    and `NO_TURN`.
13. **Name the interjection die.** `GameService.interject` (`app/runtime.py:171` today) rolls
    `self.rng.randint(1, 10) <= INTERJECTION_ODDS[candidate.chattiness]` inline, the one die that
    does not go through `core.facts.roll`. Move it into a private `_speaks(self, candidate) -> bool`
    beside `INTERJECTION_ODDS` with one line saying why it is not the game's dice: it decides
    whether to spawn a narrator, changes no state and lands no fact.
14. **One idiom for constructing an engine in a test.** 13 module-level `ENGINE = XEngine()`
    against 19 uses of the already-built `ENGINES_BUILT[...]` (`tests/support/table.py:43`); two
    files in the same directory differ (`tests/breathless/test_views.py:7` versus
    `tests/breathless/test_engine.py:27`). Each construction re-reads `rules.md` and every
    `packs/*.json` at import. Use `ENGINES_BUILT` everywhere except where a test needs its own
    instance to set class attributes on.
15. **One fixture constructor.** `open_table` (`tests/support/table.py:210`) <- `open_game_for`
    (`:193`) <- `open_game` (`tests/support/loner.py:58`): the second adds only `state_type=`, the
    third only `engine_id=LONER3E, state_type=Loner3eGame`. Collapse to one function with those as
    default arguments.
16. **Free functions whose first argument is one of our objects become methods.**
    `hire_target(request: Generation)` (`engines/base.py:215` today, moved to `engines/hiring.py` in
    Phase 6) -> `Generation.require_target()` in `core/model.py`, whose whole body is the `target is
    None` refusal and which carries no hiring vocabulary; `map_refusal(draft: MapDraft)`
    (`rooms/worldsmith.py:38`) -> a method on `MapDraft`; `requests_of(exchange: Exchange, ...)`
    (`app/speech.py:90`, called only from `Reader`) and `illustration_request(scene: NarratorView,
    ...)` (`app/media.py:171`, called once from `Illustrator._draw`) -> private methods on their one
    caller. The three `PlayerView` functions `can_type`, `standing_proposal` and `placeholder`
    (`ui/game.py:597,602,628` today) stay free: they are unit-tested on their own, which the rule as
    written does not carve out — add that carve-out to the rule in `CLAUDE.md`.
17. **A test of prose.** `tests/core/test_seam.py:139` asserts that one quoted sentence of
    `engines/scenes/rules.md` appears in `engine.instructions`. `CLAUDE.md` bars testing prose, and
    Phase 2 step 10 changes how the family rules reach `instructions`, so the assertion is brittle
    as well as wrong in kind. Keep the behaviour and drop the quotation: assert that
    `engine.instructions` ends with what `SceneEngine.family_rules()` returns. The line above it
    (`:138`, `startswith("Roll high.")`) keeps proving the engine's own instructions lead.

### Done when

No `Refusal` is raised where only a bug can reach it; no validator helper raises one either. `ruff`
runs `N` and `ARG` clean. Every module in `src/aidm` follows the declared layout. A reader of
`Runtime.playing()` learns why its raise cannot fire and what to do if it must. A marked exchange
reaches no prompt as a `>` line, proved by a test, and no test asserts a sentence of prose. Full
check green; the goldens do not move.

---

## Phase 8 — One name, one meaning

Target: 0 lines net, about 130 sites. Eight names mean more than one thing each, and no other phase
owns them. They are one phase and not a step in the consistency pass because they are larger than
that whole pass and they do not split by file: a rename touches every module that reads the name.
The diff is still readable, because every changed line is one identifier. Each target below is
chosen here; the implementer picks none of them. Every line number below is as of today and most
have moved by now — Phase 5 alone lifts about 135 lines out of `app/runtime.py` — so find the named
symbol, count the sites yourself, and treat the number as a hint.

**load-bearing: `Game.draft()`/`commit()` semantics do not change, only the spelling.**

### Steps

1. **`commit` names three things; two of them change.** `Game.commit` (`core/model.py:117` today)
   keeps the word: it is the gate How-to-work rule 10 names, and it keeps its `revalidate_instances`
   behaviour exactly. `Engine.commit(draft)` (`engines/seam.py:132`), which validates a draft and
   then calls `Game.commit`, becomes `Engine.land` — 7 sites: the definition, `seam.py:130,158`,
   `app/runtime.py:126,221,227` and `turn/run.py:135`. `GameService.commit(state)`
   (`app/runtime.py:341` today), which saves the state and re-points the session at it, becomes
   `GameService.save` — 15 sites: the definition, `app/runtime.py:106,126,149,207,221,227,231,236`,
   and six in `tests/core/` (`test_golden_turn.py:34`, `test_master_tools.py:264`,
   `test_decisions.py:107`, `test_game_service.py:199,305,335`). `app/runtime.py:126` then reads
   `self.save(self.engine.land(draft))`: two meanings, two words.
2. **`Item` names three unrelated shapes.** The room family's `Item` (`rooms/world.py:17`, a `Thing`
   filed `on` something) becomes `Prop` — 36 sites across `rooms/`, `tunnelgoons/`,
   `tests/support/tunnelgoons.py`, `tests/tunnelgoons/` and `tests/core/test_rooms.py`. Breathless's
   `Item` (`breathless/world.py:30`, a name and a die) becomes `Gear` — 16 sites. 24XX's `Item`
   (`twentyfourxx/world.py:39`, a name that is bulky, breaks and upgrades) becomes `Equipment` —
   21 sites. `ItemSheet[I]` from Phase 6 keeps its name and takes `Gear` or `Equipment` as its
   argument. No class name is stored in a save and `schema_of` strips `title`, so nothing on disk
   and no schema fixture moves.
3. **`Check` names a callback and a tool argument.** `type Check[T] = Callable[[T], str | None]`
   (`core/model.py:24`) — what `ask` asks of the value it parsed, returning the reason to re-prompt
   — becomes `Objection`: 10 sites, `core/model.py:24,83`, `app/spawn.py:17,189`, and an import plus
   a `_stub_worldsmith` signature in each of `tests/twentyfourxx/test_tools.py`,
   `tests/breathless/test_engine.py` and `tests/tunnelgoons/test_tools.py`. Breathless's `Check`
   (`breathless/tools.py:50`) keeps the word: it is the ruleset's own vocabulary, the thing the
   master rolls, and its name reaches the model through `schema_of`.
4. **`unwritten` names a field list and a card.** `Person.unwritten()` (`engines/base.py:108`
   today), which returns what the worldsmith may not write into a fresh cast member, becomes
   `Person.forbidden()` — 6 sites: the definition, the overrides at `loner3e/world.py:51`,
   `breathless/world.py:178` and `twentyfourxx/world.py:176`, the caller at
   `scenes/worldsmith.py:94`, and the `Sheeted` copy Phase 6 step 3 lifts.
   `Engine.unwritten(request) -> Fact` (`engines/seam.py:189` today), the card a player reads when
   the worldsmith could not write a request, keeps the word — 6 sites, unchanged.
5. **`require_actor` returns two shapes.** `tunnelgoons/world.py:83` returns
   `(person, abilities)`; `breathless/world.py:194` and `twentyfourxx/world.py:203` return one
   person. Rename the TunnelGoons method to `require_actor_and_sheet` — 5 sites, across
   `tunnelgoons/world.py`, `tunnelgoons/engine.py` and `tests/tunnelgoons/test_tools.py`. The other
   two keep the name, or are already gone into Phase 6 step 4's `require_sheeted`; either way one
   spelling is left meaning one thing.
6. **`starting_items` names a hook, a method and a free function.** The seam hook
   `RoomEngine.starting_items` (`rooms/engine.py:85`, overridden at `tunnelgoons/engine.py:139`)
   keeps the name. `Goon.starting_items(taken)` (`tunnelgoons/world.py:63`), which turns the
   character's kit into items, becomes `Goon.unpack_kit` — 2 sites, the definition and the call at
   `tunnelgoons/engine.py:140`. The free `starting_items(kits)` (`twentyfourxx/engine.py:507`)
   becomes `items_from_kits` — 5 sites: the definition, `twentyfourxx/engine.py:198,323` and
   `tests/twentyfourxx/test_world.py:6,119`.
7. **`_Choice` is declared twice inside `app/`.** `app/media.py:139`, which parses one image reply,
   becomes `_ImageChoice` beside `_ImageReply` — 2 sites, `:139` and `:144`. `app/builtin.py:50`
   keeps the name: a choice in a chat completion is what the word means everywhere else.
8. **`Driver.parse` shadows the project-wide `parse`.** `app/spawn.py:15` imports `parse` from
   `core.entities` into the module that declares `Driver.parse` (`:43`). Rename the protocol method
   and both implementations to `read_result` — 5 sites: `app/spawn.py:43,82,121,150` and
   `tests/core/test_spawn.py:82`.

### Done when

`Engine.land`, `GameService.save`, `Prop`, `Gear`, `Equipment`, `Objection`, `Person.forbidden`,
`require_actor_and_sheet`, `Goon.unpack_kit`, `items_from_kits`, `_ImageChoice` and
`Driver.read_result` exist, and one grep for each old word finds one meaning. A draft still becomes
committed state through `Game.commit` and `Game.draft()` still deep-copies: no behaviour moved with
the words, proved by the suite passing unchanged. `uv run aidm` plays a turn. Full check green;
`tests/core/fixtures/` does not move; `git diff` shows identifier lines and nothing else.

---

## Phase 9 — The test re-shape

Target: 0 lines changed beyond imports. 17 files move so that `tests/` mirrors `src/`; about 14 more
change only an import line. This phase is last and it is a pure move: nothing else is in its window,
so the diff is verifiable by reading the file names.

### Steps

1. **Create `tests/{engines,turn,app}`** beside the existing `tests/core`, `tests/ui` and the four
   engine directories, which stay: each holds 740-1,240 lines of genuinely different rules.
2. **Move the seven that test `app`** out of `tests/core/`: `test_builtin.py`,
   `test_game_service.py`, `test_mcp_lifespan.py`, `test_media.py`, `test_spawn.py`,
   `test_speech.py`, and `test_roles.py`, which Phase 2 step 5 created for `app/roles.py`.
3. **Move the two that test `turn`**: `test_turn.py` and `test_decisions.py`, both of which drive
   `Turn` (`aidm.turn.run`) over the Loner engine.
   `test_context_boundary.py` goes to `tests/app/` instead: after Phase 2 it renders the master
   prompt from `turn/run.py` and the narrator prompt from `app/roles.py`, and files under the higher
   layer. `test_views.py` stays in `tests/core/`: it tests `core/views.py`'s models.
4. **Move the five that test `engines`**: `test_rooms.py`, `test_scenes.py`, `test_seam.py`,
   `test_engines_base.py`, `test_integrity_boundaries.py`.
5. **Move `tests/ui/test_launcher.py` to `tests/app/`.** Its 313 lines import `app`, `config`,
   `core` and `engines`, and no `ui` at all.
6. **What stays in `tests/core/`:** `test_config.py`, `test_dice.py`, `test_documents.py`,
   `test_engine.py`, `test_golden_schemas.py`, `test_golden_turn.py`, `test_master_tools.py`,
   `test_package_boundary.py`, `test_prompt.py`, `test_store.py`, `test_views.py`, and `fixtures/`.
   `test_dice.py` stays because Phase 2 step 8 moved `keep_highest` into `core/facts.py`: it is a
   `core` test now, not an engines one. `test_prompt.py` is the half of the old `test_views.py` that
   followed `core/prompt.py` in Phase 2. The goldens keep their path, so no fixture is rewritten.
7. **Rename `tests/support/loner.py` to `tests/support/game.py`.** It is the shared default game
   fixture — 14 files outside `tests/loner3e` import it — not a Loner helper. Update every importer.
8. **Change nothing else.** No test body, no assertion, no fixture argument. `pyproject.toml` needs
   no edit: `testpaths = ["tests"]`.

### Done when

Every file under `tests/<layer>/` imports that layer and `support` and nothing further down the
tree it does not test. `git diff --stat` shows renames plus import lines, and no other changed line.
The same number of tests pass as before the phase. Full check green.
