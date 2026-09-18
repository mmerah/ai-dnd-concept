# PLAN: human code

Three phases fold twelve simplification proposals into the code: one word per thing, one home
per subject, and no copy between the two hiring engines. Every step was implemented once by a
subagent in a throwaway worktree with the four checks green; the shapes and the numbers below
come from those runs, not from estimates. The line count barely moves (about +20 on `src`);
the gain is that `Engine` loses a job and 64 lines, one table replaces two lists per engine, one
module replaces two copies of hiring, and four modules (`turn.py`, `hiring.py`, `present.py`,
`pack.py`) each hold one subject.

Decided on 2026-09-18 and not re-opened by any phase:

- The `rooms/` family stays, generic as it is. `Dungeon[N]`, `MapProposal[N]`,
  `RegionProposal[N]` and `Dweller` are what let `rooms/` type-check `Npc`-shaped data without
  importing `tunnelgoons/`; deleting them gave 30 type errors. One comment at the top of
  `rooms/engine.py` says so.
- No hook methods whose only purpose is a splice point (a `sheet_sections()` that defaults to
  empty so a child can insert in the middle). 24XX's copy of its family's `master_sections` and
  `player_view` stays.
- No shared cast-block base across the three packs: measured at +30 lines and 18 type
  suppressions, and Loner's shipped JSON says `concept` where the other two say `brief`.
- `GameService` keeps `close` inside the `try` and `save` outside it in `_write_commission`; no
  `_landed()` helper, it fitted 2 of 4 sites.
- `Tools` stays a protocol, moved next to `Turn`, its one implementer. `_MARKED` stays a module
  dict: a function attribute reads as `Any` under basedpyright strict.
- No `banner()` widget: it added wrappers and changed the proposal row's markup for no gain.
- No library for the tool mark (pydantic-ai, FastMCP): it would replace 50 lines of marking and
  none of the schema tidy the prompts also read.

Measured before any step, at `85b843b`: `src` **10,432** Python lines, `tests` **11,882**, `qa`
**2,020**, 759 tests. A phase whose count lands more than 40 lines from its target stops and
says why.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the phases in order and the parts of a phase in order: every part touches a file the
   part before it touched. Each step is one action. Symbol names are as of `85b843b`; where an
   earlier step renamed one, use the new name.
2. Change a shape and its tests in the same step. One test per new behaviour; a test of a
   deleted behaviour goes with it. A golden is regenerated only where a step says so, with
   `AIDM_GOLDEN_REGEN=1 uv run pytest`. basedpyright does not see a keyword inside a dict
   literal or a test helper's `**args`; a rename is done when pytest is green, not before.
