# Simplification proposals

Sources: a full read of `src/aidm` by four reviewers (three Fable subagents on concepts, engines/seam,
app/ui/tests, plus the lead), checked against CLAUDE.md and README.md. Baseline: 795 tests pass,
ruff and basedpyright clean. Line counts are estimates (±20%).

What was looked for and not found: import-direction violations, `Any` outside the allowed bound,
properties with side effects, settings without a reader, dead top-level code. The fat is
duplication, one-user hooks, one concept under several names, and a few subsystems that grew a
second model family.

Each proposal: what it is in plain words, what the code is now, what it becomes, feature impact,
size, and a decision where one is open. Options are listed recommended-first.

---

## 1. Packs are never optional

**Status.** Accepted, option (a): tuple + ship the Tunnel Goons SRD pack.

**Plain words.** Every game plays a list of packs. Today that list can be "nothing", only because
Tunnel Goons ships no pack. That one gap costs 28 `None` branches and four whole overrides.

**Now.** `PackSelection(Frozen)` wraps `ids: tuple[Slug, ...]` (`core/model.py:43`).
`packs: PackSelection | None` on `Game`, `Scenario`, `Character`, `CharacterHeader`. `None` is
branched on in `PackSet.require/chosen/guidance/rules_sections/seeds`, `Engine.select_packs/admit/
guidance/validate/pack_ids`, the four `SceneEngine` overrides of `validate/guidance/admit/pack_ids`
(they exist to turn the Optional back into "SRD required"), and `launch.py`. Tunnel Goons has no
`packs/` directory; its eighteen starting items live in Python as `STARTING_ITEM_LIST`
(`tunnelgoons/engine.py:47-66`), which is exactly what `TunnelGoonsPack.items` is for.

**Become.** `packs: tuple[Slug, ...]` everywhere, uniqueness checked in `PackSet.select`. Ship
`src/aidm/engines/tunnelgoons/packs/srd.json` (items = the eighteen; other fields empty, which
`Pack` already allows). `Engine.pack_ids` prepends `SRD_PACK` for every engine; `Engine.__init__`
checks the SRD pack exists. Delete `PackSelection`, `PackSet.require`, the four `SceneEngine`
overrides, every `None` branch, `STARTING_ITEM_LIST`.

**Feature impact.** Home page lists one more read-only pack ("Tunnel Goons SRD"). On disk
`"packs": {"ids": [...]}` becomes `"packs": [...]` in 3 shipped scenarios and 3 shipped characters
(hand edit). Existing saves are stale (policy: the launcher skips them).

**Size.** −55 Python, +25 JSON. Medium, 2-3 h.

**Decision.**
- (a) Tuple + ship the Tunnel Goons SRD pack. Recommended: removes the Optional and the
  SRD-required special case at once.
- (b) Tuple only; empty means "no packs"; Tunnel Goons keeps no pack. Fewer content edits, but the
  `SceneEngine` SRD overrides stay.
- (c) Keep the `PackSelection` class, make it required. Least change, keeps a wrapper around a tuple.

---

## 2. Engine generics: the world type is the parameter

**Status.** Accepted, option (a): replace `G` by `W` only.

**Plain words.** Every engine spells the same five lines to tell the type checker what its state is.
One parameter carries all of it.

**Now.** `class Engine[P: Person, M: Person, G: Game[Any], K: Pack]` (`seam.py:79`) with an
abstract `world_of(state: G) -> World[P, M]`, implemented identically as `return state.payload` in
`scenes/engine.py:91`, `rooms/engine.py:65`, `loner3e/engine.py:92`, `tunnelgoons/engine.py:89`,
`twentyfourxx/engine.py:130` (the last three only to narrow the return type). Each engine also
declares `game`, `scenario`, `character` class attributes from aliases it spells in `world.py`.

**Become.** `class Engine[P: Person, M: Person, W: World[Any, Any], K: Pack]`, `game: type[Game[W]]`,
concrete `def world_of(self, state: Game[W]) -> W: return state.payload`. `MasterTool[Game[W]]`,
`Request[Game[W]]`. `SceneEngine[C, W: SceneWorld[Any], K]`, `RoomEngine[P, N, W: RoomWorld[Any, Any], K]`.
The `Loner3eGame = Game[Loner3eWorld]` aliases stay for tests and app typing.

**Feature impact.** None.

**Size.** −14/+2. 1 h, driven by basedpyright.

**Decision.**
- (a) Replace `G` by `W` only. Recommended.
- (b) Also derive the three types in `__init__` (`self.game = Game[self.world]`,
  `self.character = Character[self.player]`, family sets `scenario`). −9 more lines per repo, but
  `self.game` is then typed weaker and pydantic parametrises at runtime.

---

## 3. Pack editor: JSON fields, not a home-made text format

**Status.** Accepted, option (a): JSON per field. Ask models stay separate.

