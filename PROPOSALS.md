# PROPOSALS — conceptual simplification and consistency, round three

Input: four independent full reads of `src/aidm` at `dbdfc10` (9,486 lines; 541 tests, ruff and
basedpyright green) on 2026-09-04, after Phases 1–3 of `PLAN.md` landed: three Fable subagents
(A generalist, B SOLID and idiom, C "delete it": every name grep-counted) and the lead. Each
inventoried every concept and hunted for what can go or be spelled once. This file merges them.
Votes are out of 4. Line counts are estimates. **Section 4 holds the decisions; each heading
takes one letter.** Section 5 lists what round two settled and this round does not reopen.

Headline, agreed by all four: there is no dead code (C found no name in `src` with zero callers),
the layering is clean (the boundary test passes; no upward import; `Any` only in the `Game[P]`
bounds), and every concept has a user. What is left is of three kinds: **the two families spell
one seam twice** (worldsmith frame, commission tool, hub block, lifecycle names), **the concrete
engines repeat one scaffold four times** (creation, items, envelopes), and **three names each
mean two things** (`draft`, `commit`, `moving_on`). One structural idea (the job spans, P10) is
the lead's alone and is a decision, not a recommendation. Total if everything lands: about
−200 `src` lines, −400 test lines, two hooks and one Protocol fewer, and one spelling for each of
the nine things now spelled twice. About two working days.

---

## 0. Verified facts (checked by the lead in this checkout, not opinion)

1. **A parametrized envelope replaces the empty subclass.** `Library.read_character("kael",
   "loner3e", Character[Loner3eSheet])` parses; `isinstance(ch, Character[Loner3eSheet])` is
   `True`; `Game[Loner3eWorld] is Game[Loner3eWorld]` (pydantic caches the class). The tree
   already spells the world both ways: `Loner3eWorld` is a subclass (it adds `twist`),
   `BreathlessWorld = SceneWorld[Person, Survivor]` and `TwentyfourxxWorld` are aliases
   (`breathless/world.py:138`, `twentyfourxx/world.py:143`), while all twelve `XGame`,
   `XScenario`, `XCharacter` are `class …: pass`. (lead, A, B)
2. **`check_scenario`'s `isinstance` stops discriminating once the envelopes are aliases**:
   Breathless and 24XX both become `Scenario[SceneCanon[Person]]`. `Engine.begin` already refuses
   on `scenario.engine != self.id` (`seam.py:162`), two lines before `new_game` runs
   `check_scenario` (`seam.py:190`); `check_character` (`seam.py:79`) and `Library._check_filed`
   (`io.py:192`) check the same fit a third and fourth time. (B, A, lead)
3. **The "on order" line is spelled twice with one article's difference**: `f"- a {c.kind}:
   {c.brief}"` at `scenes/engine.py:329`, `f"- {c.kind}: {c.brief}"` at `rooms/engine.py:286`.
   (A, B)
4. **Three spellings of "read a prompt file"**: module constant at import (`WORLDSMITH` at
   `scenes/engine.py:82` and `rooms/engine.py:62`), instance attribute in `__init__`
   (`seam.py:66`), cached function (`turn/context.py:62`). (lead, B)
5. **The scene draft class is re-derived at 14 `isinstance`/`issubclass` sites** after
   `write_next` chose it (`scenes/engine.py:248` `issubclass(answer, ReturnDraft)`,
   `issubclass(answer, NextDraft)`; `:303,342,347,352`; `scenes/world.py:312,315,319`;
   `scenes/worldsmith.py:71,190,193`). The rooms world does not do this: it has typed
   `apply_extension` and `apply_return`. (lead, A, B)
6. **`GameService.play(moving_on=True)` is three behaviours behind one flag**
   (`runtime.py:100–131`): a plain turn; a rooms write with no turn (`crossing() is None` →
   `extend`, `:105–108`); a scene turn followed by `_grow` and a narrated crossing (`:127–129`).
   `extend` has one caller, `play`; its `intent` field feeds one chat bubble
   (`ui/game.py:195–196`). (lead, B, C)
7. **The page reaches through the service into the engine 10 times**: `session.engine.
   history(session.state)`, `session.engine.narrator_view(session.state)`,
   `session.engine.ready(session.state)` in `ui/game.py`. `GameService` already wraps the
   same call for `player_view()` and `scene_art()`. (lead)
