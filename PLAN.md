# PLAN: fold the ten accepted simplifications into two commits

This plan lands the ten decided proposals: `qa/` leaves the type-check gate, the `get_args` reflection leaves `_keys_present`, media and speech stop being optional collaborators, `Roles` dissolves into three free functions, `Struck` and `Helping` become plain tuples and the two `Pool` classes get distinct names, `ui/dictation.py` moves into `ui/widgets.py`, `check_json_keys` becomes `reject_duplicate_keys`, the duplicate `Actor`/`UseMedKit` arg model goes, `Runtime.published_tools` and `Runtime.call` go, one drift rule serves both the launcher and the game page, `Subject` becomes a `DecisionOption` and `Thing.tag` stops building a Pydantic model, `render_opening` folds into the renderer it wraps, nine pure forwarder tool methods become lambdas on the registration line they already had, the hidden-name leak scan is written once, and the test suite loses its wiring tests and its triple-covered rules.

Read the line targets before the steps. PROPOSALS promised "~380 source lines and ~375 test lines". That number was gross, not net, in nine places out of ten. The honest total this plan is held to is **about 46 source lines and about 125 test lines**: `src` 10,248 to about 10,202, `tests` 12,226 to about 12,100. Every phase states its arithmetic and every step that costs more than it saves says so.