**Plain words.** The pack edit page has its own mini-language (`Label — detail` lines, `Key: value`
blocks) with a parser and a printer. One page reads it. Pydantic already knows how to read and
write a pack.

**Now.** `engines/packs.py:295-501`: `block_line`, `table_text`, `parse_table`, `parse_list`,
`blocks_text`, `parse_blocks`, `block_fields`, `block_values`, `head_values`, `body_values`,
`_blocks`, `_block_text`, `_printed`, `_field_value`, `_key_label`, `EditField`, `DASH`,
`SEPARATOR`, `PROSE_ROWS/NAME_ROWS/LIST_ROWS`. Seam: `edit_fields`, `engine_fields`,
`engine_values`, `edited`, `_asked`. Engines: `Loner3eEngine.engine_fields/engine_values/edited`
(34 lines, special cases for `spends_luck` and the twist columns the codec cannot carry),
`TunnelGoonsEngine` (18), `TwentyfourxxEngine` (50, hand-building dicts for `Specialty`/`Origin`).
`ui/packs.py` (68), `Runtime.rewrite_pack`. Reflection over `model_fields`/`annotation` in
`parse_blocks` is a second, weaker validator in front of pydantic. 13 tests.

**Become.** The page shows one textarea per top-level pack field holding pretty-printed JSON
(`pack.model_dump(mode="json")[field]`). Save: `decode` each box, `parse(engine.pack,
{**dump, **edited})`, `check_addable`, write, install. Everything in "Now" except `ui/packs.py` and
`rewrite_pack` is deleted; those two shrink. The Loner special cases vanish because JSON carries
every field.

**Feature impact.** Visible: the editor shows JSON instead of prose lines. Same fields, same Save,
validation errors now carry pydantic's field path.

**Size.** −320/+30. Low effort for the code; a product call on the page's look.

**Decision.**
- (a) JSON per field. Recommended.
- (b) One JSON textarea for the whole pack. Less code still, worse to edit.
- (c) Keep the prose codec for plain line lists only (names, seeds, items; ~20 lines) and JSON for
  tables and cast blocks.
- (d) Drop editing; keep the read-only view. −370.

**Second decision, related (worldsmith ask models).** `Labelled`, `SpecialtyDraft`, `OriginDraft`,
`PackHead/PackBody` and the three `*Head/*Body` pairs mirror the stored pack so that code mints ids
from labels and the ask can carry `min_length=6, max_length=36` steering.
- Keep as is. Recommended now: it is a boundary model, which CLAUDE.md asks for.
- Merge: `Loner3ePack(Loner3eHead, Loner3eBody, Pack)` with a before-validator that rewrites every
  table id from its label; delete `Labelled`, the two `*Draft`s, three `pack_fields`, `options()`,
  `pack_of`'s merge. −90. Cost: the 6–36 steering moves into `HEAD_ASK` prose.

---

## 4. Pack choice is one mechanism, not a creation step

**Status.** Accepted.

**Plain words.** Picking packs is smuggled through character creation as a special "multiple"
answer joined with commas, while the scenario page draws its own select for the same thing. One
select, used by both pages.

**Now.** `core/creation.py`: `MANY = ","`, `picked_many`, `CreationStep.multiple`, the `multiple`
branch of `check_picks`. Seam: `supplement_steps`, `picked_packs`, `chosen_packs`, `SUPPLEMENTS`,
`SUPPLEMENTS_LABEL`. `ui/create.py`: `choose_many`, the `multiple` branch of `_drop_stale`, and
`ScenarioForm.character_fields` rendering its own `ui.select` with `label="Packs"` and the comment
"the seam's SUPPLEMENTS_LABEL; ui may not import engines". The packs step is the only `multiple`
step in the app.

**Become.** `Engine.creation_steps(packs: tuple[Slug, ...], picks)` and
`create_character(name, brief, packs, picks)`; one `_packs_select(engine, value, on_change)` in
`ui/create.py` used by `CharacterForm` and `ScenarioForm`; `Engine.select_packs(supplements)` is the
one entry point. Delete everything listed in "Now" except `select_packs`.

**Feature impact.** None visible (same select, same place on the page).

**Size.** −50/+15. Medium: seam, three engines, `ui/create.py`, `tests/loner3e/test_create.py`,
`tests/twentyfourxx/test_create.py`.

**Decision.** None. Depends on proposal 1.

---

## 5. Lift the view and authoring builders out of the two families

**Status.** Accepted.

**Plain words.** The scene family and the room family each build the narrator's view, the player's
page and the opening prompt with the same code, only the field names differ. Build them once.