8. **`draft` names three things**: the transactional copy (`Game.draft()`, `Turn.draft`,
   every resolver's first parameter), the worldsmith's typed answer (`scenes/drafts.py`,
   `rooms/drafts.py`: `SceneDraft`, `MapDraft`, `CastDraft` …, 87 sites), and the `Turn` field.
   CLAUDE.md calls the second "typed proposals". `commit` names two: `Engine.commit`
   (validate, `seam.py:156`) and `GameService.commit` (persist, `runtime.py:293`). (lead, C)
9. **The two families name one lifecycle step two ways at every stage**: `render_opening` /
   `render_map`; `opening_draft` / `map_draft`; `write_next` / `write_extension`; `install` /
   `install_extension`; `install_cast` / `install_commission`. (B)
10. **Twenty test functions exist verbatim in two or three engine directories** (`grep -rhoE
    "def test_\w+" tests/{loner3e,breathless,twentyfourxx,tunnelgoons} | sort | uniq -d`),
    plus three `_return_draft`, three `NAMES`/`hub_world` blocks and three identical
    `golden_turn.behind`; they test `SceneEngine`, `SceneWorld` and `Campaign`, not an
    engine's rule. About 380 lines. (C)
11. **Four settings knobs are read once each and are properties of the chosen model, not
    preferences**: `scene_ratio`, `icon_ratio`, `max_references` (`config.py:40–43`, read at
    `media.py:65,71,87`), `sample_rate` (`config.py:58`, read at `speech.py`). `Pack.source`
    and `Pack.license` are required in every pack file and read nowhere in `src`. (C)
12. **The job span machinery is 70 lines across three files** (`started`/`returned` indices,
    `Attempt`, `check_spans`, `returns()`, `since_start`, `records_of`, `walked_places`, the
    "hub runs and closed jobs disagree" validator) and `tests/core/test_hub.py` is the largest
    core test at 425 lines; `Attempt(` appears 60 times in tests. (lead)
13. **Not bugs, recorded so nobody "fixes" them**: `speakers_refusal` re-checks what `spoken`
    checks (re-prompt first, hard gate second — but one can call the other, P7); the rooms bar
    runs once per advance since Phase 2; `Turn.commissioned` is the only bound on the
    `_run_master` re-spawn loop; `Refusal` inside `require_unique` works inside validators
    because it subclasses `ValueError`.

---

## 1. Inventory: every concept, one line, verdict

Verdicts: **keep** (earned, no proposal), **P#** (a proposal touches it), **D#** (a decision).
Lines are of `src` at `dbdfc10`.

### core (1,071 lines; knows no world shape)

| # | concept | where | lines | verdict |
|---|---|---|---|---|
| 1 | `Frozen`/`Mutable`/`Loose`, `Refusal`, `parse`, `Slug`/`EntityId`/`CheckedEntityId`/`EngineId`, `slug`, `require_unique`, `content_id` | `core/entities.py` | 76 | keep |
| 2 | Envelopes `Scenario[P]`/`Character[P]`/`Game[P]`, `ScenarioMeta`, the `Loose` headers, `WorldsmithAnswer`, `Check[T]` | `core/model.py` | 125 | P1 |
| 3 | `Fact`, `DiceEvent`, `roll`, `cards`, `traced` | `core/facts.py` | 62 | keep (D6 A, round two) |
| 4 | `MasterTool`, `master_tool`, `Play`, `NoArgs`, `schema_of`/`schema_text` | `core/tools.py` | 68 | keep |
| 5 | `Line`/`SpokenLine`/`Narration`, `DecisionOption`/`PendingOption`/`PendingDecision`, `Answer`, `Exchange`, `SceneRecord`/`ChapterRecord`, `Commission` | `core/play.py` | 132 | keep |
| 6 | `CreationStep`, `check_picks`, `picked`/`other_than`/`option_of`/`chosen_option` | `core/creation.py` | 50 | keep (P3 uses them) |
| 7 | Source documents to text | `core/source.py` | 49 | keep |
| 8 | `NarratorView`, `PlayerView`, `Panel`/`PanelRow`, `Subject`, `Rows`/`Sections`, `render_history`/`told_narration`/`render_whole` | `core/views.py` | 178 | P7 (speaker rule, entity row) |
| 9 | `FileStore` (saves), `Library` (content), `decode`, `routed`, `write_text` | `core/io.py` | 207 | P1 (one fit check), P7 |

### engines (4,705 lines)

| # | concept | where | lines | verdict |
|---|---|---|---|---|
| 10 | `Engine[P, G]` ABC: 12 abstract, ~20 concrete (`begin`, `commit`, `close`, `compose`, `commission`, `restore`, `tool`, `answer`, five pass-throughs to `World`) | `engines/seam.py` | 254 | P1, P2, P3, P7 |
| 11 | `Thing`/`Person`/`Counter`/`Pack`, three panel builders, `keep_highest`, `read_packs` | `engines/base.py` | 180 | P3 (items hook), D7 (`Pack.source`/`license`) |
| 12 | Hub: `Offer`/`Board`, `Attempt`, `Job`, `Campaign` (25 methods: state, prompt sections, panels), `World[P]`, prompt constants, four free functions | `engines/hub.py` | 418 | P2 (shared frame lands here), P7, P10 |
| 13 | Registry | `engines/registry.py` | 12 | keep |
| 14 | Scene family: `SceneEngine[C, P, G, K]`, `SceneWorld`/`SceneCanon`/`SceneRun`, five drafts, six shared arms + `NextScene` + `SceneCommission`, the bar, `worldsmith_prompt` | `engines/scenes/` | 1,242 | P2, P4, P6 |
| 15 | Room family: `RoomEngine[N, P, G]`, `Dungeon`/`RoomCanon`/`RoomWorld`, four drafts, three arms + `Move`/`UnlockWay` + `RoomCommission`, seven bars, a second `worldsmith_prompt` | `engines/rooms/` | 1,200 | P2, P6 (D3 C stands: not folded) |
| 16 | Loner 3e (605), Breathless (596), 24XX (691), Tunnel Goons (371): sheet, world, tools, worldsmith guidance, `rules.md`, packs | `engines/<id>/` | 2,263 | P1, P3 |
| 17 | `change_world` arms, `SharedChange` unions, four `ChangeWorld` classes | `*/tools.py` | — | keep (D5 A) |
| 18 | `commission`: `CommissionArgs` Protocol, abstract `commission_tool` ×2, `SceneCommission`/`RoomCommission`, `later` | seam + both families | ~60 | P2 |

### turn, app, ui (2,740 lines)

| # | concept | where | lines | verdict |
|---|---|---|---|---|
| 19 | `Turn`: the transaction, `call`/`apply`/`_apply`, `_consume` | `turn/run.py` | 145 | P6 (names) |
| 20 | `render_master`/`render_narrator`, `prompts/*.md` | `turn/context.py` | 78 | P7 (prompt loading) |
| 21 | `GameService` (lifecycle, role orchestration, persistence, presentation) and `Runtime` (composition root, sessions, `new_scenario`) | `app/runtime.py` | 451 | P5, P7, D2 |
| 22 | Spawn: `Driver` Protocol, two drivers, `CliSpawner`, `ask`, `final_message` | `app/spawn.py` | 307 | keep |
| 23 | `LauncherCatalog`/`CatalogEntry`/`SaveOption`/`LaunchTarget` | `app/launch.py` | 127 | P7 |
| 24 | MCP endpoint | `app/mcp.py` | 78 | keep |
| 25 | `Illustrator`, `Reader`, `providers.py` | `app/media.py`, `app/speech.py`, `app/providers.py` | 360 | keep; D2 |
| 26 | `Settings` and the reflective settings page | `config.py`, `ui/settings.py` | 302 | P9 (four knobs) |
| 27 | Pages: home, game (`GamePage`, `Observed`), create, widgets, theme | `ui/` | 1,283 | P5, P7, D6 |
| 28 | Tests: `ScriptedSpawner`, goldens, the boundary test, per-engine support builders | `tests/` | 9,586 | P8 |

---

## 2. The ten proposals, ranked by value over risk

Each: what changes, the evidence, what is lost, size, risk, who proposed it.

### P1 — Twelve envelope classes become aliases; the engine fit is checked once (4/4)

**Change.** `class Loner3eGame(Game[Loner3eWorld]): pass` → `Loner3eGame = Game[Loner3eWorld]`,
and the same for the other eleven (`loner3e/world.py:116–125`, `breathless/world.py:141–150`,
`twentyfourxx/world.py:146–155`, `tunnelgoons/world.py:72–81`). Delete `Engine.check_scenario`
(`seam.py:189–191`) and its two calls (`scenes/engine.py:117`, `rooms/engine.py:84`); the id
check in `Engine.begin` is the one gate. Keep `check_character`'s `isinstance`: the four
`Character[…]` parametrizations stay distinct, and it also checks `id == "player"`.

**Evidence.** Facts 1 and 2. Round two leaned "keep the twelve"; the new fact is that the tree
already spells the world as an alias in two engines and as a subclass in one, so this is now a
consistency fix, not a preference.

**Lost.** Tracebacks read `Game[SceneWorld[Person, Survivor]]` instead of `BreathlessGame`.
`tests/twentyfourxx/test_engine.py:109–113` expects "incompatible scenario" from `new_game`;
it moves to `begin`'s "does not play".

**Size.** −27 lines; 1 h. **Risk.** Low. Saves carry no class name; `schema_of` pops the title;
run the golden regen to confirm nothing moves.

### P2 — One worldsmith frame, one commission tool, one hub block (3/4; B keeps the two frames)

**Change.** Three near-twins between the families fold into `hub.py` and `seam.py`:
- `worldsmith_prompt` (`scenes/worldsmith.py:131–156`, `rooms/worldsmith.py:36–62`): one
  function taking `world: Sections` for the middle (scenes pass `THE WHOLE CAST`, rooms `MAP SO
  FAR` + `THE PLAYER`) and `standing: Sections = ()` for the scenes-only `STANDING INSTRUCTION`.
  The section order differs today (`ENGINE GUIDANCE` before `WHAT COMES NEXT` in scenes, after
  in rooms): D1.
- `commission_tool` (`scenes/engine.py:201–209`, `rooms/engine.py:208–217`): concrete on
  `Engine`, reading two class attributes `commission_args: type[BaseModel]` and
  `commission_hint: str`. This is round two's D4 B, decided but not landed: only
  `ask_worldsmith` was hoisted. The two args classes stay whole, so the schema goldens do not
  move. Fold `Engine.commission` (`seam.py:132–144`, one caller) into `ask_worldsmith`.
- `hub_sections` (`scenes/engine.py:220–235`, `rooms/engine.py:264–273`): the guard, title and
  brief differ; the call is one. Hoist to `Engine.hub_block(world, brief, title, *, returning,
  reopening)` only if it nets lines after D1; else leave.
- The "on order" line (fact 3) becomes `Game.on_order_lines()` beside `on_order()`.
- Move the scenes-only residents of `hub.py` (`place_unmet`, `question_heading`, `HOME_ROW`,
  `HUB_ROW`, `ONE_SHOT_OPENING`, `CAMPAIGN_OPENING`, `TAKE_BRIEF`, `AWAY_BRIEF`,
  `WRITE_HUB_SCENE`, `JOB_DONE`: ~70 lines, callers in `engines/scenes` only) into
  `scenes/worldsmith.py` and `scenes/world.py`, and `OFFER_ASK` into rooms if it stays rooms-only
  after the frame merge. A move, not a deletion; it makes "shared by both families" true of
  every line in `hub.py`.

**Evidence.** C's `comm -12` of method names: 18 shared between the two engine bases; the three
bodies above differ in one section, one string tail and one brief choice. No golden covers a
worldsmith prompt; rooms tests assert `"ENGINE GUIDANCE" in prompt`, order-free.

**Lost.** `"(none — write from the cast)"` vs `"… from the setting)"` becomes one string or a
parameter. One family's section order changes (D1).

**Size.** −45 `src` lines; 3 h. **Risk.** Low-medium: touches both families; re-run one scripted
campaign loop as in PROGRESS Phase 2. B's objection: after the merge the shared function is
"`sections` with three `Sections` arguments"; the reply is that it pins one order and one
heading set for both roles, which is the point.

### P3 — The per-engine scaffold, once: creation pipeline and one items hook (3/4)

**Change.**
- `Engine.create_character(name, brief, picks)` becomes concrete: `check_picks(self.
  creation_steps(picks), picks)`, then `sheet = self.sheet(name, brief, picks)` (new abstract,
  returns `P`), then `self.character(id=slug(name, ()), engine=self.id, payload=sheet)`.
  `SceneEngine.creation_steps` becomes concrete (`pack_step`, then `pack_steps(pack, picks)`
  abstract). Evidence: `check_picks(self.creation_steps(picks), picks)` opens all four
  `create_character` bodies and `XCharacter(id=slug(name, ()), engine=self.id, payload=sheet)`
  closes all four; the `first/pack/if None/return (first,)` prologue is at
  `loner3e/engine.py:81–84`, `breathless/engine.py:108–111`, `twentyfourxx/engine.py:106–109`.
- One hook for the player's items instead of three. Today Breathless and 24XX each render the
  same dict three ways: `sheet_sections` for the master (`- name[id] — d8`), `panels` for the
  sidebar (`PanelRow(label, detail="d8")`), `preview_character` for the create page
  (`("Backpack", "a, b")`); Tunnel Goons overrides only the third (`breathless/engine.py:146–172`,
  `twentyfourxx/engine.py:192–214`, `tunnelgoons/engine.py:135–137`). Replace with
  `Person.items_shown() -> tuple[tuple[EntityId, str, str], ...]` (id, name, detail) and a
  `items_title: str` class attribute (`BACKPACK`, `GEAR`, `Items`); `SceneEngine.
  master_sections`, `player_view` and `Engine.preview_character` render it, byte-equal to today.
  `sheet_sections`, `panels` and the three `preview_character` overrides go. Loner overrides
  nothing and is unchanged.

**Lost.** The concrete `Loner3eCharacter` return types (the seam already declares
`AnyCharacter`). Nothing user-visible: the master goldens pin the section text.

**Size.** −35 lines, two hooks fewer; 3 h. **Risk.** Low; `tests/*/test_create.py` go through the
same public calls, goldens catch drift in the sections.

### P4 — The scene write is dispatched by what `write_next` decided, not re-derived (3/4)

**Change.** `write_next` (`scenes/engine.py:316–331`) already computes `returning` and picks
the draft class. Thread that knowledge instead of sniffing the class afterwards:
- `render_next(…, *, returning: bool, follows_arc: bool)` replaces the two `issubclass` reads
  at `:248`; `render_commission` passes `False, False` explicitly instead of relying on
  `CastDraft` falling outside both branches.
- `SceneWorld.apply_scene` (`scenes/world.py:305–338`, three `isinstance` branches) splits into
  `apply_next(draft: NextDraft)`, `apply_job(draft: JobDraft, *, reopening)`,
  `apply_return(draft: ReturnDraft)`, each ending in the shared `self.runs.append(run_of(…))`.
  This is the shape `RoomWorld` already has (`apply_extension`, `apply_return`).
- `install` (`:333–357`) becomes three short installs called from the branch `write_next`
  took, or one `install` that takes the kind it was told. The `Home`/`New scene` label and the
  `job` card line follow the kind.

**Evidence.** Fact 5. NEXT-SPECS refused a flat draft ("the five classes are the schema the
worldsmith answers in"); this keeps the five classes and moves the dispatch to the one place
that already knows, so the seven `isinstance` sites become zero, not seven `if draft.offers`.

**Lost.** Nothing; the worldsmith prompt and the install are unchanged in text.

**Size.** ±0 lines, −11 `isinstance`/`issubclass`; 2 h. **Risk.** Low; `tests/core/test_scenes.py`
covers `apply_scene` on `SceneWorld[Person, Person]` and follows the split.

### P5 — `play`, `move_on`, and no `extend` (3/4)

**Change.** `GameService.play(answer)` runs a turn. `GameService.move_on(answer)` computes the
brief from `engine.crossing`, then either runs the rooms write alone or the turn followed by
`_grow` and the narrated crossing; both share a private `_turn(answer)`. `extend` (one caller)
folds into `move_on`; its three guards repeat `play`'s. `GamePage._send(answer, *, moving_on)`
becomes two callers (`ui/game.py:342,351,394`). `crossing() -> str | None` stays as D19 A
decided; its `None` is read in one method instead of two.

**Evidence.** Fact 6. **Lost.** Decision D8 on the `intent` field (one bubble during a rooms
write). If it stays, `move_on` sets it; if it goes, `_SilentEngine`/`Watching` in
`test_master_tools.py:55–70,239–269` lose their purpose (the real rooms engine runs the same path
in `tests/tunnelgoons/test_play.py:179–187`).

**Size.** −12 `src`, −35 test lines; 1.5 h. **Risk.** Low; `test_game_service.py` names
`play(…, moving_on=True)` and follows.

### P6 — One name per thing: proposal, save, and the rooms lifecycle (3/4; C: "renames, not deletions")

**Change.** Three renames, each mechanical, each a grep:
- The worldsmith's answers are proposals, as CLAUDE.md says: `scenes/drafts.py` →
  `scenes/proposals.py`, `SceneDraft` → `SceneProposal`, `NextDraft` → `NextProposal`,
  `JobDraft`, `HubDraft`, `ReturnDraft`, `CastDraft`, `MapDraft`, `NpcDraft`, `ItemDraft`
  likewise; `opening_draft`/`map_draft` → `opening_proposal`. Then `draft` means only the
  transactional copy, everywhere. D3 offers the reverse direction.
- `GameService.commit` (persist) → `GameService.save`; `Engine.commit` and `Game.commit`
  (validate) keep the name.
- The rooms family takes the scenes' step names (fact 9): `render_map` → `render_opening`,
  `write_extension` → `write_next`, `install_extension` → `install`; and scenes' `install_cast`
  takes rooms' truer `install_commission`. After it, `advance` and `fulfil` read identically in
  both bases.

**Lost.** Nothing. Class names appear in no save, schema or prompt (`schema_of` pops titles;
the worldsmith reads field descriptions).

**Size.** 0 lines, ~120 rename sites in `src` and tests; 2 h with `sed` and a grep per name.
**Risk.** Low.

### P7 — Small folds: one caller, one spelling (4/4 on the parts; bundled by the lead)

Each is under ten lines; together they are the "layers that only forward" and "spelled twice"
findings that did not earn a proposal alone. About −60 lines, 3 h, low risk throughout.

- **Prompt files, one way** (fact 4): `turn/context.py` reads `MASTER` and `NARRATOR` as module
  constants like `WORLDSMITH`; `_prompt` and the `cache` import go. `instructions` stays per
  instance (it is per engine directory).
- **`NarratorView.narration_refusal` calls `spoken` under `try/except Refusal`** and returns
  `str(refused)`; `speakers_refusal` (`views.py:79–94`, one caller, no test) goes. Keep the
  longer message on the raise. The idiom is `Engine.compose`'s.
- **Forwarders with one caller, inlined**: `Engine.answer` (`seam.py:100–107`, re-wraps one
  refusal; keep the wrapped text on `tool()`'s own refusal, `test_decisions.py:636` matches it);
  `question_heading` (`hub.py:417`); `Campaign.terms` (`hub.py:192`); `Campaign.sections` →
  `hub_block`, `board_rows` → `board_panel`, `job_row` → `tail` (each one caller);
  `Loner3eEngine.glossary → meanings → pack_meanings` (three layers, one caller each →
  one method); `SceneWorld.here_lines`/`hidden_lines` (two lines each, one caller each).
- **One entity row**: `Subject.row(label=None) -> PanelRow` in `core/views.py`;
  `PanelRow(label=x.name, detail=x.brief, icon_id=x.id)` is written at `base.py:148–149` (twice),
  `scenes/world.py:351`, `rooms/engine.py:138`.
- **Validation outside `parse`**: `ValidationError` is caught by hand at `ui/settings.py:89–93`
  and `spawn.py:84–91`; use `parse(Settings, merged)` / `parse(_ClaudeResult,
  decode(output))` and catch `Refusal`. `_object` (`spawn.py:258`) stays: a non-JSON line is
  expected there.
- **The page stops reaching through the service** (fact 7): `GameService.history()`,
  `scene()` (the narrator view) and `ready()`; `ui/game.py` never names `session.engine` or
  `session.state` except for the title. `Runtime.published_tools` likewise reads
  `playing.tools()`.
- **One decode-and-restore**: `FileStore.load` returns raw text and both callers
  (`runtime.py:69`, `launch.py:99–102`) decode, route and restore; `FileStore.restore(slug,
  engines) -> AnyGame | None` does it once. `LauncherCatalog.read` and `Runtime._open` both build
  `{engine_id: engine.scenario}`; `Library.read_scenario(s)` takes the engines mapping.
- **The `Free:` docstrings** (D5): fourteen carry it, sixty other free functions take one of our
  objects first without it.

### P8 — The tripled scene-engine tests fold into `tests/core` (1/4 proposed, nobody against)

**Change.** Every copy but one of the twenty duplicated tests (fact 10): for example
`test_only_the_players_own_fields_are_checked_for_what_they_have_not_met` at
`tests/loner3e/test_worldsmith.py:275`, `tests/breathless/test_worldsmith.py:367`,
`tests/twentyfourxx/test_worldsmith.py:458` (~40 lines each); `test_check_game_refuses_a_hub_with_
a_one_shot_meta` ×3; `test_restored_round_trips` ×3; the three `_return_draft`, three `NAMES`/
`hub_world` blocks, three identical `golden_turn.behind`. Parametrize the survivor over
`ENGINE_IDS` where the engine matters. `open_game_for` (`support/table.py:199–214`) and
`support.loner.open_game` (`:442–456`) go; `open_table` stays.

**Evidence.** They exercise `SceneEngine`, `SceneWorld`, `Campaign` and `Engine.validate`; none
reads an engine's own rule. `tests/core/test_scenes.py` already tests the same base on
`SceneWorld[Person, Person]`. CLAUDE.md: "test behaviour and boundaries, not wiring".

**Lost.** Nothing. **Size.** −380 test lines; 3 h. **Risk.** Low; tests only. A test that turns
out to read a rule stays where it is.

### P9 — Data nothing reads: four knobs become constants (1/4 proposed; D7 for the pack fields)

**Change.** `MediaConfig.scene_ratio`, `icon_ratio`, `max_references` and `SpeechConfig.
sample_rate` (fact 11) become module constants in `media.py` and `speech.py`. They leave the
settings page with them (the page reflects every field). `timeout`s, `voice`, `voices`,
`model`, `enabled` stay: those are preferences.

**Lost.** A player who switches the image model to one that wants another ratio edits a
constant instead of `.env`. **Size.** −8 lines, four boxes fewer; 0.5 h. **Risk.** Nil.
`Pack.source`/`license` are the same finding with a standing decision behind them: D7.

### P10 — The job spans: tag the runs instead of indexing them (lead only; a decision, D4)

**Today.** A `Job` holds `attempts: list[Attempt]`, each `Attempt` two indices into the world's
`runs`/`visits` list (`started`, `returned`); `Campaign.check_spans` cross-checks every index
against the place list, `SceneWorld._consistent` counts hub runs against `returns()`, and
`since_start`, `records_of`, `job_records`, `walked_places`, `history` slice the list by those
indices (fact 12). It is the most intricate state in the tree and the hardest to read back from
a save.

**Alternative.** Each `SceneRun`/`Visit` carries `job: int | None` (the index into
`campaign.jobs`; `None` at the hub). `Attempt` goes; `Job` gains `closed: bool`. Then
`records_of(job)` is a filter, the current attempt is the trailing block of runs tagged with the
open job, a chapter is a closed block, `check_spans` becomes "a tagged run is not at the hub and
a hub run is untagged", and the "hub runs after the first and closed jobs disagree" validator
goes. Reopening stays: a reopened job gets a new trailing block. Rooms' "taken at the tavern but
not walked" state (`Attempt.started is None`, `Job.walk`, `swap_out`) becomes `Job.walked:
bool` or the absence of a tagged visit.

**Evidence.** 70 `src` lines and the 425-line `test_hub.py` exist to keep two parallel
structures (the run list and the index pairs) consistent; one structure with a tag has nothing
to keep consistent. Round two's section 7 M protects `Job.attempts` (reopening) and the
three-depth history as *behaviour*; this keeps both and changes only the representation.

**Lost.** Every save with a campaign goes stale (allowed by design; Track G's G.1 is already
a stale-save commit, so this rides with it or waits for it). `test_hub.py` is largely rewritten.

**Size.** −50 `src` lines, −150 test lines; 6 h. **Risk.** Medium-high: it is the campaign's
spine, one reviewer's idea, unverified by the other three, and the tests that protect it are the
ones that change. Do it only with a scripted campaign loop run before and after.

---

## 3. Order of work, if everything is taken

1. P1, P7 (prompt files, forwarders, `parse`, Demeter, entity row): one sitting, no fixture
   moves. ~4 h.
2. P2 with D1 decided, then P3: the family and engine scaffolds. One golden regen (master
   sections must not move). ~6 h.
3. P4, P5 with D8 decided, P6 with D3 decided: dispatch, the service, the names. ~6 h.
4. P8, P9: tests and knobs. ~4 h.
5. P10 only if D4 is B, and only in the same commit as Track G's first stale-save change.

`src` after 1–4: about 9,290 lines. Every engine directory stays under 2,000; `engines/scenes/`
and `engines/rooms/` shrink.

---

## 4. Decisions for the maintainer

Each with options and the reviewers' lean. Take one letter per heading.

**D1 — Which section order does the shared worldsmith frame keep?** (P2)
- A. Scenes' order: `ENGINE GUIDANCE` before `WHAT COMES NEXT`, `STANDING INSTRUCTION` for both
  families. Rooms' prompt changes; Tunnel Goons gains the surprise instruction.
- B. Rooms' order: guidance after the intent; no standing instruction. Scenes' prompt changes.
- C. Keep both functions; rename one (`room_prompt`, `scene_prompt`). Consistency of names only.
- Lean: **A** (lead, A, C). B (reviewer) leans C.

**D2 — Split presentation out of `GameService`?** (A, B, lead)
`runtime.py:142–144,253–287`: `media`, `reader`, `_background`, `_present`, `illustrate`,
`speak`, `scene_art`, `icon`, `newest_clip`, `_newest`, `_retain` — 39 lines that never read
the turn. The page calls five of them directly.
- A. A `Presentation` dataclass (`app/present.py`: the two providers, the task set, the six
  methods), built in `Runtime._open`; `GameService.present` field; the page reads
  `session.present.scene_art()`. ±0 lines, one 50-line module; 3 h.
- B. Keep the class; move `_retain`/`_background` into `Illustrator` and `Reader` (each already
  owns `generating`). −8 lines; 1 h.
- C. Leave: 260 lines one person wrote.
- Lean: **A if Track G starts within the month** (the party adds presentation), else **B**.

**D3 — Which way does the `draft` rename go?** (P6)
- A. The worldsmith's answers become `*Proposal` (CLAUDE.md's word); `draft` is the
  transactional copy only. ~90 sites.
- B. The transactional copy becomes `candidate`/`working` and the proposals keep `Draft`.
  ~130 sites, and `Game.draft()` is the older name.
- C. Leave; one CLAUDE.md line saying "a Draft is the worldsmith's; a draft is the turn's".
- Lean: **A**.

**D4 — The job spans.** (P10)
- A. Keep the index pairs. Zero risk, the tests stand.
- B. Tag the runs, in the commit that also lands Track G's first stale-save change.
- C. Tag the runs now, as its own stale-save commit.
- Lean: **A now, B when G.1 is planned**; the lead wrote P10 and still would not do C.

**D5 — The method rule and the `Free:` docstrings.** (B)
CLAUDE.md: "a function whose first argument is one of our objects is a method". Fourteen free
functions carry a `"""Free: …` line (`providers.py:20`, `media.py:168`, `base.py:146`,
`scenes/world.py:403`, `scenes/worldsmith.py:37,43`, `rooms/worldsmith.py` ×7,
`turn/context.py:42`); about sixty others take one of our objects first with no line
(`illustration_request(scene: NarratorView, …)`, `requests_of(exchange: Exchange, …)`,
`can_type(player: PlayerView, …)`, `_strike(draft: Loner3eGame, …)`, `ask(spawner, …)`, every
`_block`/`_told`/`cards`/`traced`). Tunnel Goons spells starting items as a method
(`Goon.starting_items`), 24XX as a free function (`twentyfourxx/engine.py:351`).
- A. Drop the fourteen `Free:` lines ("it is free" is visible), move `_strike`/
  `_refuse_unless_ready`/`_pair` onto `Loner3eEngine`, make 24XX `starting_items` a method on
  the pack or the sheet. −14 lines; 1.5 h.
- B. Drop the fourteen lines only. −14 lines; 0.3 h.
- C. Enforce the rule with an AST test like `test_package_boundary.py` and an allowlist that
  starts at ~60 names. +40 lines; 3 h.
- Lean: **A**.

**D6 — The way-on affordance is drawn three times.** (C)
`ui/game.py:203–216 way_on_panel` ("there is more beyond here … press Move on"), the sidebar row
`PanelRow(label="Way on", detail="Keep playing, or name where you go and move on.")`
(`scenes/world.py:363–367`), and `move_on_button` (shown only when `ready`).
- A. Delete `way_on_panel`; the row and the button say it. −14 lines.
- B. Delete the "Way on" row; the banner sits by the composer where the button is.
- C. Keep all three (the reader wants the prompt where they look).
- Lean: **A**; the journal tab (a second view of the chat) stays under the same reasoning as C.

**D7 — `Pack.source` and `Pack.license`.** (C) Required in every pack, read nowhere in `src`.
Round two's D11 A made them required as attribution-in-data.
- A. Delete both; the attribution lives in `rules.md` and `docs/<ENGINE>.md`. −2 fields, −12
  JSON lines.
- B. Keep and add the one reader that justifies them: the create page's "Table sets" hint shows
  `source`. +4 lines.
- C. Keep as is (reconfirm D11 A).
- Lean: **B** (a required field earns its keep by being read once) — the lead; C leans A.

**D8 — The `intent` bubble during a rooms write.** (P5)
`GameService.intent` shows the player's words as their bubble while the worldsmith writes a
region without a turn (`ui/game.py:195–196`).
- A. Keep it; `move_on` sets it. The `_SilentEngine` test scaffolding stays.
- B. Drop it; the spinner and the "Worldsmith" status line remain. −12 `src`, −35 test lines.
- Lean: **A**: the bubble is the only echo of what the player typed until the region lands,
  and a Tunnel Goons write takes minutes.

---

## 5. Settled in round two and not reopened

Recorded so nobody spends a round on them again. Each was flagged by at least one reviewer
this round; the standing decision holds unless the maintainer says otherwise.

- **`RoomEngine`/`RoomWorld`/`Dweller` with one subclass** (D3 C, "stays as it is"). All four
  reviewers flagged it (`starting_items` is a three-hop forward; `sheet_rows` and `dweller`/
  `world_type`/`map_draft` have one implementer each). A's middle path, if D3 C was about the
  directory and not the generics: drop `N`/`P`/`G` and `Dweller`, keep the split; −40 to −60
  lines, 3 h. Not proposed; noted.
- **The four `ChangeWorld` classes** (D5 A; pydantic 2.13.4 cannot discriminate a generic).
- **`Fact.kind` as a free string** (D6 A).
- **`Engine.crossing() -> str | None` as the behaviour switch** (D19 A). P5 reads its `None` in
  one place instead of two and changes nothing else.
- **One flat scene draft** (NEXT-SPECS, refused). P4 keeps the five classes.
- **The reflective settings page, `PanelRow`'s three shapes, the single-overrider hooks
  `leaving`/`glossary`/`finished_note`** (round two's shared leans). `leaving` must run between
  the write and the install; `glossary` sits mid-tuple; each costs more in Loner than it saves.
- **`Turn.commissioned`/`COMMISSIONS_PER_TURN`**: the only bound on the `_run_master` re-spawn
  loop, not a duplicate of `wanted()`.
- **Reopening a left-open job** (`taken`/`left_open`/`reopen`/`swap_out`, `THE JOB BEFORE`):
  NEXT-SPECS decision 5. P10 keeps the behaviour.

## 6. Considered this round and rejected, with the reason

- **Hoist `advance` to `Engine`** (the two six-line bodies): the written proposal's type differs
  per family; hoisting costs a third type parameter or `isinstance` in `install`. (B)
- **A `Played` Protocol in `core` so `Game.payload` exposes `records()`/`record()` and the five
  seam pass-throughs go**: "core knows no world shape" is a design line; a Protocol with
  `records()` is a world shape in all but name. (lead, A)
- **Split `hub.py`** into ledger, `World` and prompt strings: `World` needs `Campaign`; a new
  module for twenty lines. P2 moves the family-only residents out instead. (B)
- **Split `Engine` into a platform ABC and a subclass-helper mixin**: every method has a caller;
  two classes in one file explain less than one. (B)
- **`render_master`'s seven parameters → a picture model**: one caller. (B)
- **`Exchange.decision`** (written once, read once): a stale-save commit for four UI lines. (C)
- **Packs machinery for engines with one pack** (`pack_step`, the multi-select): hiding a
  one-item choice adds code; Loner's two packs earn the concept. (C)
- **`Kit` → `Item`** in 24XX (`Kit` is `Item` minus `broken_times`): "value models are frozen"
  is exactly what `Kit` obeys inside a frozen pack. (C, withdrawn)
- **`Slug` on dataclass fields in `launch.py`** validates nothing but documents; keep. (B)
- **`Engine.restore` re-parsing the header `routed` parsed**: two lines, and `restore` must
  stand alone for `GameService.__post_init__`. P7's `FileStore.restore` removes the double call
  at the two sites without touching `restore`. (B)
- **Folding the three item renderings into `rows()`**: the master prompt and the Character
  panel would print items twice. P3's hook renders them once each, byte-equal. (A)
- **Moving `rules.md`/`worldsmith.md`/pack reads out of engine construction**: the content is
  the engine's own; the registry is already the edge. P7 only makes the three reads one shape.
  (A)
- **`Named`, `WorldsmithAnswer`, `Spawner`, `Driver`, `CommissionArgs`** as one-implementation
  types: each is the test-stub seam "never start a process in a test" requires, or D4 B. P2
  drops `CommissionArgs` only because a concrete `commission_tool` reads `args.kind`/`brief`/
  `later` from the pydantic base both families already share by field name. (C)
- **`SceneRun.left` as a tri-state string** (`None` open, `""` settled here, text = pursuit):
  read at five sites, each unambiguous; an enum plus a field is more spelling for the same
  three states. (lead)