3. Count `src` and `tests` lines at the start and the end of each phase and write both in
   `PROGRESS.md`, one entry per phase, with the decisions taken off-plan:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   ```
4. Every phase commits once, after the full check.

## Phase 1: words

Parts A, B, C in order. Target: `src` about +45 (10,432 → about 10,480), `tests` about 0,
759 tests. Nothing serialised changes except the pack JSON keys in Part C.

### Part A: one noun for the worldsmith's request

1. **`request` is `commission`.** Every `request: Commission` parameter and local becomes
   `commission` (`engines/engine.py`, `scenes/engine.py`, `rooms/engine.py`,
   `tunnelgoons/engine.py`, `twentyfourxx/engine.py`, `app/runtime.py`). `turn/run.py`
   `REQUEST_WAIT` becomes `COMMISSION_WAIT`. `GameService._grow` becomes `_write_commission`.
2. **`Written` says what it carries.** In `engines/engine.py`, `Written.telling: str | None`
   becomes `narrator_prompt: str | None`. `Engine.__init__(self, written: Path)` becomes
   `player_packs: Path`; `engines/registry.py` and every test subclass follow.
3. **Names that say what they return.** `Engine.over` and `PlayerView.over` become `ending`
   (`core/views.py`, every engine, `turn/run.py`, `app/runtime.py`, `ui/`). `Engine.answer`
   becomes `play_option`. `SceneWorld.offer()` and `Scene.offered` become `offer_way_on()` and
   `way_offered` (`scenes/world.py`, `scenes/engine.py`; no shipped scenario carries `offered`).
4. **One worldsmith renderer.** In `engines/engine.py`, replace the method `render_worldsmith`
   and the adapter `render_request` with a free function and one method:
   ```python
   def render_worldsmith(
       role: str,
       *,
       source: str,
       scope: str,
       world_sections: Sections,
       intent: str,
       guidance: str,
       answer_model: type[BaseModel],
   ) -> str: ...

   class Engine:
       worldsmith_role: str  # read once in __init__ from family_dir / "worldsmith.md"

       def render_commission(
           self, draft: Game[W], *, intent: str, guidance: str, answer_model: type[BaseModel]
       ) -> str:
           return render_worldsmith(
               self.worldsmith_role,
               source=draft.source,
               scope=draft.scenario.scope,
               world_sections=self.worldsmith_sections(draft),
               intent=intent,
               guidance=guidance,
               answer_model=answer_model,
           )
   ```
   `author` in both families and `author_pack` call the free function with named arguments
   (`scope=meta.scope` / `scope=""`, `world_sections=OPENING_SECTIONS` / `()`); `write_next`,
   `write_hire` and `render_next` call `render_commission`. The rendered text is unchanged, so
   the prompt goldens do not move.

### Part B: small renames

5. **Engine files.** `git mv src/aidm/engines/<engine>/worldsmith.py
   src/aidm/engines/<engine>/pack.py` for `loner3e`, `tunnelgoons`, `twentyfourxx`; update
   imports in `src` and `tests`. Every engine then has `engine.py`, `world.py`, `pack.py`,
   `tools.py`; both families keep `engine.py`, `world.py`, `worldsmith.py`, `tools.py`.
6. **`_unmet` means "not met by the player".** `_scene_unmet`, `_map_unmet`,
   `_overlap_unmet`, `_named_unmet`, `_planted_unmet` (family `worldsmith.py`) and
   `required_unmet` (`engines/base.py`) become `*_needs`. `World.unmet()` and
   `named_unmet` keep their names.
7. **A CLI conversation is not a session.** In `app/spawn.py`: `RunResult.session` becomes
   `conversation`, `SessionId` becomes `ConversationId`, and the `session` parameter of
   `Spawner.run`, `RoleRunner.run`, `Driver.command`, `run_cli` becomes `conversation`; the local
   in `roles.ask` follows. `tests/support/table.py` and `qa/agents.py` construct `RunResult` by
   keyword and implement `Spawner`; update them. `GameService`-side `session` stays.
8. **Role runners named as verbs.** `app/roles.py`: `master` → `run_master`, `narrate` →
   `run_narrator`, `interject` → `run_interjection`, `worldsmith(spawner)` →
   `worldsmith_answer`. Call sites in `app/runtime.py` and tests.
9. **Plain Python where a trick stood.** `PackSet.installed` becomes a `@property` returning
   `{**self.shipped, **self.written}`; drop the `field(init=False)` and `__post_init__`. The free
   function `packs.options()` becomes `with_ids()`. `app/providers.py`: replace the `@cache`
   singleton `posting()`/`close_posting()` with a module-level `_client: AsyncClient | None`
   and `client()`/`close_client()`. `Echoed` moves from `core/entities.py` to `app/builtin.py`.
10. **`twentyfourxx/world.py::raised`** returns `SkillDie | None` (None at d12) instead of
    raising; `Crewmate.raise_skill` and `build_character` branch on it. Player-visible refusal
    texts are unchanged; `tests/twentyfourxx/test_world.py::test_raised_refuses_past_d12` becomes
    `test_raised_returns_none_past_d12`.
11. **Locals and one-offs.** `Turn.action` → `player_action`; `Engine.act(action)` and
    `GameService.act(action)` → `action_id`. In `tunnelgoons/engine.py` `ds` → `difficulty`.
    The three `me = player.subject()` locals are inlined. `scenes/world.py`
    `_resolve_ids` → `resolved_ids`. `Loner3eEntity.lose()` → `run_out_of_luck()`. 24XX pack
    field `hostiles` → `monsters` (`twentyfourxx/pack.py`, `docs/24XX.md`; the SRD ships none).

### Part C: one word for a name and a brief

12. **`label`/`detail` are `name`/`brief`.** Rename the fields on `DecisionOption` and
    `PendingOption` (`core/play.py`), `Subject`, `Companion`, `PanelRow` (`core/views.py`),
    `CreationStep` (`core/creation.py`), `Labelled` and `Location` (`engines/packs.py`),
    `CatalogEntry` and `PackEntry` (`app/launch.py`), and every subclass (`Specialty`, `Origin`,
    `Body`, `SkillChoice`, `SpecialtyProposal`, `OriginProposal`) and use in engines, `ui/` and
    tests. `DiceEvent.label`, `Panel.title`, `Commission.detail` and NiceGUI `label=` stay.
    `PendingOption` already has `name` (the tool it plays): that field becomes `tool_name`
    (`level_up_decision`, `_succession`, `Engine.play_option`). Reword the two sentences of
    `HEAD_ASK` that say "labels" and "`detail`".
13. **`Subject` is not an option.** `core/views.py`:
    ```python
    class Subject(Frozen):
        id: Slug
        name: str = Field(min_length=1)
        brief: str = ""
    ```
    `Thing.subject()` becomes a plain field copy. `Thing.tag` and `Subject.headline` share
    `tag_of(name, entity_id) -> str` in `core/entities.py` (`f"{name}[{entity_id}]"`).
14. **Shipped packs follow.** Write a throwaway script that renames the keys `label` → `name`
    and `detail` → `brief` inside the pick and location rows of `src/aidm/engines/loner3e/packs/
    *.json` (13 files) and `src/aidm/engines/twentyfourxx/packs/srd.json` (rows under `skills`,
    `specialties`, `origins`, nested `choice`, `kit_choice`, and `locations`), as a plain text
    substitution so every file changes line for line; verify with `json.loads` before and after;
    run the suite; delete the script. Tunnel Goons' `srd.json` has no such rows.

## Phase 2: engines

Parts A, B, C in order. Target: `src` about −55 (about 10,480 → about 10,425), `tests` about
−25, 760 tests. One golden regenerates in Part B.

### Part A: one table, and pack authoring off `Engine`

1. **The comment the rooms family owes.** Top of `engines/rooms/engine.py`, one line: the
   family stays generic over its dweller because it cannot import the one engine that names it.
2. **`Operation` replaces `unwritten` and the `advance` chains.** In `engines/engine.py`:
   ```python
   @dataclass(frozen=True, slots=True)
   class Operation:
       write: Callable[[AnyGame, Commission, WorldsmithAnswer], Awaitable[Written]]
       failure_fact: Fact  # filed when the write fails

   class Engine:
       def operations(self) -> Mapping[Slug, Operation]:
           return {}

       async def advance(self, draft, commission, worldsmith) -> Written:
           return await self.operations()[commission.operation].write(draft, commission, worldsmith)
   ```
   `validate` checks `commission.operation not in self.operations()`. `SceneEngine.operations`
   returns `{DEPARTURE: Operation(self.depart, WAY_UNWRITTEN), COMPLICATION:
   Operation(self.complicate, COMPLICATION_UNWRITTEN)}`; `RoomEngine.advance`'s inline body
   becomes a method `extend` and `operations` returns `{EXTEND: Operation(self.extend,
   MAP_UNWRITTEN)}`; `TunnelGoonsEngine` and `TwentyfourxxEngine` return
   `{**super().operations(), HIRE: Operation(self.write_hire, HIRE_UNWRITTEN)}`. Delete the
   `unwritten` ClassVar everywhere, the four `advance` overrides, and `WRITES_NO`'s use in
   `advance` (`validate` keeps it). `GameService._write_commission` reads
   `self.engine.operations()[commission.operation].failure_fact`. `tests/engines/
   test_engine.py`'s drift test between `unwritten` and `advance` goes: the table's `write`
   field is required, so a missing writer is a type error. `tests/core/test_golden_turn.py`
   picks an operation id from `engine.operations()`.
3. **`PackAuthor`.** In `engines/packs.py`:
   ```python
   @dataclass(frozen=True, slots=True)
   class PackAuthor[K: Pack]:
       pack_model: type[K]
       head_model: type[PackHead]
       body_model: type[PackBody]
       authoring: str
       role: str  # the family's worldsmith.md, for render_worldsmith

       async def author(self, *, name, source, origin, license, worldsmith) -> K: ...
       def edited(self, pack: K, values: Mapping[str, str]) -> K: ...
   ```
   `author` is today's `Engine.author_pack` with `pack_of` folded in as a local `built`;
   `edited` is today's `Engine.edited`; both call `render_worldsmith(self.role, ...)`.
   `PACK_SO_FAR` moves with them. `Engine.__init__` builds `self.pack_author = PackAuthor(
   pack_model=self.pack, head_model=self.head, body_model=self.body, authoring=self.authoring,
   role=self.worldsmith_role)`; `Engine.guidance` reads `self.pack_author.authoring`; the
   `head`/`body`/`authoring` class attributes stay declared (the engines set them) and
   `install_pack` stays. `Runtime.new_pack` and `rewrite_pack` call `engine.pack_author.author`
   and `.edited`. `tests/engines/test_packs.py::test_a_twentyfourxx_head_never_gives_two_picks_
   the_same_id` builds its pack with `parse(TwentyfourxxPack, {"name": ..., "source": ...,
   "license": ..., **head.pack_fields()})` instead of `engine.pack_of`.

### Part B: one hire flow, one goon

4. **`engines/hiring.py`.** New module holding, moved out of `engines/tools.py`: `HIRE`,
   `HIRE_PENDING`, `SIGNED_ON`, `SIGNS_ON`, `HIRED`, `HIRE_UNWRITTEN`, `NO_HIRE_TARGET`,
   `UNWRITTEN_CAST`, the `Hire` args model, and two free functions:
   ```python
   def file_hire(draft: AnyGame, member: Person, terms: str) -> list[Fact]:
       draft.commission = Commission(operation=HIRE, detail=terms, target=member.id)
       return [Fact(trace=HIRE_PENDING.format(name=member.name, terms=terms))]

   def signed_on(world: World[Any], member: Person, summary: str) -> Written:
       facts = world.join(member) if member.id not in world.party else []
       facts.append(member.fact(SIGNS_ON.format(who=member.mention, summary=summary),
                                card=SIGNS_ON.format(who=member.name, summary=summary)))
       return Written(tuple(facts), SIGNED_ON.format(name=member.name))
   ```
   `hiring.py` imports `engine.py` for `Written`; nothing imports `hiring.py` back. Both
   engines' `hire` tool bodies become `return file_hire(draft, member, args.terms)` under their
   own docstring; both `write_hire` tails become `return signed_on(draft.world, member,
   summary)`. `engines/tools.py` keeps `ACTOR` and the five shared arg models. Tests import
   the constants from `aidm.engines.hiring`.
5. **`require_actor` and `require_hireable` on `World`.** `engines/base.py`: `Person` gains
   `@property hired -> bool` returning `False`; `World` gains the two methods verbatim from
   `TwentyfourxxWorld` (`require_actor(actor_id: Slug | None) -> M`,
   `require_hireable(entity_id: Slug) -> M`); delete the copies in `TunnelGoonsWorld` and
   `TwentyfourxxWorld` and the now-unused `ALREADY_SHEETED`/`NOT_AN_ACTOR` imports there.
6. **One `Goon`.** `tunnelgoons/world.py`: merge `Goon` and `Npc` into
   ```python
   class Goon(Dweller):
       """A dweller who carries dice: the played character, or an npc once hired."""
       hp: Gauge
       sheet: GoonSheet | None = Field(default=None, description="Leave empty.")
       kit: tuple[str, ...] = ()  # the player's starting items by name; empty on an npc
   ```
   with `Npc`'s `hired`, `require_sheet`, `sign_on`, `rows`, `level`, `required` and `Goon`'s
   `unpack_kit`. `TunnelGoonsWorld(RoomWorld[Goon])` gains the `_player_carries_a_sheet`
   validator 24XX has. Delete `sheet_of`; `roll` and `level_up` call `actor.require_sheet()`.
   `build_character` passes `place=PLAYER_ID` and `hp=Gauge(current=HP_START,
   maximum=HP_START)`. `TunnelGoonsEngine(RoomEngine[Goon, TunnelGoonsWorld, TunnelGoonsPack])`
   with `member = Goon`; `TunnelGoonsScenario = Scenario[MapProposal[Goon]]`. `hp` stays
   required so the worldsmith's npc schema keeps demanding a Difficulty Score.
7. **`World[M]`.** `engines/base.py`: `class World[M: Person]` with `player: M`;
   `SceneWorld[C](World[C])`; `RoomWorld[N: Dweller](Dungeon[N], World[N])` with `opening(...,
   player: N, ...)`, `here() -> Iterator[N]`, `kill`'s `actor: N`, `line(entity: N | Prop)`;
   `Engine[W: World[Any], K]`, `RoomEngine[N: Dweller, W: RoomWorld[Any], K]`. Regenerate
   `tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json` (the npc schema now lists
   `kit`, unread for an npc) and add `place` and `hp` to `characters/kael/tunnelgoons.json`.
   Old Tunnel Goons saves go stale, which is the documented behaviour.

### Part C: the tool mark, explicit

8. **`args` by name.** `core/tools.py::_args_of` reads `signature(function).parameters.get(
   "args")` and raises `ValueError(f"{function.__qualname__} does not take (self, draft, args,
   rng)")` when it is missing or not a `BaseModel`. `TunnelGoonsEngine.rest` and
   `tests/turn/test_decisions.py::Deciding.strike` spell their parameter `args` with a
   `del args` (the repo's idiom for an unused parameter).
9. **No invisible tool.** `tools_of` walks the MRO as today, but a method whose name is already
   marked and which carries no mark itself raises
   `ValueError(f"{value.__qualname__} overrides a tool but carries no @tool mark")`.
   `TwentyfourxxEngine.kill` gets `@tool` and the docstring `"""Someone here dies."""`.
   `tests/core/test_tools.py`: mark `Adding.second`, replace the test that read an unmarked
   override's inherited description with one that reads the override's own, add one test for
   the refused unmarked override and one for a marked method with no `args` parameter.
   Publication order is unchanged; `master_tools.json` goldens do not move.
10. **`Tools` beside `Turn`.** Move the `Tools` protocol from `core/tools.py` to `turn/run.py`;
    `app/spawn.py`, `app/builtin.py`, `tests/support/table.py`, `tests/app/test_mcp.py`,
    `tests/app/test_roles.py` and `qa/agents.py` import it from there.

## Phase 3: app and pages

Parts A, B, C in order. Target: `src` about +30 (about 10,425 → about 10,455), `tests` about
+10, 763 tests. No golden moves.

### Part A: three prompts in one place

1. **`render_master` beside the other two.** Move `render_master` and `MASTER_ROLE` from
   `turn/run.py` to `app/roles.py` (`MASTER_ROLE = PROMPTS_DIR / "master.md"`); `git mv
   src/aidm/turn/prompts/master.md src/aidm/app/prompts/master.md`. Delete
   `Turn.master_prompt`; `run_master` builds the prompt from `turn.engine.instructions`,
   `turn.engine.master_sections(turn.draft)`, `turn.draft`, `turn.player_action`, `turn.notes`.
   One comment above `render_master`: the worldsmith's renderer stays in `engines/` because it
   needs the engine's own sections. `tests/app/test_context_boundary.py` imports from
   `aidm.app.roles`. The `master.txt` goldens are byte-identical.
2. **`turn` is one module.** `git mv src/aidm/turn/run.py src/aidm/turn.py`; delete
   `src/aidm/turn/__init__.py`; every `aidm.turn.run` import becomes `aidm.turn`.
   `tests/core/test_package_boundary.py::_source_files` must also accept
   `SOURCE / f"{package}.py"`; the `turn` layer stays in `LAYERS`.

### Part B: the game service

3. **`app/present.py`.** `git mv src/aidm/app/media.py src/aidm/app/present.py`; move
   `Reader` and its helpers (`voice_of`, `requests_of`, `clip_key`, `speech_body`,
   `SPEECH_DIR`, `SAMPLE_WIDTH`) from `app/speech.py` into it and delete `speech.py`. Add:
   ```python
   @dataclass(frozen=True, slots=True)
   class Presenter:
       illustrator: Illustrator
       reader: Reader

       @classmethod
       def open(cls, settings, store, slug, *, style, icon_dirs, voice) -> Self: ...
       @property
       def enabled(self) -> bool: ...          # either feature on
       def scene_art(self, view: NarratorView) -> Path | None: ...
       def icon(self, entity_id: Slug) -> Path | None: ...
       def clip(self, newest: Exchange | None) -> Path | None: ...
       def present(self, view, player, newest) -> tuple[Coroutine[Any, Any, None], ...]: ...
       def speak(self, newest) -> tuple[Coroutine[Any, Any, None], ...]: ...
   ```
   `present` returns the illustrate coroutine (when illustration is on; `newest=None` means
   art only, say so in a comment) plus what `speak` returns (the read coroutine when `newest`
   is not `None`). `Tasks` stays in `runtime.py`. No shared base class for `Illustrator` and
   `Reader`.
4. **`GameService` uses it.** Replace the fields `media` and `reader` with `presenter:
   Presenter`; `Runtime._open` builds `Presenter.open(settings, self.store, target.slug,
   style=..., icon_dirs=..., voice=...)`. Delete `presents`, `illustrate`, `speak`. `_present()`
   stays one line: `for coroutine in self.presenter.present(view, player, newest):
   self.tasks.retain(create_task(coroutine))`; `let_party_speak` does the same over
   `presenter.speak`. `scene_art`, `icon`, `newest_clip` forward to the presenter. `ui/game.py`
   reads `session.presenter.enabled` for the media timer. `tests/app/test_media.py`,
   `test_speech.py`, `tests/ui/test_game.py` import from `aidm.app.present` and reach
   `session.presenter.illustrator`.
5. **One way to say a role is working.** `GameService.phase` becomes `working_role: Role |
   None`, and:
   ```python
   @asynccontextmanager
   async def working(self, role: Role) -> AsyncGenerator[None]:
       self.working_role = role
       try:
           yield
       finally:
           self.working_role = None
   ```
   `open` runs under `working("narrator")`; `_turn` nests `working("master")` then
   `working("narrator")` and keeps only `self.turn = None` in its `finally`;
   `_write_commission` nests `working("worldsmith")` then `working("narrator")` with `close`
   still inside the `try` and `save` still outside it. Delete the `busy` property; `ui/game.py`
   and `ui/transcript.py` read `session.working_role`; `unopened` reads it too.

### Part C: pages read the view

6. **The transcript reads `PlayerView`.** `PlayerView` gains `premise: str`, filled by every
   engine's `player_view` from `state.scenario.premise` (`scenes/engine.py`, `rooms/engine.py`,
   `twentyfourxx/engine.py`); one parametrised test in `tests/engines/test_views.py`.
   `ui/transcript.py::chat` reads `view.premise` and `view.decision` instead of
   `session.state.scenario.premise` and `session.state.pending`.