**Now.** `SceneEngine.narrator_view` (`scenes/engine.py:143-156`) and `RoomEngine.narrator_view`
(`rooms/engine.py:106-121`) differ only in `scene.place/title/focus/situation` vs
`place.id/name/brief/description`, a `known` filter and one sheet row. `player_view`
(`scenes:158-177`, `rooms:123-156`) differ only in family panels and the action button. `author`
(`scenes:243-261`, `rooms:158-180`) differ in the answer model, the ask string and how the premise
is read off the answer. `ui/game.py:357-363` guesses the sheet panel is `index == 0`.

**Become.** `World` gains `headline() -> tuple[Slug, str, str, str]` (place, title, focus,
situation), `trail() -> Iterable[str]`, `narrator_sheet() -> Rows` (default `sheet_rows()`;
`RoomWorld` appends "Carrying"). `Engine` gains `family_panels(state)`, `action(state) ->
DecisionOption | None` (MOVE_ON if offered / MORE_MAP if frontier == 0), `opening() -> (model, ask)`,
`premise_of(answer) -> str`, and writes `narrator_view`, `player_view`, `author` once.
`SceneEngine.author` overrides only to add its `packs.select` line. `Panel.portrait: bool` set by
`character_panel`; the page reads it.

**Feature impact.** None; `tests/engines/test_views.py` and `test_scene_bar.py` pin the outputs.

**Size.** −110/+60. Half a day.

**Decision.** None.

---

## 6. State owns its own mutation

**Plain words.** Four places change the game's log or the party from outside the object that holds
them. Move each onto its owner, as CLAUDE.md says.

**Now.**
- `Engine.close` (`seam.py:383-402`) builds an `Exchange` from draft fields and appends to
  `draft.log[-1].exchanges`; `Engine.open_chapter` (l.404-409) pops and appends chapters.
- `World.leave_party` is abstract (`base.py:214`) while `join_party` is concrete; both
  implementations are "look up member, `self.part(member)`" (`scenes/world.py:491`,
  `rooms/world.py:226`).
- `SceneWorld.kill` (l.481) and `RoomWorld.kill` (l.387) share resolve → refuse if dead → drop
  from party → `alive = False` → "You are dead"/"{name} is dead" card; rooms also drops carried items.
- `SceneDraft`/`NextDraft` are `Mutable` (`scenes/tools.py:41`) though no code assigns their fields.

**Become.** `Game.close(lines, facts, *, words, mark, proposal)` and `Game.open_chapter(title,
focus)` in `core/model.py`; `Engine.close` = `draft.close(...); return self.land(draft)`. Base
`World.leave_party` via `member_of` + `UNKNOWN_ID`. Base `World.kill` on an abstract
`require_present(entity_id)` plus a `fallen(actor) -> list[Fact]` hook (rooms drops items there).
`SceneDraft(Frozen)`.

**Feature impact.** One refusal string: scenes `leave_party("player")` says "unknown id 'player'"
instead of "does not travel with the player".

**Size.** −30/+18, plus ~20 moved. 2 h.

**Decision.** None.

---

## 7. Meanwhile: the world keeps the clock, the tool resolves the ids

**Plain words.** The "time passes offscreen" clock is spread over six files, and the room world
does the tool's id-lookup job itself.

**Now.** Clock: `World.turns_played/meanwhile_due/count_turn/disarm` (`base.py`),
`Engine.meanwhile_turns/tick/disarm` (`seam.py`), `RoomEngine.tick` override, `Settings.meanwhile`,
`GameService.meanwhile` → `Turn.finish(enabled=)`, `Runtime._resumed` disarm. Tool:
`RoomWorld.meanwhile(args: Meanwhile)` (`rooms/world.py:337-385`) takes the tool model, looks up
npcs, items and places itself, and is why `rooms/world.py` imports `rooms/tools.py`. CLAUDE.md: the
engine tool resolves ids; the world changes fields.

**Become.** `World.tempo: ClassVar[int]` per world class (scenes 6, Tunnel Goons 4);
`World.tick(*, counted)` owns count-and-arm; `RoomWorld.tick` overrides to skip when nothing is
offscreen and to spend an armed turn. `Engine.tick/disarm` stay as one-line pass-throughs (the app
knows no world shape); `Engine.meanwhile_turns` and the `RoomEngine.tick` override go.
`RoomEngine.meanwhile(draft, args, _rng)` resolves the three pairs and calls
`world.walk_offscreen(npc, place)`, `world.drift_item(item, place)`, `world.shut_way(start, end)`,
`world.spend_meanwhile()`. Atomicity unchanged (`Turn.apply` discards a refused candidate).

**Feature impact.** None.

**Size.** −15 net. 2 h; `test_rooms.py:205-239` pins every refusal.

**Decision (tool shape).**
- (a) One `meanwhile` tool with three optional pairs, as now. Recommended unless the master is seen
  fumbling the pairs.
- (b) Three tools (`walk_offscreen`, `shift_offscreen`, `shut_way`), each gated by `meanwhile_due`,
  each disarming. Simpler schema; the player may see two "Elsewhere" cards in one turn.

