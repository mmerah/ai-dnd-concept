# PLAN — one spelling per thing

Three phases, in order: the fixes and the two boundary conventions; the engine seam and the two
families; the platform and the stored shapes, with the test consolidation. The twenty decisions of
`PROPOSALS.md` (2026-09-04, section 6, every heading settled) land here: D1, D6, D18, D19 and P1–P7,
P22, P23 in Phase 1; D2, D4 B, D7, D13, D16 (the seam half) and P3, P8–P16, P20 in Phase 2; D8, D9,
D14, D15, D17, D16 (the launcher half) and P17–P19, P21, P24, P25 in Phase 3. D3 C, D5 A, D10 A,
D11 A, D12 A, D20 need no step beyond what is named below. Self-standing: an implementer needs this
file, `CLAUDE.md` and the code.

Saves have no version field; a save from before a stored-shape change is stale and is skipped with
the launcher's warning. Phase 3 is the one stale-save commit: `SpokenLine` changes shape (D8) and
`Game.turn` goes (D9). D14 changes no stored shape: `SceneRecord` is not persisted, it is derived by
`SceneWorld.records()` and `RoomWorld.records()` from `SceneRun` and `Visit`, and `SceneRun.question`
keeps its name. Phases 1 and 2 leave every save readable (D2 reorders the dump's keys; a dict does
not care).

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
2. **Run the full check at the end of every step.** Change a shape and update its tests in the same
   step. One test per new behaviour; no test of prose or wiring.