Not built: **P3(a)**, de-genericising `rooms/` (`Dungeon[N]`, `MapDraft[N]` and `RegionDraft[N]` are what put `Npc`'s schema, not `Dweller`'s, in front of the worldsmith: `rooms/engine.py:174` answers with `MapDraft[self.member]` and `:228` with `RegionDraft[self.member]`, and `tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json` pins the result. Dropping the parameter would strip `hp` and `sheet` from the npc shape while `tunnelgoons/worldsmith.md` still says "Every npc needs `hp`". `RoomWorld[P, N]` and `RoomEngine[P, N, G]` cannot shed theirs either: `N` is `Engine[P, M, G]`'s `M`, which `self.member` reads, and the "2-line narrowing override" at `tunnelgoons/engine.py:75-76` exists because `TunnelGoonsGame.payload` is a `TunnelGoonsWorld`, not because of the type parameters, so it survives the change. What is left is 31 inline mentions and no deleted line); **P9b as PROPOSALS spells it** (one renderer taking `source`, `scope` and `family` explicitly deletes 12 lines from `engines/seam.py` and adds about 17 back across the five `render_request` callers, a net gain of lines — only `render_opening` is deleted, see phase 2 step 1); **P6's four `base.py` arg models** (`Reveal`, `Kill`, `JoinParty` and `LeaveParty` carry four different `entity_id` descriptions; collapsing them into one model changes `entity_id`'s description in four tools and drifts all four `master_tools.json` goldens, which is option (a), declined, not option (b)); **`Turn.published_tools`** (it is the `Tools` Protocol member `app/builtin.py:79` calls and `qa/agents.py` stubs, and `app/roles.py:60` passes the `Turn` as that argument — deleting it breaks the builtin completion loop); **P8's `resumed(...)` merge** (`_save_option` derives its target from the file name and `_resumed` from the player's selection, so sharing the whole body needs a new slug parser; measured at a net gain of 6 to 8 lines, and merging the code does not remove the second validation because the two run on different files at different times — only the drift rule is shared, in phase 1 step 9); **P10's `tests/support/fifth.py` deletion** (four tests in `tests/engines/test_seam.py` — `test_the_tempo_floor_refuses_a_tempo_below_two`, both `test_construction_refuses_*` and `test_a_pack_with_doubled_keys_is_refused` — need an engine rooted at `tmp_path` with a minimal pack on disk, which `Loner3eEngine` cannot be); and `NOISE_KEYS` (`core/tools.py:14`), which stays a prompt-quality experiment to measure, not a refactor to perform.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each is one action on the files it names. Every `file.py:line` anchor is as of `aad5391`; where an earlier step moved the code, find the named symbol and ignore the number.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
3. Count lines at the start and end of each phase and write both in `PROGRESS.md`, one entry per phase. At the start `src` is 10,248 lines, `tests` 12,226 and `qa` 2,104:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   ```
   A phase that misses its target by more than the stated tolerance stops and says so. Never pad, and never claim a cut the count does not show.
4. Golden files live in `tests/core/fixtures/`. **Neither phase regenerates one.** Every step is either invisible to a prompt and a schema or is checked against a fixture that must not move. A changed fixture is a bug in the step that changed it. If one is genuinely meant to move, the phase says so, and only then:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
5. One commit per phase, full check green, reviewed adversarially against the staged diff first. Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the staged tree: CI runs exactly that. `ruff format` also formats the Python fences in this file, so run `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of every phase: `uv run aidm`, open each shipped scenario, take a turn.
6. Delete, do not preserve. No compatibility path reads an old save or scenario file. No constant, helper, prompt line or test stays for a caller that is gone.
7. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles. No `Any` beyond the `Game[P]` bound. Every `__init__.py` stays empty. Tests never start a process and stub roles with `ScriptedSpawner`. `Refusal` stays the one message-bearing exception and any other exception is a bug. A bad model answer is re-prompted once with the error, then raises. Only code changes state or rolls dice. The narrator reads revealed facts only. Data is validated at each boundary with strict Pydantic models. Names must explain themselves and a comment is one line, only where the reason is not visible in the code.

## Phase 1: the edges

Nothing here touches an engine's tool table, the worldsmith renderers or the hidden-name scan; phase 2 owns those. Target: `src` about **10,210**, at most 10,225 (10,248 minus 38). `tests` about **12,231**, at most 12,245: no test is deleted in this phase. `qa` stays 2,104.

### Steps

1. `pyproject.toml:46`: drop `"qa"` from `[tool.basedpyright] include`, leaving `include = ["src", "tests"]`. One line. `extraPaths` is untouched. The scripts still run as they do now through `qa/run_all.sh`. **The trade, stated:** a signature change in `src/` that breaks `qa/agents.py` or `qa/art.py` now surfaces the next time the harness runs rather than at type-check time. Step 4 changes what `qa/art.py:20` subclasses and step 6 leaves `GeneratedImage` alone for it, so prove the harness still imports once at the end of this phase: `PYTHONPATH=qa uv run --group qa python -c "import art, agents"`.
2. `core/io.py:177-179`: rename `check_json_keys` to `reject_duplicate_keys`, docstring unchanged. **This is a rename and never a deletion.** `parse_json` silently keeps the last of two equal keys — `parse_json(M, '{"a": 1, "a": 2}')` returns `a=2`, verified — so the separate `decode()` pass with the `_unique_keys` hook is the only thing rejecting a doubled id. Repoint the two callers, `core/io.py:192` (in `read_model`) and `app/spawn.py:219` (in `ask`), and the import at `app/spawn.py:18`. Zero lines; the name is the whole point. `tests/engines/test_seam.py:53-60` (`test_a_pack_with_doubled_keys_is_refused`) keeps proving the behaviour and does not change.
3. `config.py:151-154`: delete the `get_args` reflection and its comment. `for_name` and its `match` stay — they are the compile-time exhaustiveness check that flags a fourth `Role`:
   ```python
   roles: tuple[Role, ...] = ("master", "narrator", "worldsmith")
   for role in roles:
       config = self.roles.for_name(role)
   ```
   The annotation is load-bearing: a bare tuple literal infers `tuple[str, str, str]` and `for_name` would not accept it. Drop `get_args` from the import at `config.py:3`. **Net −1 line.** It is done for the deleted reflection call and the PEP 695 footgun comment that explains it, not for the line.
4. Media and speech stop being optional. The `| None` is a setting, not a domain fact, so the feature flag moves to the object that owns it.
   `app/media.py:46-58`: `Illustrator.open` returns `Self`, not `Self | None`; delete the `if not settings.media.enabled: return None` pair. `scene_art` becomes one line, `return _existing(self.saves, scene_key(scene)) if self.config.enabled else None`; `icon` and `illustrate` each open with `if not self.config.enabled:` (returning `None` and nothing). Gating all three keeps the behaviour exact: with media off, art cached by an earlier enabled run stays invisible.
   `app/speech.py:33-52`: `Reader.open` returns `Self`; `clip` becomes `return path if self.config.enabled and path.is_file() else None`; `read`'s early return becomes `if not self.config.enabled or not requests or path.is_file():`.
   `app/runtime.py`: `media: Illustrator` and `reader: Reader`, both without a default (the dataclass is `kw_only`, so the order does not matter, and `runtime.py:433` is the only construction site). The six guards go:
   ```python
   @property
   def presents(self) -> bool:
       return self.media.config.enabled or self.reader.config.enabled


   def scene_art(self) -> Path | None:
       return self.media.scene_art(self.engine.narrator_view(self.state))


   def icon(self, entity_id: Slug) -> Path | None:
       return self.media.icon(entity_id)


   def newest_clip(self) -> Path | None:
       newest = self._newest()
       return None if newest is None else self.reader.clip(newest)


   def illustrate(self, narration: str = "") -> None:
       view = self.engine.narrator_view(self.state)
       task = create_task(self.media.illustrate(view, self.player_view().player, narration))
       self.tasks.retain(task)


   def speak(self, newest: Exchange | None) -> None:
       if newest is not None:
           self.tasks.retain(create_task(self.reader.read(newest)))
   ```
   `newest_clip` and `speak` keep a guard because `_newest()` is genuinely optional; that is a domain fact. `tests/ui/test_game.py:499` becomes `assert session.media.config.enabled`. `qa/art.py:20`'s `PlaceholderIllustrator` subclasses `Illustrator` and overrides `_generate` alone, and `qa/server.py:95` swaps the class in wholesale, so both keep working — but the QA settings must have `media.enabled` on, or the placeholder now draws nothing where it used to draw. **Net −9 lines** (`media.py` +2, `speech.py` −2, `runtime.py` −9). PROPOSALS said ~20 and meant the six guards gross; a separate `NoIllustrator`/`NoReader` pair, which is what "null implementations" literally asks for, measures at **+20** — two new classes and two union aliases against six one-line guards — and is not built.
5. `app/roles.py:53-108`: `Roles` is a frozen dataclass with one field and no state of its own, and `runtime.py:232` already reaches through it (`worldsmith(self.roles.spawner)`). Delete the decorator, the class line and the `spawner: Spawner` field; `master`, `narrate` and `interject` become module functions beside the `render_*` functions already free in that file, each taking `spawner: Spawner` where it took `self`:
   ```python
   async def master(spawner: Spawner, turn: Turn) -> None: ...
   async def narrate(
       spawner: Spawner, engine: AnyEngine, draft: AnyGame, facts: tuple[Fact, ...], prompt: str
   ) -> tuple[SpokenLine, ...]: ...
   async def interject(
       spawner: Spawner, engine: AnyEngine, state: AnyGame, member: Companion
   ) -> tuple[tuple[SpokenLine, ...], str]: ...
   ```
   `app/runtime.py`: `GameService.roles: Roles` at `:79` becomes `spawner: Spawner`; `:164` calls `master(self.spawner, turn)`, `:207` `interject(self.spawner, self.engine, self.state, member)`, `:232` `worldsmith(self.spawner)`, `:257` `narrate(self.spawner, self.engine, draft, facts, prompt)`, `:438` passes `spawner=self.spawner`; the import at `:14` becomes `from aidm.app.roles import RoleRunner, interject, master, narrate`. `tests/app/test_roles.py:8,112,127` call `master(spawner, turn)` bare. **Net −4 lines** — the decorator, the class line, the field and one blank. PROPOSALS said ~14; the three signatures keep every line they had, they only swap `self` for `spawner`.
6. Micro-dataclasses, where they are really local.
   `engines/loner3e/world.py:131-134`: delete `Struck`; `strike` returns `tuple[list[Fact], str]` — `return facts, ""` and `return facts, hit.name`. `engines/loner3e/engine.py:207-210` unpacks at once: `facts, loser = world.strike(actor, opponent, outcome)`, then `exchange, effects = _absorbed(facts)` and `if loser:` / `DEFEAT_NOTE.format(name=loser)`.
   `engines/twentyfourxx/engine.py:88-92`: delete `Helping`; `:397` becomes `helping = None if helper is None else (world.require_actor(helper.actor_id), helper)`, typed `tuple[Crewmate, Helper] | None`. Unpack once at the top of each reader rather than indexing: `:403` `staked.append(helping)`, and `_pool` at `:450` takes `helping: tuple[Crewmate, Helper] | None` and opens with `who, terms = helping` inside its `if helping is not None` arm.
   `app/media.py:29-32`: **`GeneratedImage` stays.** PROPOSALS calls it a two-element return that never crosses a module; it crosses three — `tests/app/test_media.py:98,131,164` and `qa/art.py:26` all name it as the return type of the `_generate` stub they install.
   Rename the two sibling classes both called `Pool`: `engines/breathless/engine.py:56` becomes `SkillPool` and `engines/twentyfourxx/engine.py:82` becomes `DicePool`, with their `_pool` return annotations and the four construction sites (`breathless:282,285,286`, `twentyfourxx:478`). Zero lines; the point is that `grep -n "class Pool"` stops finding two different things. `DiceEvent(label="Pool", ...)` in `tests/core/test_dice.py` is a die label, not this class, and does not change. **Net −10 lines.**
7. `src/aidm/ui/dictation.py`: move `Dictation` into `src/aidm/ui/widgets.py` and delete the file. `widgets.py` already imports `from nicegui import ui`, so only the class travels. `component="dictation.js"` resolves against the directory of the module that declares it, and both modules live in `src/aidm/ui/`, so `dictation.js` stays where it is and keeps loading. `ui/game.py:20` drops `from aidm.ui.dictation import Dictation` and adds `Dictation` to its existing `aidm.ui.widgets` import. **Net −2 lines, one file gone.**
8. `engines/breathless/tools.py`: `UseMedKit` at `:44-45` and `Actor` at `:102-103` are byte-identical — `actor_id: Slug | None = Field(default=None, description=ACTOR)`, declared 58 lines apart in one file, both in use. Delete `UseMedKit` and keep `Actor`, which names an argument shape rather than a tool. `engines/breathless/engine.py:90` registers `master_tool("use_med_kit", USE_MED_KIT, Actor, self.use_med_kit)`, `:166` types `args: Actor`, and the import at `:29` loses `UseMedKit`. `schema_of` pops `title`, so `tests/core/fixtures/schemas/breathless/master_tools.json` does not move — that fixture holds zero `"title"` keys today and must still hold zero after. `tests/breathless/test_tools.py:11` already imports `Actor`. **Net −4 lines.**
9. `app/launch.py` and `app/runtime.py` judge a save by one drift rule. Add to `app/launch.py`, after `SaveOption`:
   ```python
   def check_drift(state: AnyGame, meta: ScenarioMeta) -> None:
       """One rule, so the launcher's `unresumable` and the game page never disagree."""
       if drifted := state.scenario.drift(meta):
           raise Refusal(f"save scenario differs from the selected scenario in: {', '.join(drifted)}")
   ```
   `_save_option` at `launch.py:145-146` and `Runtime._resumed` at `runtime.py:420-421` both call it, and the launcher's "scenario differs from disk in" text becomes this one. `AnyGame` is imported into `launch.py` from `aidm.core.model`, which it already imports `ScenarioMeta` from. **`_save_option` keeps its `None` return for a save that vanished between `slugs()` and `read` (`launch.py:127-130`): that is a race guard, not noise, and it is the reason `LauncherCatalog.read` can list a Start that works.** `tests/app/test_launcher.py` pins the refusal texts; the one that changes is the drift text, so update that assertion and no other. **Net +2 lines**, and it is kept for the closed drift risk alone: the launcher deciding a save is playable while the game page refuses it is exactly the bug a player reports as "it's listed but won't open". PROPOSALS' "home page gets faster" does not follow from merging these two — they validate different files at different times — and is dropped.
10. `Subject` and `DecisionOption` become one model. `core/play.py:65-68`: `DecisionOption` keeps its three fields and gains the two projections:
    ```python
    class DecisionOption(Frozen):
        id: Slug
        label: str = Field(min_length=1)
        detail: str = ""

        @property
        def tag(self) -> str:
            return f"{self.label}[{self.id}]"

        @property
        def headline(self) -> str:
            return self.tag + (f" — {self.detail}" if self.detail else "")
    ```
    `core/views.py:27-40`: `Subject` becomes three lines and `core/views.py` keeps importing `DecisionOption` from `core/play.py` as it already does at `:8`:
    ```python
    class Subject(DecisionOption):
        def row(self) -> PanelRow:
            return PanelRow(label=self.label, detail=self.detail, icon_id=self.id)
    ```
    `Companion(Subject)` and `PendingOption(DecisionOption)` are unchanged. `engines/base.py:61-67`: `Thing.tag` and `Thing.headline` stop constructing a validated Pydantic model per call — `Subject` is `Frozen`, so `entity.tag` ran a full strict construction to produce one f-string, and `Person.headline` did it twice through `super()`:
    ```python
    @property
    def tag(self) -> str:
        return f"{self.name}[{self.id}]"


    @property
    def headline(self) -> str:
        return self.tag + (f" — {self.brief}" if self.brief else "")
    ```
    `Thing.subject()` at `:106-107` stays: `Engine.companions`, `narrator_view` and `PlayerView.player` genuinely hand a `Subject` across the seam. Do **not** add a shared free function for the two f-strings — it would be three lines to save none. The `name`/`brief` on disk versus `label`/`detail` in a prompt stays as it is; `tests/app/test_context_boundary.py:46-58` pins it. `Subject.label` inherits `min_length=1`, which is safe: every `Subject` is built from `Thing.name`, already `Field(min_length=1)`. **Net −3 lines** (`views.py` −11, `play.py` +8). PROPOSALS said ~30. The rendered output is byte-identical, so no prompt fixture moves.
11. `app/runtime.py:348-357`: delete `Runtime.published_tools` and `Runtime.call`. Both are pure forwards to `self.turn`, and `app/roles.py:60` already hands the builtin completion loop the `Turn` itself, so they exist only for the MCP path. `app/mcp.py` holds the `Runtime` and reads `runtime.turn` itself: in `on_list_tools`, `turn = runtime.turn` then `tools = () if turn is None else turn.published_tools()`; in `on_call_tool`, inside the existing `try` so a missing turn still returns an error result rather than a traceback:
    ```python
    turn = runtime.turn
    if turn is None:
        raise Refusal(NO_TURN)
    answered = turn.call(params.name, params.arguments or {})
    ```
    Add `from aidm.turn.run import NO_TURN` to `app/mcp.py`; `app <- turn` is the allowed direction. `runtime.py` drops the now unused `MasterTool` import at `:24`, `JsonValue` at `:9`, and `NO_TURN` from `:28`. `Runtime.turn` at `:344-346` stays — it is what `mcp.py` reads. **`Turn.published_tools` at `turn/run.py:131-132` stays**: it is the `Tools` Protocol member `app/builtin.py:79` calls and `qa/agents.py` stubs. `tests/support/table.py:165-173` and `tests/app/test_master_tools.py:93,95,492,495` drive tools through `runtime.call` today; they go through `runtime.turn` instead — `table.py`'s `call` reads `turn = self.runtime.turn` and raises `Refusal(NO_TURN)` when it is `None`, and `test_master_tools.py:93` becomes `assert table.runtime.turn is None`. **Net −7 lines in `src`, about +2 in `tests`.** PROPOSALS said ~25 and counted the three deletions gross, one of which cannot happen.

### Done when

- `grep -rn "check_json_keys\|get_args(Role\|class Roles\|class Struck\|class Helping\|class UseMedKit\|class Pool\b" src tests qa` prints nothing. `ls src/aidm/ui/dictation.py` finds nothing and `src/aidm/ui/dictation.js` is still there.
- `grep -rn "Illustrator | None\|Reader | None\|self.media is None\|self.reader is None" src` prints nothing; `grep -rn "def published_tools\|def call(self, name" src` prints `turn/run.py` once each.
- `grep -n "qa" pyproject.toml` no longer shows it under `[tool.basedpyright]`, and `uv run basedpyright` reports no file under `qa/`. `qa/run_all.sh` still starts.
- `tests/core/fixtures/` does not change at all. `master_tools.json` for breathless keeps `use_med_kit` with the same description and the same one-property schema; every prompt fixture is byte-identical to the commit before this phase.
- Media off and speech off still mean no art request, no speech request and no cached art shown. Media on still draws. `uv run aidm` opens each of the four shipped scenarios, plays a turn, and the home page still skips an unreadable save with a warning instead of hiding the others.
- `src` is about 10,210, at most 10,225: 10,248 minus step 3 (−1), step 4 (−9), step 5 (−4), step 6 (−10), step 7 (−2), step 8 (−4), step 10 (−3), step 11 (−7), plus step 9 (+2). Steps 1 and 2 are zero by construction. `tests` is about 12,231, at most 12,245. `qa` stays 2,104.
- Full check green.

## Phase 2: the engines, the leak scan and the test prune

Every step here touches an engine, and the prune must follow the scan it covers. Target: `src` about **10,202**, at most 10,215. `tests` about **12,100**, at most 12,140.

### Steps

1. `engines/seam.py:204-208`: delete `render_opening` and rename `_render` at `:209` to `render_worldsmith`, signature and body unchanged. Its two callers pass the family sections at the call site, which is what `opening_sections` is for, and stay three lines each because `_render` is positional: `scenes/engine.py:292-294` becomes
   ```text
   prompt = self.render_worldsmith(
       source, meta.scope, self.opening_sections, OPENING, guidance, model
   )
   ```
   and `rooms/engine.py:175-177` the same with `MAP_ASK`, `self.guidance(None)` and its `model`. `render_request` at `:197-202` stays and calls `self.render_worldsmith(...)`. `opening_sections` stays a class attribute on `scenes/engine.py:85` and `rooms/engine.py:58`. **Net −5 lines.** Do not go further: making one method take `source`, `scope` and `family` explicitly, which is what PROPOSALS asks for, grows each of the five `render_request` callers by two to five lines and is a net gain of about 5. The four `worldsmith.txt` prompt fixtures must not move; that is what they are for.
2. Nine pure forwarder tool methods become the lambda on the registration line they already had. The rule that made them — *"an engine tool method resolves ids and rolls dice"* — does real work for `roll`, `job` and `defend`; these nine resolve nothing and roll nothing. Add to `engines/seam.py`, after `Request`:
   ```python
   def world_tool[G: Game[Any], W, A: BaseModel](
       name: str,
       description: str,
       args: type[A],
       world_of: Callable[[G], W],
       resolve: Callable[[W, A], Sequence[Fact]],
   ) -> MasterTool[G]:
       """A tool with nothing to resolve and nothing to roll: the world method is the handler."""
       return master_tool(name, description, args, lambda draft, a, _rng: resolve(world_of(draft), a))
   ```
   `world_of` is what lets the checker solve `W` and `G`; passing the engine instead would leave both unsolved. Each `master_tools()` that uses it binds the getter once, `world = self.world_of`, so the registration lines stay inside 100 columns:
   ```text
   world_tool("reveal", REVEAL, Reveal, world, lambda w, a: w.reveal_hidden(a.entity_id)),
   world_tool("enter", ENTER, Enter, world, lambda w, a: w.enter(a.entity_id)),
   world_tool("leave", LEAVE, Leave, world, lambda w, a: w.leave(a.entity_id)),
   world_tool("move", MOVE, Move, world, lambda w, a: w.move(a.to_id, a.with_ids)),
   world_tool("meanwhile", MEANWHILE, Meanwhile, world, lambda w, a: w.meanwhile(a)),
   ```
   and four more that ruff wraps onto three lines each: `join_party` (`w.join_party(a.entity_id)`), `move_item` (`w.move_item(a.item_id, a.to)`), `unlock_way` (`w.unlock_way(a.to_id)`) and `take_lead` (`w.take_lead(a.entity_id)`). Delete the nine methods: `reveal`, `join_party` (`seam.py:113-114,119-120`), `enter`, `leave` (`scenes/engine.py:206-210`), `move_item`, `unlock_way`, `move`, `meanwhile` (`rooms/engine.py:203-213`) and `take_lead` (`twentyfourxx/engine.py:323-324`). The `master_tools()` overrides, their order and every tool name, description and args model stay exactly as they are.
   **Four forwarders are deliberately left alone.** `kill` is overridden at `twentyfourxx/engine.py:334-337`, where it calls `super().kill(...)` and then `_succession(draft)`; registering a lambda in `Engine.master_tools()` would bind the seam's body and drop `_succession` in silence — a real bug, not a style point. `leave_party`, `ship_upgrade` and `use_med_kit` have registration lines that ruff breaks one argument per line, so dissolving them costs more lines than the method they replace.
   `tests/engines/test_rooms.py:43,161,193,194,349,350` and `tests/tunnelgoons/test_tools.py:258,263,269,278,279,300,306,317,327,337,343` call `ENGINE.move(draft, Move(...), Random(0))` directly; they call `ENGINE.world_of(draft).move(to_id, with_ids)` instead, same line count. Nothing else in `src` or `qa` calls any of the nine.
   **Net about −4 lines**, and a correction worth stating: PROPOSALS priced this at ~105 and the decorator-and-MRO variant it recommends is worse still — the machinery is about 50 lines against 69 of registration that becomes 33 of decorator, a net gain of 14, and its prototype dropped the draft. **Before writing the helper, try it without one**: `master_tool("move", MOVE, Move, lambda d, a, _: world(d).move(a.to_id, a.with_ids))` needs no new function and saves about 11 lines instead of 4, but the checker must solve `G` from the enclosing return annotation rather than from an argument. Run `uv run basedpyright` on one engine both ways and keep whichever is clean; if the bare form type-checks, `world_tool` is not written at all and this step is **−11**. Either way `tests/core/fixtures/schemas/*/master_tools.json` must not move: same names, same order, same descriptions, same schemas.
3. The hidden-name leak scan is written once. `engines/scenes/worldsmith.py:73-79` and `engines/rooms/worldsmith.py:66-71` implement *"no text the player reads may name something hidden"* twice with a byte-identical inner loop, differing only in id-versus-object indirection. This is safety logic: a fix to one side is a silent spoiler leak on the other. Add to `engines/base.py`, beside `named_unmet`:
   ```python
   def leaked_names(read: str, things: Iterable[Thing], hidden: Sequence[Thing]) -> set[str]:
       """No text the player may read names something hidden; nothing watches itself."""
       leaked = set(named_unmet(read, hidden))
       for thing in things:
           text = "\n".join((thing.brief, *(value for _, value in thing.rows())))
           leaked.update(named_unmet(text, (other for other in hidden if other.id != thing.id)))
       return leaked
   ```
   `scenes/worldsmith.py` calls it with the entities it has already resolved:
   ```python
   read = "\n".join((draft.title, draft.focus, draft.situation))
   watched = [everyone[entity_id] for entity_id in hidden]
   seen = (everyone[entity_id] for entity_id in (*present, *followers, *hidden))
   leaked = leaked_names(read, seen, watched)
   ```
   and `rooms/worldsmith.py`, inside its per-place loop:
   ```python
   read = "\n".join((place.name, place.brief, place.description))
   leaked.update(leaked_names(read, things, hidden))
   ```
   `scene_unmet`'s surrounding checks and `_map_unmet`, `_overlap_unmet` and `_planted_unmet` stay where they are: they verify genuinely different invariants. **Net about +1 line** — the duplicated block is 13 lines, not the 30 PROPOSALS counted, and the function plus its blanks is about 9. It is kept for the deleted duplication of safety logic, and for nothing else.
   **This is the one step in the plan that can regress in silence.** Run `uv run pytest tests/engines/test_integrity_boundaries.py tests/engines/test_scene_bar.py` green before the edit and green after, and read the two call sites against the two originals line by line. Both originals exclude the entity from its own watcher set; `leaked_names` does it by `other.id != thing.id`, which is what the rooms side already did and what the scenes side did by id. **If the two turn out to differ in a way that cannot be reconciled, do not merge — leave both and write the difference into `PROGRESS.md`.**
4. Prune the wiring tests `CLAUDE.md` forbids — *"test behavior and boundaries, not prose or wiring"*. `tests/engines/test_seam.py`: delete the two `instructions` assertions inside `test_a_fifth_scene_engine_begins_a_playable_game` at `:65-68` (they assert that string concatenation happened; the rest of that test stays), delete `test_a_scene_engine_offers_the_familys_tools_without_naming_them` at `:86-98` whole (a literal list of seven tool names already pinned byte for byte by `tests/core/fixtures/schemas/*/master_tools.json`), and delete `_CountingFifthEngine` with `test_close_builds_no_narrator_view` at `:100-124` (a third engine subclass defined to count calls to one method). Drop the imports each leaves unused — `read_cached_text`, `NarratorView`, `SpokenLine` and `scenario` if nothing else in the file names them. `tests/engines/test_rooms.py:47-57`: delete the same tool-name list from `test_the_familys_tools_are_offered_in_order`, keeping whatever the test does after it; if nothing is left, delete the test. About −70 lines.
5. Prune the rules paid for three times. `tests/engines/test_scene_bar.py`: the four scene-level word-boundary tests at `:301`, `:315`, `:329` and `:343` collapse to one that proves `scene_unmet` reaches `named_unmet` — `named_unmet` is already unit-tested directly with exactly those four properties at `tests/engines/test_engines_base.py:112,123`, and after step 3 it is reached through `leaked_names`. The three "the scene must not list the player" tests at `:157`, `:256` and `:544` become one. `tests/app/test_context_boundary.py`: delete the positive prompt-substring assertions (`"luck: 6/6" in master`, `"Kael[player]" in master` and their kin) that `tests/core/fixtures/prompts/{engine}/master.txt` already pins exactly. About −60 lines.
   **Keep, in full:** `test_the_narrators_view_has_no_field_that_could_hold_unrevealed_canon` at `tests/app/test_context_boundary.py:41-59`, which asserts the exact field set of `NarratorView`, and the two negative assertions that a secret appears in the master prompt and does **not** appear in the narrator prompt. Those are boundary tests. `tests/support/fifth.py` and `tests/support/sixth.py` both stay: `sixth.py` gives `test_rooms.py` maps the shipped scenario cannot produce, and `fifth.py` is the only engine that can be rooted at a `tmp_path`, which four construction tests in `test_seam.py` need.

### Done when

- `grep -rn "def render_opening\|def _render" src` prints nothing; `grep -rn "def render_worldsmith" src` prints `engines/seam.py` once.
- `grep -rn "    def reveal(self, draft\|    def join_party(self, draft\|    def enter(self, draft\|    def leave(self, draft\|    def move_item(self, draft\|    def unlock_way(self, draft\|    def move(self, draft\|    def meanwhile(self, draft\|    def take_lead(self, draft" src` prints nothing, and `grep -rn "def kill(self, draft" src` prints `engines/seam.py` and `engines/twentyfourxx/engine.py`. Killing an npc in 24XX still runs `_succession`: `uv run pytest tests/twentyfourxx` green.
- `grep -rn "named_unmet(text" src` prints `engines/base.py` once. `tests/engines/test_integrity_boundaries.py` and the surviving `tests/engines/test_scene_bar.py` are green, and a hidden entity named in a scene's `situation`, in another entity's `brief`, in a place's `description` or in a thing's rows is still refused on both families.
- `tests/core/fixtures/` does not change at all: same tool names in the same order with the same schemas, and four `worldsmith.txt`, four `master.txt`, four `narrator.txt` and four `turn/*.json` byte-identical to the phase 1 commit.
- `grep -rn "class _CountingFifthEngine\|startswith(\"Roll high" tests` prints nothing; `ls tests/support/fifth.py tests/support/sixth.py` finds both.
- `src` is about 10,202, at most 10,215: 10,210 minus step 1 (−5) and step 2 (−4, or −11 if the bare-lambda form type-checks), plus step 3 (+1). `tests` is about 12,100, at most 12,140: 12,231 minus step 4 (−70) and step 5 (−60), plus the `world_of` rewrites in step 2 (0). `qa` stays 2,104.
- Full check green. `uv run aidm` opens each of the four shipped scenarios and plays a turn; the master is offered the same tools it was offered before this phase, and a save written before it still restores.
