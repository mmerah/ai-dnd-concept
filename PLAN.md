# PLAN — the form

Five phases, in order: the ground, the engine is the class, the shapes, the chores, the rooms.
Self-standing:
an implementer needs this file, `CLAUDE.md` and the code. `NEXT-SPECS.md` stays for Track G.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action. Finish it before starting the next.
2. **Run the full check at the end of every step.** Tests must be green. Change a shape and
   update its tests in the same step. One test per new behaviour; no test of prose or wiring.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of every step that
   changes a stored shape or a prompt:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. Each phase below names exactly which fixtures may change and
   how. Anything else is a bug. The shipped `scenarios/*/world.json` and `characters/kael/*.json`
   have no regen: a step that changes their shape rewrites them with a throwaway script in the
   scratchpad, never committed.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs far past its target, stop and say so.** Never pad, never invent a deletion.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** Never leave two versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **No phase adds, removes or renames a tool or an arm.** The cap stays fifteen, counted as
   tools plus `change_world` arms, the two party arms not counted. Every engine stays under
   2,000 lines, imports flow `core <- engines <- turn <- app <- ui`, no `Any` beyond the
   `Game[P]` bound, every `__init__.py` empty. Prompts, `rules.md`, `worldsmith.md` and
   `master_tools.json` do not change in any phase: `prompts/*`, `schemas/*` and `turn/*` are the
   safety net and stay byte-identical throughout.
10. **A rename is a rename.** A step that renames touches every import, test and `NEXT-SPECS.md`
    mention in the same step and changes no behaviour. A step that deletes, moves or re-signs a
    name lists in its brief every file `grep -rln <name> src tests` returns; the orchestrator
    runs the grep, the implementer does not explore.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`ae6be39`) | | 9,205 |
| 1 — the ground | mechanical cleanups, `Refusal`, the boundary test fixed, one `kill()` per world, verbs and one stem per engine | 9,190 |
| 2 — the engine is the class | resolvers, creation and sections as engine methods; shared arms, `next_scene`, sections and the worldsmith flow on `SceneEngine`; `Thing`; methods on `Counter`, `Turn`, the worlds; `player_id` gone; notes a list; the pipeline tidied | 8,720 |
| 3 — the shapes | `Campaign`, dict-shaped tags and abilities, the payload is the sheet, `ScenarioMeta` carries style and voice, the goldens trimmed; one stale-save commit | 8,540 |
| 4 — the chores | `GamePage`, `LaunchForm`, `CharacterForm`, `ScenarioForm`, `SettingsForm`; one `tests/support` package; the `one` sweep | 8,520 to 8,600 |
| 5 — the rooms | `engines/rooms/`: the map world, the drafts, the bars and `RoomEngine`, shared by every room crawler the way `scenes/` is shared by every scene engine; Tunnel Goons subclasses it | 8,580 to 8,680 |

---

## Phase 1 — the ground

### 1.1 Mechanical

1. `type X = ...` for every alias assigned today: `config.py` `ProviderName`, `Role`,
   `CliProvider`, `Effort`; `engines/loner3e/world.py` `TagKind`; `engines/tunnelgoons/world.py`
   `Ability`, `Boost`; `core/entities.py` `Slug`, `CheckedEntityId`. `ui/settings.py::_widget`
   reads the alias through: `bare = field.annotation; if isinstance(bare, TypeAliasType): bare =
   bare.__value__` (`TypeAliasType` from `typing`), because `get_origin` of a PEP 695 alias is
   `None`. Pydantic 2.13 accepts every one of these as a `type` alias, `Annotated` included.
2. Delete the sixteen `_ =` discards: `ui/game.py` (3), `ui/create.py` (2), `app/spawn.py` (1),
   `app/runtime.py` (2), `app/speech.py` (1), `app/media.py` (3), `engines/tunnelgoons/world.py`
   (2), `core/tools.py` (2). `reportUnusedCallResult` is already off.
3. The seventeen relative imports become absolute: `ui/settings.py`, `ui/panels.py`,
   `ui/widgets.py`, `ui/game.py` (2), `ui/__main__.py`, `ui/app.py` (4), `ui/create.py`,
   `app/runtime.py` (4), `app/speech.py`, `app/media.py`. Add `"TID252"` to
   `[tool.ruff.lint] select` in `pyproject.toml`.
4. `app/mcp.py::_build_server`: the unused parameters are `_ctx` and `_params`; delete the two
   `del` lines (51 and 58).
5. `app/media.py`: `parts: list[JsonValue]` in `_generate` and `body: Mapping[str, JsonValue]` in
   `post_bearer`; `app/speech.py` follows where it builds the body it posts.
6. Resolvers return `list[Fact]`; tuples only on the seam (`Engine.advance`, `Engine.answer`,
   `SceneEngine.leaving`, `MasterTool.call`). Change to `list[Fact]`: `SceneWorld.settle`,
   the three `next_scene`, `breathless/tools.py::test_luck`, `twentyfourxx/tools.py::test_luck`,
   `loner3e/tools.py::Oracle.resolve_question`, `tunnelgoons/worldsmith.py::install_extension`,
   `scenes/worldsmith.py::install_scene`.
7. Keyword construction in-process: `breathless/creation.py:75` builds
   `BreathlessCharacter(pronouns=..., job=..., skills=..., item=...)`;
   `twentyfourxx/creation.py:143` builds `TwentyfourxxCharacter(specialty=..., ...)`;
   `tunnelgoons/worldsmith.py:90` builds `MapCanon(places=draft.places, ways=draft.ways,
   npcs=draft.npcs, items=draft.items, start=draft.start, source=source, hub=..., board=...)`.
8. `core/entities.py`: add `class Loose(BaseModel)` with `ConfigDict(extra="ignore",
   frozen=True)`, docstring "A foreign shape read for a few of its keys." `EngineHeader`
   (`core/model.py`), `_ClaudeResult` (`app/spawn.py`) and the three `extra="ignore"` models in
   `app/media.py` subclass it and drop their own `model_config`.
9. `loner3e/tools.py::Outcome` becomes `class Outcome(Frozen)` with the same two fields.
   `app/launch.py`: `CatalogEntry`, `LaunchTarget`, `SaveOption`, `LauncherCatalog` become
   `@dataclass(frozen=True, slots=True)` with the same fields, properties and methods;
   `tests/ui/test_launcher.py` compares fields where it compared `model_dump()` (lines 68, 135).
10. `app/media.py::Illustrator` and `app/speech.py::Reader` become `@dataclass(slots=True)`: a
    class carrying a mutable `generating: set` is not frozen.
11. `app/spawn.py`: delete the comment above `DRIVERS` (line 131). `CLAUDE.md`, Code, the layout
    bullet becomes "Module layout: imports, constants, classes, public functions, private
    functions. A constant built from a class follows that class."

### 1.2 `Refusal`

1. `core/entities.py`: add
   ```python
   class Refusal(ValueError):
       """A message a role or the player is meant to read. Any other exception is a bug."""


   def parse[T: BaseModel](model: type[T], value: object) -> T:
       """Validation at a boundary; a shape the model rejects reads back as a refusal."""
       try:
           return model.model_validate(value)
       except ValidationError as broken:
           raise Refusal(broken.errors()[0]["msg"]) from broken
   ```
   `require_unique` and `content_id` raise `Refusal`.
2. `core/model.py::Game.committed` becomes
   ```python
   def committed(self) -> Self:
       """The commit gate: the draft revalidated whole; a state the rules refuse never lands."""
       try:
           return type(self).model_validate(self)
       except ValidationError as broken:
           raise Refusal(f"the state this leaves is invalid: {broken.errors()[0]['msg']}") from broken
   ```
   `Mutable.model_config` gains `revalidate_instances="always"`, which is what makes
   `model_validate(instance)` re-run every validator down the tree. Constructing a `Mutable`
   from instances copies them; nothing may keep a reference to a sub-object across a
   constructor or a `commit()`.
3. `turn/run.py::_apply`: delete the `try/except ValidationError` around the play; `validate`
   and `committed` raise `Refusal` themselves. `core/tools.py::master_tool.call` parses with
   `parse(args, raw)`. `engines/seam.py::restored` parses with `parse(EngineHeader, value)` and
   `parse(self.game, value)`; `core/io.py::_read` and `read_scenario` with `parse`;
   `app/launch.py::load_catalog` with `parse(SaveHeader, decoded(raw))`. `core/io.py::decoded`
   wraps `json.loads` in `try/except json.JSONDecodeError as broken: raise Refusal(f"not JSON:
   {broken}") from broken`: a file that will not parse is a message for whoever wrote it. One
   test in `tests/core/test_store.py`: a scenario folder whose `world.json` holds `{not json`
   is skipped and logged.
4. Every `raise ValueError(` under `src/aidm/engines/` and `src/aidm/turn/` becomes `raise
   Refusal(`. In `core` and `app` these become `Refusal`: `core/creation.py::check_picks` (4),
   `core/source.py::whole_text` (2), `core/io.py` all but `_safe_path`, `app/spawn.py` (4),
   `app/mcp.py::call`, `app/launch.py` (2), `app/runtime.py` all but `Runtime.playing`. These
   stay `ValueError`: `core/facts.py`, `core/play.py`, `core/tools.py::master_tool`,
   `config.py`, `core/io.py::_safe_path`, `app/runtime.py::Runtime.playing`. `require_unique`
   raising `Refusal` from `Engine.__init__` (a duplicate tool name) and from inside pydantic
   validators is accepted: the first crashes at start either way, the second is wrapped.
