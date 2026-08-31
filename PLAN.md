# PLAN

The order of work. `VISION.md` says what we are building and why; read it once, first. This file
says what to do, step by step, and is self-standing.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

Rules:

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step**, unless the step says it is part of a group
   that is checked together. Never carry a red check past a checkpoint.
3. **Tests must be green.** Delete a feature and its tests in the same step. Change a shape and
   update its tests in the same step. Never skip a test to make the check pass.
4. **Golden files** live in `tests/core/fixtures/`. To rebuild them:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest
   ```
   Do this **once**, at the end of a phase, then read every changed line before you continue.
   If a change surprises you, stop and ask.
5. **Count the lines** at the start and end of each phase; write both in `PROGRESS.md`:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never invent extra deletions to hit
   a number.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive.

| phase | `src` after |
|---|---|
| start | 9,452 |
| 0 — keep the probe code | 9,452 |
| 1 — one engine | 7,471 |
| 2 — the scene kit and the port | 5,806 |
| 3 — the three roles and the tool surface | 5,458 |
| 4 — the pages | 5,625 |
| 5 — the sweep | 5,627 |
| (scene transitions rebuilt, off-plan) | 5,791 |
| 6 — the architecture deletion | 5,600 |
| 7A — the restructuring pass | about 5,540 |
| 7B — the roles get drivers | about 5,880 |
| 8 — the engines return | + about 1,050, then about 770 |

---

# Phases 0–6 — done

The work is in the git log and the per-phase entries were pruned from `PROGRESS.md`; read
`git log --stat` for the detail. In order: **0** kept the two probes under `docs/probes/`;
**1** cut the game to Loner 3e alone and deleted succession, `resolvers` and `PlayerAction`;
**2** replaced the map with the scene kit and ported Loner onto it; **3** made the game master,
the narrator and the worldsmith spawned CLIs behind one MCP surface, and deleted `pydantic-ai`
model code from the turn; **4** made the browser the whole game; **5** swept the prose, the dead
names and the last dependency; **6** collapsed the live-game lifecycle into one session owner,
cut `Engine` to one extension point, fixed the four-file engine template, merged `state/`,
`kernel/` and `content/` into `core/`, and applied one strict file order across `src/`.

**What those phases settled, and what stays true.** Everything below was measured or paid for
once; do not re-litigate it.

1. **A sheet union is a plain assignment**, `Sheet = Annotated[A | B, Field(...)]`. `type Sheet =
   ...` breaks the discriminator and every sheet fails to parse. Three lines apart, both forms are
   in use on purpose.
2. **The four-file engine template is law**: `state.py`, `rules.py`, `creation.py`, `engine.py`,
   the same four names for every engine. A tool argument model stays in the same *file* as the
   resolver that reads it. An `oracle.py` or an `advancement.py` cannot repeat across engines.
3. **One strict file order per module**: imports, constants and type aliases, models and classes,
   public functions, private helpers — with the exception recorded in `CLAUDE.md`: a statement
   evaluated at module scope keeps its dependency order, and the section rank only breaks ties.
4. **The generic-`Game` step was refuted as a *union* and skipped on cost, not impossibility.**
   `core/model.py` still aliases four types straight at `engines.loner3e.state`. (`core/envelope.py`
   also stood at the end of phase 6; phase 7A step 2 deletes it, which does not change anything
   below.) What five probes proved: a union payload dies on invariance at
   `narrator_view`, `apply_change` and `apply_scene`; sheet erasure dies on the published schema,
   because the worldsmith would be handed a sheet of `{}`; a two-parameter shape is rejected by
   the type checker. **Route 2 — `Game[S]` with a `SerializeAsAny` payload and a per-engine `Game`
   subclass — works and round-trips byte-identically**, at about 46 annotation sites and one `Any`
   behind an alias, and it buys three lines while there is one engine. It is Phase 8's to pay.
5. **Save golden fixtures are the contract.** `tests/core/fixtures/save/loner3e.json` and
   `state/loner3e.json` are dumps of `Game`. If a refactor changes them, stop and ask.
6. **No backwards compatibility.** Stale saves are invalid, there is no version field and no
   migration path.

---

# Phase 7 — split in two

Phase 7 is two phases, **7A** then **7B**.

- **7A restructures.** It removes mirrored persistence types, a split tool dispatcher, a
  default-engine guess, and the two-graph chronology. **It is not a line-deletion phase.** Most of
  what it touches moves rather than disappears, so `src` lands near **5,540**, inside a
  5,500–5,610 range. Judge it by what is gone from the design, not by the count.
- **7B gives the three roles real CLI drivers.** Provider, model, effort, resumed provider
  sessions, a scrubbed child environment, and a measured record of what a spawned Codex can
  reach. `src` goes **up** about 340 lines, to about **5,880**.

**Do 7A first.** 7B stores a provider session per save, and 7A step 6 rewrites the save shape.
7A also empties `app/runtime.py`, which is where most of 7B lands.

**These decisions are settled. Do not re-open them inside phase 7.**

1. **`core/views.py` stays.** `NarratorView`'s absence of hidden fields is a correctness
   boundary. `PlayerView` is read by pages that import neither the engine nor the kit, which is
   `VISION.md` §5. Deleting or thinning it is not a phase 7 step.
2. **The generic `Game[S]` is not paid here.** Phase 8 step 0 owns it, measured. 7A step 2
   removes the reason to bring it forward.
3. **`Loner3eState` is not flattened into `Game`.** That deepens the one inversion phase 8 exists
   to pay off.
4. **`PendingOption.name`/`args` and `Engine.answer` stay**, although no code in `src` builds an
   option today. Phase 8 books them for Breathless's loot tool. Redesigning suspension into an
   engine-private continuation is a phase 8 decision, taken when Breathless measures the tool
   budget.
5. **`LaunchTarget` does not carry the engine.** The URL is `/game/{slug}/{scenario}/{character}`
   and the route builds a target from those three parts alone. The scenario file on disk is the
   authority for which engine plays it, so `Runtime._open` resolves it there. Adding a fourth
   coordinate would force the route to load the catalog before it can build a target.
6. **A per-turn MCP endpoint is not in phase 7.** Today one endpoint is created once, mounted
   once at `/mcp`, and bound to the whole `Runtime`. A per-turn endpoint needs dynamic serving,
   path allocation, readiness, address injection and teardown, and it buys concurrent games,
   which is not a goal. `Runtime.playing()` and the global lock stay. Revisit it only when two
   games must play at once.

---

# Phase 7A — the restructuring pass

**Goal:** remove the architecture that represents possibilities instead of behaviour.

**Why:** four structures cost real maintenance today. Persistence types are mirrored, so a field
added to `Game` is silently dropped from a save listing. Tool legality is decided in five places
across three layers, and every engine tool body runs twice. `Runtime.engine` means "whichever
engine the dict happens to yield first", which breaks the moment phase 8 installs a second one.
And the story's chronology exists twice — as scenes inside the world, and as a flat history beside
it — joined back together by scene *title*.

**A move counts as zero.** Do not expect a deletion phase. Step 6 removes the most design and
adds the most code back.

**Order matters.** Step 1 is first because you look at that panel at every later checkpoint. Step
6 is last because it is the only step that can be dropped.

## Step 1 — four cards in the scene tab

`sheet_panel` in `src/aidm/ui/panels.py` renders scene status, cast, sheet and threads as one
unbroken column. Split it into four bordered cards, always visible, no nesting.

1. Rename `sheet_panel` to `scene_sidebar`. It has two consumers: the import in
   `src/aidm/ui/game.py` and the call inside `GameView.sheet`. Keep the method name
   `GameView.sheet` — `refresh_all` binds the refreshables by attribute.
2. Add four private helpers in `panels.py`, each taking the arguments it needs and nothing more:
   - `_scene_card(view: PlayerView, failure: str) -> None` — `view.question`, plus the `NO_WAY_ON`
     warning when `failure` is non-empty.
   - `_cast_card(session: GameService, view: PlayerView) -> None` — the player row, `view.present`,
     `view.companions`. It needs `session` for `session.icon`.
   - `_sheet_card(session: GameService, view: PlayerView) -> None` — `view.sheet`, `view.traits`,
     `view.carrying`.
   - `_threads_card(threads: tuple[ThreadRow, ...]) -> None` — what `_threads` renders today;
     fold `_threads` into it.
   `scene_sidebar` reads `session.player_view()` once and calls the four inside one
   `ui.column().classes("w-full").style("gap: 0.75rem")`. Each helper opens
   `with ui.column().classes("game-card w-full")`.
3. Reuse the `.game-card` token in `src/aidm/ui/theme.py`. Add no CSS.
4. **Keep `heading(..., tight=...)`.** `journal_panel` still passes `tight=True`, so the parameter
   stays even though the four cards no longer need it.
5. Full check, then `uv run aidm` and read the panel at a narrow and a wide splitter width.

**Done when:** four bordered cards. About **+18** lines.

## Step 2 — delete the envelope stack

`src/aidm/core/envelope.py` holds three models that restate `Game`, `Scenario` and `Character`
field for field with a raw payload. `Engine.restored` validates the same string twice.
`io.scenario_of` and `io.character_of` dump one model and validate another. The only thing the
mirrors buy is reading a document's `engine` **before** the engine is known. A header buys that
for a fraction of the size.

**"Parse once" means one JSON decode, not one disk read.** Decode the text to a Python value, then
validate that same value against as many models as the caller needs. Never decode twice.

1. Add to `src/aidm/core/entities.py`, beside `Frozen` and `Mutable`:

   ```python
   class Header(BaseModel):
       """Routes a document before its engine is known; the rest of the document is ignored."""

       model_config = ConfigDict(extra="ignore", frozen=True)
   ```

2. Add to `src/aidm/core/model.py`, after `ScenarioMeta`:

   ```python
   class EngineHeader(Header):
       engine: EngineId


   class SaveHeader(EngineHeader):
       scenario_id: Slug
       character_id: Slug
       scenario: ScenarioMeta
       turn: int = Field(ge=0)


   class CharacterHeader(EngineHeader):
       id: Slug
       name: str
   ```

3. In `src/aidm/core/io.py`, make the decode public and separate from validation, so every reader
   keeps the duplicate-key guard that `_unique_keys` gives file reads today:

   ```python
   def decoded(raw: str) -> JsonValue:
       """`json` keeps the last of two equal keys, so a doubled id would vanish without a word."""
       return json.loads(raw, object_pairs_hook=_unique_keys)
   ```

   `_read(path, model)` becomes `model.model_validate(decoded(_read_text(path)))`.
   **Every caller outside `io.py` must go through `decoded` too.** `SaveEnvelope
   .model_validate_json(raw)` in `app/launch.py` and `Game.model_validate_json(raw)` in
   `engines/core.py` skip that guard today; both must use `decoded` after this step.
4. Rewrite the readers in `src/aidm/core/io.py`. Delete `scenario_of` and `character_of`.
   - `read_scenarios`: `value = decoded(text)` once, then `EngineHeader.model_validate(value)`;
     skip and log when `header.engine not in engines`; then `Scenario.model_validate(value)`.
   - `read_characters`: the filename already names the engine, so validate `Character` directly
     and raise when `character.engine` disagrees with the filename.
   - `scenario_envelope` becomes `read_scenario(directory, name) -> Scenario`.
   - `load_character` validates `Character` and keeps both existing checks (engine, filed-under id).
   - `write_character(directory, character: Character)` takes the domain model. Its sibling
     name-check validates `CharacterHeader`, because a sibling file may belong to another engine
     and its payload would not validate.
5. `src/aidm/engines/core.py`: `Engine.restored` decodes once, validates `EngineHeader` for the
   engine check, then `Game` from the same value. `CharacterCreation.created` returns
   `tuple[Character, Rows]`; delete the envelope it builds.
6. `src/aidm/app/launch.py`: `load_catalog` validates `SaveHeader` from `decoded(raw)`.
7. `src/aidm/app/runtime.py`: `Runtime._open` calls `read_scenario`. `src/aidm/ui/create.py`
   passes a `Character` to `write_character`.
8. Delete `src/aidm/core/envelope.py`, including `RawPayload`.
9. Full check. **The save, scenario and character JSON must not change.** The golden fixtures
   under `tests/core/fixtures/` must be byte-identical without a regen. If any changes, stop and
   ask.

**Done when:** `core/envelope.py` is gone, and no document is decoded more than once. About
**−31** lines.

## Step 3 — one dispatcher, owned by `Turn`

Tool legality is decided in five places: `GameService._tool_refusal`, `GameService._engine_call`,
`Turn.apply`, `core.tools.apply_to_draft`, and `mcp.call`. There are two tool dataclasses and two
dispatch paths. And **every engine tool body runs twice** — once against a throwaway copy to see
whether it is refused, then again for real — which quietly requires every resolver to be safe to
run twice. (`start_turn`, `scene` and `next_scene` already run once; only `MasterTool` calls and
the pending-option resolver go through `_apply`.)

1. In `src/aidm/turn/run.py`, define `TurnTool` **after** the `Turn` class, because this module
   has no postponed annotations and a dataclass field annotation is evaluated at class creation:

   ```python
   @dataclass(frozen=True, slots=True)
   class TurnTool:
       name: str
       description: str
       run: Callable[[Turn], str]
       args: type[BaseModel] = NoArgs
   ```

   `Turn.tools()` therefore needs a quoted return type:
   `def tools(self) -> tuple["TurnTool | MasterTool", ...]:`. `TURN_TOOLS` is a module-level
   tuple defined after `TurnTool`, holding `start_turn`, `scene` and `next_scene` with the
   descriptions `SERVER_TOOLS` carries today, word for word. The three become `Turn.start_turn`,
   `Turn.picture` and `Turn.offer_the_way_on`.
2. `Turn` gains two fields so it needs no `GameService`:
   - `started: bool = False` — was `GameService.turn_started`.
   - `recent: int` — **a plain integer parameter of `Turn.begin`**, passed by `GameService.play`
     as `self.settings.turn.recent_exchanges`. `Turn` must not read settings itself; `turn` may
     import `config`, but injecting the value keeps the dependency explicit.
   `Turn.picture` then calls `render_picture` itself.
3. Add `Turn.call(name: str, raw: Mapping[str, JsonValue]) -> str` holding the whole gate, in this
   order:
   1. `scene` is always allowed.
   2. `start_turn` answers `ALREADY_OPEN` when `self.started`, else opens.
   3. Anything else answers `START_FIRST` when not `self.started`.
   4. `engine.over(self.draft)` refuses with the game-over sentence.
   5. `next_scene` refuses with `DECIDING` when `self.draft.pending is not None`.
   6. A `TurnTool` validates `NoArgs` against `raw`, then runs.
   7. A `MasterTool` keeps the pending-decision answer of `_engine_call` unchanged: when a
      decision is open and the tool is not `during_suspension` on a turn that opened suspended,
      return the "the rules are waiting on the player" text — an answer, never a refusal.
      Otherwise apply it.
   8. An unknown name raises `f"{name!r} is not a tool of the {engine.id!r} engine."`
   Move `NO_TURN`, `START_FIRST`, `ALREADY_OPEN`, `DECIDING` and `OFFERED` from
   `src/aidm/app/runtime.py` into `src/aidm/turn/run.py` with them.
4. Replace trial-and-replay with copy-and-swap. `_apply` becomes:

   ```python
   def _apply(turn: Turn, play: Play) -> tuple[Fact, ...]:
       """One execution against a candidate; a refused call leaves the draft and the dice alone."""
       candidate, dice = turn.draft.draft(), deepcopy(turn.rng)
       try:
           landed = apply_to_draft(turn.engine.validate, candidate, play, dice)
           committed = candidate.committed()
       except ValidationError as broken:
           raise ValueError(
               f"the state this leaves is invalid: {broken.errors()[0]['msg']}"
           ) from broken
       turn.draft = committed
       turn.rng.setstate(dice.getstate())
       turn.landed(landed)
       return landed
   ```

   Delete `draft_refusal` from `src/aidm/core/model.py`; `run.py` is its only caller.
   - The rng is copied and its state written back **only on success**, so a refused call still
     consumes no dice and the golden turn stays identical.
   - The `ValidationError` wrapper keeps the exact sentence `draft_refusal` produced, so the
     refusal text the model reads does not change. A plain `ValueError` from a resolver passes
     through untouched, as it does today.
5. **Fix the stale reference in `consume_answer`.** It binds `draft = turn.draft` at the top, then
   calls `_apply`, then reads `draft.pending` and writes `draft.notes`. `_apply` now rebinds
   `turn.draft`, so every read and write after the `_apply` call must say `turn.draft`. Audit the
   whole function; the same rule applies to any other caller that holds a `Game` across `_apply`.
6. `src/aidm/app/runtime.py`: delete `ServerTool`, `SERVER_TOOLS`, `_DISPATCH`,
   `GameService.call_tool`, `_tool_refusal`, `_engine_call`, `_require_turn`, `start_turn`,
   `picture`, `offer_the_way_on` and `turn_started`.
7. `src/aidm/app/mcp.py`:
   - `call` narrows explicitly, because `Runtime.playing()` returns `GameService | None` and
     `GameService.turn` is `Turn | None`, and strict checking is on:

     ```python
     def call(runtime: Runtime, name: str, raw: dict[str, JsonValue]) -> str:
         session = runtime.playing()
         turn = None if session is None else session.turn
         if turn is None:
             raise ValueError(NO_TURN)
         return turn.call(name, raw)
     ```

   - `_published` loses its `isinstance` branch, because both tool types now carry `.args`.
   - `offered(runtime)` becomes `[_published(one) for one in runtime.published_tools()]`.
8. `Runtime.published_tools` **keeps the cross-family duplicate-name check** that `offered` does
   today. `Engine.__post_init__` only checks engine tools against each other, so this is the only
   place a server name and an engine name are compared:

   ```python
   def published_tools(self) -> tuple[TurnTool | MasterTool, ...]:
       """The live turn names the engine. With no turn open the choice cannot matter: a CLI only
       ever lists tools inside the turn that spawned it."""
       playing = self.playing()
       engine = playing.engine if playing is not None else next(iter(self.engines.values()))
       published = (*TURN_TOOLS, *engine.tools)
       require_unique("published tool names", (one.name for one in published))
       return published
   ```

9. Full check. The golden turn fixture must not change; if it does, the rng handling in step 4 is
   wrong. Stop and ask.

**Done when:** one dispatcher, one execution per tool call, and the resumed picture after a
re-suspension still ends in `RULES_WAIT` — no automated check covers that today, so read it in a
played turn. About **−20** lines.

## Step 4 — the engine id is an explicit coordinate

`Runtime.engine` returns `next(iter(self.engines.values()))`. Phase 8 installs a second engine,
and dict order then decides which rules the create pages use. Carry the id in the catalog instead
of guessing it.

`LaunchTarget` is deliberately unchanged; see settled decision 5 above.

1. `src/aidm/app/launch.py`: add `engine: EngineId` to `CatalogEntry`. Delete
   `LauncherCatalog.engines` — it is populated and never read.
2. `read_characters` in `src/aidm/core/io.py` yields **one entry per character and engine
   written**, not one per character, as `tuple[Slug, EngineId, Character]`. `load_catalog` turns
   each into its own `CatalogEntry`, so a character written for two engines appears twice, once
   per engine, with the same `id`. Delete the "the first written engine names them" rule and its
   comment. Every consumer must therefore key characters by `(id, engine)`, never by `id` alone.
3. `launch_target(catalog, scenario_id, character_id)` reads the engine from the scenario's
   catalog entry and refuses a character with no entry for that engine.
4. Saved-game discovery in `load_catalog` must check three things together, not three independent
   memberships: the save's engine equals the scenario entry's engine, and a character entry exists
   for that same engine. A save that fails any of them is skipped and logged, as now.
5. Delete the `Runtime.engine` property. Its remaining callers each take an explicit id:
   - `src/aidm/ui/create.py` `character_page`: an engine `ui.select` shown only when
     `len(runtime.engines) > 1`, defaulting to the single installed engine. Changing it must
     refresh the creation form, because the steps come from that engine.
   - `src/aidm/ui/create.py` `scenario_page`: the same select, and **both** the character list and
     the pack list must filter to the selected engine. Without that filter the page offers a
     character `new_scenario` will reject only after the worldsmith has run for minutes.
   - `Runtime.new_scenario` takes an `engine_id: EngineId` parameter.
6. `src/aidm/ui/app.py` `_new_game`: after the scenario select, offer only characters whose entry
   names that scenario's engine.
7. Full check, then start a game from the home page and resume one from a save.

**Done when:** no page or transport asks for "the engine". `Runtime.published_tools` still holds
one arbitrary-engine fallback for the case where no turn is open; that is deliberate and
documented in step 3, and it is the only one left. About **+20** lines.

## Step 5 — authoring leaves `runtime.py`, creation leaves the ABC

`Runtime.new_scenario` is 45 lines of scene authoring inside the composition root, and it
duplicates the worldsmith plumbing `GameService._write` already has. `CharacterCreation` is an
abstract base class with one implementation, while every other engine variation in `Engine` is a
plain callable.

**`app/spawn.py` is not split.** `CliSpawner` stays the only thing that starts a process, and
`answered` stays beside it. Moving `answered` into `turn/` would force `turn` to import the
provider result type that 7B adds, which the layer order forbids.

1. Add `src/aidm/app/scene_write.py` holding both worldsmith calls, with the exact signatures:

   ```python
   async def write_next(
       snapshot: Game, intent: str, engine: Engine, ask: Callable[[str], Awaitable[str]]
   ) -> SceneWrite


   async def write_opening(
       source: str,
       packs: Sequence[Slug],
       engine: Engine,
       ask: Callable[[str], Awaitable[str]],
       check: Check[SceneWrite],
   ) -> SceneWrite
   ```

   Both raise; neither logs and neither writes a file. `GameService._write` keeps its
   `try`/`except`, its `write_failure` bookkeeping and its logging around `write_next`.
   **The caller builds `check`.** `Runtime.new_scenario`'s refusal closure depends on the scenario
   name, the chosen character, its local `as_scenario`, and `begin_game`; it stays in
   `new_scenario` and is passed in. `new_scenario` also keeps the `write_scenario` call.
2. In `src/aidm/engines/core.py`, delete `class CharacterCreation` and replace it with three
   fields on `Engine`, bound with `partial(..., packs)` exactly as `guidance` and `validate`
   already are:

   ```python
   creation_steps: Callable[[Picks], tuple[CreationStep, ...]]
   create_character: Callable[[str, str, Picks], Character]
   preview_character: Callable[[Character], Rows]
   ```

   `created` becomes a free function in the same module:
   `def created(engine: Engine, name: str, brief: str, picks: Picks) -> tuple[Character, Rows]`.
3. `src/aidm/engines/loner3e/creation.py`: `Loner3eCreation` becomes three module-level functions
   named for the fields they fill — `creation_steps(packs, picks)`,
   `create_character(packs, name, brief, picks)`, `preview_character(character)`.
   `src/aidm/engines/loner3e/engine.py` binds them in `build`.
4. `src/aidm/ui/create.py` calls `created(engine, ...)`.
5. Full check, then write one new character and one new scenario from the pages.

**Done when:** `app/runtime.py` is under 400 lines and no ABC has one implementation. About
**+2** lines: this step is almost entirely a move.

## Step 6 — the world becomes a list of played scenes

This is the largest step and the only one that may be dropped. The chronology exists twice:
`SceneState` holds `played` plus `current`, while `Game` holds a flat `history` beside it. Every
`Exchange` stores its scene's **title**, and the worldsmith prompt joins the two graphs back
together on that string — so two scenes sharing a title merge their history. `Scene` is frozen but
holds `present` and `hidden`, so six call sites rebuild the whole scene to move one entity.

**This invalidates every save and regenerates every golden fixture. Do it in one commit.**

1. In `src/aidm/kits/scenes/state.py`, cut `Scene` down to authored content and add the run.
   **`SceneRun` is not generic** — no field of it mentions the sheet type. Ids keep
   `CheckedEntityId`, exactly as `Scene.present` has them today; a bare `EntityId` would lose the
   slug pattern.

   ```python
   class Scene(Frozen):
       place: Slug
       title: str
       question: str = Field(min_length=10)
       situation: str = Field(min_length=40)
       secret: str = ""


   class SceneRun(Mutable):
       """One scene as it was played: who was in it, and what happened."""

       scene: Scene
       present: list[CheckedEntityId] = Field(default_factory=list)
       hidden: list[CheckedEntityId] = Field(default_factory=list)
       exchanges: list[Exchange] = Field(default_factory=list)
       # The game master has called the question answered; the player may move on, or play on.
       settled: bool = False
       # Why the scene looks finished already, written by the rule that settled it.
       spent: str = ""
   ```

   **`Scene.id` goes.** Nothing reads it except the call that generates the next unique
   `Scene.id`, and `SceneState._each_id_once`'s error message. A run is identified by its
   position. Delete both `slug(draft.title, ...)` calls in `src/aidm/kits/scenes/worldsmith.py`.
2. `SceneState` holds `runs: list[SceneRun] = Field(min_length=1)` in place of `played`,
   `current`, `opened_at`, `spent` and `settled`, with `run` (the last) and `current` (its scene)
   as properties. Move the per-scene checks in `_consistent` and `_check_named` onto the run.
3. `SceneCanon.opening` becomes a `SceneRun` with no exchanges, so a scenario still ships the
   opening's `present` and `hidden`.
4. **Rewrite `new_game` in `src/aidm/engines/loner3e/engine.py`.** It builds
   `SceneState(current=opening)` today and prepends the player with
   `opening.model_copy(update={"present": (PLAYER_ID, *canon.opening.present)})`. Construct the
   opening run explicitly instead:

   ```python
   opening = canon.opening
   run = SceneRun(
       scene=opening.scene,
       present=[PLAYER_ID, *opening.present],
       hidden=list(opening.hidden),
   )
   ```

   **Do not use `model_copy(update=...)` here.** It skips validation and would leave a tuple
   sitting in a list field.
5. `src/aidm/core/model.py`: delete `Game.history` and `Game.turn_facts`. `turn_facts` is written
   in three places and read nowhere in `src` — the play page shows live cards from
   `GameView.live_facts`. `Game.record` appends one `Exchange` to `world.run.exchanges` and no
   longer takes a scene label. **Keep `Game.turn`**: `SaveHeader` reads it for the home page
   without validating the payload, and deriving it would cost that read.
   Add one named flattening helper and use it everywhere a flat history was read:

   ```python
   # SceneState
   def exchanges(self) -> tuple[Exchange, ...]:
       return tuple(one for run in self.runs for one in run.exchanges)
   ```

6. **Every reader of `Game.history` must move.** There are five, and missing one is a silent
   break:
   - `src/aidm/app/runtime.py` `play` — `state.history[-1].narration` for the illustration.
   - `src/aidm/app/runtime.py` `_cross_over` — the same, after the crossing.
   - `src/aidm/app/runtime.py` `_write` — `snapshot.history` into `render_worldsmith`.
   - `src/aidm/ui/panels.py` `journal_panel` — `session.state.history` for the chronicle.
   - `src/aidm/turn/context.py` — `told_passages` and `_recent`.
7. `src/aidm/core/play.py`: delete `Exchange.scene`. Grouping is now structural.
8. `src/aidm/kits/scenes/verbs.py`: the six `world.current = scene.model_copy(update={...})`
   rewrites in `Reveal`, `Enter`, `Leave`, `ImproviseItem`, `_move_item` and `_kill` become
   `world.run.present.append(...)` and `.remove(...)`.
9. `src/aidm/kits/scenes/boundary.py`: `scene_spent` counts `len(world.run.exchanges)` against
   `SCENE_TURN_CAP` and reads `world.run.spent`. **The crossing exchange counts as one of the
   twelve, exactly as it does today** — a crossing installs the new scene before `close_segment`
   records it, so `len(run.exchanges)` and `turn - opened_at` agree. This is a deliberate
   no-change; the cap stays 12 and no behaviour moves.
10. `src/aidm/kits/scenes/worldsmith.py`: `apply_scene` appends a new `SceneRun` instead of
    shuffling `current` into `played`, and **loses its `turn` parameter** — `opened_at` is gone.
    Update its two call sites.
11. `src/aidm/turn/context.py`: `_history` iterates `world.runs` and reads each run's own
    exchanges. Delete the `told` dictionary and the title lookup. `_recent` and `told_passages`
    take the last N of `world.exchanges()`.
12. `src/aidm/turn/run.py`: `close_segment` calls `draft.record(prompt, lines, facts)`. Keep the
    present order — the crossing exchange is recorded after `apply_scene`, so it belongs to the
    new run, exactly as it does today.
13. `src/aidm/ui/game.py` `chat`: iterate `world.runs` and print each run's scene title as its
    header; the `here` tracking variable goes. **Keep the last-pending rule.** Today the final
    exchange's "Paused:" line is suppressed while `state.pending` is set, because the live
    decision widget sits directly below it. Reproduce that: the very last exchange of the last run
    prints no "Paused:" line while a decision is open.
    `_breadcrumb` reads `world.runs`. `src/aidm/kits/scenes/render.py`: `player_view` sets
    `scenes` from `world.runs`.
14. `last_seen` scans `reversed(world.runs)`. Its behaviour does not change: an entity removed by
    `leave` still stops counting as seen in that run. Record that in `PROGRESS.md` under
    "Open — known and accepted" rather than adding a field to fix it.
15. Delete every file in `saves/`, then regenerate the golden fixtures **once**:
    `AIDM_GOLDEN_REGEN=1 uv run pytest`. Read every changed line. If a change surprises you, stop
    and ask.
16. Full check, then play a whole scene through a scene change and read the journal.

**Done when:** `world.runs` is the only chronology. About **−45** lines; the fields move into a
wrapper rather than disappearing, so do not expect more.

## Step 7 — three dead branches

Small, verified, and cheap once step 6 has already regenerated the fixtures. If step 6 is dropped,
drop the `Scene.id` half of this with it.

1. `src/aidm/engines/loner3e/state.py`: `Loner3eState.twist_pack` becomes `Slug`, not
   `Slug | None`. `Loner3eCharacter.twist_pack` is already required and `new_game` always copies
   it, so the `None` case is unreachable. Delete the `or state.packs[0]` fallback in
   `rules.twists` and the `is not None` guard in `engine._validate`.
2. Confirm no other `| None` in `src` is unreachable in the same way before you stop.
3. Full check, regenerate the golden fixtures if step 6 has not already, then play a turn.

**Done when:** about **−8** lines.

## 7A — done when

- `src` is near **5,540**, inside **5,500–5,610**. **This is not a deletion target.** Steps 1, 4
  and 5 add lines on purpose. Never invent a deletion to reach a number, and never skip a named
  deletion to protect one.
- Full check green at every step.
- The game plays from the browser: open a save, take a turn, answer a decision, cross into a new
  scene, read the journal.
- These four behaviours have no automated check today. Read each one in a played game before you
  call the phase done:
  1. After a decision re-suspends, the picture the master receives still ends in `RULES_WAIT`.
  2. A save file and a character file with a duplicated JSON key are both refused.
  3. A crossing counts as one turn against the twelve-turn scene cap.
  4. The chat prints no "Paused:" line directly above the live decision widget.
- Counts written into `PROGRESS.md`.
- **Step 6 is the cut line.** If it runs long, ship steps 1–5 and 7, write the reason in
  `PROGRESS.md`, and carry step 6 forward as its own phase.

---

# Phase 7B — the roles get drivers

**Goal:** make provider, model and effort explicit settings, resume a role's own conversation
between turns, and record what a spawned role can actually reach.

**Why:** `RoleConfig.command` is one raw string with the model buried in it, so there is no way to
change a model without rewriting a command line. Every call starts a cold conversation, and a
validation retry tells a brand-new process "your last answer was refused" when that process never
saw the answer. The child process inherits the whole environment. And the master's isolation is
enforced by Claude-only flags in one string.

**This phase adds lines.** It is a feature phase, not a deletion phase.

**Two histories, kept apart, and never confused.** `Game` is canonical, validated, saved and
portable. A provider conversation is disposable memory: losing one costs a cold start and can
never corrupt a save. The game master still calls `start_turn` every turn and the narrator still
receives the current revealed view, so an old transcript can never override committed state.

**One boundary rule for the whole phase.** A driver **builds a command and parses its output**. It
never starts a process. `CliSpawner` in `src/aidm/app/spawn.py` stays the only thing in the
codebase that starts a process, and it keeps the process-group isolation and timeout it has today.
`RunResult` lives in `src/aidm/app/spawn.py` beside `Spawner`, so nothing below `app` has to know
a provider exists.

## Step 1 — provider, model and effort become settings

This comes first, because the driver in step 2 selects on `RoleConfig.provider`.

1. In `src/aidm/config.py`, replace the raw command as the primary knob:

   ```python
   CliProvider = Literal["claude", "codex"]
   Effort = Literal["low", "medium", "high"]


   class RoleConfig(BaseModel):
       model_config = ConfigDict(frozen=True)

       provider: CliProvider = "claude"
       model: str = Field(min_length=1)
       effort: Effort = "medium"
       timeout: float = Field(default=300.0, gt=0.0)
       # An explicit escape hatch. A raw command cannot resume a session.
       command: str = ""
   ```

   The settings page renders a `Literal` as a select already, so neither field needs a page
   change. Keep `model` a validated non-empty string, not a `Literal`: model aliases move.
2. **Replace `Roles.for_name`.** It currently means "an empty command inherits the master's
   command". Under the new shape an empty `command` means "build the command from provider, model
   and effort", and a non-empty `command` is used verbatim and marks the role unresumable. Delete
   the inheritance rule; each role now carries its own provider and model.
3. Exact defaults, all three with `provider="claude"`:

   | role | model | effort | timeout |
   |---|---|---|---|
   | master | `opus` | `high` | 300.0 |
   | narrator | `sonnet` | `low` | 120.0 |
   | worldsmith | `sonnet` | `medium` | 900.0 |

   The timeouts are the measured ones already in `Roles`; do not change them.
4. Delete `MASTER_COMMAND` and `WRITER_COMMAND`. The isolation flags they carried move into the
   Claude driver in step 2, with the provider that understands them.
5. Full check. `CliSpawner` still builds its command from `command` alone at this point; step 2
   is what reads the new fields.

**About +22 lines.**

## Step 2 — typed drivers behind one boundary

1. Add to `src/aidm/app/spawn.py`:

   ```python
   @dataclass(frozen=True, slots=True)
   class RunResult:
       text: str
       session: str | None
       input_tokens: int = 0
       cached_tokens: int = 0


   class Driver(Protocol):
       def command(self, config: RoleConfig, session: str | None) -> Sequence[str]: ...
       def parse(self, output: str) -> RunResult: ...
   ```

   The token fields are **not speculative**: step 5 logs them. Do not add a field this phase does
   not read.
2. `ClaudeDriver` asks for JSON output, parses the result text and the session id, resumes with
   `--resume <id>`, and carries the tool-isolation flags that `MASTER_COMMAND` and
   `WRITER_COMMAND` held. `CodexDriver` asks for JSONL, captures `thread.started.thread_id`,
   collects the final agent message, and resumes with `codex exec resume <id>`. Neither starts a
   process. `final_message` stays the fallback when `parse` finds no structured result.
3. `Spawner.run` changes shape across the whole codebase in this step, or it will not typecheck.
   The new contract is `async def run(self, role: Role, prompt: str, session: str | None) ->
   RunResult`. Update every caller in one go: `answered`, `GameService._act`,
   `GameService._narrate`, and both functions in `app/scene_write.py`. Each of them reads
   `.text` where it read a `str` before; only `answered` cares about `.session`.
4. `ScriptedSpawner` in the test support returns a `RunResult`, records the session it was given,
   and still starts no process.
5. Full check, then play a turn.

**About +145 lines.**

## Step 3 — a retry resumes its own attempt

`answered` re-prompts once with the validation error, but the retry starts a new conversation that
never saw the refused answer. Give the retry the failed attempt's session and send only the error.

1. `answered` takes a `session: str | None` and returns `tuple[T, str | None]` — the value and the
   session that produced it — so its caller can store or discard it. The retry passes the session
   from the failed attempt.
2. When the retry process itself fails to start or times out, that is the same loud failure as
   today: the role has answered nothing usable and the step raises.
3. The worldsmith's session is discarded after success or final failure; it is per attempt, never
   per save.
4. Full check.

**About +12 lines.**

## Step 4 — a session per save, per role

1. Store provider session references in a sidecar at `saves/.sessions/<slug>.json`.
   `FileStore.slugs` matches `[a-z0-9][a-z0-9-]*` against a file stem, so a `.sessions` directory
   cannot enter the save catalog.
2. Two strict models in `src/aidm/app/spawn.py` or a new `src/aidm/app/sessions.py`:

   ```python
   class SessionEntry(Frozen):
       fingerprint: str
       session: str


   class SessionFile(Frozen):
       roles: dict[Role, SessionEntry] = Field(default_factory=dict)
   ```

   The fingerprint is a sha256 hex digest of one deterministic string:
   `f"{provider}|{model}|{effort}|{role_instructions}"`. A `SessionStore` dataclass owns the path,
   reads, writes and per-role locks. Write with the same staged-then-replace method
   `io._write` uses; a reader must never see a half-written file.
3. A sidecar that does not validate is **deleted and treated as absent**. It is disposable memory,
   never state. Log it and start cold.
4. The game master and the narrator get one conversation per saved game. The worldsmith stays one
   conversation per attempt, from step 3.
5. Invalidate an entry when its fingerprint no longer matches, when `GameService.restart` runs, or
   when a resume is rejected before the process starts.
6. **A failed resume falls back to a cold start only before the first tool call of that turn.**
   After the master has applied any tool, a cold retry would re-run the same prompt and apply a
   second set of mutations. Once `turn.facts` is non-empty, a failure ends the turn exactly as
   `GameService._act` already handles a crashed master: log it, keep what landed, narrate.
7. Serialise per save and role, so two requests cannot resume and mutate one transcript at once.
8. Full check, then take three turns in a row and confirm the second and third resume; then change
   the master's model in Settings and confirm the next turn starts cold.

**About +145 lines.**

## Step 5 — what a spawned role can reach, measured

The Claude master command disables built-in tools and exposes only this game's MCP server. Codex
has no documented equivalent of `--tools ""`. **Measure before you assume, in either direction.**

1. **Scrub the child environment first.** `CliSpawner` passes no `env` today, so the child
   inherits every variable the app was started with, including any API key exported in the shell.
   Pass an explicit allowlist: `PATH`, `HOME`, `LANG`, `TERM`, plus only the variables the chosen
   provider's CLI needs for authentication. Nothing else. This applies to all three roles and to
   both providers, and it is worth doing whatever step 2 below finds.
2. Run each role from an isolated empty working directory, under the narrowest sandbox the CLI
   offers, with the user's own configuration ignored rather than inherited.
3. **The Codex probe.** `codex exec` in this repo's installed version accepts
   `--disable <feature>`, which is documented as equivalent to `-c features.<name>=false`. Write a
   probe under `docs/probes/` that spawns each role and records the exact tool list it sees.
   - If the shell tool can be removed, the acceptance is "no tool but this game's MCP server for
     the master, and no tool at all for the narrator and the worldsmith".
   - **If it cannot**, the acceptance drops to least privilege and is recorded as such: read-only
     sandbox, empty working directory, ignored user configuration, scrubbed environment, no
     network tool, and no MCP server but this game's. Write what the probe actually saw into
     `docs/probes/`, and record the residual shell exposure in `PROGRESS.md` under
     "Open — known and accepted".
   Either way, the probe's recorded output is the acceptance, not a claim in this file.
4. Delete the generated configuration and the temporary working directory when the process exits,
   in the same `finally` that kills the process group.
5. Full check, then play a turn with every role on Codex.

**About +35 lines.**

## Step 6 — say what happened

The plan adds token counts in step 2 and a cold-or-resumed decision in step 4. Nothing reads them
yet. One log line per spawn closes that.

1. Log, at the end of every spawn: role, provider, model, effort, cold or resumed, duration in
   seconds, input tokens, cached tokens, and — when it fell back — the reason.
2. Full check, then take three turns and read the log.

**About +18 lines.**

## 7B — done when

- `src` is about **5,880**, from about 5,540.
- Full check green at every step.
- A turn plays on Claude and a turn plays on Codex, each with its tool surface recorded under
  `docs/probes/`.
- A second turn in the same game resumes the master's and the narrator's conversations, and
  changing a model in Settings makes the next turn start cold.
- A master that fails **after** applying a tool does not re-run. Check this by hand: kill the
  master process mid-turn once a card has appeared, and confirm no fact lands twice.
- The child process environment holds nothing but the allowlist.
- Counts written into `PROGRESS.md`.

---

# Phase 8 — The engines return

**Goal:** 24XX and Breathless play again, on the new design.

Do them one at a time, and only after phase 7 is done and the game has been played for real.

**They cost about 1,050 and about 770 lines of `src` python, not 500 each.** Both were measured
after phase 5, each three ways. 24XX: 1,005 / 1,035 / 1,132. Breathless: 767 / 801, with the
port-delta method rejected because it assumes helpers Breathless does not use. So the first engine
lands near **1,050** and the second near **770**. The floor needs no estimate: **Loner 3e, the
simplest engine here, is 823 lines**, and 24XX is larger than Loner at every comparable symbol. The
port makes an engine grow, not shrink: Loner went 675 -> 823 across phases 1–6, because the engine
now owns its typed state, its sheet union, `new_game`, `guidance` and `scene_closed`. Budget on top
of the 1,050: about **460** non-python lines (the pack alone is 278), about **740** test lines, and
about **59** for the shared machinery below. Each engine also regenerates about **1,300–1,400 lines
of golden JSON**, because the golden tests parametrize over `ENGINE_IDS` — machine-written, but a
real diff to read at the end of the phase.

## Step 0 — the setup Phase 6 did not pay

Phase 6 step 4 gave every engine the same four files, so "give the shared helpers a home" is
already done. **What is still owed is the generic `Game`**, which Phase 6 step 3 refuted as a union
and skipped on cost. See "Phases 0–6 — done", item 4: route 2 is the shortest path open.

1. **Take route 2 before you write engine two**, or `core/model.py` keeps aliasing
   `engines.loner3e.state` and the second engine cannot be persisted at all. `Game[S]` carries a
   `SerializeAsAny` payload; each engine subclasses `Game` to narrow the payload back to its own
   concrete type. About 46 annotation sites and one narrow `pyright: ignore`.
2. **`SceneWrite` becomes an `Engine` member**, `scene: type[SceneDraft[S]]`. It is rendered into
   the worldsmith's prompt as its answer schema and passed as the spawn's output type in two
   places. A union there would hand the worldsmith both engines' schemas and let a Loner game
   accept a 24XX scene. The schema argument that killed sheet erasure does not touch route 2: the
   sheet stays a concrete Pydantic union, so `SceneDraft[LonerSheet]` still renders.
3. **Move `ScenarioPayload` and `CharacterPayload` too, or the inversion survives**, and
   `ALLOWED = {"core": {"aidm.engines.loner3e.state"}}` stays standing in
   `test_package_boundary.py`. `Scenario` and `Character` become generic alongside `Game` — about
   17 more annotation sites.
4. **The headers are already the answer to engine discovery**, so do not reintroduce an envelope.
   Phase 7A deleted `core/envelope.py`. `EngineHeader`, `SaveHeader` and `CharacterHeader` in
   `core/model.py` are what let the app open a file *before* it knows which engine wrote it:
   `core/io.py` skips scenarios whose engine is not installed, and `app/launch.py` lists a save
   with no engine built. Keep them; they cost nothing that `Game[S]` would save.
5. **The save golden fixtures must not change.** A correct `Game[S]` dumps byte-identically. They
   are the only place the dropped-payload-field trap shows up — a `Payload[S]` base with `Game[S]`
   keeping `world` type-checks green and silently drops `twist` and `twist_pack` on every commit.
   **If they change, stop and ask.**
6. Full check.

Then, for each engine:

1. Read its notes in `docs/24XX.md` or `docs/BREATHLESS.md`. **`docs/24XX.md` deviation 1 is now
   false**: succession was deleted in phase 1, so a killed 24XX player no longer passes to a
   companion. Re-make that rules decision and rewrite the deviation.
2. Create `src/aidm/engines/<name>/` to the four-file template, with its typed state embedding
   `SceneState` with its own sheet union. 24XX's ship is a sheet on an entity, not a place.
3. Write its procedure tools — one per SRD rule, never more than eight. **24XX has no headroom**:
   `resolvers` went in phase 1, so `defend` — which used to be hidden from the model — must sit in
   the public list, taking 24XX to exactly eight.
4. Write its `guidance`, `scene_closed`, `over`, and creation options. A scene-ending signal
   no predicate can see is written to `SceneState.spent` by the rule that causes it.
5. Add its pack file under `src/aidm/engines/<name>/packs/` and one character file.
6. Write one scenario for it.
7. Add its test directory to `pythonpath` in `pyproject.toml`.
8. Full check, then play a turn.

**Let the second engine prove a helper is shared before you move it into `engines/core.py`.** About
40 lines inside `loner3e` name no Loner rule — the party and advance-ledger cluster, and the pack
and option lookups. Move them when 24XX uses them, not before, and keep the two clusters apart:
`core.py` was cut from 483 to 141 and should not become a dumping ground again.

**With the second engine**, bring back the little that holds more than one, measured at about
**59 lines**: the closed payload union in `core/model.py` (+8), engine discovery in the registry
(+3 — two explicit imports and a two-entry dict; the `import_module` loop costs 12 and buys nothing
for two engines), the engine choice and badge on the home page (+26), `app/launch.py`'s
`characters_for` and `CatalogEntry.engines` (+10), the `runtime.engine` property becoming a lookup
(+10), and the two tables in `test_package_boundary.py` that name `loner3e` (+2).

**`AnyEngine` is not needed.** The composition root holds `dict[EngineId, core.Engine]`, the
concrete dataclass, and that stays valid with two engines.

## Breathless, measured

**It is the smallest of the three: about 770 `src` python lines**, below Loner's 823 and well below
24XX. One thing drives that: **Breathless has no advancement system at all** — no chapters, no
milestones, no advances. Loner spends 119 lines on that ledger and its tag glossary; Breathless
writes none of it, which more than pays for its three extra tools and its 48-line `Check`. Budget:
~256 non-python (its pack is 60 lines, against 24XX's 278), ~615 test lines, and about 10 lines of
shared machinery.

1. **Breathless needs none of the shared helpers.** Verified by reading: zero uses of `party`,
   `party_member`, `advances_owed`, `ADVANCE_SPENT`, `find_entry`, `other_than` or `pack_meanings`.
   That cluster serves 24XX and Loner only. Breathless shares exactly `check_packs` and
   `pack_options` — about 5 lines. `stake_decision`, deleted in phase 1, has exactly two callers
   ever, one each in Breathless and 24XX: inline it in whichever lands first.

2. **Do not bring player actions back. `catch_breath` goes on the scene boundary.** Measured, the
   `PlayerAction` route costs **118 lines**, of which **80 are core**. The boundary route is **13**:
   `scene_closed` iterates `world.here()` and resets `worn`/`loot`/`stunted`, exactly as Loner's
   `close_conflicts` refills luck in 8. **Saving: 105 lines, and `PlayerAction` never returns.**
   `breathers`, `med_kit_holders` and `_party` (29 lines) die with it. `use_med_kit` needs no button
   either — it was already a master tool, and `rules.md` already tells the game master to call it.

   **Play a real session before committing to this.** Dice stepping down *is* Breathless, and a
   free involuntary reset at every scene end defuses it. Keep it SRD-faithful: `scene_closed` must
   also write the complication note, because a breather is always paid for. The fallback is the
   +118 route.

3. **Fold the two loot tools into one.** `resolvers` went in phase 1, so `LOOT_ITEM` and
   `LOOT_MED_KIT` would both have to be public, putting Breathless at eight with no headroom.
   `PendingOption` already carries `name` plus `args`, so both options can name **one** tool with
   `med_kit: true|false`. That leaves 7 engine tools plus `change_world` — one slot spare, where
   24XX has none.

4. **`improvise_item` is unconditional, and it breaks a Breathless invariant.** The old engine set
   `improvised=False` with the comment "every item is a die a loot check hands out". Today the kit
   publishes `improvise_item` to every engine, and it creates an item with `sheet=None`, which
   Breathless's "every item is rated" `_validate` refuses — every time the game master calls it.
   Fix it in the engine, not in core: `_validate` tolerates a sheet-less item and `_rolls` refuses
   to roll one. Two lines, plus one new deviation in `docs/BREATHLESS.md`. Do not add a per-engine
   flag back to the kit's tools for one engine.

5. **Two porting traps.** A worn-out item is un-carried *and* put into `world.current.present`, or
   it vanishes from every view — the old room tree did that implicitly. And Breathless was
   under-tested, not simple to test: its old suite was 286 lines against Loner's 731, with no
   events test, no packs test and no creation test. About 240 of its ~615 lines are coverage that
   never existed.

---

# Checklist

- [x] Phases 0–6 — done. `src` 9,452 -> 5,600
- [x] Phase 7A — the restructuring pass. `src` 5,600 -> 5,578
- [ ] Phase 7B — the roles get drivers. `src` 5,578 -> about 5,880
- [ ] Phase 8 — the engines return
- [ ] Full check green at every checkpoint
- [ ] The game plays from the browser at the end of every phase
- [ ] Line counts in `PROGRESS.md` for every phase
- [ ] This file deleted in the last commit; `VISION.md` stays