3. **Golden files** live in `tests/core/fixtures/`. Rebuild them at the end of every step that
   changes a stored shape or a prompt:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest    # exits red by design; it wrote, it did not check
   uv run pytest
   ```
   Then read every changed line. Each phase names which fixtures may change and how; anything
   else is a bug. Phases 1 and 2 change none. Phase 3 changes the four `prompts/<id>/master.txt`
   by one heading line (D9). `scenarios/*/world.json` and `characters/kael/*.json` change in no
   phase.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one entry
   per phase. Phase 1 recreates the file:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs far past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** Never leave two versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **The standing limits hold.** Fifteen engine tools per engine, counted as tools plus
   `change_world` arms, the two party arms and `commission` not counted; 24XX is at fifteen and no
   step adds an arm to it. Every `engines/<id>/` stays under 2,000 lines (`engines/scenes/` and
   `engines/rooms/` too); imports flow `core <- engines <- turn <- app <- ui`; no `Any` beyond the
   `Game[P]` bound and the bounds D2 derives from it; every `__init__.py` empty; tests never start a
   process (`ScriptedSpawner`); `Refusal` stays the one message-bearing exception; both views stay;
   the `Engine` ABC and the generics stay; `RoomEngine` stays as it is (D3 C).
10. **A rename is a rename.** A step that deletes, moves or re-signs a name lists the grep the
    orchestrator runs (`grep -rn <name> src tests`, `--include=*.py`); after the step it finds only
    what the step says. The implementer does not explore.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`36be6f4`) | | 9,481 |
| 1 — the fixes and the conventions | the two content bugs; `PendingOption.name` required; `ValueError` inside every validator and `parse` at every construction from model data; `read_packs` through `decode`+`parse`; `draft.payload` in every concrete engine; the prompt facts; the idiom bundle; `config.py` on `Frozen`; `Turn._consume` | 9,430 to 9,460 |
| 2 — the seam and the two families | `World` in `hub.py`, `Engine[P, G]` with the five hoists, `Engine.begin` and `Engine.commit`; one entity line, one `reveal`, prompt lines on the worlds; sheet methods; shared refusals; `Pack.source`/`license`; `pack_step`/`srd_pack`; the party arms on the base; `taken` via `left_open`; rooms on one `worldsmith_prompt` and `Campaign.sections`, `apply_extension`/`apply_return`, the bar run once | 9,240 to 9,300 |
| 3 — the platform, the stored shapes, the tests | `Library`; `Engine.tool`, `restore(value)`, one `final_message`; `ask(spawner, role, …)`; `app/providers.py`, one opener shape, `_present`, `_run_master`; `withdraw` returns `None`; `game_path` in `ui`, `LauncherCatalog.read`/`target`; `Game.turn` gone; `Speaker` gone; `SceneRecord.focus`; one scene-world builder in `tests/support/scenes.py`, Loner's test files renamed | 9,200 to 9,270 |

---

## Phase 1 — the fixes and the two boundary conventions

Every no-loss fix, plus the two rules every later phase writes to: a validator raises
`ValueError`, and untrusted data reaches a model through `parse`. No fixture moves.

1. **P1.** `core/io.py`: `read_scenarios` (`:77`) and `read_characters` (`:91`) both open with
   `if not directory.is_dir(): return`; `read_characters` iterates
   `sorted(p for p in directory.iterdir() if p.is_dir())` and moves `name = content_id(path.name)`
   (`:92`) inside the `try`, so a non-slug folder is skipped with the same warning. Test,
   `tests/core/test_store.py`: a `.DS_Store` file and a `My Backup` folder under `characters/` are
   skipped and the slug beside them is read; a missing `scenarios/` yields nothing.
2. **P2.** `core/play.py:45-49`: `PendingOption.name: str = Field(min_length=1)`; the docstring
   becomes `"""The frozen tool call an engine plays this option by."""`. `tests/ui/test_game.py:17`
   names one (`name="pick"`); `tests/core/test_decisions.py:54` already does.
   Grep: `PendingOption(` in `tests` finds no call without `name=`.
3. **D1, P6a: validators raise `ValueError`.** Every `raise Refusal` inside a `@model_validator`
   body becomes `raise ValueError` with the message unchanged: `engines/base.py:97,99`;
   `engines/breathless/tools.py:51,78`; `engines/breathless/world.py:45`;
   `engines/breathless/worldsmith.py:34`; `engines/hub.py:95,158,162,165`;
   `engines/loner3e/worldsmith.py:41,44`; `engines/rooms/world.py:59,64,67,71,75,140,143,147,160,167`;
   `engines/scenes/world.py:71,74,76,96,100,104,106,108,110,114,116,118`;
   `engines/tunnelgoons/tools.py:58`; `engines/twentyfourxx/tools.py:23`;
   `engines/twentyfourxx/worldsmith.py:51`. Helpers a validator shares with a resolver
   (`require_unique`, `check_filing`, `check_named`, `Campaign.check_spans`, `Dungeon.require_place`)
   keep `Refusal`: their other callers read it unwrapped, and pydantic wraps either. Drop each
   `Refusal` import ruff now flags. `CLAUDE.md`, under "Code", after the `Refusal` bullet:
   "Inside a validator raise `ValueError`; `parse` turns it into the refusal." Every existing
   `pytest.raises(ValueError)` holds (`Refusal ⊂ ValueError`); the three `pytest.raises(Refusal)`
   on validator messages (`tests/tunnelgoons/test_world.py:17`, `tests/ui/test_launcher.py:280`,
   `tests/core/test_integrity_boundaries.py:112`) already go through `commit`, `compose` and
   `read_character`, and hold. Grep: `raise Refusal` inside `@model_validator` bodies finds none.
4. **P6b: constructions from model data go through `parse`.** `engines/scenes/world.py:122-132`
   `SceneWorld.begin` returns `parse(cls, {"cast": canon.cast, "player": player, "runs":
   [canon.opening], "source": canon.source, "campaign": canon.campaign, "arc": canon.arc})`;
   `engines/rooms/world.py:171-183` `RoomWorld.begin` the same shape with its own keys;
   `engines/registry.py:32-39` `begin_game` builds `parse(engine.game, {...})` (Phase 2 moves it
   onto the seam); `engines/scenes/engine.py:331-337` returns `parse(SceneCanon[self.cast],
   {...})`; `engines/rooms/engine.py:503-511` returns `parse(RoomCanon[self.dweller], {...})`.
   Why: `Engine.compose` re-prompts on a `Refusal` from `build` and lets anything else propagate
   as a bug, so an opening the world refuses must reach it as a `Refusal`. Tests: `tests/core/
   test_scenes.py`, `SceneWorld.begin` on a canon whose player id is in the cast raises `Refusal`
   matching "the player is in the cast"; `tests/tunnelgoons/test_world.py`, `RoomWorld.begin` on a
   canon whose npc stands in no place raises `Refusal` matching "in no place".
5. **D12, P22.** `engines/base.py:165-170`: `read_packs` returns `{path.stem: parse(model,
   decode(path.read_text(encoding=ENCODING))) …}`; import `decode` from `aidm.core.io`. Test,
   `tests/core/test_seam.py` beside `_installed`: a pack with a doubled key is refused at
   construction with a `Refusal` matching "duplicate keys".
6. **P7.** One way to the world in a concrete engine: `draft.payload` / `state.payload`. Breathless
   (`engines/breathless/engine.py:163,170,191,194,242,262,266,276`), 24XX
   (`engines/twentyfourxx/engine.py:206,216,255,258,306,339`), Loner
   (`engines/loner3e/engine.py:156,183,251`). Why Loner must: `self.world()` is typed
   `SceneWorld[C, P]` and hides `Loner3eWorld.twist`; one spelling per family, so the other two
   follow. Grep: `self.world(` in `src/aidm/engines/{loner3e,breathless,twentyfourxx,tunnelgoons}/`
   finds nothing; `SceneEngine.world` and `RoomEngine.world` stay for the bases.
7. **P4.** `engines/hub.py:71`: "`summary` and the recap fields are written from it for the game
   master, `debrief` for the player." `:64` comment: "Shared by the scene engines and the room
   engine." `:102` comment: "empty for a room engine". `engines/rooms/engine.py:62` `REPORT_ROW.detail`
   stays (it names the tavern to the player, who reads it as such in Tunnel Goons; a second crawler
   overrides the row). No golden holds these strings.
8. **P5a, model idioms.** `core/model.py:33-41`: `with_premise` returns
   `self.model_copy(update={"premise": self.premise or fallback})`. `app/media.py:129-135`:
   `_ImageUrl(Loose)`, `_Image(Loose)`. `app/runtime.py:48`: `@dataclass(slots=True)` on
   `GameService`. `app/spawn.py:157`: `"resumed" if session is not None else "cold"`.
   `ui/widgets.py:68`: `answer: Callable[[str], Awaitable[None]]`. `app/launch.py:21`:
   `CatalogEntry.kind: ScenarioKind | None = None` (characters carry none; `ui/app.py:93` compares
   to `"campaign"` unchanged).
9. **P5b, constants.** `core/views.py`: `WHOLE_SCENES = 2` after `SCENE_EXCHANGES`, used at
   `views.py:125,145` (`records[-WHOLE_SCENES:]`, `index >= total - WHOLE_SCENES`) and
   `engines/hub.py:231` (`attempt.returned <= total - WHOLE_SCENES`). `turn/context.py:11-14`
   `ANSWERED_BY_OPTION` moves to `turn/run.py` beside `RULES_WAIT`; `tests/core/test_context_boundary.py:9`
   imports it from `aidm.turn.run`. `engines/twentyfourxx/tools.py:78` `Attempt` → `Roll`
   (`engine.py:16,84,257` follow); the schema golden is unchanged (`schema_of` pops the model
   title). Grep: `\bAttempt\b` in `src/aidm/engines/twentyfourxx` and `tests/twentyfourxx` finds
   only `hub.Attempt` imports.
10. **P5c, the page.** `ui/game.py:409-418` `_observed` becomes
    ```python
    @dataclass(frozen=True, slots=True)
    class Observed:
        """Phase, facts landed, exchanges filed, the way on, the end: what a render reads."""

        phase: Role | None
        facts: int
        exchanges: int
        ready: bool
        over: str | None

        @classmethod
        def of(cls, session: GameService) -> Self: ...
    ```
    with `GamePage.seen: Observed = Observed(None, 0, 0, False, None)` and `poll_turn` comparing
    `now.phase != self.seen.phase`, `now != self.seen`. `ui/panels.py` folds into `ui/game.py`:
    `scene_sidebar`'s body becomes `GamePage.sidebar`'s, `journal_panel`'s becomes
    `GamePage.journal`'s; delete `ui/panels.py`. `_can_type` → `can_type` (public, `:421`);
    `tests/ui/test_game.py:4` drops the pyright ignore. Grep: `aidm.ui.panels`, `_observed`,
    `_can_type` find nothing.
11. **P5d, the small no-ops.** `engines/rooms/engine.py:137-142`: `here = tuple(entity for entity
    in world.here() if entity.known)` (`here()` yields the player first). `engines/breathless/
    engine.py:213-224`: `worn = stepped(die)` once after the roll, used at `:218,221,224,230`; the
    `args.item_id is not None` at `:219` stays, it narrows the key `del` needs.
12. **D18.** `config.py`: `ProviderConfig`, `RoleConfig`, `MediaConfig`, `SpeechConfig`, `Roles`,
    `Providers` subclass `Frozen` from `aidm.core.entities` and drop their `model_config` lines;
    `Settings` keeps `extra="ignore"`. Allowed: `tests/core/test_package_boundary.py::CONFINED`
    restricts who imports `aidm.config`, not what it imports, and `config.py` is outside the
    checked packages. Test, `tests/core/test_config.py`: `ROLES__NARATOR__MODEL=x` (monkeypatched)
    makes `read_settings()` raise a `ValidationError` naming `roles.narator`.
13. **D19, D10, the leans.** `app/runtime.py:102-103` `play` docstring gains one line: "A crossing
    of `None` means the world grows without a turn: `extend` runs instead." `CLAUDE.md`, under
    "Tests": "A golden is a drift detector, not a prose test." `core/entities.py:12-15`, one
    comment above `EngineId`: "`Slug` for content ids and places; `CheckedEntityId` for an id a
    model writes; `EntityId` for one the world has checked." `NEXT-SPECS.md:81`: "13 → 15" for
    Breathless. D6 A: `Fact.kind` stays; no edit.
14. **P23.** `turn/run.py:46-79`: `consume` → `_consume`; `:66` becomes `option = option_of(
    consumed.options, chosen)` from `aidm.core.creation`. `tests/core/test_decisions.py:217` goes
    through `Turn.begin(engine, _pending(state, closed), Answer(text=...), Random(0))`; the two
    `Turn(...)` constructions at `:177,184` stay (they need the pending kept open). Grep: `.consume(`
    finds nothing.

**Fixtures:** none change. Run the regen once at the end and confirm `git status` shows no
fixture.

**Done when:** green; `src` 9,430 to 9,460; the greps of 2, 3, 6, 9, 10, 14 as stated;
`ROLES__NARATOR__MODEL=x uv run python -c "from aidm.config import read_settings; read_settings()"`
exits non-zero naming `narator`; `uv run aidm` opens the home page with a stray folder under
`characters/`; `PROGRESS.md` created with the phase's entry.

---

## Phase 2 — the engine seam and the two families

One commit: what both lifecycle bases duplicate moves to the seam, and each thing the two families
spell twice gets one spelling.

### 2.1 The seam (D2 A, D16 seam half, P18's gate)

1. **`World`.** `engines/hub.py`, after `Campaign` (it names `Campaign`, and `hub.py` already
   imports `base.py`):
   ```python
   class World[P: Person](Mutable):
       """What both families' worlds share; the sequence of places is each family's own."""

       player: P
       source: str = ""
       campaign: Campaign | None = None

       @property
       @abstractmethod
       def at_hub(self) -> bool: ...
       @abstractmethod
       def records(self) -> tuple[SceneRecord, ...]: ...
       @abstractmethod
       def record(self, exchange: Exchange) -> None: ...

       def exchanges(self) -> tuple[Exchange, ...]:
           return tuple(exchange for record in self.records() for exchange in record.exchanges)

       def scenes(self) -> tuple[HistoryRecord, ...]:
           records = self.records()
           return records if self.campaign is None else self.campaign.history(records)
   ```
   `abstractmethod` works on a pydantic model (`ModelMetaclass` extends `ABCMeta`); no `ABC` mixin.
   `engines/scenes/world.py:80-89`: `class SceneWorld[C: Person, P: Person](World[P])` drops
   `source`, `campaign`, `player`; keeps `at_hub`; `record(exchange)` appends to
   `self.run.exchanges`; delete `exchanges()` and `scenes()` (`:151-152,165-167`).
   `engines/rooms/world.py:151-155`: `class RoomWorld[N: Dweller, P: Person](Dungeon[N], World[P])`
   drops the three fields; keeps `at_hub`; `record` appends to `self.visit.exchanges`; delete
   `exchanges()` and `scenes()` (`:406-407,423-425`). Both `records()` stay. Verified in pydantic
   2.13.4: generic multiple inheritance merges the fields (`player, source, campaign` first) and
   runs both validators.
2. **`Engine[P, G]`.** `engines/seam.py:40`: `class Engine[P: Person, G: Game[Any]](ABC)`;
   `type AnyEngine = Engine[Any, Any]` (the sheet type is the payload's, as invariant as the
   payload: the same bound, spelled twice). Add abstract
   `def world(self, state: G) -> World[P]: ...` — the one `Any` crossing, `state.payload`, stays in
   the two bases. Hoist as concrete, replacing the abstract lines `:156,162-168` and the bodies at
   `scenes/engine.py:112-132` and `rooms/engine.py:87-117`:
   ```python
   def player_of(self, character: AnyCharacter) -> P:
       self.check_character(character)
       return deepcopy(character.payload)

   def check_scenario(self, scenario: AnyScenario) -> None:
       if not isinstance(scenario, self.scenario):
           raise Refusal(f"{self.title} received an incompatible scenario")

   def over(self, state: G) -> str | None:
       return "You died." if not self.world(state).player.alive else None

   def record(self, state: G, exchange: Exchange) -> None:
       self.world(state).record(exchange)

   def history(self, state: G) -> tuple[Exchange, ...]:
       return self.world(state).exchanges()

   def scenes(self, state: G) -> tuple[HistoryRecord, ...]:
       return self.world(state).scenes()

   def reopening(self, state: G, intent: str) -> Job | None:
       """The left-open job the intent takes again; only at the hub."""
       world = self.world(state)
       campaign = world.campaign
       return campaign.taken(intent) if campaign is not None and world.at_hub else None
   ```
   `new_game` becomes abstract `-> World[P]`; `SceneEngine.new_game -> SceneWorld[C, P]` and
   `RoomEngine.new_game -> RoomWorld[N, P]` call `self.check_scenario(scenario)` first. `validate`
   stays abstract: scenes checks the packs then `check_kind`; rooms checks for no packs then
   `check_kind`. `scenes/engine.py:77`: `class SceneEngine[C: Person, P: Person, G: Game[Any],
   K: Pack](Engine[P, G])` with `def world(self, state: G) -> SceneWorld[C, P]: return
   state.payload` (the comment goes; P7 said it). `rooms/engine.py:65`: `class RoomEngine[N:
   Dweller, P: Person, G: Game[Any]](Engine[P, G])`. `scenes/engine.py:441` and
   `rooms/engine.py:225-227` read `self.reopening(draft, intent)`. Five abstract methods leave the
   seam (`player_of`, `over`, `record`, `history`, `scenes`); `world` arrives. Panels stay per
   family: the trail reads runs in one and visits in the other, and the Board panel sits in a
   different slot. Grep: `def player_of\|def over\|def record\|def history\|def scenes` in
   `src/aidm/engines` finds `seam.py` only; `\.taken(` in `src` finds `seam.py` and `hub.py` only.
3. **`Engine.commit` and `Engine.begin`.** `engines/seam.py`:
   ```python
   def commit(self, draft: G) -> G:
       """The one gate: the engine's own check, then the draft revalidated whole."""
       self.validate(draft)
       return draft.commit()

   def begin(self, scenario_id: Slug, scenario: AnyScenario, character: AnyCharacter) -> G:
       if scenario.engine != self.id:
           raise Refusal(
               f"{scenario_id!r} is authored for the {scenario.engine!r} rules, "
               f"which the {self.id!r} engine does not play"
           )
       if character.engine != self.id:
           raise Refusal(
               f"{character.id!r} is written for the {character.engine!r} rules, "
               f"which the {self.id!r} engine does not play"
           )
       state = parse(
           self.game,
           {
               "scenario_id": scenario_id,
               "character_id": character.id,
               "scenario": scenario.meta,
               "engine": self.id,
               "packs": scenario.packs,
               "payload": self.new_game(scenario, character),
           },
       )
       return self.commit(state)
   ```
   `close` ends `return self.commit(draft)`. `turn/run.py:139-140`: `self.draft =
   self.engine.commit(candidate)`. `app/runtime.py:225-226`: drop the `self.engine.validate(draft)`
   after `advance` (`close` commits through the gate); `:237` becomes `self.commit(self.engine.commit(draft))`.
   `engines/registry.py` keeps `build_engines` only. Callers of `begin_game` → `engine.begin(...)`:
   `app/runtime.py:22,293,373`; `tests/support/table.py:24,73`; `tests/core/test_seam.py:14,106`;
   `tests/core/test_rooms.py:10,106`; `tests/loner3e/test_create.py:12,35`;
   `tests/core/test_integrity_boundaries.py:7` (imports it from `support.table`). Grep: `begin_game`
   finds nothing; `\.validate(` in `src` finds `seam.py` and `runtime.py:306` only (Phase 3 drops the
   latter). Test, `tests/core/test_seam.py`: `engine.begin` with the fifth engine's scenario tagged
   for another engine raises `Refusal` matching "does not play".
4. **D4 B.** `ask_worldsmith` moves to the seam as concrete
   `def ask_worldsmith(self, draft: G, args: CommissionArgs, _rng: Random) -> list[Fact]` where
   `CommissionArgs` is a `Protocol` in `seam.py` with `kind: str`, `brief: str`, `later: bool`
   (read-only properties); `SceneCommission` and `RoomCommission` stay whole and are passed to
   `master_tool` by each family's `commission_tool` as today (`scenes/engine.py:210-221`,
   `rooms/engine.py:246-258`). Not done: a `CommissionArgs` base model — pydantic prints parent
   fields first, so `kind` would print last in the schema the master reads and the schema goldens
   would drift.

### 2.2 The cast and the worlds (P8, P9, P10, P13, D7 A)

5. **P8, one entity line.** `engines/base.py`, on `Thing`:
   ```python
   @property
   def tag(self) -> str:
       return f"{self.name}[{self.id}]"

   @property
   def headline(self) -> str:
       return self.tag + (f" — {self.brief}" if self.brief else "")

   def rows(self) -> Rows:
       return ()

   def line(self, *, rows: Rows | None = None, detail: str = "") -> str:
       """The master's entity line, then the sheet, then a detail; `rows` overrides the sheet."""
       parts = [f"- {self.headline}"]
       shown = self.rows() if rows is None else rows
       if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in shown):
           parts.append(f"  {sheet}")
       if detail:
           parts.append(f"  {detail}")
       return "\n".join(parts)
   ```
   `Person` keeps `rows()` off (inherits) and overrides `headline` to append `" (dead)"` when not
   `alive`; delete `Person.line` (`:72-81`). `label` stays (it prefixes the player). `engines/rooms/
   world.py:372-385`: `line(entity)` becomes `entity.line(rows=self.sheet_rows()) if entity.id ==
   self.player.id else entity.line()`. The six hand-written `name[id]` become `.tag`:
   `scenes/world.py:263,272,338`; `rooms/world.py:396` (`self.require_place(way.to).tag`);
   `rooms/engine.py:125` (`place.tag`), `:360` (`map_so_far`, moves in 7). Goldens unchanged: no
   shipped brief is empty (`grep -rn '"brief": ""' scenarios characters` finds none), and rooms
   already skipped ` — ` on the kit's empty briefs. Test, `tests/core/test_engines_base.py`: an
   `Item`-like `Thing` with an empty brief prints `- Name[id]` alone; a dead `Person` prints
   `(dead)` on the first line.
6. **P9, one `reveal`.** `engines/base.py:48-53`: `def reveal(self, *, card: str = "") ->
   list[Fact]` passes `card=card` to the fact. `scenes/world.py:215-221`: `reveal_hidden` returns
   `entity.reveal(card=sentence(f"{entity.name} discovered"))` after its own two refusals.
   `rooms/world.py:303-323`: keep the holder check and the "already {found}" refusal, then
   `return entity.reveal(card=f"{entity.name} {found}")`. Kinds and traces unchanged; the Loner
   turn golden's "The vault map discovered" card is the same string.
7. **P10, prompt lines on the world they read.** `scenes/engine.py:223-243` `here_lines`,
   `hidden_lines`, `cast_lines` → `SceneWorld.here_lines()`, `hidden_lines()`, `cast_lines()` (no
   parameters); `rooms/engine.py:348-363` `map_so_far` → `RoomWorld.map_so_far()`. Callers in
   `scenes/engine.py:143,145,284` and `rooms/engine.py:286,333` follow. Grep: `here_lines\|hidden_lines\|cast_lines\|map_so_far`
   in `src` finds `world.py` definitions and `engine.py` calls only.
8. **P13, shared refusals.** `engines/base.py`, after `CHANGE_WORLD`: `UNKNOWN_ID = "unknown id
   {entity_id!r}. Use only ids you were shown."` and `IS_DEAD = "{name} is dead; they take no
   further part."`, used with `.format(...)` at `scenes/world.py:184,200` and
   `rooms/world.py:84,224,226`. `scenes/world.py:187-208`: `require_here(self, entity_id: EntityId,
   *, alive: bool = False) -> C | P` replaces both methods: `entity = self.require(entity_id)`; when
   `alive` and not `entity.alive`, refuse `IS_DEAD`; the player returns at once; otherwise refuse
   `f"{entity.name} is not here with the player. Bring them here first, or act on who is here."`
   when not in `run.here` or unknown. Callers of `require_alive_here` (`scenes/world.py:258`;
   `loner3e/engine.py:193,195,206,210,251`; `tests/twentyfourxx/test_world.py:86-90`) pass
   `alive=True`. `tests/loner3e/test_loner3e_engine.py:81,202` match "is not here with the player"
   and hold. Grep: `require_alive_here` finds nothing; `Use only ids you were shown` in `src` finds
   `base.py` only.

### 2.3 The sheets and the packs (P12, P14, P15, P16, C13)

9. **P12, 24XX.** `engines/twentyfourxx/world.py`, on `Item`: `def detail(self) -> str` (today's
   `gear_detail`, `engine.py:432-440`). On `Operator`: `require_item(item_id: EntityId) -> Item`
   (refuses `f"{item_id!r} is not among the player's items"`), `pay(cost: int) -> None` (refuses
   `f"the player has only ₡{self.credits}, not ₡{cost}"`), `change_hindrances(gained:
   Sequence[str], lost: Sequence[str]) -> list[Fact]` (`require_unique("gained hindrances",
   gained)`; refuse the first gained already carried and the first lost not carried with today's
   two messages; then mutate), `gain_item(name: str, *, bulky: bool, breaks: int, cost: int) ->
   list[Fact]`, `drop_item(item_id: EntityId) -> list[Fact]`, `repair_item(item_id: EntityId, cost:
   int) -> list[Fact]`, `spend(amount: int, why: str) -> list[Fact]`; each body is today's
   `engine.py:353-418` with `pay`/`require_item` inside. `apply_change` arms become one-liners
   (`case GainItem(): return player.gain_item(change.name, bulky=change.bulky, breaks=change.breaks,
   cost=change.cost)`); `defend` uses `require_item`. Messages verbatim. `tests/twentyfourxx/
   test_views.py:5-25` call `Item(...).detail()`.
10. **P12, Breathless.** `engines/breathless/world.py`, on `Survivor`: `require_item(item_id) ->
    Item` (same message), `drop_item(item_id) -> list[Fact]`, `loot_options(item: str, granted:
    Die) -> tuple[PendingOption, ...]` and `take_loot(item: str, granted: Die, choice: str) -> Fact`
    (today's `tools.py:97-145`, with `SWAP` beside them). `BreathlessEngine.roll_loot(draft, item,
    rng)` takes `tools.py:148-183`. `tools.py` keeps the arg models and `outcome`. `check` reads
    `item = player.require_item(args.item_id)`.
11. **P12, Loner.** `engines/loner3e/world.py`, on `Loner3eSheet`: `change_tags(kind: TagKind,
    gained: Sequence[str], lost: Sequence[str]) -> list[Fact]`, `drive(*, goal: str, motive: str,
    nemesis: str) -> list[Fact]` (today's `engine.py:257-295`), `refill(why: str) -> list[Fact]`
    (today's `_refill`). On `Loner3eWorld`: `conflict_prompt(actor, opponent) -> str` (today's
    `tools.py:103-108`). `tests/loner3e/test_loner3e_engine.py:15,192` call
    `draft.payload.conflict_prompt(...)`. Grep: `gear_detail\|_refill\|conflict_prompt(world`
    finds nothing.
12. **P14, D11.** `engines/base.py:84-87` `Pack` gains `source: str` and `license: str` (required);
    delete the pairs at `loner3e/worldsmith.py:29-30`, `breathless/worldsmith.py:21-22`,
    `twentyfourxx/worldsmith.py:39-40`. `tests/core/test_seam.py:78` writes
    `{"name": "The SRD", "source": "the test", "license": "CC0"}`.
13. **P15, C13.** `engines/scenes/engine.py`: `def pack_step(self) -> CreationStep: return
    CreationStep(id="pack", prompt="Choose a table set", options=self.pack_options())` and
    `def srd_pack(self) -> K` (refuses `"the SRD table set is not installed"`); the three
    `first = CreationStep(...)` blocks (`loner3e/engine.py:92-94`, `breathless/engine.py:110`,
    `twentyfourxx/engine.py:110`) call it; `twist_table` (`loner3e/engine.py:173-178`) reads
    `srd = self.srd_pack()` then refuses `"the SRD table set has no twist columns"` when either
    column is `None`; `complications` (`breathless/engine.py:176-181`) returns
    `self.srd_pack().complications`. `BOARD_GUIDANCE` (`twentyfourxx/engine.py:46-49`) moves to
    `twentyfourxx/worldsmith.py`; `STARTING_DICE` (`breathless/engine.py:45`) to `breathless/world.py`.
    Grep: `character table set\|SRD_PACK` in `src/aidm/engines/{loner3e,breathless,twentyfourxx}`
    finds nothing.
14. **P16, the party arms on the base.** `engines/scenes/tools.py:68`: `type SharedChange = Reveal
    | Enter | Leave | Kill | JoinParty | LeaveParty`; `scenes/engine.py:195-205` `shared_change`
    gains `case JoinParty(): return world.join_party(change.entity_id)` and `case LeaveParty():
    return world.leave_party(change.entity_id)`. Each engine's `apply_change` ends `case _: return
    self.shared_change(world, change)` and drops its shared arms: `loner3e/engine.py:188-199` keeps
    `ChangeTags` and `Drive` only; `breathless/engine.py:183-188` keeps `DropItem`;
    `twentyfourxx/engine.py:239-252` keeps its five. Pyright narrows the remainder to a subset of
    `SharedChange`. The three `WorldChange` unions are unchanged, so the schema goldens do not
    move. Test, `tests/breathless/test_tools.py`: a `join_party` verb is refused by the schema
    (not in Breathless's union), as today.

### 2.4 The hub and the rooms (P11, P3, P20, D13)

15. **P20.** `engines/hub.py:255-263`: `taken` splits `TAKE_JOB` on `{title}` into `prefix,
    suffix`; when `intent.casefold()` starts with `prefix.casefold()` and ends with
    `suffix.casefold()`, returns `self.left_open(intent[len(prefix) : len(intent) - len(suffix)])`,
    else `None`. `tests/core/test_hub.py:375-380` holds.
16. **P11b, `Campaign` renders the hub block for both families.** `engines/hub.py:318-332`:
    `def sections(self, hub_title: str, brief: str, *, returning: bool) -> Sections` takes the
    brief instead of choosing it; add
    ```python
    def this_job(self, records: Sequence[SceneRecord]) -> Sections:
        return (("THIS JOB", render_whole(self.job_records(records))),)

    def job_before(self, job: Job | None, records: Sequence[SceneRecord]) -> Sections:
        if job is None:
            return ()
        return (("THE JOB BEFORE", render_whole(self.records_of(job, records))),)

    def board_panel(self, *, at_hub: bool, reporting: PanelRow | None = None) -> tuple[Panel, ...]:
        """`reporting` is the one row a walked job leaves on the board."""
        if not at_hub:
            return ()
        rows = self.board_rows() if reporting is None else (reporting,)
        return (Panel(title="Board", rows=rows),)
    ```
    `scenes/engine.py:245-261` `hub_sections` computes `brief = WRITE_HUB_SCENE + RETURN_BRIEF if
    returning else TAKE_BRIEF if world.at_hub else AWAY_BRIEF` and returns
    `(*(campaign.this_job(records) if returning else ()), *campaign.job_before(reopening, records),
    *campaign.sections(world.runs[0].title, brief, returning=returning))`.
    `tests/core/test_hub.py:144-164` pass the brief. `rooms/engine.py:184-195` becomes
    `*(() if campaign is None else campaign.board_panel(at_hub=world.at_hub,
    reporting=REPORT_ROW if world.walked_job() is not None else None))`.
17. **P11a, D13, one rooms prompt assembler.** `engines/rooms/worldsmith.py`: `NO_SOURCE = "(none
    — write from the setting)"`, `MAP_ASK = "Write the opening map."`, `TAVERN_ASK` loses its
    surrounding parentheses and "(no map yet — " prefix, and
    ```python
    def worldsmith_prompt(
        role: str,
        *,
        source: str,
        map_so_far: str,
        history: str,
        player: str,
        intent: str,
        guidance: str,
        answer: type[BaseModel],
        hub: Sections = (),
        asked: str = "",
    ) -> str:
        return sections(
            (
                ("YOUR ROLE", role),
                ("SOURCE MATERIAL", source or NO_SOURCE),
                ("MAP SO FAR", map_so_far),
                ("SCENES SO FAR", history),
                *hub,
                ("THE PLAYER", player),
                *((("THE GAME MASTER ASKED FOR", asked),) if asked else ()),
                ("WHAT COMES NEXT", intent),
                ("ENGINE GUIDANCE", guidance),
                ("ANSWER WITH", schema_text(answer)),
            )
        )
    ```
    `rooms/engine.py`: `render_map(source, kind)` calls it with `map_so_far="(no map yet)"`,
    `history="(no scenes yet — write the opening)"`, `player="(no player yet — the map is authored
    before anyone stands in it)"`, `intent=TAVERN_ASK if kind == "campaign" else MAP_ASK`;
    `render_extension(world, intent, hub=(), *, answer=None, asked="")` calls it with
    `world.source`, `world.map_so_far()`, `render_history(world.scenes())`, `world.line(world.player)`,
    `self.guidance()`, `answer or self.map_draft()`; add `hub_sections(self, world, *, returning:
    bool, reopening: Job | None) -> Sections` returning `()` off the hub or without a campaign,
    else `(*(campaign.this_job(records) if returning else ()), *campaign.job_before(reopening,
    records), *campaign.sections(world.current.name, RETURN_BRIEF if returning else JOB_BRIEF,
    returning=returning))`; delete `render_job` and `render_return` (`:307-346`). `write_extension`
    computes `returning = campaign is not None and world.at_hub and intent == REPORT_IN`, keeps
    its two refusals verbatim, builds `hub = self.hub_sections(world, returning=returning,
    reopening=reopening)`, and asks `ReturnDraft` through `render_extension(world, intent, hub,
    answer=ReturnDraft)` with `return_refusal`, else `self.map_draft()` through
    `render_extension(world, intent, hub, asked=asked)` with `job_refusal` at the hub and
    `extension_refusal` away. `JOB_BRIEF` (`worldsmith.py:21`) says "WHAT COMES NEXT is the job they
    take". Accepted (D13): the return prompt gains ENGINE GUIDANCE and THE HUB, and its intent is
    the player's `Report in.`. Grep: `WHAT THE PLAYER WANTS TO PURSUE\|render_job\|render_return`
    finds nothing. `tests/tunnelgoons/test_worldsmith.py:242-258,445-456,459-480` assert headings
    (`AUTHORING`, `SCENES SO FAR`, `THE JOB BEFORE`) and hold; add one test there: the return
    prompt carries `THIS JOB`, `THE VERDICT` and `ENGINE GUIDANCE`, and `WHAT COMES NEXT` reads
    `Report in.`.
18. **P11c, P3: the map side of the install moves to the world; the bar runs once.**
    `engines/rooms/world.py`, after `attach`:
    ```python
    def apply_extension(
        self, region: Dungeon[N], start: EntityId, *, reopening: Job | None = None
    ) -> Place:
        """At the hub the region is the job's, known, joined at its anchor; away it is hidden.
        Returns the anchor place."""

    def apply_return(
        self, *, debrief: str, summary: str, recaps: Mapping[EntityId, str], offers: Board
    ) -> Job:
        """Close the walked job, land each recap on that place's last visit, swap the board."""
    ```
    (`Dungeon[N]` and keyword fields, not the drafts: `rooms/drafts.py` imports `rooms/world.py`.)
    `apply_extension` at the hub with a campaign: `campaign.swap_out()` when the open job is
    unwalked; with `reopening`, `anchor = self.require_place(EntityId(reopening.place))`,
    `campaign.reopen(reopening, started=None)`, `attach(region, start, known=True, anchor=anchor.id)`;
    else `anchor = self.current`, `attach(known=True)`, `campaign.jobs.append(Job(title=self.places
    [start].name, place=start, attempts=[Attempt()]))` — the start place is read after `attach`.
    Away: `attach(known=False)`, `anchor = self.current`. `apply_return`: `job = self.walked_job()`
    or refuse `"no job is open to report"`; `job.close(returned=len(self.visits) - 1, ...)`; recaps
    on the last visit of each place in `visits[job.start() : -1]`; `campaign.board = offers`.
    `rooms/engine.py:393-439` `install_extension` becomes: a `ReturnDraft` → `[world.apply_return(
    debrief=..., summary=..., recaps=..., offers=...).closed()]`; a `MapDraft` → `anchor =
    world.apply_extension(extension, extension.start, reopening=reopening)`,
    `draft.commissions.clear()`, `start = world.require_place(extension.start)`, then the `job_taken`
    fact (told; trace `f"a way opens from {anchor.name} to {start.name}"`, card `f"A way opens:
    {start.name}"`) at the hub or the untold `region_added` (`f"a hidden region opens beyond
    {anchor.name}"`) away. The re-run bars at `:413-414,433-434` go: `write_extension` ran them,
    and `attach`'s docstring already says every caller refuses first. The eight direct
    `install_extension` calls in `tests/tunnelgoons/test_worldsmith.py` pass drafts that meet the
    bar and hold; retarget none. Tests, `tests/tunnelgoons/test_world.py`: `apply_extension`
    reopens at the job's own start and returns that place; `apply_return` refuses with no job
    walked.

**Fixtures:** none change. Run the regen once at the end and confirm `git status` shows no
fixture; if a `master.txt` moves, step 5 printed a brief that was empty before, which is a bug.

**Done when:** green; `src` 9,240 to 9,300; `engines/scenes/` and `engines/rooms/` under 1,300
each; the greps of 2, 3, 7, 8, 11, 13, 17 as stated; `grep -rn "Any" src/aidm/engines` finds the
`Game[Any]` bounds and `AnyEngine` only; `uv run aidm`, Tunnel Goons campaign: take a job, walk
into it, report in, take it again; the worldsmith prompts in the log carry `WHAT COMES NEXT`;
`PROGRESS.md` entry.

---

## Phase 3 — the platform, the stored shapes, the tests

One commit; a save from before it is stale (D8, D9). Say so once, in the commit message.

### 3.1 The content library and the gates (D15 B, P18, P19, C10)

1. **`Library`.** `core/io.py`, after `FileStore`:
   ```python
   @dataclass(frozen=True, slots=True)
   class Library:
       """The two content directories; `FileStore` is the third, the saves."""

       scenarios: Path
       characters: Path

       def scenario_folder(self, name: Slug) -> Path: ...   # scenarios / content_id(name)
       def character_folder(self, name: Slug) -> Path: ...
       def scenario_ids(self) -> tuple[str, ...]: ...        # today's Runtime._scenario_ids
       def read_scenarios(self, models: Mapping[EngineId, type[AnyScenario]]) -> Iterator[tuple[Slug, AnyScenario]]: ...
       def read_characters(self, engines: Collection[EngineId]) -> Iterator[tuple[Slug, EngineId, CharacterHeader]]: ...
       def read_scenario(self, name: Slug, models: Mapping[EngineId, type[AnyScenario]]) -> AnyScenario: ...
       def read_character(self, name: Slug, engine: EngineId, model: type[AnyCharacter]) -> AnyCharacter: ...
       def write_character(self, character: AnyCharacter) -> None: ...
       def write_scenario(self, name: Slug, scenario: AnyScenario, source: Path | None = None) -> None: ...
   ```
   The bodies are today's free functions (`:74-151`) with `self.scenarios`/`self.characters` for
   the `directory` argument; delete the free functions. `app/runtime.py:320-321`
   `Runtime.__post_init__` builds `self.library = Library(self.settings.scenarios_dir,
   self.settings.characters_dir)` and `self.store = FileStore(self.settings.saves_dir)` (fields
   `init=False`); `reload_settings` rebuilds both; `new_scenario`, `_scenario_ids` (deleted),
   `_open` read them; `_open` passes `self.store`. `app/media.py:175-193`: `open_illustrator(settings:
   Settings, store: FileStore, slug: str, *, style: str, icon_dirs: tuple[Path, ...])`; `Runtime._open`
   passes `icon_dirs=(self.library.scenario_folder(target.scenario_id) / ICON_DIR,
   self.library.character_folder(target.character_id) / ICON_DIR)`; `media.py` drops its
   `aidm.app.launch` import. `tests/support/table.py`: `LIBRARY = Library(SCENARIOS, CHARACTERS)`
   and every `read_*` through it; `tests/support/loner.py:8,67,75`; `tests/loner3e/test_create.py`;
   `tests/twentyfourxx/test_engine.py:14,106-121`; `tests/core/test_integrity_boundaries.py`;
   `tests/core/test_store.py` (`Library(tmp_path, tmp_path)`); `tests/core/test_media.py:129-155`.
   Grep: `read_scenario\|read_character\|read_scenarios\|read_characters\|write_scenario\|write_character`
   finds `core/io.py` definitions and `library.`/`LIBRARY.` calls only; `scenarios_dir\|characters_dir`
   in `src` finds `config.py` and `runtime.py:__post_init__` only.
2. **P18, one gate each.** `engines/seam.py`: `def tool(self, name: str) -> MasterTool[G]` raises
   `Refusal(f"{name!r} is not a tool of the {self.id!r} engine.")`; `turn/run.py:95-97` calls it;
   `answer` (`:85-91`) wraps: `try: found = self.tool(chosen.name) except Refusal as missing:
   raise Refusal(f"the {self.id!r} engine has no tool {chosen.name!r} to play option {chosen.id!r}")
   from missing` (`tests/core/test_decisions.py:204` matches it). `restore(self, value: JsonValue)
   -> G` takes the decoded value: `app/launch.py:101-109` decodes once (`value = decode(raw)`, the
   header, `engine.restore(value)`); `app/runtime.py:73` passes `decode(saved)`; `_resumable`
   (`:295-307`) drops `self.engine.validate(state)`. Callers: `tests/support/table.py:192`;
   `tests/core/test_store.py:50`; `tests/core/test_decisions.py:202`;
   `tests/core/test_integrity_boundaries.py:31,138,145`; `tests/{twentyfourxx,breathless,tunnelgoons}/
   test_engine.py`, `tests/loner3e/test_loner3e_engine.py:222` — each wraps its JSON in `decode(...)`.
   `app/spawn.py:84-91`: `ClaudeDriver.parse` returns `RunResult(final_message(result.result),
   result.session_id)`; `ask` (`:202`) validates `parse(model, decode(spoken.text))` and catches
   `Refusal` where it caught `ValidationError` (the re-prompt text is the first error, as every
   other boundary reports it). Grep: `final_message` in `src` finds `spawn.py` drivers only;
   `model_validate_json` in `src` finds `spawn.py:86` (`_ClaudeResult`) and `media.py:119` only.
3. **P19, C10.** `app/spawn.py:189-195`: `async def ask[T: BaseModel](spawner: Spawner, role: Role,
   prompt: str, model: type[T], refusal: Check[T]) -> T` spawning through `spawner.run(role, asked,
   session)`; `type Check[T] = Callable[[T], str | None]` moves to `core/model.py` beside
   `WorldsmithAnswer`, whose `refusal` parameter is annotated `Check[M]`. `app/runtime.py:422-424`:
   `return partial(ask, spawner, "worldsmith")`; `:201-212` `ask(self.spawner, "narrator", …)`.
   `tests/core/test_spawn.py:86-98` passes a `ScriptedSpawner`-shaped object whose `run` records
   `(prompt, session)`. Grep: `spawn=` finds nothing.

### 3.2 Presentation and the launcher (P17, D17, P24, P25, D16 launcher half)

4. **P17.** New `app/providers.py` holds `claim` and `post_bearer` (`media.py:153-172`);
   `media.py` and `speech.py` import them from there (`speech.py:8` no longer names `media`).
   `app/speech.py:74-85`: `open_reader(settings: Settings, store: FileStore, slug: str, *, voice:
   str)`; `Runtime._open` passes `voice=scenario.meta.voice or settings.speech.voice`.
   `tests/core/test_speech.py:84-91,122` patch `aidm.app.providers.post_bearer` through
   `aidm.app.speech`'s import (patch `aidm.app.speech.post_bearer` as today); `:129-158` pass `voice=`.
   `ui/game.py:156`: `clip := session.newest_clip()`. Grep: `reader.clip` in `src/aidm/ui` finds
   nothing.
5. **D17.** `app/runtime.py`: `async def _run_master(self, turn: Turn) -> None` holds `:114-121`
   (the first `_act` and the commission loop); `def _present(self) -> None` holds
   `self.illustrate(_latest_narration(self.engine, self.state)); self.speak()` and replaces the
   three pairs at `:97-98,130-131,135-136` (every caller has just committed, so the state is
   `self.state`). `play` reads: gate, `_run_master`, narrate, finish, commit, present, grow, present.
6. **P24.** `core/model.py:122-125`: `def withdraw(self, asked: Commission) -> None`. `app/runtime.py:149`
   applies a local `Play`:
   ```python
   def _withdrawing(asked: Commission) -> Play[AnyGame]:
       def withdraw(draft: AnyGame, _rng: Random) -> tuple[Fact, ...]:
           draft.withdraw(asked)
           return ()

       return withdraw
   ```
   The two engine callers (`scenes/engine.py:407`, `rooms/engine.py:479`) already discard the return.
7. **P25, D16 launcher half, the catalog.** `app/launch.py:33-35` `path` goes; `ui/widgets.py`
   gains `GAME_ROUTE = "/game/{scenario}/{character}"` and `def game_path(target: LaunchTarget)
   -> str: return f"/game/{target.scenario_id}/{target.character_id}"` (`ui/app.py` imports
   `ui/create.py`, so the route cannot live beside the page and be reached from the create page);
   `ui/app.py:183` decorates with `GAME_ROUTE`; `:162` and `ui/create.py:244` navigate to
   `game_path(target)`. `launch_target` (`:65-69`) becomes `LauncherCatalog.target(self,
   scenario_id: Slug, character_id: Slug) -> LaunchTarget` (message verbatim); `read_catalog`
   (`:72-134`) becomes `@classmethod def read(cls, library: Library, store: FileStore, engines:
   Mapping[EngineId, AnyEngine]) -> Self` on `LauncherCatalog` — a method on its owner, since
   `core` cannot hold a class from `app`. `ui/app.py:29`, `ui/create.py:252`:
   `LauncherCatalog.read(runtime.library, runtime.store, runtime.engines)`. `tests/ui/test_launcher.py`
   (every `read_catalog`/`launch_target`) follows; `support/ui.py::ui_settings` stays, tests build
   `Library`/`FileStore` from it. Grep: `launch_target\|read_catalog\|\.path\b` in `src tests`
   finds nothing (`Path` is not `.path`).

### 3.3 The stored shapes (D9 B, D8 B, D14 A)

8. **D9.** `core/model.py:100`: delete `turn`. `engines/seam.py:139`: delete `draft.turn += 1`.
   `turn/context.py:19-40`: `render_master(instructions, engine_sections, state, scenes, action,
   *, played: int, notes=())` prints `f"RECENT PLAY (this is turn {played + 1})"`; `turn/run.py:82-89`
   passes `played=len(self.engine.history(self.draft))`. `app/launch.py:128`:
   `turn=len(engine.history(state))` (`SaveOption.turn` stays, derived; `ui/app.py:146` unchanged).
   Tests: `tests/core/test_context_boundary.py::_master_prompt` passes `played=`;
   `tests/ui/test_launcher.py:258` asserts `len(engine.history(state)) == 0`; `:190` keeps its
   `{"turn": -1}` (an unknown key is as stale as a wrong one); `tests/tunnelgoons/test_play.py:88,93`,
   `tests/core/test_master_tools.py:206,253,260`, `tests/core/test_turn.py:62,201`,
   `tests/core/test_game_service.py:92,105` count `engine.history(state)`;
   `tests/core/test_game_service.py:29-34` round-trips `notes=["kept"]` instead of `turn=7` and
   asserts `restart` leaves `notes == []`; `tests/core/test_integrity_boundaries.py:29` doubles
   `"notes"` (`'{"notes": [], "scenario_id"'`). Grep: `state\.turn\|\.turn ==\|"turn"\|turn=state`
   in `src tests` finds `launch.py:128`'s `turn=len(...)` and `test_launcher.py:190` only.
9. **D8.** `core/play.py:18-27`: delete `Speaker`;
   ```python
   class SpokenLine(Frozen):
       """A line as recorded: the speaker's id and name ride on it, so chat, journal and speech
       never resolve an id through state."""

       speaker_id: CheckedEntityId | None = None
       speaker: str = ""  # the name as it was when spoken; empty for narration
       text: str = Field(min_length=1)

       @model_validator(mode="after")
       def _named_when_spoken(self) -> Self:
           if (self.speaker_id is None) != (not self.speaker):
               raise ValueError("a spoken line names its speaker; narration names nobody")
           return self
   ```
   `core/views.py`: delete `Subject.speaker()` (`:28-29`); `NarratorView.speakers:
   tuple[CheckedEntityId, ...]` with
   ```python
   @model_validator(mode="after")
   def _speakers_are_subjects(self) -> Self:
       here = {subject.id for subject in self.subjects}
       if strangers := sorted(set(self.speakers) - here):
           raise ValueError(f"speakers who are not subjects: {strangers}")
       return self
   ```
   `spoken()` resolves `here = {subject.id: subject for subject in self.subjects if subject.id in
   self.speakers}` and builds `SpokenLine(speaker_id=who.id, speaker=who.name, text=line.text)`;
   `speakers_refusal` reads `set(self.speakers)`. `scenes/engine.py:169`: `speakers=tuple(member.id
   for member in here)`; `rooms/engine.py:150`: `tuple(entity.id for entity in here if entity.alive)`.
   `app/speech.py:88-99`: `voice_of(speaker_id: EntityId | None, narrator, pool)`;
   `requests_of` passes `line.speaker_id`. `ui/game.py:383-390`: `_bubble(session, speaker_id:
   EntityId | None, name: str, text: str, *, sent: bool)`; the player's bubbles (`:142,166,171`)
   pass `player.id, player.name` from `session.player_view().player`; lines pass
   `line.speaker_id, line.speaker`; the journal prints `f"**{line.speaker}:** {line.text}"` when
   `speaker_id` is set. `tests/support/table.py:47` `KAEL` and `tests/core/test_speech.py:27,35,62`
   build `SpokenLine(speaker_id=..., speaker="Kael", ...)` and pass ids to `voice_of`;
   `tests/core/test_views.py:42` and `tests/tunnelgoons/test_views.py:24` test `id in view.speakers`.
   `tests/core/test_context_boundary.py:200-207` holds: the field set is unchanged. Tests,
   `tests/core/test_views.py`: a `NarratorView` naming a speaker who is not a subject is refused;
   `spoken()` on a line whose speaker is a subject but not a speaker refuses "nobody here has id".
   Grep: `Speaker\b\|\.speaker()` finds nothing.
10. **D14.** `core/play.py:105`: `SceneRecord.focus: str`; `core/views.py:155` prints
    `scene.focus`; `scenes/world.py:158` fills it from `run.question`, `rooms/world.py:416` from
    `place.brief`. `tests/core/test_views.py` (14 constructions), `tests/core/test_hub.py` (1),
    `tests/core/test_context_boundary.py:102` pass `focus=`. Grep: `question=` in `tests/core`
    finds `SceneRun(` constructions only.

### 3.4 The tests (P21)

11. **One scene-world builder.** New `tests/support/scenes.py`:
    ```python
    @dataclass(frozen=True, slots=True)
    class HubNames:
        """What one engine's hub world is called: the hub run, the job run, the job's terms."""

        hub_place: str
        hub_title: str
        hub_question: str
        hub_situation: str
        job_place: str
        job_title: str
        job_question: str
        job_situation: str
        terms: str


    BOARD = (Offer(title="Job One", pitch="I take job one."), Offer(title="Job Two", pitch="I take job two."))


    def hub_scene(names: HubNames, *, here: Sequence[EntityId] = ()) -> SceneRun: ...
    def job_scene(names: HubNames, *, here: Sequence[EntityId] = ()) -> SceneRun: ...
    def hub_runs(names: HubNames, *, keeper: EntityId) -> list[SceneRun]: ...   # [hub_scene(here=[keeper]), job_scene()]
    def hub_campaign(names: HubNames) -> Campaign: ...   # BOARD; one job, terms, attempts=[Attempt(started=1)]
    ```
    `tests/support/{loner,breathless,twentyfourxx}.py` each keep a `NAMES = HubNames(...)` from
    their constants, delete `_hub_scene`/`_job_scene`, and `hub_world()` becomes the six lines:
    the keeper, `<World>(cast=..., player=_player(), runs=hub_runs(NAMES, keeper=KEEPER),
    campaign=hub_campaign(NAMES))`, the `<Game>(...)`. Grep: `_hub_scene\|_job_scene` in `tests`
    finds nothing.
12. **Loner's test package.** `git mv tests/loner3e/test_loner3e_engine.py tests/loner3e/test_engine.py`;
    `test_loner3e_events.py` → `test_tools.py`; `test_hub_play.py` → `test_worldsmith.py`;
    `test_packs.py` (one test) folds into `test_engine.py`; `test_counters.py` moves to
    `tests/core/test_engines_base.py` (`Counter` is `base.py`'s). Grep: `loner3e_\|hub_play` in
    `tests` finds nothing.
13. **Narrowing and the class attribute.** Every `raise AssertionError` that follows an
    `isinstance` test becomes `assert isinstance(x, T), "<the same message>"`:
    `tests/core/test_seam.py:108`, `tests/core/test_rooms.py:108`, `tests/core/test_decisions.py:230`,
    `tests/support/table.py:186,194`, `tests/support/loner.py:69,77,84`, `tests/ui/test_launcher.py:38`,
    the four `golden_turn.py`, `tests/{twentyfourxx,breathless,tunnelgoons}/test_engine.py`,
    `tests/tunnelgoons/test_worldsmith.py:45,488`, `tests/loner3e/test_create.py`. `tests/support/golden.py:20,23`
    and `tests/tunnelgoons/test_worldsmith.py:212,236` stay (they are checks, not narrowing).
    `tests/core/test_seam.py:79` and `tests/core/test_rooms.py:77`
    stop setting `directory` on the shared class: `_installed` declares `class Installed(FifthEngine):
    directory = tmp_path` inside the function and returns `Installed()`. Grep: `raise AssertionError`
    in `tests` finds `support/golden.py` and the two "no answer should be asked for" only.

**Fixtures:** the four `prompts/<id>/master.txt` change in one line, `RECENT PLAY (this is turn 1)`
→ `(this is turn 3)` (the golden state carries two hand-built exchanges that `Game.turn` never
counted). `narrator.txt`, `schemas/*`, `turn/*` are byte-identical.

**Done when:** green; `src` 9,200 to 9,270; tests about 130 lines fewer than at the end of Phase 2;
the greps of 1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13 as stated; `grep -rn "Any" src/aidm` finds the
`Game[Any]` bounds, `AnyEngine`, `AnyScenario`, `AnyCharacter`, `AnyGame` only; `uv run aidm`: a
save from Phase 2 is skipped with the launcher's warning; a new game opens, a turn plays, the chat
names the speaker and the journal shows it; `PROGRESS.md` entry.