---

## 8. The save copies nothing from the scenario it does not need

**Plain words.** Every save file carries a copy of the scenario's source text (up to 48 KB) and a
copy of its title, premise and scope. The source is read once per world-growth request; the copy of
the meta exists so a changed scenario file can be detected.

**Now.** `World.source` (`base.py:177`) is filled by both `opening` classmethods from
`scenario.source`, saved inside `payload` on every save, read only by `Engine.render_request`
(`seam.py:337`). `Game.scenario: ScenarioMeta` is a copy; `ScenarioMeta.check_drift` is called by
`launch._save_option` and `Runtime._resumed`; `render_master` and `ui/game.py` read the copy.

**Become.** `Engine.advance(draft, request, source, worldsmith)` and `render_request(draft, source,
...)`; `GameService._grow` passes `self.scenario.source`; both `opening` classmethods lose the
parameter; `World.source` deleted.

**Feature impact.** Save shape changes (stale by policy). Saves shrink.

**Size.** −12. 30 min.

**Decision.**
- (a) Source not saved at all (as above). Recommended.
- (b) Move it to `Game.source`, set in `Engine.begin`. −8/+3; still saved.
- (c) Also drop the `Game.scenario` copy: `Turn.begin` takes `ScenarioMeta`, `render_master` and
  the page read it from the session's scenario; delete `check_drift`, `with_premise`, the drift
  branch of the launcher. −25 more. Behaviour change: editing a scenario file no longer invalidates
  its saves; the launcher lists a save by ids alone.

---

## 9. Runtime and GameService: one job each, no back-reference

**Plain words.** `Runtime` is five things (builder, spawner holder, one-writer gate, session cache,
author). `GameService` is orchestration plus presentation plus persistence and points back at
`Runtime` for one method. The in-flight guard is a string the UI compares.

**Now.** `Runtime.admitted/admit/turn/require_turn` (`runtime.py:314,334-352`); `GameService.gate:
"Runtime"` (l.79) used only for `admit`; `mcp.endpoint(runtime)` uses only `turn/require_turn`.
`IN_FLIGHT_HERE/ELSEWHERE` raised as `Refusal(text)` and compared as text in `ui/game.py:578,598`.
`launch._save_option` and `Runtime._resumed` spell the "this save resumes this game" rule twice.
`GameService` holds `media`, `reader`, `tasks`, `_speaking`, `chatter`, `rng`, flags, and
`scene_art/icon/newest_clip/illustrate/speak/_present/presents` beside `open/play/act/_turn/_grow/
interject/restart/save`; `open`, `_grow`, `interject` each spell narrate → close → save → present.
`Runtime.spawn: Callable[[Settings], Spawner]` exists for 15 test lambdas; `GameService.speaking`
and `Tasks.settled` have no reader in `src`.

**Become.**
- `Gate` dataclass (`admitted`, `admit()`, `turn`, `require_turn()`); `Runtime.gate`,
  `GameService.gate: Gate`, `mcp.endpoint(gate)`.
- `class Busy(Refusal)` with `elsewhere: bool`; the page does `except Busy`.
- `check_resumes(state, target, meta)` in `launch.py`, called from both sites.
- `Presentation` (media, reader, tasks; `present`, `scene_art`, `icon`, `newest_clip`, `enabled`)
  owned by `GameService` as `show`; the page calls `session.show.icon(...)`.
- `GameService._tell(draft, facts, prompt, *, mark, words, proposal)` shared by `open`, `_grow`,
  `interject`.
- `Runtime(settings, spawner: Spawner | None = None)`; delete `speaking`, `resumed`; keep
  `Tasks.settled` only as the documented test hook.

**Feature impact.** None.

**Size.** −40 src, −20 tests; ~60 lines moved. Half a day.

**Decision.** None.

---

## 10. The rooms family has one engine

**Plain words.** `RoomEngine`/`RoomWorld` are generic over exactly one engine (Tunnel Goons) plus a
test double. CLAUDE.md says no abstraction until two things need it; IDEAS.md #18 (Maze Rats) is a
future need.

**Facts.** `RoomEngine[P, N, G, K]`, `RoomWorld[P, N](Dungeon[N], World[P, N])`, `Dweller`,
`MapDraft[N]`, `RegionDraft[N]`, `starting_items` (one override). Folding saves ~40-50 source lines
(generic params, `Dweller`/`Npc` split, `world`/`member` attrs, the hook); the map logic itself
(497 lines) stays either way. `tests/engines/test_rooms.py` (409) and `tests/support/sixth.py` (105)
are written against the family. The scene family has two real users and stays.

**Decision.**
- (A) Keep, and adopt the rule "no new room-only hook until a second room engine lands".
  Recommended now: the family boundary is where map integrity is tested engine-agnostically, and
  folding costs ~500 test lines for ~50 source lines.