7. **Pages go through `Runtime`.** `app/runtime.py` gains `catalog() -> LauncherCatalog`,
   `engine(engine_id) -> AnyEngine`, `look(engine_id) -> Look`, `engine_options() ->
   dict[EngineId, str]`, `pack_options(engine_id)`, `seeds(engine_id, pack_id)`,
   `art_style(engine_id)`, and `pack_boxes(engine_id, pack_id) -> tuple[str, bool, dict[str,
   str]]` (name, writable, boxes) sharing one private lookup with `rewrite_pack`, whose refusal
   becomes `f"no pack {pack_id!r} for {engine_id!r}"`. `ui/app.py`, `ui/create.py` and
   `ui/packs.py` use them; `create.py` keeps `runtime.engine(id)` for `creation_steps`,
   `create_character`, `preview_character`. `PackEditor.build` holds no `Refusal` of its own.
8. **Pure view logic in one module.** `placeholder`, `near_end`, `draft_spent`, `whole_page`
   and the `Observed` dataclass move from `ui/game.py` to `ui/transcript.py` beside `can_type`,
   `standing_proposal`, `clock`; `tests/ui/test_game.py` imports follow.
9. **`ui/dice.py` dissolves.** `DiceSound`, `DICE_SOUND`, `DICE_SOUND_ROUTE` go to
   `ui/widgets.py`; `rolled_since` to `ui/transcript.py`; `ui/app.py`, `ui/game.py`,
   `tests/ui/test_dice.py` follow.
10. **One trim.** `ui/widgets.py` gains `typed(box: ui.input | ui.textarea) -> str` using the
    composer's `BLANK` set (moved from `game.py`); every `(x.value or "").strip()` and
    `.strip(BLANK)` in `ui/game.py` and `ui/create.py` calls it. A title of one non-breaking
    space is no longer accepted. Locals named `typed` in `submit`/`act` become `words`.