5. The catch sites narrow: `app/mcp.py::on_call_tool` `except Refusal`; `app/runtime.py`
   `_act`, `_narrate`, `_grow` `except (OSError, Refusal)`, `new_scenario.playable` `except
   Refusal`; `engines/seam.py::authored.refusal` `except Refusal`; `app/launch.py::load_catalog`
   both `except Refusal`; `core/io.py::read_scenarios` and `read_characters` `except Refusal`;
   `ui/create.py` `except Refusal` (2) and `except (OSError, Refusal)` (1);
   `ui/widgets.py::working` `except (OSError, Refusal)`: a bug in a turn is no longer shown as a
   notification; NiceGUI logs it and `play`'s `finally` resets `phase`, which is the intent.
   `app/spawn.py`'s two `except ValueError` around `json` stay.
6. Tests: `tests/core/core_test_support.py::ScriptedSpawner.run` raises `Refusal` when a role
   has no answer left; `Table.call` catches `Refusal`. Every other `pytest.raises(ValueError)`
   keeps passing and is tightened to `Refusal` when its file is next touched.
7. `CLAUDE.md`, Code, after the boundary bullet: "A message a role or the player is meant to read
   is a `Refusal`; any other exception is a bug and is not caught."

### 1.3 The two bugs

1. `tests/core/test_package_boundary.py:7`: `ENGINES` lists all four:
   `("aidm.engines.loner3e", "aidm.engines.tunnelgoons", "aidm.engines.breathless",
   "aidm.engines.twentyfourxx")`.
2. `engines/tunnelgoons/world.py`: add `TunnelWorld.kill(self, one: Goon | Npc) -> list[Fact]`:
   the body of `tools.py::_kill` (reveal, `alive = False`, carried items fall loose at the
   current place with the `items_dropped` fact, then the `actor_killed` fact), the card
   `"You are dead"` when `one.id == self.player.id`, else `f"{one.name} is dead"`; a dead
   player's items fall loose too.
   `tools.py::_kill` becomes `world.kill(world.require_npc_here(change.entity_id))`.
   `tools.py::action_roll` lines 209 to 220: `facts.extend(world.kill(npc))` when the npc's hp
   hits 0 and `facts.extend(world.kill(player))` when the player's does; the `npc_slain` and
   `goon_killed` facts go. `tests/tunnelgoons/test_tools.py:89` and `:108` assert
   `"actor_killed"`.
3. `engines/twentyfourxx/tools.py::Skills.attempt`: the death branch is
   `facts.extend(world.kill(player.id))`; the hand-rolled `alive = False` and its fact go.

### 1.4 Names

1. Participles become verbs, every caller and test following: `Engine.restored` → `restore`;
   `Game.committed` → `commit`; `app/spawn.py::answered` → `ask` and its `ask` parameter →
   `spawn`; `engines/seam.py::authored` → `compose`; `core/io.py::decoded` → `decode`;
   `app/mcp.py::offered` → `list_tools`; `app/spawn.py::_spawned` → `_spawn`;
   `tests/core/core_test_support.py` `opened` → `open_game`, `opened_for` → `open_game_for`,
   `played` → `play_turn`.
2. One verb for reading content: `core/io.py::load_character` → `read_character`,
   `engines/core.py::load_packs` → `read_packs`, `config.py::load_settings` → `read_settings`,
   `app/launch.py::load_catalog` → `read_catalog`.
3. One stem per engine, `<Stem>Engine/World/Game/Scenario`, the role noun for the played entity,
   `<Stem>Payload` for the four file payloads (deleted in Phase 3, when the sheet becomes the
   payload), `<Stem>CharacterFile` until then:
   - Loner (the stem is the package name, `Loner3e`): `Loner3eEngine` and `Loner3eGame` stay;
     `Loner3eScenarioFile` → `Loner3eScenario`; `Loner3eCharacterFile` stays until Phase 3
     makes it `Loner3eCharacter`; `Loner3eCharacter` (the payload) → `Loner3ePayload`;
     `LonerCharacter` → `Loner3eSheet`; `LonerWorld` → `Loner3eWorld`.
   - Breathless: `BreathlessScenarioFile` → `BreathlessScenario`, `BreathlessCharacter` →
     `BreathlessPayload`; `BreathlessEngine`, `BreathlessGame`, `BreathlessWorld`,
     `BreathlessCharacterFile`, `Survivor` stay.
   - 24XX: `TwentyfourxxScenarioFile` → `TwentyfourxxScenario`, `TwentyfourxxCharacter` →
     `TwentyfourxxPayload`; the rest stay.
   - Tunnel Goons: `TunnelWorld` → `TunnelGoonsWorld`, `TunnelGoonsScenarioFile` →
     `TunnelGoonsScenario`, `TunnelGoonsCharacter` → `TunnelGoonsPayload`; the rest stay.
     `NEXT-SPECS.md` lines 80 and 157 say `TunnelGoonsWorld`.
4. `engines/core.py` → `engines/base.py`; every `aidm.engines.core` import follows;
   `tests/core/test_engines_core.py` → `test_engines_base.py`; `NEXT-SPECS.md` line 212 says
   `engines/base.py`.
5. Recreate `PROGRESS.md` with this phase's entry. Its first entry records, under a "Standing
   decisions" heading, the two decisions that leave with `PROPOSALS.md`, quoted: "A base class
   where we own every implementation; a `Protocol` only where a test double or a foreign object
   must fit without inheriting." and "The page polls the service; the service never calls the
   page."

### Done when

Green; every golden unchanged. `grep -rn "raise ValueError" src/aidm/engines src/aidm/turn`
finds nothing; `grep -rn "except ValueError\|except (OSError, ValueError)" src` finds only
`app/spawn.py`; `grep -rn "LonerWorld\b\|LonerCharacter\b\|TunnelWorld\b\|ScenarioFile\|engines\.core\|committed()\|restored(\|npc_slain\|goon_killed" src tests` finds nothing;
`grep -rn "^from \.\|del ctx" src` finds nothing. `uv run aidm`: a Tunnel Goons npc killed by
`action_roll` leaves its items loose; a refused tool call reaches the master as a refusal, a
`KeyError` in a resolver reaches the log as a crash. `src` about 9,190.

---

## Phase 2 — the engine is the class

### 2.1 `Thing`, `Counter`, notes, tools

1. `engines/base.py` (`PLAYER_ID` stays where it is; `core` never names a world thing): add
   ```python
   class Thing(Mutable):
       """What every world thing shares: an id, a name, a brief, and whether the player has met it."""

       id: CheckedEntityId
       name: str
       brief: str
       known: bool = False

       @property
       def label(self) -> str:
           """Name and exact id, so a role can reuse the id; the player is named as such."""

       def fact(self, kind: str, trace: str, *, narrate: bool = True, card: str = "",
                dice: tuple[DiceEvent, ...] = ()) -> Fact:
           """`told` only when the player has learned of this thing, so no unknown name leaks."""

       def reveal(self) -> list[Fact]:
           """Leave cards to the containing action or the standalone reveal arm."""

       def subject(self) -> Subject: ...
   ```
   The bodies are today's `labeled`, `entity_fact`, `reveal`, compared against `PLAYER_ID`;
   `subject()` returns `core.views.Subject`. `core/views.py::Subject.speaker() -> Speaker`
   replaces `speaker_of`.
2. `engines/base.py`: delete `Entity`, `labeled`, `entity_fact`, `reveal`, `pool`, `adjust`,
   `counter_fact`; `keep_highest` stays. `Person(Thing)` adds `alive`, `rows()`, `unwritten()`
   and `line(*, detail: str = "") -> str`, the body of `scenes/world.py::entity_line`.
   `check_filing(pool: Mapping[EntityId, Thing]) -> None` (`dict` is invariant in its value; the
   callers pass `dict[EntityId, Person | Place | Npc | Item]`). `Counter` gains
   ```python
   def __str__(self) -> str: return f"{self.current}/{self.maximum}"
   @property
   def shortfall(self) -> int: return self.maximum - self.current
   def adjust(self, amount: int) -> int:
       """Move a bounded pool and say how far it moved; a clamp can land short of `amount`."""
   def change(self, owner: Thing, amount: int, label: str, why: str) -> list[Fact]:
       """The move as a fact on its owner; a zero move is no fact."""
   ```
   Every `pool(x)` is `str(x)`, every `counter_fact(one, c, n, label, why, player_id)` is
   `c.change(one, n, label, why)`, every `_shortfall(c)` is `c.shortfall`
   (`loner3e/tools.py`), every `labeled(one, pid)` and `world.label(one)` is `one.label`,
   every `entity_fact(one, ...)` is `one.fact(...)`, every `world.reveal(one)` and
   `reveal(one, pid)` is `one.reveal()`. Delete `SceneWorld.label`, `SceneWorld.reveal`,
   `TunnelGoonsWorld.label`, `TunnelGoonsWorld.reveal`. `tests/loner3e/test_counters.py`
   reads `Counter.adjust` and `Counter.change`.