- (B) Fold `rooms/*` into `tunnelgoons/*`: `Npc` gains `place`; params, hook and `sixth.py` go;
  `test_rooms.py` is rewritten against Tunnel Goons. Honest to CLAUDE.md, expensive.
- (C) Demote: keep `rooms/world.py` (the map and its checks, tests intact), delete `RoomEngine`,
  `TunnelGoonsEngine` subclasses `Engine` directly with the map tools inline. −40, middle ground.

---

## 11. Every model-facing string has one home; role logic sits with the roles

**Plain words.** A prompt edit is a treasure hunt: prose the models read is spread over four kinds
of module per family and three places in the app. The re-prompt loop lives in the process-spawning
module.

**Now.** Per family: `scenes/engine.py` (`OPENING`, `MOVING_ON`, `MEANWHILE_NUDGE`),
`scenes/world.py` (`WAY_OFFERED`, `SCENE_LEFT`), `scenes/worldsmith.py` (`CROSSING`, `COMPLICATING`,
`TURNING`), `scenes/tools.py` (descriptions), `loner3e/engine.py` (`TWIST_NOTE`, `DEFEAT_NOTE`),
`rooms/engine.py` (`ELSEWHERE`), `rooms/world.py` (`NOTHING_OFFSCREEN`, `MOVES_OFFSCREEN`,
`MOVED_CARD`), `engines/tools.py` (`HIRED`, `SIGNED_ON`, `UNWRITTEN_CAST`, plus 24XX-only
`DropItem`/`AskWorld`), `engines/seam.py` (`SOURCELESS`, `SCOPELESS`), `engines/packs.py`
(`HEAD_ASK`, `BODY_ASK`). App: `OPENING_NARRATION` in `runtime.py`; `master.md` + `render_master` in
`turn/`; `narrator.md`/`interjection.md` in `app/prompts`; `ask`, `worldsmith`, `Spawner`, `Tools`
in `spawn.py` after the `DRIVERS` constant; `run_cli` and `run_builtin` each own a timeout, the
"answered nothing in Ns" refusal and the info log; `RoleRunner.run` only dispatches.

**Become.** Rule: `worldsmith.py` holds everything the worldsmith reads; `tools.py` holds
everything the master reads (descriptions and the `Fact` traces that are instructions); nothing
model-facing in `world.py`/`engine.py`. 24XX-only pieces move to `twentyfourxx/`. App:
`OPENING_NARRATION` → `roles.py` (or `prompts/opening.md`); `ask`/`worldsmith` → `roles.py`;
protocols to the top of `spawn.py`; `RoleRunner` → `spawn.py` beside `Spawner`, owning the one
timeout, refusal and log line; `run_cli`/`run_builtin` return a result and a detail string.

**Feature impact.** None.

**Size.** −15 net (the hoist); the rest moved.

**Decision (master prompt).**
- (a) `master.md` and `render_master` stay in `turn/`. Recommended: the master's picture is what
  `Turn` plays against.
- (b) Move both to `app/roles.py` so all three role renders sit together and `turn/` is mechanics
  only.

---

## 12. Vocabulary: one word per thing, and the rules written as the code lives them

**Plain words.** "Draft" means two things. Tool arguments name the same idea five ways. `line` is a
property in three classes and a method in three others. Two CLAUDE.md rules are broken by the code
in ways that are right, so the rules should change.

**Now.**
- `draft` is the `Game` working copy everywhere and also `SceneDraft`, `NextDraft`, `MapDraft`,
  `RegionDraft`, `SheetDraft`, `AbilitiesDraft`, `SpecialtyDraft`, `OriginDraft` (the worldsmith's
  typed proposals). `SceneEngine.install(self, draft: G, scene: SceneDraft[C])`.
- Who-fields: `entity_id` (Loner tools, seam tools, `TakeLead`), `actor_id` (TG/24XX, Loner `Roll`),
  `against` (TG `Roll`) vs `opponent_id` (Loner `Roll`), `to` (`MoveItem`) vs `to_id` (`Move`,
  `UnlockWay`), `dweller_id/dweller_to`.
- `Loner3eBlock.line`, `TunnelGoonsBlock.line`, `TwentyfourxxBlock.line` are properties;
  `Specialty.line()`, `Thing.line()`, `RoomWorld.line()` are methods. `Gear.broken_message`/
  `harmless_message` are properties formatting a constant. `Thing.headline` duplicates
  `Subject.headline`.
- CLAUDE.md "names shown to a role... are id/label/detail; things saved to disk keep name/brief":
  shipped pack files hold `label/detail` tables beside `name/brief` blocks in one JSON; every
  scene, scenario and engine has a `title`. CLAUDE.md's property rule would make ~40 render
  methods properties; the code draws an unwritten, sensible line instead.
