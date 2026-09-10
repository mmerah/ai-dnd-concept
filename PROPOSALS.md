# PROPOSALS — round 2: conceptual simplification, drastic cuts, over-engineering

Next action: read proposals 1 to 4 (about 10 minutes). They need no decision; say "go" on any of
them and it becomes the first phase of a new plan. Proposals 5 to 9 each end in a decision with
two or three options: pick one letter per proposal.

Four independent reads of the whole codebase (one lead, three subagents: shared machinery,
engines, edges and tests). Baseline: `src` 9,994 lines, `tests` 11,113 lines, `qa` ~1,400
lines, 571 tests passing. Line counts below are ±20 %. Time estimates are for one person with
the tests as a net.

Every proposal keeps every player-facing feature unless its risk line says otherwise. Things the
previous round already decided (`git show 93fe061:PROPOSALS.md`) are not re-proposed unless the
reasoning is new; those cases are marked "reopened".

## The ten, ranked

### 1. One way to refuse a model answer: a bar raises `Refusal`, nothing returns `str | None`

**Concept.** CLAUDE.md says a message a role reads is a `Refusal`. The code has a second idiom
beside it: a bar that returns `str | None` (`Objection[T]`). Every string bar is converted back to
a raise at its consumer, and `Engine.compose` does the reverse (catches a `Refusal` from `build`,
returns the string).

**Where.** `scene_refusal`, `map_refusal`, `extension_refusal` (`engines/scenes/worldsmith.py`,
`engines/rooms/worldsmith.py`); `SheetDraft.refusal` (`twentyfourxx/worldsmith.py`);
`Hiring.hire_bar`; `NarratorView.narration_refusal / speakers_refusal / interjection_refusal`
(`core/views.py`); `Engine.compose`'s inner closure; `Runtime.new_scenario`'s `playable`
closure. Four `if (refused := x_refusal(draft)) is not None: raise Refusal(refused)` sites.

**Change.** `Objection[T]` becomes `Callable[[T], None]` that raises. `ask()` in `app/spawn.py`
already wraps `parse` in `try/except Refusal`; the bar call moves inside that `try`. The joined
"the scene needs a; b; c" text survives as the raised message, so the one re-prompt still sees
every unmet item. `compose` collapses to two lines; `playable` becomes `lambda built:
engine.begin(name, built, character)`.

**Files.** `core/model.py`, `core/views.py`, `app/spawn.py`, `app/runtime.py`,
`engines/seam.py`, `engines/hiring.py`, both families' `engine.py` and `worldsmith.py`,
`twentyfourxx/worldsmith.py`, `tests/support/table.py`, `tests/engines/test_scene_bar.py`
(string asserts become `pytest.raises(Refusal, match=...)`).

**Delta.** About −45 / +10. **Risk.** Low; no player-facing change; the hidden-info gate is
untouched. **Confidence.** High. **Time.** About 2 hours. Unblocks 3.

### 2. One request table replaces `unwritten`, the `advance` if-chain and the `Hiring` MRO rule

**Concept.** A worldsmith request is keyed by `operation` in three places: `unwritten:
dict[Slug, Fact]` (read by `Engine.validate` and `GameService._generate`), the `advance()`
dispatch (an if-chain in `SceneEngine.advance`, a `raise ValueError` guard in
`RoomEngine.advance`), and `Hiring.advance`'s cooperative `super()` that only works because of
the docstring rule "List it first in the bases". Three of four reads picked this independently.

**Change.** `requests: dict[Slug, Request[G]]` built in `Engine.__init__` like `tools`, where
`Request(unwritten: Fact, write: Callable[[G, Generation, WorldsmithAnswer], Awaitable[...]])`.
`SceneEngine` registers `departure` and `complication` (split into `depart` and `complicate`
methods), `RoomEngine` registers `extend`, `Hiring` registers `hire` after `super().__init__()`
and loses its `advance`. `Engine.advance` becomes concrete and three lines long; `validate` and
`runtime._generate` read the same dict. The four `unwritten = {**SceneEngine.unwritten, HIRE:
HIRE_UNWRITTEN}` lines go.

**Files.** `engines/seam.py`, `engines/hiring.py`, `engines/scenes/engine.py`,
`engines/rooms/engine.py`, the four concrete `engine.py`, `app/runtime.py:226`,
`tests/core/test_golden_turn.py:66`.