3. `engines/tunnelgoons/world.py`: `Goon(Person)`, `Npc(Person)`, `Item(Thing)`, `Place(Thing)`
   lose their repeated `id/name/brief/known/alive` lines; the module's `type Entity = Goon |
   Npc | Item | Place` stays (it is Tunnel Goons' own union, not the deleted Protocol).
   `Dungeon.ways: dict[EntityId, list[Way]]`.
4. `core/model.py::Game.notes: list[str] = Field(default_factory=list)` and
   `def note(self, text: str) -> None: self.notes.append(text)`. Every `x.notes = (*x.notes, t)`
   is `x.note(t)` (`breathless/tools.py` 4, `loner3e/tools.py` 2, `scenes/worldsmith.py` 1,
   `turn/run.py` 2). `turn/run.py::Turn.notes: list[str]`; `Turn.begin` sets `turn.notes,
   turn.draft.notes = turn.draft.notes, []`. `twentyfourxx/world.py::Operator.hindrances:
   list[str]`; `_change_hindrances`, `defend` and `attempt` append and remove in place.
5. `engines/seam.py`: `tools: dict[str, MasterTool[G]]`; `__init__` checks `require_unique`
   over the names, then builds the dict. `Engine.answer` reads `self.tools.get(chosen.name)`;
   `turn/run.py::Turn.call` reads `self.engine.tools.get(name)`;
   `app/runtime.py::Runtime.published_tools` returns `tuple(playing.engine.tools.values())`;
   `tests/core/test_golden_schemas.py` iterates `engine.tools.values()`;
   `tests/core/test_decisions.py:96` and `tests/core/test_tool_surface.py:522` assign a dict
   keyed by name where they assign a tuple and `()`.
6. `core/tools.py`: add `def schema_text(model: type[BaseModel]) -> str: return
   json.dumps(schema_of(model), indent=2, ensure_ascii=False)`; `turn/context.py::_shape`,
   `scenes/world.py::worldsmith_prompt` and the three `json.dumps(schema_of(...))` in
   `tunnelgoons/worldsmith.py` call it.
7. `core/creation.py`: add `option_of[T: DecisionOption](options: Sequence[T], chosen: str) -> T
   | None` and `chosen_option[T: DecisionOption](options: Sequence[T], chosen: str) -> T`, the
   second raising `Refusal(f"no option {chosen!r}")`. `twentyfourxx/creation.py`: `SkillChoice`,
   `Specialty` and `Origin` subclass `DecisionOption` (they carry its three fields already);
   delete `_options`, `_by_key`, `_require`; steps pass `pack.specialties` and `pack.origins`
   as `options` directly. `loner3e/creation.py::find_entry` → `chosen_option`.
   `engines/base.py`: `SRD_PACK: Slug = "srd"` once; `loner3e/tools.py` and
   `breathless/tools.py` import it.

### 2.2 The scene engine owns the flow

1. Create `engines/scenes/tools.py` holding `Reveal`, `Enter`, `Leave`, `Kill`, `NextScene`,
   `NEXT_SCENE` from `scenes/world.py` and `JoinParty`, `LeaveParty` from `engines/base.py`, plus
   `type SharedChange = Reveal | Enter | Leave | Kill`.
2. `engines/scenes/worldsmith.py` takes from `scenes/world.py`: `SURPRISE`, `cast_unmet`,
   `hub_unmet`, `scene_unmet`, `scene_refusal`, `worldsmith_prompt`, `named_in`; `world.py` keeps
   `SceneRun`, `SceneCanon`, `SceneWorld`, `check_named`, `check_hub`, `resolved_id`,
   `resolve_ids`, `run_of`. `cast_unmet` becomes `_cast_unmet(draft: SceneDraft[C], everyone,
   held, *, needs_return)` and `hub_unmet` becomes `_hub_unmet(draft, world)`, each reading
   what it needs off the draft. Delete `WORLDSMITH` (`world.py:44`); `worldsmith_prompt` takes
   `role: str` first. `SceneWorld.render_worldsmith`, `here_lines`, `hidden_lines`, `hub_rows`
   move onto `SceneEngine` as `render_next(world, intent, answer)`, `here_lines(world)`,
   `hidden_lines(world)`, `hub_rows(world, *, returning)`; `render_next` passes
   `self.worldsmith`.
3. `core/views.py`: `type Sections = tuple[tuple[str, str], ...]` for prompt sections;
   `Rows` stays for a sheet. `sections()`, `Engine.master_sections`, `hub_sections`,
   `master_tail`, `worldsmith_prompt(hub=)` are typed `Sections`.
4. `SceneWorld` gains `join_party(entity_id) -> list[Fact]` (require alive here, reveal, join),
   `leave_party(entity_id) -> list[Fact]`, `party_rows() -> Sections`, `party_panel() ->
   tuple[Panel, ...]`; `_consistent` inlines `check_party`. Delete `join_party`, `leave_party`,
   `check_party`, `party_rows`, `party_panel` from `engines/base.py`. `apply_scene` sets
   `self.board = draft.offers` on a `ReturnDraft` (the install no longer writes the board).
   `world.py` also gains
   ```python
   @classmethod
   def begin(cls, canon: SceneCanon[C], player: P) -> Self:
       """The player is added by code and never authored, so no scenario can claim their id."""
   ```
   replacing the module `new_world`.
5. `engines/scenes/engine.py::SceneEngine`: class attributes `world_type: type[SceneWorld[C, P]]`
   and `worldsmith: str`; `__init__` reads `Path(__file__).parent / "worldsmith.md"` into
   `self.worldsmith`. New concrete methods, bodies moved from `scenes/worldsmith.py` and the
   three engines:
   - `shared_change(self, world: SceneWorld[C, P], change: SharedChange) -> list[Fact]`: the
     four-arm match (`reveal_hidden`, `enter`, `leave`, `kill`).
   - `next_scene(self, draft: G, args: NextScene, _rng: Random) -> list[Fact]`.
   - `master_sections(self, state: G) -> Sections`: SCENE, the question heading, YOU PLAY FOR,
     `*self.sheet_sections(state)`, HERE WITH THE PLAYER, `*world.party_rows()`, HIDDEN HERE,
     `*self.glossary(state)`, `*master_tail(...)`, in that order, so `master.txt` stays
     byte-identical. Hooks `sheet_sections(self, state: G) -> Sections` and `glossary(self,
     state: G) -> Sections` default to `()`.
   - `new_game(self, scenario, character) -> BaseModel`: the scenario `isinstance` check, then
     `self.world_type.begin(scenario.payload, self.player_of(character))`; abstract
     `player_of(self, character: AnyCharacter) -> P` replaces `new_state`. In this step each
     scene engine's `new_state` becomes `player_of(character) -> P` with the same body
     (`player_survivor(character)`, `player_operator(character)`,
     `player_character(character)`), each sets `world_type` (`SceneWorld[Person, Survivor]`,
     `SceneWorld[Person, Operator]`, `Loner3eWorld`), and each engine's `master_sections`
     override and `views.py` go, replaced by `sheet_sections` (Breathless: the BACKPACK row;
     24XX: the GEAR row, `gear_detail` moved into `twentyfourxx/engine.py`) and `glossary`
     (Loner: the WHAT THE TAGS IN PLAY MEAN row over `meanings(self.packs, state.packs, one)`)
     overrides on the engine, so the step is green on its own.
   - `opening_draft(self, kind) -> type[SceneDraft[C]]`, `render_opening(self, source,
     guidance, kind) -> str`, `build_scenario(self, title, premise, packs, written, source, kind)
     -> AnyScenario`, `write_next(self, world, intent, worldsmith) -> SceneDraft[C]`,
     `install(self, draft: G, written) -> list[Fact]`: `write_next` reads `self.cast` and
     `self.guidance(...)`; `install` reads `self.finished_note` and calls `draft.note(...)`;
     `build_scenario` reads `self.scenario` and `self.id`. `opening_canon(draft, source)` stays a
     free function in `scenes/worldsmith.py`.
   - `crossing(self, pursuit: str) -> str` returns `CROSSING.format(pursuit=pursuit)`, see 2.7.5.
   - `ready(self, state)` inlines `way_open`; `over` inlines `player_over`; `validate` inlines
     `check_game`. Delete `way_open`, `player_over`, `check_game` from `world.py`.
   Delete `engines/scenes/views.py` after moving `narrator_view` and `player_view` onto
   `SceneEngine` (`player_view` calls `self.panels(state)`; both use `one.subject()`).
   Delete `scenes/worldsmith.py`'s `write_next`, `install_scene`, `render_opening`,
   `build_scenario`, `opening_draft`.
6. `engines/seam.py`: `compose` becomes a concrete method `Engine.compose(self, worldsmith,
   prompt, model, build, playable)` whose `refusal` closure keeps the last scenario it built
   (`nonlocal built`) so the accepted answer is not built twice. Add concrete
   ```python
   def close(self, draft: G, prompt: str, lines: tuple[Line, ...], facts: tuple[Fact, ...]) -> G:
       """File the exchange, count the turn, commit."""
   ```
   the body of `turn/run.py::close_segment` with `self.narrator_view(draft).spoken(lines)`.
7. `turn/context.py`: delete the two import-time reads (lines 20 and 21); add
   `@cache def _prompt(name: str) -> str` reading `_PROMPTS_DIR / f"{name}.md"`;
   `render_master` and `render_narrator` call `_prompt("master")` and `_prompt("narrator")`.

### 2.3 Breathless

1. `engines/breathless/engine.py::BreathlessEngine` (`world_type`, `player_of` and
   `sheet_sections` landed in 2.2.5): methods `creation_steps`, `create_character`,
   `preview_character`, `guidance`, `panels`, `catch_breath(draft, _args: NoArgs, rng) ->
   list[Fact]` (the body of
   `Complications.catch_breath`, `self.packs` for the table), `complications() ->
   tuple[str, ...]`, `apply_change(world, change: WorldChange) -> list[Fact]` with `case Reveal()
   | Enter() | Leave() | Kill(): return self.shared_change(world, change)` and `case
   DropItem(): return self.drop_item(world, change.item_id)`, `change_world(draft, args:
   ChangeWorld, _rng)`, `check`, `change_stress`, `use_med_kit`, `loot_check`, `test_luck`,
   `drop_item`, `master_tools()` building `master_tool(...)` from the bound methods in today's
   order. Every `packs: Mapping[str, Pack]` parameter goes; `self.packs` replaces it;
   `self.id` replaces `EngineId("breathless")`.
2. `engines/breathless/tools.py` keeps `DropItem`, `ChangeWorld`, `Check`, `ChangeStress`,
   `LootCheck`, `TestLuck`, `WorldChange`, `SWAP`, `outcome`, `loot_options`, `_take_loot`,
   `_roll_loot` (the last two take the `Survivor` and return facts as today). Delete
   `Complications`, `tools`, `apply_change`, `change_world`, `next_scene`, `complications_of`.
3. `engines/breathless/creation.py` keeps `Pack` and `_AUTHORING` only.
4. Tests: `tests/breathless/breathless_test_support.py` deletes `changed_facts`, `changed`,
   `refused`; `tests/core/core_test_support.py` gains the engine-agnostic
   ```python
   def change(engine: AnyEngine, draft: AnyGame, verb: str, **fields: JsonValue) -> list[Fact]:
       return list(engine.tools["change_world"].call(draft, {"change": {"verb": verb, **fields}}, Random(0)))


   def refused(engine: AnyEngine, draft: AnyGame, verb: str, **fields: JsonValue) -> str:
       """The refusal's text, from `pytest.raises(Refusal)`."""
   ```
   `tests/breathless/test_tools.py`, `test_create.py`, `test_views.py`, `test_engine.py` build
   `BreathlessEngine()` and call its methods where they called `tools(PACKS)`,
   `Complications(PACKS)`, `creation_steps(PACKS, ...)`, `master_sections(state)`.

### 2.4 24XX

1. `engines/twentyfourxx/engine.py::TwentyfourxxEngine` (`world_type`, `player_of`,
   `sheet_sections` and `gear_detail` landed in 2.2.5): methods `creation_steps`,
   `create_character`, `preview_character`, `guidance`, `panels`,
   `attempt`, `after_job`, `resolve_skill(player, wanted) -> str` (from `Skills`),
   `apply_change` with the shared case and the five own arms, `change_world`, `test_luck`,
   `defend`, `change_hindrances`, `gain_item`, `drop_item`, `repair_item`, `spend`,
   `master_tools()` in today's order.
2. `engines/twentyfourxx/tools.py` keeps the arg models, `WorldChange`, `outcome`. Delete
   `Skills`, `tools`, `apply_change`, `change_world`, `next_scene` and the six `_` resolvers
   moved. `twentyfourxx/views.py` is already gone (2.2.5); `gear_detail` lives in `engine.py`,
   read by `panels` and `sheet_sections`. `creation.py` keeps `Pack`, `Specialty`, `Origin`,
   `SkillChoice`, `_AUTHORING`.
3. Tests: `tests/twentyfourxx/test_tools.py` builds `TwentyfourxxEngine()` in place of
   `Skills(PACKS)`; `twentyfourxx_test_support.py` and the other test files follow 2.3.4.

### 2.5 Loner

1. `engines/loner3e/engine.py::Loner3eEngine` (`world_type`, `player_of` and `glossary` landed
   in 2.2.5; `glossary` now calls `self.meanings`): methods `creation_steps`,
   `create_character`, `preview_character`, `guidance`,
   `meanings(selected, one) -> tuple[tuple[str, str], ...]`, `twist_table()`,
   `resolve_question` (from `Oracle`), `restore_luck`, `leaving` (the body of
   `close_conflicts`), `apply_change` with the shared case and `ChangeTags`, `Drive`,
   `JoinParty` (`world.join_party`), `LeaveParty` (`world.leave_party`), `change_world`,
   `change_tags`, `drive`, `master_tools()` in today's order. `_refill`, `_strike`, `_twist`,
   `_pair`, `_absorbed`, `_refuse_unless_ready` become private methods or stay module-private
   helpers over their arguments; none takes `packs`.
2. `engines/loner3e/tools.py` keeps `ChangeTags`, `Drive`, `ChangeWorld`, `Question`,
   `Outcome`, `RestoreLuck`, `WorldChange`, `Position`, `AND_AT`, `BUT_AT`, `outcome_for`,
   `twist_pairing`, `twist_note`, `defeat_note`, `conflict_prompt`, `_pack_meanings`. Delete
   `Oracle`, `tools`, `apply_change`, `change_world`, `next_scene`, `twist_table`, `meanings`,
   `close_conflicts`. `creation.py` keeps `Pack` and `_AUTHORING`.
3. Tests: `tests/loner3e/loner3e_test_support.py` builds `Loner3eEngine()` in place of `ORACLE`,
   `PACKS`, `TWISTS`; `test_loner3e_engine.py`, `test_loner3e_events.py`, `test_world.py`,
   `test_create.py` call engine methods.

### 2.6 Tunnel Goons

1. `engines/tunnelgoons/world.py`: `Dungeon` gains `frontier() -> int`, `reachable(start:
   EntityId) -> set[EntityId]`, `has_shortcut() -> bool` and `add_way(from_id, to_id, *, known:
   bool) -> None`; a module-private `_walk(ways, start)` serves `reachable` and the pruned walk
   in `has_shortcut`. Delete `frontier`, `walk`, `has_shortcut`, `_append_way`.
   `TunnelGoonsWorld` gains `move(to_id, with_ids) -> list[Fact]` (it sets `job.started`
   itself), `unlock_way(to_id) -> list[Fact]`, `reveal_hidden(entity_id) -> list[Fact]`,
   `move_item(item_id, to) -> list[Fact]`, `attach(draft: MapDraft, *, known: bool) -> None`,
   `carried_items(item_ids) -> tuple[Item, ...]`, `line(one: Goon | Npc | Item) -> str` (the
   body of `views.py::entity_line`) and `sheet_rows(goon) -> Rows` (`_character_rows`). Delete
   `tools.py`'s `move`, `unlock_way`, `_reveal`, `_move_item`, `_kill`, `_here_and_way`,
   `_carried_items` and `worldsmith.py`'s `attach`, `_append_way`.
2. `engines/tunnelgoons/engine.py::TunnelGoonsEngine`: `__init__` reads `self.directory /
   "worldsmith.md"` into `self.worldsmith` after `super().__init__()`; methods `creation_steps`,
   `create_character`, `preview_character`, `player_of(character, place) -> Goon`,
   `starting_items`, `apply_change` (three arms calling the world), `change_world`, `move`,
   `unlock_way`, `action_roll`, `rest`, `level_up`, `master_tools()`, `master_sections`,
   `narrator_view`, `player_view`, `render_map`, `render_extension`, `render_job`,
   `render_return`, `map_so_far`, `write_extension`, `install_extension`, `build_scenario`,
   `ready` (inlining `way_open`), `over`. Every render reads `self.worldsmith`; delete
   `worldsmith.py:38`.
3. `engines/tunnelgoons/worldsmith.py` keeps `MapDraft`, `ReturnDraft`, the constants, the
   five `*_refusal` and `_*_unmet` bars, `opening_canon`. `MapDraft` loses its hand-written
   `model_config`: an answer held only until it is installed needs no freezing.
   `tools.py` keeps the arg models and `_LEVEL_OPTIONS`. `tunnelgoons/views.py` stays, holding
   `REPORT_IN`, `REPORT_ROW`, `_place_lines`, `_ways_lines`, `_lines`: `engine.py` absorbs the
   tools, the renders and the views and would pass 500 lines with them too.
4. Tests: `tests/tunnelgoons/tunnelgoons_test_support.py` deletes its `changed_facts`,
   `changed`, `refused`; `test_tools.py`, `test_worldsmith.py`, `test_views.py`,
   `test_engine.py`, `test_world.py` call `TunnelGoonsEngine()` and world methods.

### 2.7 The turn, the service, the pipeline

1. `core/views.py::NarratorView` gains `spoken(lines: Sequence[Line]) -> tuple[SpokenLine,
   ...]`, `speakers_refusal(lines) -> str | None`, `narration_refusal(written: Narration) ->
   str | None`, the bodies of `turn/run.py`'s `_spoken`, `speakers_refusal`,
   `narration_refusal`. Delete those three and `close_segment` from `turn/run.py`;
   `tests/core/test_speech.py:23,166` call `engine.close(...)`.
2. `turn/run.py::Turn`: `consume(self, player_input: str | Answer) -> None` sets `self.prompt`
   and `self.action` (the body of `consume_answer`, the `str | Answer` type kept until step 3);
   `_apply(self, play) -> tuple[Fact, ...]` (the body of the module `_apply`); `finish(lines)`
   returns `self.engine.close(self.draft, self.prompt, lines, tuple(self.facts))`. Delete
   `consume_answer`, the module `_apply`, `TurnStep`; `Role` from `aidm.config` replaces
   `TurnStep` in `app/runtime.py`, `ui/game.py` and the tests.
3. Drop `str | Answer` end to end, one step so basedpyright is never red between files:
   `Turn.begin(engine, state, answer: Answer, rng)` and `Turn.consume(answer: Answer)`;
   `GameService.play(answer: Answer, *, moving_on=False)` and `extend(answer: Answer)`, where
   `extend` refuses an `option_id` and reads `answer.text`; `ui/game.py` `submit` always sends
   `Answer(text=typed)`, `move_on` sends `Answer(text=intent)`, `_send(view, answer: Answer, *,
   moving_on)`, and `speaker_of(x)` is `x.speaker()`; `tests/core/core_test_support.py::play_turn`
   wraps a `str` action in `Answer(text=...)` before `service.play`. In the same step, delete
   `GameService.scene()` and `transition_available()`: callers read
   `session.engine.narrator_view(session.state)` and `session.engine.ready(session.state)`.
   `app/spawn.py::ask` takes `(role: Role, prompt: str, model: type[T], refusal: Check[T],
   spawn: Callable[[str, str | None], Awaitable[RunResult]])`, the `Ask` alias deleted; with
   those parameter names `partial(ask, "worldsmith", spawn=partial(self.spawner.run,
   "worldsmith"))` type-checks as a `WorldsmithAnswer`, so `_Worldsmith` is deleted and the
   partial is what `new_scenario` and `_grow` hand the engine. `open()` calls
   `self.engine.close(draft, BEGUN, lines, ())`; `_grow` likewise. `_begun` → `_begin`.
4. `app/launch.py::read_catalog`: parse `EngineHeader` with `parse`, pick the engine, call
   `engine.restore(raw)` once inside the `except Refusal` skip, then check `played_by` and
   `titles` off `state.scenario_id`, `state.character_id`, `state.engine` and skip with the
   warning before anything else is read; `state.scenario`, `state.turn` and
   `engine.scenes(state)` are read only for a save that passed. Delete `SaveHeader` from
   `core/model.py`. `ui/create.py::scenario_page.write` builds `LaunchTarget(scenario_id=name,
   character_id=character.value)` instead of rereading the catalog.
5. `engines/seam.py`: `crossing: str | None = None` becomes a method `crossing(self, pursuit:
   str) -> str | None` returning `None`, docstring "The narrator's brief for the arrival; None
   when the world is extended without a turn, as Tunnel Goons grows its map." `GameService.play`
   computes `brief = self.engine.crossing(answer.text) if moving_on else None` once and reads
   `brief` where it read `crossing`.
6. Drop `packs_dir`: delete `Settings.packs_dir` (`config.py`), `build_engines()` takes no
   argument and constructs every engine with no argument; `SceneEngine.__init__(self)` reads
   `read_packs(self.directory / "packs", self.pack)` (one directory, `read_packs(directory:
   Path, model)`). Tests: `tests/core/core_test_support.py` `ENGINES_BUILT = build_engines()`
   and `LONER3E_PACKS` deleted; `tests/core/test_decisions.py:95`,
   `tests/core/test_tool_surface.py:254,520`, `tests/ui/test_launcher.py:27` and
   `tests/twentyfourxx/test_worldsmith.py:30` construct with no argument;
   `tests/loner3e/test_packs.py:15` tests the user-packs feature this step removes, so that test
   is deleted (the file with it when nothing else is left); `read_packs((PACKS_DIR,), Pack)` in
   `tests/breathless/test_create.py`, `tests/breathless/test_tools.py`,
   `tests/twentyfourxx/test_create.py`, `tests/twentyfourxx/test_tools.py` becomes
   `<Engine>().packs`.
7. `PROGRESS.md` entry.

### Done when

Green. Goldens: `prompts/*`, `schemas/*`, `turn/*` unchanged; `state/tunnelgoons*.json` and
`save/tunnelgoons.json` change only in key order (`alive` follows `known` on every goon and
npc); every other fixture unchanged. `ls src/aidm/engines/*/views.py src/aidm/engines/scenes/views.py`
lists `tunnelgoons/views.py` alone; `grep -rn "packs: Mapping\|player_id\|packs_dir\|class Oracle\|class Skills\|class Complications\|def tools(\|close_segment\|consume_answer\|speaker_of\|entity_fact\|counter_fact\|str | Answer" src`
finds nothing; `grep -rn "read_text" src/aidm/engines src/aidm/turn` finds only `__init__`
bodies, `read_packs` and `_prompt`. `uv run aidm`: every engine plays a turn, a Loner scene is
written and installed, a Tunnel Goons job is taken and reported. `src` about 8,720; every
`engines/<id>/` under 2,000.

---

## Phase 3 — the shapes

One commit: every step below changes a stored shape; a save from before it is stale.

### 3.1 Trim the goldens

1. Delete `tests/core/test_golden_state.py`, `tests/core/fixtures/state/`,
   `tests/core/fixtures/save/`, the `golden(FIXTURES / "save" / ...)` line of
   `tests/core/test_golden_turn.py` and `golden_test_support.py::dumped`. `prompts/*`,
   `schemas/*` and `turn/*` stay.

### 3.2 `Campaign`

1. `engines/hub.py`: add
   ```python
   class Campaign(Mutable):
       """The hub the player comes back to, its board, and the jobs walked from it."""

       place: Slug
       board: Board
       jobs: list[Job] = Field(default_factory=list)
   ```
   with a validator `_jobs_in_order` (every job but the last has a `debrief`; a debriefed or
   finished job has `started`) and methods `check_walked(walked: int) -> None` (`started <
   walked`), `open_job() -> Job | None`, `closed_jobs() -> tuple[Job, ...]`, property
   `finished -> bool` (the open job's verdict), `terms() -> str`, `since_start[T](walked:
   list[T]) -> list[T]`, `ledger() -> str` over the closed jobs, `board_rows()`,
   `board_lines()`, `sections(hub_title: str, *, at_hub: bool, returning: bool) -> Sections`,
   `tail(*, at_hub: bool) -> Sections` (THE JOB from `terms()`, JOBS SO FAR, THE BOARD at the
   hub), `board_panel(*, at_hub: bool) -> tuple[Panel, ...]`, `jobs_panel() -> tuple[Panel,
   ...]`. `Job.closed() -> Fact` replaces `job_closed`. `check_kind(kind, campaign: Campaign |
   None)`. Delete `check_board`, `check_jobs`, `open_job_of`, `closed_jobs_of`, `since_start`,
   `ledger`, `hub_sections`, `master_tail`, `board_rows`, `board_lines`, `board_panel`,
   `jobs_panel`, `job_closed`; `place_unmet` and `question_heading` stay.
2. `engines/scenes/world.py`: `SceneCanon` and `SceneWorld` replace `hub`, `board`, `jobs` with
   `campaign: Campaign | None = None`. `SceneCanon._playable_canon` refuses a campaign with
   jobs and an opening away from `campaign.place`. `SceneWorld._consistent` inlines
   `check_hub`: `campaign.check_walked(len(self.runs))`, run 0 at `campaign.place`, hub runs
   after the first equal the closed jobs. `at_hub` reads `campaign.place`. Delete `open_job`,
   `closed_jobs`, `job_terms`, `job_done`: `settle`, `scene_rows`, `apply_scene`, `job_runs`
   (`self.runs` when `campaign is None`, else `campaign.since_start(self.runs)`) and the
   `SceneEngine` renderers read `world.campaign` after a `None` check. `opening_canon` builds
   `Campaign(place=draft.place, board=draft.offers)` for a `HubDraft`. `SceneWorld.begin`
   copies `campaign`.
3. `engines/tunnelgoons/world.py`: `MapCanon` and `TunnelGoonsWorld` replace `hub`, `board`,
   `jobs` with `campaign: Campaign | None = None`; `MapCanon._startable` refuses `campaign.place
   != start` and a campaign with jobs; `_playable` runs `require_place(EntityId(campaign.place))`,
   `campaign.check_walked(len(self.visits))`, visit 0 at `campaign.place`. `at_hub`, `job_open`,
   `job_visits`, `move`, `level_up`, `install_extension`, `write_extension`, the renders and
   `player_view` read `world.campaign`. `opening_canon` builds `Campaign(place=draft.start,
   board=draft.board)` when `kind == "campaign"`.
4. Rewrite `scenarios/{amber-tap,buried-bell,salt-lantern,waystation}/world.json`: `hub` and
   `board` become `"campaign": {"place": <hub>, "board": <board>, "jobs": []}`. The four
   one-shots carry no `campaign` key.
5. Tests: `tests/core/test_hub.py` tests `Campaign` where it tested `check_board`, `check_jobs`,
   `hub_sections`, `master_tail`, `board_panel`, `jobs_panel`, `ledger`, `job_closed`; the
   "board with no hub" tests go (unrepresentable). `tests/core/test_scenes.py`, every
   `hub_world()` and `small_world()` in the four `*_test_support.py` and
   `tests/core/core_test_support.py` build `campaign=Campaign(...)`.

### 3.3 Dict-shaped tags and abilities

1. `engines/loner3e/world.py`: `TAG_KINDS: tuple[TagKind, ...] = ("skill", "frailty", "gear",
   "condition")`; `Loner3eSheet` replaces `skills`, `frailties`, `gear`, `conditions` with
   `tags: dict[TagKind, list[str]] = Field(default_factory=dict)` and gains `tagged(kind:
   TagKind) -> list[str]` returning `self.tags.get(kind, [])`; `rows()` prints the same four
   rows from `tagged`. Delete `tags_of`, `set_tags`. `Loner3eEngine.change_tags` reads
   `one.tagged(change.kind)` and writes `one.tags[change.kind] = [...]`; `meanings` reads
   `tagged` for `skill`, `frailty`, `gear`. `Loner3ePayload` stays as it is (3.4.5 deletes it);
   `Loner3eEngine.player_of` builds `tags={"skill": list(payload.skills), "frailty":
   list(payload.frailties), "gear": list(payload.gear)}`, so `characters/kael/loner3e.json`
   still loads.
2. `engines/tunnelgoons/world.py::Goon`: `abilities: dict[Ability, int] = Field(
   default_factory=lambda: dict.fromkeys(ABILITIES, 0))` with `min_length=3, max_length=3`
   replaces `brute`, `skulker`, `erudite`; delete `Goon.ability`; `rows()` iterates `ABILITIES`.
   `action_roll` reads `player.abilities[args.ability]`; `level_up` does
   `player.abilities[args.ability] += 1` in place of its match.
3. Rewrite `scenarios/{whispering-vault,buried-bell}/world.json`: every cast entry's `skills`,
   `frailties`, `gear` become `"tags": {"skill": [...], "frailty": [...], "gear": [...]}`.

### 3.4 The payload is the sheet

1. `core/model.py`: `Character[P: BaseModel]` keeps its bound and carries `id: Slug`, `engine:
   EngineId`, `payload: P` only; `name` and `brief` leave the envelope for the sheet. `core`
   never names `Thing`: what the sheet is stays the engine's. Add `class Named(Loose): name:
   str; brief: str = ""`; `CharacterHeader(EngineHeader)` carries `id: Slug` and `payload:
   Named`. `core/io.py::write_character` reads `held.payload.name`;
   `core/io.py::read_characters(directory, engines: Iterable[EngineId]) ->
   Iterator[tuple[Slug, EngineId, CharacterHeader]]` parses `parse(CharacterHeader,
   decode(text))` only, and `app/launch.py::read_catalog` builds its character entries from
   `header.payload.name` and `header.payload.brief`; `read_character` (the engine's full model)
   stays for `Runtime.new_scenario` and `Runtime._open`.
   `tests/core/test_store.py::test_a_character_written_for_two_engines_is_read_once_for_each`
   reads headers.
2. `engines/seam.py`: concrete
   ```python
   def check_character(self, character: AnyCharacter) -> None:
       """The file is this engine's and its sheet is the player's."""
       if not isinstance(character, self.character):
           raise Refusal(f"{self.title} received an incompatible character")
       if character.payload.id != PLAYER_ID or not character.payload.known:
           raise Refusal("a character sheet is the player's: id 'player', known")

   def preview_character(self, character: AnyCharacter) -> Rows:
       return self.player_of(character).rows()
   ```
   and abstract `player_of(self, character: AnyCharacter) -> Person`. `SceneEngine.player_of(
   character) -> P` is `self.check_character(character); return deepcopy(character.payload)`;
   `TunnelGoonsEngine.player_of(character) -> Goon` the same. The three engine `preview_character`
   overrides append their extra row: Breathless `("Backpack", ", ".join(item.name for item in
   sheet.items.values()))`, 24XX `("Gear", ", ".join(item.name for item in
   sheet.items.values()))`, Tunnel Goons `("Items", ", ".join(sheet.kit))`; Loner uses the
   default.
3. `engines/breathless/world.py`: delete `BreathlessPayload` and `player_survivor`;
   `BreathlessCharacter(Character[Survivor])`; delete `Survivor._filled_out` (a validator that
   mutates); `skills` and `worn` become required, `Field(min_length=6, max_length=6)`.
   `tests/breathless/breathless_test_support.py::_player` and
   `tests/breathless/test_world.py:32,46` pass all six skills and `worn` explicitly.
   `BreathlessEngine.create_character` builds
   `Survivor(id=PLAYER_ID, name=name, brief=brief, known=True, pronouns=..., job=...,
   skills={**dict.fromkeys(SKILLS, 4), **chosen}, worn=dict(skills), items={EntityId(slug(item,
   ())): Item(name=item, die=STARTING_ITEM)})` and returns `BreathlessCharacter(id=slug(name,
   ()), engine=self.id, payload=sheet)`.
4. `engines/twentyfourxx/world.py`: delete `TwentyfourxxPayload` and `player_operator`;
   `TwentyfourxxCharacter(Character[Operator])`; `Kit` stays as the pack's item shape.
   `TwentyfourxxEngine.create_character` builds the `Operator` with `items` keyed by
   `slug(kit.name, taken)` as `player_operator` did.
5. `engines/loner3e/world.py`: delete `Loner3ePayload` and `player_character`;
   `Loner3eCharacterFile` → `Loner3eCharacter(Character[Loner3eSheet])`;
   `Loner3eEngine.create_character` builds the `Loner3eSheet` with `tags={"skill": [...],
   "frailty": [...], "gear": [...]}`.
6. `engines/tunnelgoons/world.py`: delete `TunnelGoonsPayload` and `player_goon`;
   `TunnelGoonsCharacter(Character[Goon])`; `Goon` loses `place` and gains `kit: tuple[str, ...]
   = Field(min_length=STARTING_ITEMS, max_length=STARTING_ITEMS)`, one comment: "the starting
   items by name; `new_game` files them as `Item`s on the player" (it then rides in every save
   as a record of the start; note it under known-and-accepted in `PROGRESS.md`).
   `TunnelGoonsWorld.current`
   reads `self.places[self.visits[-1].place]`; `here`, `require_npc_here`, `reveal_hidden`,
   `move` read `self.current.id` where they read `player.place`, and `move` no longer writes
   it; `_playable` drops the "last visit is not where the player stands" check.
   `TunnelGoonsEngine.create_character` checks the three abilities sum to `ABILITY_POINTS`
   (`Refusal`) and builds `Goon(id=PLAYER_ID, name=..., brief=..., known=True,
   abilities=..., kit=...)`; `new_game` files `starting_items(sheet.kit, taken)`.
7. Rewrite `characters/kael/{loner3e,breathless,twentyfourxx,tunnelgoons}.json`: the envelope
   keeps `id` and `engine`; `payload` is the sheet with `"id": "player"`, `name`, `brief`,
   `"known": true` and the rules fields as steps 3 to 6 define them; defaults are omitted.
8. Tests: `tests/core/core_test_support.py::character()` and every `*CharacterFile` mention read
   `<Stem>Character`; `tests/*/test_create.py` assert on the sheet in `payload`.

### 3.5 `ScenarioMeta` carries the style and the voice

1. `core/model.py::ScenarioMeta` gains `art_style: str = ""` and `voice: str = ""` and
   `with_premise(fallback: str) -> Self` (keyword construction, `premise or fallback`);
   `Scenario` loses `art_style` and `voice`.
2. `engines/seam.py::Engine.author(self, meta: ScenarioMeta, source, packs, worldsmith,
   playable)`; `SceneEngine.build_scenario` and `TunnelGoonsEngine.build_scenario` take `meta`
   and file `meta.with_premise(...)`. `app/runtime.py::Runtime.new_scenario(engine_id, meta:
   ScenarioMeta, document, packs, character_id)` writes `written` as authored; the
   `model_copy(update=...)` goes. `Runtime._open` reads `scenario.meta.art_style` and
   `open_reader` reads `scenario.meta.voice`. `ui/create.py::scenario_page.write` builds
   `ScenarioMeta(title=chosen, premise=told, kind=kind, art_style=..., voice=...)`.
   `tests/core/test_speech.py:143` sets the voice through `meta` where it did
   `scenario().model_copy(update={"voice": "Puck"})`.
3. Rewrite `scenarios/{buried-keep,salt-lantern}/world.json`: delete their empty `art_style`
   key (the other six carry neither key); `tests/core/test_store.py` and
   `tests/ui/test_launcher.py` follow the envelope.
4. `PROGRESS.md` entry.

### Done when

Green. Goldens: `prompts/*`, `schemas/*`, `turn/*` unchanged; `state/` and `save/` gone. The
eight `scenarios/*/world.json` and four `characters/kael/*.json` load. `grep -rn "hub is None\|hub is not None\|world\.board\|payload\.board\|\.hub\b\|check_board\|check_jobs\|Payload\b\|CharacterFile\|tags_of\|set_tags\|\.brute\b\|player_survivor\|player_operator\|player_character\|player_goon" src`
finds nothing; `grep -rn "model_copy" src/aidm/app` finds nothing. `uv run aidm`: a new
character is created and previewed in every engine; a
campaign takes a job, plays it, goes home and the ledger lists it; a save from before this
phase is skipped with a warning. `src` about 8,540.

---

## Phase 4 — the chores

### 4.1 UI as small classes

1. `ui/game.py`: `class GamePage` replaces `GameView` and the module functions; `__init__(self,
   runtime: Runtime, session: GameService)` holds today's fields; `@ui.refreshable_method` on
   `scene_header`, `chat`, `live_turn`, `decision_panel`, `way_on_panel`, `sidebar`,
   `journal`; `refresh()` refreshes those seven; `build()` is today's `game_page` body;
   `poll_turn`, `poll_media`, `submit`, `move_on`, `restart`, `composer` are methods.
   `composer` keeps the widgets on `self.box`, `self.send`, `self.move_on_button`,
   `self.over_label` with no `bind_*_from`; `poll_turn` sets `enabled`, `visible` and the text
   from one `player_view()` when `now != self.seen`. `game_page(runtime, session)` builds a
   `GamePage` and calls `build()`. `ui/panels.py::scene_sidebar` and `journal_panel` lose
   `@ui.refreshable`; `GamePage.sidebar` and `journal` call them. `ui/app.py::_new_game`
   becomes `class LaunchForm` (`catalog`, `scenario_id`, `character_id`; methods
   `choose_scenario`, `choose_character`, refreshable `form`, `build`), its two `nonlocal`s
   gone.
2. `ui/create.py`: `class CharacterForm` (`runtime`, `engine_id`, `picks`, `name`, `brief`;
   methods `choose_engine`, `write`, `choose`, `field`, `create`, refreshable `form`, `build`)
   and `class ScenarioForm` (`runtime`, `catalog`, `engine_id`, `document`; methods `took`,
   `choose_engine`, `write`, refreshable `form`, `build`) replace the `nonlocal` closures;
   `character_page` and `scenario_page` build one each.
3. `ui/settings.py`: `class SettingsForm` holding `settings`, `apply`, `boxes: Boxes`; `render(
   value, field, path) -> None` fills `self.boxes`; `changes() -> Changes`; `save() -> None`;
   `settings_page` builds one. `tests/ui/test_settings.py` builds a `SettingsForm` where it
   called `_changes` and `_save`.

### 4.2 Tests: one support package

1. Create `tests/support/` with an empty `__init__.py`; move `tests/core/core_test_support.py` →
   `tests/support/table.py` (`ScriptedSpawner`, `Table`, `EnvFileFreeSettings`,
   `offline_settings`, `game`, `SHIPPED`, `open_game_for`, `play_turn`, `change`, `refused`,
   `narrated`, the `Call` helpers) and `tests/support/loner.py` (`with_entity`, `loner_sheet`,
   `scenario`, `character`, `initialized`, `open_game`, merged with
   `tests/loner3e/loner3e_test_support.py`); `golden_test_support.py` → `tests/support/golden.py`;
   `golden_turn_support.py` → `tests/support/golden_turn.py`; the other three
   `*_test_support.py` → `tests/support/<engine>.py`; `tests/ui/ui_test_support.py` →
   `tests/support/ui.py`. `pyproject.toml`: `pythonpath = ["tests"]`, `extraPaths = ["src",
   "tests"]`; imports read `from support.table import ...`.
2. Pin one seed per hunt: `tests/loner3e/test_loner3e_engine.py` lines 113, 131, 160, 180 and
   `tests/loner3e/test_loner3e_events.py` lines 80, 101 each find their seed once, then the
   loop becomes `Random(<that seed>)` with a comment naming what the seed rolls.
3. File names by subject: `tests/core/test_pipeline.py` → `test_turn.py`,
   `test_tool_surface.py` → `test_master_tools.py`, `test_session.py` → `test_game_service.py`;
   `test_crossing_integrity.py`'s two tests move into `test_turn.py`; `test_decisions.py` stays.
   Every `pytest.raises(ValueError)` that expects a refusal reads `Refusal`.

### 4.3 The `one` sweep

1. Per package, one step each, in this order: `src/aidm/core` and `src/aidm/turn`;
   `src/aidm/engines`; `src/aidm/app` and `src/aidm/ui`; `tests`. In each file: every local,
   parameter or comprehension variable named `one`, `held`, `said`, `told`, `landed`,
   `written`, `came` becomes the noun it holds (`entity`, `member`, `item`, `offer`, `pack`,
   `way`, `exchange`, `fact`, `option`, `line`, `session`, `answer`, `reply`, `text`); field
   names, tool names and JSON keys (`Fact.told`, `Way.known`) do not change. A docstring
   written as an aphorism states the contract instead ("A value nothing owns" → "Frozen and
   compared by fields; every model answer and fact is one.").
2. `PROGRESS.md` entry.

### Done when

Green; every golden unchanged. This AST check, run from the scratchpad over `src` and again
over `tests`, exits 0 (a `grep -w` would match `"one-shot"` and every docstring):
```bash
uv run python -c "import ast,pathlib,sys; hits=[(p,n.lineno) for p in pathlib.Path('src').rglob('*.py') for n in ast.walk(ast.parse(p.read_text())) if (isinstance(n,ast.Name) and n.id=='one') or (isinstance(n,ast.arg) and n.arg=='one')]; print(hits); sys.exit(bool(hits))"
```
`ls tests/*/*_test_support.py` lists nothing; `grep -rn "bind_.*_from\|nonlocal\|refresh_all" src/aidm/ui`
finds nothing. `uv run aidm`: two tabs on one game each refresh their own panels; the composer
enables and disables within a second of the turn; the launcher, create and settings pages
behave as before. `src` 8,520 to 8,600; a rise of up to 60 over Phase 3 is the class overhead,
not padding.

---

## Phase 5 — the rooms

One crawler exists today, so this is the one place the plan builds a base ahead of its second
implementation. The reason is layout, not reuse: after Phase 4 every engine has the same five
files, and Tunnel Goons alone carries a whole lifecycle (the map world, the drafts, the bars,
the worldsmith flow, both views) that in the scene engines lives in `scenes/`. `engines/rooms/`
holds that lifecycle, file for file as `scenes/` does, and `tunnelgoons/` keeps its sheet, its
rolls and its creation, the size of `breathless/`. The `RoomEngine` docstring says so, so the
next maintainer knows why a base has one subclass.

Rule 9 bends once here, and only where it must: the Tunnel Goons worldsmith prompt text
splits between `rooms/worldsmith.md` (the map craft, engine-free) and the engine's
`AUTHORING` (the `hp` sentence). No golden holds a worldsmith prompt. `prompts/*`,
`schemas/*` and `turn/*` stay byte-identical: no tool or arm changes, no field description
changes, and every master section keeps its exact text. `scenarios/*/world.json` and
`characters/kael/tunnelgoons.json` keep their keys, so they do not change.

Every step moves code verbatim unless a shape below says otherwise. The generic parameter
`N` is the room engine's npc type, as `C` is the scene engine's cast type; the same
`revalidate_instances="always"` rule applies, so every model over `N` is parametrized at
runtime (`MapDraft[self.dweller]`, `RoomCanon[self.dweller]`) exactly as `scenes/` does with
`self.cast`.

### 5.1 `engines/rooms/world.py`

1. From `tunnelgoons/world.py`, move `Item`, `Place`, `Way`, `Visit` and `_walk` verbatim. Add
   ```python
   class Dweller(Person):
       """Anyone who stands in a place; a room engine's npc adds its own stats."""

       place: CheckedEntityId
   ```
2. `class Dungeon[N: Dweller](Mutable)`: the body of today's `Dungeon` with `npcs: dict[EntityId, N]`;
   `entity` returns `N | Item | Place | None`, `require` returns `N | Item | Place`, `at` yields
   `N`. Delete the module-level `Entity` alias.
3. `class RoomCanon[N: Dweller](Dungeon[N])`: today's `MapCanon`, renamed, body verbatim.
4. `class RoomWorld[N: Dweller, P: Person](Dungeon[N])`: today's `TunnelGoonsWorld` with
   `player: P`; `here` yields `P | N`; `require_npc_here` returns `N`; `kill(actor: P | N)`;
   `attach(region: Dungeon[N], start, *, known)`; `entity` returns `P | N | Item | Place | None`.
   Two changes of shape, so the sheet lines stay the engine's:
   ```python
   def sheet_rows(self) -> Rows:
       """The player's sheet as the master and the panel print it; a rule may amend a row."""
       return self.player.rows()

   def line(self, entity: P | N | Item) -> str:
       """One card line; the player's sheet is the world's, everyone else's is their own."""
       line = f"- {entity.name}[{entity.id}]" + (f" — {entity.brief}" if entity.brief else "")
       if isinstance(entity, Person) and not entity.alive:
           line += " (dead)"
       rows = self.sheet_rows() if entity.id == self.player.id else entity.rows() if isinstance(entity, Person) else ()
       sheet = "; ".join(f"{label.lower()}: {value}" for label, value in rows)
       return f"{line}\n  {sheet}" if sheet else line
   ```
   and a constructor the engine calls, as `SceneWorld.begin` is:
   ```python
   @classmethod
   def begin(cls, canon: RoomCanon[N], player: P, items: Iterable[Item]) -> Self:
       """The played character at the canon's start, their starting items filed on them."""
       canon = deepcopy(canon)
       return cls(places=canon.places, ways=canon.ways, npcs=canon.npcs,
                  items={**canon.items, **{item.id: item for item in items}},
                  player=player, visits=[Visit(place=canon.start)],
                  source=canon.source, campaign=canon.campaign)
   ```
   `place_lines`, `ways_lines`, `exchanges`, `scenes` and every other method move verbatim.
5. Full check. Nothing imports the module yet; the step is the file.

### 5.2 `engines/rooms/drafts.py`, `tools.py`, `worldsmith.py`, `worldsmith.md`

1. `drafts.py`: `class MapDraft[N: Dweller](Dungeon[N])` (today's `MapDraft`, its two fields
   verbatim) and `ReturnDraft(Frozen)` verbatim.
2. `tools.py`: `Reveal`, `MoveItem`, `Kill`, `Move`, `UnlockWay` verbatim, descriptions
   included, and `type SharedChange = Reveal | MoveItem | Kill`. `ChangeWorld` does not move.
3. `worldsmith.py`: `MIN_PLACES`, `MIN_EXTENSION_PLACES`, `TAVERN_ASK`, `JOB_BRIEF`, the four
   `*_refusal` functions and their `_unmet` helpers verbatim, each generic over the draft:
   `def map_refusal[N: Dweller](draft: MapDraft[N]) -> str | None`; the two that read the
   world take `world: RoomWorld[N, Any]` (the player type is not read; this is the one `Any`
   the phase adds, under the `Game[P]` rule's reason). `opening_canon` does not move: it becomes
   a `RoomEngine` method in 5.3, as `SceneEngine.opening_canon` is.
4. `worldsmith.md`: today's `tunnelgoons/worldsmith.md` without the sentence that begins
   "Every npc needs `hp`". Every other sentence verbatim.
5. Full check.

### 5.3 `engines/rooms/engine.py`

1. ```python
   class RoomEngine[N: Dweller, P: Person, G: Game[Any]](Engine[G]):
       """The room-crawl lifecycle, once; a subclass says what its rules add.

       One crawler subclasses it today. The split mirrors `scenes/`, so a second one adds only
       its sheet, its rolls and its creation, and every engine reads the same five files.
       """

       dweller: type[N]
       world_type: type[RoomWorld[N, P]]
       worldsmith: str
   ```
   `__init__` reads `Path(__file__).parent / "worldsmith.md"` into `self.worldsmith`, then
   `super().__init__()`. `REPORT_IN` and `REPORT_ROW` move here from `tunnelgoons/engine.py`.
2. Move from `TunnelGoonsEngine`, verbatim in text and in section order: `over`, `record`,
   `history`, `scenes`, `master_sections`, `narrator_view`, `player_view`, `author`, `ready`,
   `advance`, `move`, `unlock_way`, `render_map`, `render_extension`, `render_job`,
   `render_return`, `map_so_far`, `write_extension`, `install_extension`, `build_scenario`,
   with `TunnelGoonsGame` → `G`, `TunnelGoonsWorld` → `RoomWorld[N, P]`, `draft.payload` →
   `self.world(draft)` where `def world(self, state: G) -> RoomWorld[N, P]: return state.payload`,
   `TunnelGoonsScenario(` → `self.scenario(`, `MapDraft` as an answer model or a schema →
   `self.map_draft()` where `def map_draft(self) -> type[MapDraft[N]]: return MapDraft[self.dweller]`.
   `validate` refuses `f"{self.title} has no table sets"` when `state.packs`, then `check_kind`.
   `player_of` as today. `apply_change` becomes
   `shared_change(self, world: RoomWorld[N, P], change: SharedChange) -> list[Fact]`.
3. `new_game` builds `self.world_type.begin(canon, player, self.starting_items(player, taken))`
   with `taken = (*canon.places, *canon.npcs, *canon.items)` and the hook
   `def starting_items(self, player: P, taken: Iterable[str]) -> tuple[Item, ...]: return ()`.
4. `opening_canon(self, draft: MapDraft[N], source: str, kind: ScenarioKind) -> RoomCanon[N]`:
   today's free function, returning `RoomCanon[self.dweller](...)`.
5. `@abstractmethod def guidance(self) -> str`. `render_map`, `render_extension` and
   `render_return` gain `("ENGINE GUIDANCE", self.guidance())` immediately before
   `("ANSWER WITH", ...)`; `render_job` passes through `render_extension` and needs nothing.
6. Full check. Nothing subclasses it yet; the step is the file.

### 5.4 Tunnel Goons as a room engine

1. `tunnelgoons/world.py` keeps `Ability`, `ABILITIES`, `Boost`, the four constants, `Goon`
   verbatim (`Item` imported from `rooms.world`), and
   ```python
   class Npc(Dweller):
       """Every non-player character, friend or foe: the SRD gives them one shape."""

       # SRD: an NPC's Difficulty Score is also its Health Points, so one counter serves both.
       hp: Counter

       def rows(self) -> Rows:
           return (("Health", f"{self.hp} (its Difficulty Score)"),)


   class TunnelGoonsWorld(RoomWorld[Npc, Goon]):
       def sheet_rows(self) -> Rows:
           carried = len(list(self.carried(self.player.id)))
           return tuple(
               (label, f"{carried}/{self.player.inventory}") if label == "Inventory" else (label, value)
               for label, value in self.player.rows()
           )
   ```
   `TunnelGoonsGame`, `TunnelGoonsScenario(Scenario[RoomCanon[Npc]])`, `TunnelGoonsCharacter`
   stay. Everything else in the file is gone.
2. `tunnelgoons/tools.py` keeps `LEVEL_OPTIONS`, `ActionRoll`, `LevelUp`, and
   `ChangeWorld` with `change: SharedChange = Field(discriminator="verb", description=...)`,
   the description verbatim. The five moved models and `WorldChange` are gone.
3. `tunnelgoons/worldsmith.py`: `AUTHORING = "TUNNEL GOONS AUTHORING\n" + ` the `hp` sentence
   dropped from the prompt in 5.2.4, verbatim.
4. `tunnelgoons/engine.py`: `class TunnelGoonsEngine(RoomEngine[Npc, Goon, TunnelGoonsGame])`
   with `dweller = Npc`, `world_type = TunnelGoonsWorld`; keeps `STARTING_ITEM_LIST`,
   `POINT_OPTIONS`, `master_tools`, `creation_steps`, `create_character`,
   `preview_character`, `action_roll`, `rest`, `level_up` verbatim; adds
   `starting_items(self, player: Goon, taken) -> tuple[Item, ...]: return player.starting_items(taken)`,
   `change_world(self, draft, args: ChangeWorld, _rng) -> list[Fact]: return self.shared_change(draft.payload, args.change)`
   and `guidance(self) -> str: return AUTHORING`. Every method 5.3 moved is deleted here.
   Delete `tunnelgoons/worldsmith.md`.
5. Imports follow the moves in `tests/tunnelgoons/*` and `tests/support/tunnelgoons.py`
   (`grep -rln "tunnelgoons.world\|tunnelgoons.worldsmith\|tunnelgoons.tools\|tunnelgoons.engine" tests`
   lists the eight files); every `MapDraft(` in a test becomes `MapDraft[Npc](`.
6. Full check, then `AIDM_GOLDEN_REGEN=1 uv run pytest` and `uv run pytest`: every golden
   byte-identical, or the step is wrong.

### 5.5 The proof, the record

1. `tests/core/test_rooms.py`: a sixth engine, as `tests/core/test_seam.py` builds its fifth —
   `SixthEngine(RoomEngine[Dweller, Person, SixthGame])` with no tools, a one-line `guidance`
   and a `create_character` that files a `Person`; a four-place `RoomCanon[Dweller]` scenario
   with one `Dweller` at the start. One test: `begin_game` returns a `SixthGame`, `master_sections`
   opens with `("CURRENT PLACE", ...)`, `player_view` lists the known way out, and `move`
   through it appends a visit. That test is what says the base is engine-free.
2. `CLAUDE.md`, the engine bullet: "the three scene engines subclass `SceneEngine` in
   `engines/scenes/engine.py`, Tunnel Goons subclasses `RoomEngine` in `engines/rooms/engine.py`;
   all four share the hub in `engines/hub.py`."
3. `docs/TUNNEL-GOONS.md`, under "The tools", one line: the three `change_world` arms are
   `engines/rooms/tools.py`'s, shared by every room engine, and count here as before.
4. `PROGRESS.md` entry.

### Done when

Green; every golden byte-identical; `scenarios/` and `characters/` untouched.
`ls src/aidm/engines/rooms` is `__init__.py drafts.py engine.py tools.py world.py worldsmith.md worldsmith.py`;
`ls src/aidm/engines/tunnelgoons` is `__init__.py engine.py rules.md tools.py world.py worldsmith.py`.
`grep -rn "tunnelgoons" src/aidm/engines/rooms` finds nothing;
`grep -rn "class .*Draft\|def .*_refusal\|def render_\|def install_extension\|def player_view\|def master_sections\|class Dungeon\|class Place\|class Way" src/aidm/engines/tunnelgoons`
finds nothing; `grep -rn "Any" src/aidm/engines/rooms` finds only the `Game[Any]` bound and the
two bars' `RoomWorld[N, Any]`. `uv run aidm`: a Tunnel Goons game opens and plays a turn; a
campaign takes a job. `src` 8,580 to 8,680; `engines/tunnelgoons/` under 450 lines; `engines/rooms/`
under 1,000.