- `SceneDraft`/`NextDraft` live in `scenes/tools.py`; `MapDraft`/`RegionDraft` in `rooms/world.py`.

**Become.**
- Tool arguments: `actor_id` for who acts, `target_id` for who is acted on, `to_id` for a
  destination, `_id` suffix on every id field. Loner's `entity_id` → `actor_id`. `rules.md` files
  follow; schema and prompt goldens regenerate. Impact: schema text only.
- `line()` a method in all six; the two `Gear` messages become module constants formatted at the
  raise sites; `Thing.headline` built from `self.subject().headline`.
- CLAUDE.md: "A property is a scalar or attribute-like read; anything that renders text or builds a
  collection is a method." and "`id`/`label`/`detail` for a pick, an option or a panel row, on disk
  too; `name`/`brief` for an entity; `title` for a scene, a scenario, an engine."
- `SceneDraft`/`NextDraft` move to `scenes/world.py`.

**Feature impact.** None for the player; the master sees one argument vocabulary across engines.

**Size.** ±0 code; 3 h including goldens.

**Decision (the word "draft").**
- (a) Rename the worldsmith's classes to `*Proposal` (~60 mechanical sites; no class name reaches
  a prompt or a file; matches README/CLAUDE.md "typed proposals"). Recommended.
- (b) Leave the collision.

---

## 13. UI trims: no engine knowledge above the seam, and one file per job

**Plain words.** The UI reaches into engine internals in four places, registers media routes
through a module-global dict, and `ui/game.py` (709 lines) mixes page state with transcript
rendering.