**Delta.** About −30 / +15; one ordering constraint fewer to remember. **Risk.** Low.
**Confidence.** High. **Time.** About 1.5 hours.

### 3. Author once: one seam `author`, the opening bar run once, the scenario built once

**Concept.** Authoring runs the same check three times per worldsmith answer: `build_scenario`
runs `scene_refusal`/`map_refusal`, then `playable` → `engine.begin` → `new_game` runs it again
plus the world validator, then `land` re-parses the world. `compose` calls `build` twice. Both
families carry near-identical `render_opening`, `render_request`, `write_next`, `build_scenario`
and `author` (about 55 lines each); they differ only in the sections function, the draft model,
the opening intent, where the premise comes from, and the next-draft bar.

**Change.** After 1, make `Engine.author` concrete. Two options:

- (a) Full hoist. Families supply `draft_model()`, `family_sections(world | None)`,
  `next_refusal(draft, world)`, `premise_of(draft)`, `opening_intent`. About −70 net. Costs a
  third type parameter on `Engine` (the draft) or a `type[BaseModel]` narrowed in the family.
- (b) Hoist only the pure renderers (`render_opening`, `render_request`, `build_scenario`; they
  take `answer: type[BaseModel]` and need no new generic) and drop the bar from `build_scenario`
  (`begin` is the real bar and always runs through `playable`). Leave `author`/`write_next` per
  family. About −35 net, no new generic. Rooms needs `draft.places.get(draft.start)` for the
  premise instead of `[]`.

Recommend (b): the duplication goes without a fourth type parameter.

**Files.** `engines/seam.py`, `engines/scenes/engine.py`, `engines/rooms/engine.py`,
`app/runtime.py:new_scenario`. **Risk.** Low-medium; the golden `worldsmith.txt` fixtures must
not change (section order is preserved). Two `test_build_scenario_*` tests move to `author`.
**Confidence.** High for (b) after 1. **Time.** About 1.5 hours.

### 4. Same code in three engines, written once

**Concept.** Five places where two or three engines carry the same lines, verified by grep:

1. `Hiring.hireable` is abstract and all three bodies are `return
   draft.payload.require_hireable(entity_id)`. `World.require_hireable` already exists. Delete
   the hook; `Hiring.hire`/`advance` call `self.world(draft).require_hireable(...)`. To keep
   `install_sheet(member: M)` typed, replace the three methods with one attribute `member:
   type[M]` and an `isinstance` narrow. `hire_bar` has one override (24XX); after 1 it folds into
   that engine's `install_sheet` as a raise.
2. `DropItem` (`breathless/tools.py`, `twentyfourxx/tools.py`) is the identical arm class twice;
   `Survivor.require_item/drop_item` equals `Crewmate.require_item/drop_item`. `ItemSheet` sits in
   `hiring.py` but has nothing to do with hiring. Move `ItemSheet` to `base.py` beside `Sheeted`,
   give it `drop_item(owner)`, and share `DropItem`.
3. Breathless `roll` and 24XX `roll` carry the same 8-line branch (one die → `roll()` plus a
   hand-built `DiceEvent`; several → `keep_highest()` with a `d8+d6` label); Loner's `_pair` is
   the same idea twice. One `roll_pool(faces, reason, rng, *, label) -> (kept, DiceEvent, Fact)`
   in `core/facts.py` that highlights only when `len(faces) > 1`.
4. `test_luck` in Breathless and 24XX is the same five lines with different band words; a
   `luck_test(question, die, bands, rng)` in `base.py` beside `banded`.
5. The three `master_tool("change_world", ...)`, `("next_scene", ...)`, `("hire", ...)` lines
   repeat ×4/×3/×3; a `family_tools()` on `SceneEngine` and on `Hiring` prepends them.

**Delta.** About −60. **Risk.** None to features; golden `master_tools.json` schemas stay
byte-identical if docstrings and descriptions are kept; keep `highlight=()` for one die so the
turn goldens do not drift. **Confidence.** High. **Time.** About 2 hours.

### 5. Decision: the world grows one way, through the master's tool call (reopened, widened)

**Concept.** Today the world grows two ways. The master calls `next_scene(pursuit=...)` or
`next_scene(complication=...)` or `hire`, which sets `Game.generation`. Or the player presses the
page's own button ("Move on" for scenes, "More map" for rooms), which goes through `Engine.act`,
`GameService.act` and `intent`, a second `_generate` flow (`act` → worldsmith → turn, the reverse
of the normal turn → worldsmith), `PlayerView.action`, `SceneRun.offered` and `offer()`, and in
the UI `action_button`, `way_on_panel`, `submit(acting=True)`, plus "the way on has changed"
staleness checks. For scenes the button does nothing the composer cannot: it adds the
`MOVING_ON` note and opens a normal turn. For rooms it is the only trigger for `extend`.

The previous round left "More map as a master tool" as a play-feel change costing one extra
master spawn per push-on. Reopened because the scene half of the same machinery is pure UI sugar,
and because deleting both halves removes a concept (the page's own action) rather than a method.

**Options.**

- (a) Delete the page action entirely. Scenes: `next_scene(pursuit)` already covers it; drop
  `offered`, `offer()`, `MOVE_ON`, `act`. Rooms: add an `extend_map` tool (or an arm) the master
  calls when `frontier() == 0`; the rules prompt already tells it the map is out, and a NOTES line
  when the frontier is empty makes it hard to miss. Removes `Engine.act`, `GameService.act` and
  `intent`, `PlayerView.action`, and about 40 lines of `ui/game.py`. About −150 in `src`, more in
  tests. Feature kept: the world grows when it runs out. Lost: the explicit button; a weak master
  that forgets to extend leaves the player typing "I push on" twice.
- (b) Delete only the scene half. Keep `act` for rooms. About −70. Removes `offered`/`offer()`
  and the scene `act`; keeps the two `_generate` flows.
- (c) Leave it. The button is a documented affordance ("the page's buttons are the engine's
  own", README).

Recommend (a). **Confidence.** Medium. **Time.** Half a day including the room tool and tests.

### 6. Decision: where the scene log lives

**Concept.** Every exchange the player reads is core-typed (`Exchange`), yet it is stored inside
the engine payload (`SceneRun.exchanges`, `Visit.exchanges`) and projected back out through three
abstract `World` methods (`records()`, `record()`, `exchanges()`) into a fourth type,
`SceneRecord`, on every prompt render. Nine call sites in `app/` and `turn/` reach through
`engine.world(state)` only to get history; it is the one thing above the engines that still
touches the world for something that is not world shape.

The previous round left the projection because `Visit` has no title without a place lookup. One
read this round proposes the reverse move; another read lists the projection as load-bearing
(core cannot import a world shape). Both are right about different halves, so it is a decision.

**Options.**

- (a) The log moves to `Game.log: list[Chapter]` in core (`Chapter(Mutable)`: `title, focus,
  recap, exchanges`). `Engine.close` appends to `draft.log[-1].exchanges`; `Engine.begin`,
  `SceneEngine.install` and `RoomEngine.move` open a chapter. Deletes `SceneRecord`, the three
  abstract `World` methods and their six implementations, `SceneRun.exchanges/recap`, and `Visit`
  (visits become `list[Slug]`). `LauncherCatalog`, `GameService.history/_newest/unopened` read
  `state.log` with no engine call. About −60 / +30. `title`/`focus` are stored twice (run and
  chapter). Every save goes stale once, which the README allows.
- (b) Keep the log in the world but make `log: list[Chapter]` a concrete field on `World` (no
  abstract methods, no projection; `app` still calls `engine.world(state).log`). Half the deletion,
  no save-shape change beyond a rename.
- (c) Leave it.

Recommend (a): it is the last place the app reaches into the world. **Confidence.** Medium.
**Time.** Half a day; regenerate the goldens and diff to prove the prompts did not change.

### 7. Decision: engines stop knowing hex colours (reopened, widened)

**Concept.** `Engine` carries `palette` (a dict of CSS custom properties), `dice_look` (three
hex colours) and `art_style` (a prompt). The first two are UI; `core/views.py` holds `Palette`
and `DiceLook` only to type them. `ui/theme.py` then keeps a module-level `_PALETTES` registry
filled by `seed()` at startup, generates one CSS block per engine, and `set_engine` juggles
`game-theme-<id>` classes on the layout with a `cast`. The previous round left "theme tokens on
the layout" as small; reopened because moving the data out of the engines is the conceptual
half, and it makes the registry unnecessary.

**Options.**

- (a) Move `palette` and `dice_look` to one table in `ui/theme.py` keyed by `EngineId`, with the
  neutral palette as the fallback for an engine not in it. `art_style` stays on the engine (a
  prompt is engine data). Delete `Palette` and `DiceLook` from `core/views`, `seed()`,
  `_PALETTES`, `_palette_css`, and the class juggling: `set_engine(engine_id)` writes the
  variables inline on `body` plus `ui.colors(...)`. About −60 / +25. The UI gains a per-engine
  table, which is a second place that names engine ids (the registry being the first); the
  boundary test that forbids built engine ids in `ui/` would need to allow this one file.
- (b) Keep the data on the engine, only drop the registry: `set_engine(palette)` takes the
  palette from the engine the caller already holds. About −45 / +10; engines still carry CSS.
- (c) Leave it.

Recommend (a). **Confidence.** Medium (needs a visual check of drawer and menu colours).
**Time.** About 1.5 hours.

### 8. Decision: settings apply at the next start, not live

**Concept.** Live apply needs `Runtime.reload_settings`, `busy_refusal`, `play_refusal`, the
`_mount` split, `GameService.stop`, the `apply_settings` closure in `ui/app.py`,
`GamePage.refuse_play` (four call sites), the "The settings changed. Reload this page" message,
`QaRuntime.reload_settings` and three tests. The settings page already says "The server port
applies at the next start".

**Options.**

- (a) Every key applies at the next start. `save()` writes `.env` and says "Restart to apply".
  About −60. Lost: changing a model or a key without restarting the app. Keep the five-line
  "a turn is in flight in another tab" check if multi-tab safety matters.
- (b) Leave it.

**Confidence.** Medium; only worth it if the restart is acceptable. **Time.** About 40 minutes.

### 9. Decision: every spawn is cold, drop CLI session resume (reopened)

**Concept.** `ask()` re-prompts a refused answer with `--resume <session>` / `codex exec resume
<thread>`. For that one path there are `RunResult.session`, `Driver.command(..., session, ...)`,
`_ClaudeResult.session_id`, `_string()` (thread-id extraction), the `session` parameter on all
nine `Spawner.run` implementations, `ScriptedSpawner.resumed`, and qa's fake session ids. The
completion-API path already resends the whole prompt. README says roles "start cold every turn".

The previous round left this because a cold retry re-reads up to 30k tokens, near-free under
prompt caching and unmeasured on Codex. Reopened because it is a whole concept ("a spawn can be
warm") for a path that runs at most once per call (`RETRIES = 1`).

**Options.**

- (a) Drop it. `run_cli` always sends `f"{prompt}\n\n{correction}"`; `RunResult` collapses to
  `str`. About −70 / +10 across `spawn.py`, `builtin.py`, `roles.py`, seven test doubles and
  `qa/agents.py`. Cost: one full re-prompt per refusal.
- (b) Keep it.

**Confidence.** High that it is safe; medium that it is worth the token cost on Codex.
**Time.** About 45 minutes.

### 10. Edge and test cuts (bundle, no decisions inside)

Each is small; together about −250 lines and one afternoon.

1. **Settings nobody sets become constants.** `media.scene_ratio`, `media.icon_ratio`,
   `media.max_references`, `speech.sample_rate`, `speech.voices` (not even reachable from the
   settings page, which skips tuples). Each is a config field, an env key, a settings box and a
   form line. Module constants instead. Optionally `RoleConfig.max_rounds` too.
2. **Fewer spellings for "provider".** Drop `RoleConfig.api`, `RoleSettings.each()` and
   `ROLE_NAMES` (each used once, in `_keys_present`); the validator iterates three tuples.
3. **`Roles` without the engine.** `Runtime.new_scenario` builds a throwaway
   `Roles(spawner, engine).worldsmith()` that uses no engine. `Roles` holds only the spawner;
   `narrate`/`interject` take the engine; `worldsmith(spawner)` is a free function beside `ask`.
4. **`Engine.begin` validates the new world three times** (`parse` in `new_game`, `parse` of the
   game, `land` → `commit`). Trim to `parse` + `validate`; `land` stays the tool-path pipeline.
5. **Tests that test wiring.** `tests/ui/test_theme.py` (CSS class names on NiceGUI internals),
   `tests/app/test_mcp_lifespan.py` (a private `_task_group`; `test_mcp.py` already runs the
   lifespan end to end), `test_an_aliased_literal_field_is_a_dropdown`,
   `test_poll_turn_walks_the_player_view_and_history_once` (monkeypatched call counting). About
   −130.
6. **Test helpers.** `ui_settings` and `offline_settings` are one builder; `support/game.py::
   session()` builds a `GameService` by hand beside `open_game()` which builds it through
   `Runtime`; `SettingsForm(..., boxes)` and the `Box` Protocol exist only so a test can inject
   `FakeBox` (make `changes(settings, typed)` a free function). About −45.
7. **Small deletions.** `Engine.tool()` re-wrapped by `answer` with a second message;
   `Generation.require_target` (one caller); `mcp.list_tools` (inline); `GameService.drain()` (a
   test-only hook on a production class; move to test support); `ui/__main__.py` (a second
   entry point beside `uv run aidm`); `.mcp.json` and `.codex/config.toml` (the spawned CLIs get
   their MCP config from flags; these serve only an interactive CLI in the checkout);
   `Loner3eSheet.forbidden` recomputing "alive" instead of `super()`; `sentence()` living in
   `scenes/world.py` but used by two engines (move to `core/prompt.py`).

**Confidence.** High for all. **Risk.** None to features.

## Looked at and left (so nobody reopens them)

- **`qa/`** (~1,400 lines). One read proposed deleting or halving it. Left: the earlier round
  settled D7 to keep every scenario under CI and the linters, because it is the only coverage of
  `ui/app.py`, `ui/create.py`, `ui/widgets.py` and the real MCP transport. Reopen only if the UI
  gets its own tests.
- **`session.engine` readable from the UI** (delete the three forwarders and the AST test). Left:
  the earlier round settled D11 to give the UI those accessors on purpose.
- **Interjections** (56 mentions across 11 source files for one party line after a turn). A
  documented player feature; a cut, not a simplification. Its footprint is the price of a
  feature that spans every layer.
- **`schema_of` normalisation** (35 lines). Saves tokens in every worldsmith prompt and tool
  declaration; measure a prompt before touching it.
- **`final_message` / `_last_said` / `_found`** in `spawn.py`. Five real CLI output shapes are
  pinned by one parametrised test; the Codex event stream needs the walker.
- **Both transports, the `turn` layer, `rooms/` with one engine, `Engine[P, G]` and
  `Game[P]`, `Line` vs `SpokenLine`, `Subject` vs `Thing`, `NarratorView`/`PlayerView` as
  separate frozen models, `Turn._apply`'s copy-then-land, `PendingOption.name/args` replay,
  `MountedLifespan`, the reflection-based settings form, the import-direction test, the 17
  goldens.** Each is a promised feature, a stated property, or the hidden-info gate; decided in
  the previous round and confirmed by all four reads this round.
- **`Person.hired()/hireable()/forbidden()` on the non-sheeted base.** They let
  `World.require_actor` and `scene_unmet` be generic over Loner (no sheets) and the three hiring
  engines.
- **One `Cached` base for `Illustrator` and `Reader`** (−30). An abstraction with two users that
  buys little; listed so it is not re-derived.
- **`WorldChange` unions restating `SharedChange`** (−12). Pydantic's discriminated union over a
  nested PEP 695 alias may change the `$defs` layout; try only with the schema goldens watching.
- **Deriving `scenario`/`character` from `cast` in `SceneEngine.__init__`** (−10). Real but
  small, and basedpyright's narrowing of a runtime-parametrised generic is unverified.

## Suggested order once decided

1. Proposal 1 (bars raise), then 2 (request table), then 3(b): they all touch
   `engines/seam.py`, so in sequence, about 5 hours total.
2. Proposal 4 and bundle 10: independent of everything, one afternoon.
3. Decisions 5 to 9 in whatever order they are taken; 5 and 6 change save shapes, so do them
   before any long game is worth keeping.

Next: pick one letter each for 5, 6, 7, 8 and 9, or say "go" on 1 to 4 to start there.