**Now.** `ScenarioForm.seeds` reaches `engine.packs.seeds(engine.select_packs(...))`
(`create.py:562-567`); `_drop_stale` (the legality rule's complement) lives in `ui/create.py` and is
tested against engine steps; `GamePage.sidebar` decides the portrait by `index == 0`;
`widgets.media_url` hashes each directory into a lazily mounted route kept in `_media_routes`;
`_register_pages` defines seven nested page functions with seven pyright ignores and is imported
privately by `qa/server.py`; the three create forms repeat the same header/body/intro/card/engine
select scaffold and two register the upload's `on_delete` with a pyright ignore; `GamePage` holds
25 attributes and does layout, transcript rendering (`chat`, `live_turn`, `journal`, `_card`,
`_dice_group`, `_bubble`, `_inline_status`), polling (`Observed`, `whole_page`, `_dice_landed`) and
actions.

**Become.**
- `Engine.seeds(supplements) -> tuple[str, ...]` (3 lines); `drop_stale` beside `check_picks` in
  `core/creation.py` with its test in `tests/core`; `Panel.portrait` (proposal 5).
- Three static mounts at startup (`/media/saves`, `/media/scenarios`, `/media/characters`) on the
  settings roots; `media_url(path)` becomes a relative-path join; no global.
- `register_pages(runtime)` public, using `ui.page(...)(partial(...))`; only the game and pack
  pages keep a small function for the refusal page.
- `_form_page(runtime, engine_id, *, eyebrow, title, lead)` context manager; `DocumentUpload.build`
  registers its own `on_delete`.
- `ui/transcript.py` with the pure renderers as free functions (they render at the edge);
  `GamePage.chat/live_turn/journal` become five-line refreshables. `game.py` lands near 520.

**Feature impact.** Image URLs change shape (not persisted anywhere). Nothing else.

**Size.** −50 src net; ~180 moved. Half a day.

**Decision (polling).**
- (a) Keep `Observed` diffing (rebuilds `PlayerView` every second per tab). Recommended: simple,
  correct across tabs.
- (b) `GameService.version` bumped on every save/phase change/`Turn.apply`; the page compares one
  int. −25 lines, less CPU per open tab; `Observed`/`whole_page` go.

---

## 14. Tests: delete what the goldens already pin, parametrize the copies

**Plain words.** About 450 test lines test prose already pinned by goldens, or repeat one shape
six times. One script and its test exist for a conversion that ran once.

**Now.**
- Prose/wiring tests CLAUDE.md says not to write, already covered by
  `tests/core/fixtures/prompts/*`: `test_context_boundary.py` (4 tests asserting `"YOUR PARTY:\nyou
  are Kael"`, `"- Concept: ..."`, section order), `test_roles.py` (3 tests asserting
  `endswith(schema_text(...))`).
- Copy-pasted shapes: `test_launcher.py` six "write one bad save → skipped" tests; `test_game.py`
  24 `spy_notify`/`Client`/`try…finally client.delete()` blocks and five toast tests differing in
  one exception; `test_spawn.py` three 12-line stub drivers differing in one tuple;
  `test_config.py` five `base_url` tests.
- `tests/support`: `take()` repeats `play_turn`'s action branch (used once); `fifth.installed` and
  `sixth.installed` duplicate 12 lines; `open_game` is a 10-line pass-through of `open_table`;
  `ScriptedSpawner.resumed` is recorded and never read.
- `scripts/srd_packs.py` (390 lines) converted the Loner SRD markdown to the twelve committed pack
  files; `tests/scripts/test_srd_packs.py` (156) and `tests/fixtures/srd/AP01_fantasy.md` keep it
  alive, plus two `pyproject` entries.
- `qa/agents.py` (257) and `tests/support` (~340) both implement scripted roles.

**Become.** Delete the 7 prose tests (leak tests in the same files stay). One `parametrize` per
shape; a `page` fixture and a `notified` fixture in `tests/ui`; one `_StubDriver(argv)`. Delete
`take`, `resumed`; `support/engine_dir.py: install_engine_dir(tmp_path, *, srd)`; `open_game =
partial(open_table, ...)`.

**Feature impact.** None; drift still fails through the goldens.

**Size.** −95, −170/+30, −35. 3 h.

**Decisions.**
- `scripts/srd_packs.py`: (a) delete script, test, fixture and the two `pyproject` entries; git
  keeps it for a re-run (−560). Recommended by CLAUDE.md's "do not build for future needs".
  (b) Keep for a Loner SRD revision.
- Scripted roles: (a) leave both. (b) `qa/` imports one implementation from `tests/support`
  (−150; pytest `pythonpath` already includes `tests`). Low priority.

---

## 15. Small cuts, one PR

**Plain words.** Two dozen one-file changes, each obvious once seen. No behaviour change unless
marked.

- `RoleSettings.for_name` and `Providers.for_name`: two 8-line `match` blocks → `getattr` or a
  dict property. −12.
- `Turn.narrates()`/`landed()` → properties (no argument, no side effect, own fields).
- JSON entry points: `parse_unique` renamed `parse_text` and made the one entry for our own files
  and model answers; bare `parse_json` kept for provider replies. Or one docstring line saying
  which to use where. ±0.
- `PackStore` (`core/io.py`) folded into `PackSet` (`written_dir`, `write`); `Runtime.packs` and the
  two-source id computation in `new_pack` go. −15.
- `Look`/`DiceLook` flattened to one palette mapping; the three `look.json` spell `game-die-body/
  ink/glow` directly; `set_look` is one merge. −15.
- `Engine.master_tools`: a bound method only where an engine overrides it (`kill`); every other
  two-liner a lambda. −8.
- `PackSet.installed` as a `@property` instead of `object.__setattr__` in `__post_init__`. −3.
- `Engine.validate` runs `packs.select` (the defined-id overlap scan) on every `land`, i.e. every
  tool call; run it in `restore`/`begin` only. Less work per call.
- `Loner3eEngine.twist_table()` recomputed per twist; compute once into `self.twists`. −4.
- `items_from_kits`: `Gear(**kit.model_dump())`. `CrewSheet.gear_text()` shared by `carried()`,
  `sheet_rows()`, `preview_character`; `GoonSheet.rows(*, carried=)` instead of patching the
  Inventory row by label. −14/+6.
- `Engine.tool(name) -> MasterTool` with one miss refusal, used by `Engine.answer` and `Turn.call`.
  One refusal string changes.
- `launch._save_option` routes, then `restore` re-reads the header; drop the third decode. −4.
- `Engine.pack_of(source=)` receives `origin`; rename the parameter, keep the on-disk field.
- `PendingOption` docstring says "not every name is a tool"; `Engine.answer` refuses any non-tool.
  Fix the docstring. `Game.generation` is `exclude=True`, so `restore`'s refusal fires only on a
  hand-edited file; say so.
- Settings page: `description=` on `RoleConfig.max_rounds` (API only) and `timeout` (whole process
  on a CLI), shown as a hint by `_label`. +3.
- `source_max_bytes` → `SOURCE_MAX_BYTES` in `core/source.py`. Behaviour: the undocumented env key
  stops working. Decision: constant (recommended) / keep the setting.
- Hire stub: `Engine.hires: bool` plus `write_sheet` whose default body raises `ValueError`.
  Decision: (a) keep (two users, 35 lines) / (b) the two hiring engines add the hire tool and
  request themselves through a `hire_tools()` helper; the flag and the raising default go. −10.
- `GameService.interject` (method) and `roles.interject` (function) share a name across layers;
  rename the method `let_party_speak`.

**Size.** ~−90 net. Half a day.

---

## Appendix: concept inventory

One line per concept: where, verdict, which proposal touches it.

| Concept | Where | Verdict |
|---|---|---|
| `Refusal` vs bug | core/entities | keep |
| `Frozen`/`Mutable`/`Loose`/`Echoed`/`Configured` bases | core/entities, config | keep |
| `Slug`, `content_id`, `EngineId` | core/entities | keep |
| `parse`/`parse_json`/`parse_unique`/`read_model`/`decode`/`routed` | core/entities, io | simplify (15) |
| `Fact`/`DiceEvent`/`Rolled`/`cards`/`traced`/`roll` | core/facts | keep |
| `Line`/`SpokenLine`/`Narration`/`Interjection` | core/play | keep |
| `DecisionOption`/`PendingOption`/`PendingDecision`/`Answer` | core/play | keep; docstring (15) |
| `Exchange`/`Chapter`/`Mark`/journal | core/play, ui | keep; `Game.close` owns the append (6) |
| `Game[P]`/`Scenario[P]`/`Character[P]` | core/model | keep; generics (2), copies (8) |
| `ScenarioMeta`, `check_drift`, `with_premise` | core/model | keep; decision (8c) |
| `PackSelection` | core/model | remove (1) |
| `EngineHeader`/`SheetHeader`/`CharacterHeader` | core/model | keep |
| `Generation`/`Request`/`Written` | core/model, seam | keep |
| `WorldsmithAnswer`/`Check` | core/model | keep |
| Draft / commit / `Turn.apply` | core/model, turn | keep; rename proposals (12) |
| `MasterTool`/`master_tool`/`NoArgs`/`schema_of` | core/tools | keep; lambda rule (15) |
| `Sections` + prompt helpers, history rendering | core/prompt | keep |
| Source document reader, PDF | core/source | keep; constant (15) |
| `NarratorView`/`PlayerView`/`Panel`/`PanelRow`/`Subject`/`Companion` | core/views | keep; builders lifted (5) |
| `Look`/`DiceLook` | core/views, ui/theme | flatten (15) |
| `CreationStep`/`Picks`/`picked*`/`check_picks`/`MANY`/`multiple` | core/creation | simplify (4), `drop_stale` in (13) |
| `Gauge`, `Thing`, `Person`, `Sheet`, `Sheeted` | engines/base | keep |
| `World[P, M]`, party, join/part, kill, leave_party | engines/base | base owns more (6) |
| Meanwhile clock and tool | base, seam, rooms | simplify (7) |
| Hire (`hires`, `write_sheet`, `write_hire`) | seam, tools | keep; decision (15) |
| Reveal / `known` / leak checks | engines/base | keep |
| `Engine` seam | engines/seam | slim (1, 2, 4, 5, 6, 8) |
| `SceneEngine` family | engines/scenes | keep |
| `RoomEngine` family | engines/rooms | decision (10) |
| `SceneRun`/`SceneDraft`/`NextDraft`/`next_scene` | engines/scenes | keep; frozen, moved, renamed (6, 12) |
| `Dungeon`/`Place`/`Way`/`Dweller`/`Prop`/`MapDraft`/`RegionDraft` | engines/rooms | keep |
| `Pack`/`PackSet`/`Names`/`Location` | engines/packs | keep; `PackStore` folded in (15) |
| `PackHead`/`PackBody`/`Labelled`/`pack_fields`/`options()` | engines/packs, */worldsmith | keep; decision (3) |
| Pack edit codec, `EditField`, `engine_fields/values/edited` | packs, seam, engines, ui | remove (3) |
| Cast blocks (`*Block`) ×3 | */worldsmith | keep (three 25-line blocks read fine) |
| Registry | engines/registry | keep |
| `Turn` | turn/run | keep; properties (15) |
| Notes from the rules | core/model, turn | keep |
| `Spawner`/`RoleRunner`/`Driver`/`run_cli`/`final_message` | app/spawn, roles | keep; hoist and move (11) |
| Built-in completion loop | app/builtin | keep |
| `ask` re-prompt once, `worldsmith` partial | app/spawn | move to roles (11) |
| `Tools` protocol | app/spawn | keep (test stubs are the second user) |
| MCP endpoint, `MountedLifespan` | app/mcp | keep; takes `Gate` (9) |
| `Runtime`, `GameService`, `Tasks` | app/runtime | split (9) |
| `LauncherCatalog`/`CatalogEntry`/`PackEntry`/`SaveOption`/`LaunchTarget` | app/launch | keep; `check_resumes` (9) |
| `Library`/`FileStore` | core/io | keep |
| Media, Speech, `Claims`, `post_bearer` | app | keep separate; wrapped in `Presentation` (9) |
| Settings + reflection form | config, ui/settings | keep; hints (15) |
| Interjection / proposal / chattiness | runtime, roles, views, ui | keep (widest footprint per feature, README-level behaviour) |
| `GamePage`/`Observed` polling | ui/game | split (13); decision on polling |
| `DiceSound`, theme, widgets, create forms, `PackEditor`, `SettingsForm` | ui | keep; trims (13) |
| Goldens (prompts, schemas, turn) | tests | keep |
| `tests/support` harness | tests | dedupe (14) |
| qa harness | qa/ | keep; decision (14) |
| `scripts/srd_packs.py` | scripts, tests | decision (14) |
