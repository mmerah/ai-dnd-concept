# Simplification proposals

Six independent reads of the whole codebase (five Opus reviewers with different lenses plus the
lead) produced about 75 proposals. This file keeps the 15 that were raised most often or that
remove the most code for the least risk. Everything else is parked at the end.

Baseline: 10,432 lines in `src/aidm`, 759 tests green, ruff and basedpyright clean.

Status legend: `open` (not yet decided), `accepted`, `refused`, `trial` (a Sonnet subagent is
implementing it on a branch to measure the real diff), `reworked`, `dropped` (trial showed no
net gain).

The overall verdict from every reviewer: the layering, the `Refusal` rule, the `Fact`/`told`
gate, `Turn.apply`, the goldens and the boundary tests are good and stay. The problems are
vocabulary (one word for several things, several words for one thing), one family with one
child, and copy-paste between the two hiring engines.

---

## Group 1: the engine layer

### 1. Fold the `rooms/` family into `tunnelgoons/`

**Status:** open. **Raised by:** A, C, D, lead (4 of 6).

**Plain English.** There are two "families" between the abstract `Engine` and the three real
engines. `scenes/` has two children (Loner, 24XX) and earns its place. `rooms/` has exactly one
child (Tunnel Goons) and costs 836 lines, three generic type parameters and six generic helper
signatures to stay reusable for a second dungeon engine that does not exist. CLAUDE.md says "do
not add an abstraction before two things need it".

**Code change.**
- Move `engines/rooms/{engine,world,tools,worldsmith}.py` into `engines/tunnelgoons/`
  (world.py would be about 680 lines; split into `world.py` and `map.py` if that is too long).
- Delete `Dweller`; `Npc` gains `place: Slug` directly.
- Drop `[N: Dweller]` from `Dungeon`, `MapProposal`, `RegionProposal`, `RoomWorld` and from the
  six `check_*`/`_*_unmet` functions in `rooms/worldsmith.py`.
- `TunnelGoonsEngine(Engine[TunnelGoonsWorld, TunnelGoonsPack])` directly; `RoomEngine` and its
  `member: type[N]` go away.
- `rooms/rules.md` and `rooms/worldsmith.md` move under `tunnelgoons/`; `Engine.family_dir`
  stays for `scenes/` (Tunnel Goons sets `family_dir = directory` or the attribute becomes
  optional).
- `tests/engines/test_rooms.py` re-points its imports.

**LOC.** About -120 to -150. **Feature impact.** None: same tools, same prompts (the two `.md`
files concatenate in the same order), same saves. **Risk.** Medium, mechanical. `RoomWorld`
has two `model_validator` hooks and an `entity()` `super()` call whose MRO order must be kept.

**Decision needed.**
- (a) Full fold, as above. Most clarity, biggest diff. README wording about `RoomEngine` is
  updated. IDEAS 18/19 (Maze Rats, Pokémon) may want a map engine one day; re-extracting a
  family when a second child lands is about an hour's work.
- (b) Keep the `rooms/` package but delete `Dweller` and every `[N]`/`[P, N]` parameter. About
  -50 lines, near-zero risk, leaves a one-child family standing.
- (c) Leave it as a deliberate bet on IDEAS 18/19, and say so in a comment at the top of
  `rooms/engine.py`.

### 2. One character class for Tunnel Goons, and `World[M]` instead of `World[P, M]`

**Status:** open. **Raised by:** D (and implied by 1).

**Plain English.** Tunnel Goons is the only engine with two person classes: `Goon` for the
player and `Npc` for everyone else. They duplicate `rows()`, `level()`, `hp`, `required()` and
sheet handling, need a `sheet_of()` bridge with an `isinstance`, and force a second type
parameter onto `World` that Loner and 24XX fill with the same type twice.

**Code change.**
- Merge `Goon` and `Npc` (`tunnelgoons/world.py`) into one `Goon(Person)` with `place: Slug`,
  `hp: Gauge`, `sheet: GoonSheet | None = None`, `kit: tuple[str, ...] = ()`.
- `TunnelGoonsWorld` gains the validator 24XX already has: the player carries a sheet.
- Delete `sheet_of()` and the duplicated `rows`/`level`/`required` pairs.
- `World[P: Person, M: Person]` becomes `World[M: Person]` in `engines/base.py`;
  `SceneWorld[C](World[C])`; `RoomWorld[N](Dungeon[N], World[N])` (or, after 1, plain classes);
  `Engine[W: World[Any], K]`.

**LOC.** About -55 to -70. **Feature impact.** Old Tunnel Goons saves become stale (the saved
shape changes). Saves have no version, so that is the documented behaviour. **Risk.** Medium.
`roll` and `level_up` call `require_sheet()` on the player too; `RoomWorld.kill`'s `P | N`
annotation simplifies.

**Decision needed.**
- (a) Merge the classes and collapse `World[P, M]`. Recommended.
- (b) Merge the classes only; keep `World[P, M]`. Smaller blast radius, keeps a useless
  parameter.

### 3. One hire flow instead of two copies

**Status:** open. **Raised by:** A, B, D, E, lead (5 of 6).

**Plain English.** Tunnel Goons and 24XX both let the player hire someone. The `hire` tool
(docstring included), the `advance` override, the head and tail of `write_hire`, and the world
methods `require_actor`/`require_hireable` and the person methods `hired`/`require_sheet` are
byte-identical between `tunnelgoons/` and `twentyfourxx/`. A model-facing docstring that exists
twice will drift.

**Code change (low-risk half).**
- `World` (`engines/base.py`) gains `require_actor(actor_id)` and `require_hireable(entity_id)`;
  delete both from `TunnelGoonsWorld` and `TwentyfourxxWorld`. `Person` gains
  `hired -> bool` (False by default) so `World` can ask.
- `engines/tools.py` (which already owns `HIRE`, `HIRE_PENDING`, `SIGNS_ON`, `SIGNED_ON`,
  `HIRE_UNWRITTEN`, `NO_HIRE_TARGET`, `Hire`) gains two free functions: `file_hire(draft,
  member, terms) -> list[Fact]` (the tool body) and `signed_on(world, member, summary) ->
  Written` (the six-line tail). Each engine's `hire` and `write_hire` shrink to the prompt, the
  answer model and the `sign_on` call.

**Code change (full half).** A `Hiring` engine mixin in `engines/hiring.py` owning the `hire`
tool, the `HIRE` branch of `advance` and the `write_hire` skeleton, with one abstract hook
`write_sheet(draft, member, terms, worldsmith) -> str`. `TunnelGoonsEngine(Hiring, RoomEngine)`
and `TwentyfourxxEngine(Hiring, SceneEngine)` implement only `write_sheet`.

**LOC.** Helpers: about -45 (src) and -40 (tests, `test_hire_tool.py` stops parametrising the
duplicate). Mixin: about -70. **Feature impact.** None. With the mixin, `tools_of` walks the MRO
so the `hire` tool may move one slot in `master_tools.json` goldens. **Risk.** Helpers: low.
Mixin: medium (a second inheritance axis; pydantic generics on `Person` if `hired` moves there
as a field).

**Decision needed.**
- (a) Free helpers plus the `World` methods. Safe, keeps a four-line `hire` per engine.
- (b) Helpers plus the `Hiring` mixin. Kills the duplicated docstring; adds a mixin.

### 4. One table for worldsmith operations; delete the unreachable branch

**Status:** open. **Raised by:** A, B, D, E, lead (5 of 6).

**Plain English.** Each engine says twice which world-writing operations it supports: once as
`unwritten`, a dict of failure facts, and once as an `if request.operation == ...` chain in
`advance`. The chain ends in `raise ValueError(WRITES_NO)`, which cannot fire because
`Engine.validate` already refused an unknown operation. A test exists whose only job is to stop
the two lists drifting.

**Code change.**
```python
# engines/engine.py
@dataclass(frozen=True, slots=True)
class Operation:
    write: Callable[[AnyGame, Commission, WorldsmithAnswer], Awaitable[Written]]
    unwritten: Fact
```
`Engine` gains `def operations(self) -> Mapping[Slug, Operation]` (a method, so subclass
overrides of the writer methods are honoured). `SceneEngine` returns `{DEPARTURE:
Operation(self.depart, WAY_UNWRITTEN), COMPLICATION: Operation(self.complicate,
COMPLICATION_UNWRITTEN)}`; `RoomEngine` returns `{EXTEND: ...}`; the hiring engines return
`{**super().operations(), HIRE: Operation(self.write_hire, HIRE_UNWRITTEN)}`. `Engine.advance`
becomes concrete and four lines; `validate` checks membership; `runtime._grow` reads
`engine.operations()[op].unwritten`. `WRITES_NO`, the four `advance` overrides and the drift
test go.

**LOC.** About -20 (with 3b it is -30). **Feature impact.** None. **Risk.** Low.

**Decision needed.**
- (a) The table, as above. One concept where there were two.
- (b) Cheapest: keep `unwritten` and the if-chains, delete only the unreachable `raise` lines
  and move the `HIRE` branch into a concrete `Engine.advance` base with `super()` fall-through.
  About -12, no table.

### 5. One vocabulary for the worldsmith request, and four names that say what they do

**Status:** open. **Raised by:** A, B, C, E, lead (5 of 6).

**Plain English.** The one flow that grows the world is called a commission, a request, an
operation, a growth and a "telling" depending on the file. Four other names say the wrong
thing: `Engine.over` returns the ending message, not a boolean; `Engine.answer` plays an option;
`render_request(answer=...)` takes a schema; `Written.telling` is the narrator prompt.

**Code change (pure rename, compiler-checked).**
- Pick `commission` everywhere: `request: Commission` parameters become `commission`,
  `Engine.render_request` becomes `render_commission`, `GameService._grow` becomes
  `_write_commission`, `REQUEST_WAIT` becomes `COMMISSION_WAIT`.
- `Written.telling` becomes `narrator_prompt` (or `Written` becomes `Advance` with a
  `narrator_prompt` field; `Written` also collides with `PackSet.written` and the
  `written: Path` constructor argument, which becomes `player_packs`).
- `Engine.over` and `PlayerView.over` become `ending`.
- `Engine.answer(draft, chosen, rng)` becomes `play_option`; the `answer: type[BaseModel]`
  keyword on the render methods becomes `answer_model`.
- `Engine.render_worldsmith` becomes keyword-only after `source`; today every call is six bare
  positional arguments.
- `SceneWorld.offer()` / `Scene.offered` become `offer_way_on()` / `way_offered`.

**LOC.** About +2. **Feature impact.** None (`Game.commission` is `exclude=True`, so no save or
golden moves). **Risk.** Very low.

**Decision needed.** Only the noun: `commission` (the type already says it) or `request`
(README says it). Recommended: `commission`, because `request` is spent on HTTP.

---

## Group 2: engine families and packs

### 6. Two hooks so 24XX stops copy-pasting its family

**Status:** open. **Raised by:** A, B, D, E (4 of 6).

**Plain English.** Both scene engines add rows to the master prompt and panels to the page.
Loner calls `super()` and appends. 24XX re-types all eight sections and all seven panels of
`SceneEngine` so it can insert GEAR / THE JOB / THE SHIP and two panels in the middle. When the
family changes, one child follows and one silently does not.

**Code change.** `SceneEngine` gains `sheet_sections(state) -> Sections` (default `()`, spliced
after `YOU PLAY FOR`) and `sheet_panels(state) -> tuple[Panel, ...]` (default `()`, spliced
after the character panel). `TwentyfourxxEngine.master_sections` (16 lines) and `player_view`
(30 lines) become two short hook overrides. Loner's `master_sections` keeps its `super()` shape
or moves its glossary to a third hook `extra_sections` at the end.

**LOC.** About -32. **Feature impact.** None if the splice points match today's order; the
golden prompt fixtures under `tests/core/fixtures/prompts/twentyfourxx/` will catch any drift.
**Risk.** Low.

### 7. One cast-block shape in `packs.py`

**Status:** open. **Raised by:** D.

**Plain English.** Each engine declares its own "faction / person / monster" block class, its
own three pack fields, its own three body fields with the same `min_length=1, max_length=6`
descriptions, and its own `counts()`/`sections()` lines to print them. The three copies differ
only in the stat line, and 24XX spells "monsters" as "hostiles".

**Code change.** `engines/packs.py` gains `CastBlock(Frozen)` with `name`, `brief`, the
one-line validator, `stats() -> Rows` (default `()`) and `line()` via `block_line`. `Pack`
gains `factions`/`npcs`/`monsters: tuple[CastBlock, ...] = ()` plus their `counts()` and
`sections()` entries. A `CastBody(PackBody)` carries the three fields with shared descriptions.
Each engine narrows: `Loner3eBlock(CastBlock)` keeps its tags and drives; `TunnelGoonsBlock`
keeps `hp`; `TwentyfourxxBlock` keeps skills/items/hindrances and renames `hostiles` to
`monsters` (no shipped pack carries `hostiles`; `docs/24XX.md` follows).

**LOC.** About -70 to -90. **Feature impact.** The worldsmith's pack-body schema gets one shared
wording per list; Tunnel Goons block lines read `; hp: 8` instead of ` (hp 8)` in prompts.
Golden prompt fixtures shift. Shipped JSON keys are unchanged. **Risk.** Low-medium.

**Decision needed.**
- (a) As above, including `hostiles` to `monsters`.
- (b) As above but keep `hostiles` as 24XX's field name (an alias on the shared base).

### 8. Names for a person and a pick: `name`/`brief` and `label`/`detail`

**Status:** open. **Raised by:** E, A, lead.

**Plain English.** A thing in the world has `name` and `brief`. A pick in a list has `label`
and `detail`. They are the same two strings, and the code renames them back and forth:
`Thing.subject()` exists only to turn `name`/`brief` into `label`/`detail`, `Subject.row()`
renames them again, and `Subject` (a person standing in the room) inherits from
`DecisionOption` (a thing the player can click). Meanwhile `engines/packs.Labelled` is
`DecisionOption` minus the id.

**Code change.** Three options, ordered by size.
- (a) Rename `label`/`detail` to `name`/`brief` everywhere (`DecisionOption`, `Subject`,
  `Companion`, `PanelRow`, `CatalogEntry`, `PackEntry`, `CreationStep`). `Thing.subject()`
  becomes a field copy; `Subject.headline` reuses `Thing.headline`'s shape. `DecisionOption` is
  serialised inside every shipped pack JSON (15 files), so this is a content migration too.
  About -50 lines. Risk medium.
- (b) Only fix the class tree: rename `DecisionOption` to `Entry`, define `Entry(Labelled)` so
  it is literally `Labelled` plus `id`, and give `Subject` its own three fields (or a shared
  `Named` base in `core/entities.py`) so a person no longer is-a option. No content migration.
  About -10 lines. Risk low.
- (c) Leave the words; do nothing.

**Feature impact.** None for (b). For (a), pack JSON keys change; the pack editor page shows
the new keys. **Risk.** See options.

### 9. Pack authoring off `Engine`

**Status:** open. **Raised by:** A, E.

**Plain English.** `Engine` is the class you read to learn how a game is played. It has 40
methods and 17 class attributes. A quarter of it (`pack_of`, `author_pack`, `edited`,
`install_pack`, and the `pack`/`head`/`body`/`authoring` attributes) is about writing and
editing setting packs, which happens on another page and never during play.

**Code change.** A `PackAuthor[K]` frozen dataclass in `engines/packs.py` holding `pack_model`,
`head_model`, `body_model`, `authoring` and a `render` callable (the engine's
`render_worldsmith`), with `author(...)`, `edited(...)`. `Engine` exposes one `pack_author`
attribute; `Runtime.new_pack` and `rewrite_pack` call it. `install_pack` stays on `Engine`
because it swaps `self.packs`.

**LOC.** About 0 net (-55 in `engine.py`, +50 in `packs.py`); `Engine` drops to about 330
lines. **Feature impact.** None. **Risk.** Medium: `render_worldsmith` needs `family_dir`, so a
callable is threaded through.

**Decision needed.**
- (a) Extract `PackAuthor`.
- (b) Leave it on `Engine`; the class is cohesive by subject (this engine's data) even if not by
  use case. Then only delete the dead `head = PackHead` / `body = PackBody` defaults (all three
  engines override them).

### 10. Master prompt beside the other two role prompts; `turn` becomes one module

**Status:** open. **Raised by:** A, B, C (3 of 6).

**Plain English.** The narrator's and the party member's prompts are rendered in `app/roles.py`
from `app/prompts/`. The master's is rendered in `turn/run.py` from `turn/prompts/`. Nothing
explains the split, and it is the only thing keeping `turn/` a package.

**Code change.** Move `render_master` and `MASTER_ROLE` into `app/roles.py`; move
`turn/prompts/master.md` to `app/prompts/master.md`; delete `Turn.master_prompt()`;
`roles.master()` builds the prompt from `turn.engine`, `turn.draft`, `turn.action`,
`turn.notes`. `turn/run.py` becomes pure turn mechanics. The worldsmith's `render_worldsmith`
stays in `engines/` because it needs the engine's sections; say so in a one-line comment.

**LOC.** About -5 net, one directory gone. **Feature impact.** None; rendered text is
byte-identical so the `master.txt` goldens do not move. **Risk.** Low.
`tests/app/test_context_boundary.py` updates one import.

**Decision needed.**
- (a) Move the prompt and flatten `src/aidm/turn/run.py` to `src/aidm/turn.py`. The layer
  stays (the boundary test handles a single-file package).
- (b) Move the prompt, keep the package.

---

## Group 3: app, tools and UI

### 11. `GameService` tidy: one way to say "a role is working", one way to land a step

**Status:** open. **Raised by:** B, C.

**Plain English.** The page shows "Narrator is working" by reading a `phase` field the runtime
sets by hand in four methods and clears in three `finally` blocks. Four things answer "is this
game busy": the gate, `phase`, `turn` and a `busy` property. And four methods end the same way
(narrate, close, save, present) with slightly different spellings.

**Code change.**
- `GameService.working(role)` async context manager sets and clears `phase`; `open`, `_turn`,
  `_grow` use it. Delete the `busy` property (it is `phase is not None`).
- `_landed(draft, lines, facts, *, words, mark, proposal)` = close + save + present, used by
  `open`, `let_party_speak` and both branches of `_grow`. Read the two asymmetries first:
  `open` presents even with no lines; the interjection path speaks but does not illustrate.
- Rename `phase` to `working` and `presents` to `has_media`.

**LOC.** About -25. **Feature impact.** None. **Risk.** Low-medium; `tests/app/test_game_service.py`
has 29 tests over these paths and some set `service.phase` directly.

**Decision needed.**
- (a) All three.
- (b) Only the context manager and the `busy` deletion (about -14, no behaviour-adjacent change).

### 12. Media and speech in one module, one `Presenter`

**Status:** open. **Raised by:** B, C, lead (3 of 6).

**Plain English.** `Illustrator` (art) and `Reader` (speech) are the same shape twice: a config,
a provider, a cache directory under the save, a `Claims` lock, an `enabled` guard, an `open()`
classmethod and a "log and carry on" failure policy. `GameService` carries both and grows seven
members to forward to them; `Runtime._open` spends 27 lines constructing them.

**Code change.** New `app/present.py` holding both classes and a `Presenter(illustrator,
reader)` with `open(settings, store, slug, *, style, icon_dirs, voice)`, `enabled`,
`scene_art(view)`, `icon(id)`, `clip(newest)`, `present(view, player, newest)`. `GameService`
loses `media`, `reader`, `presents`, `_present`, `illustrate`, `speak`; keeps one-line forwards
for `scene_art`/`icon`/`newest_clip`. No shared base class for the two: the duplicated shape is
about 12 lines.

**LOC.** About -10 net; `GameService` loses 7 of 43 members. **Feature impact.** None.
**Risk.** Medium: `tests/app/test_media.py`, `test_speech.py` and one `test_game_service.py`
test import the classes by path or touch `service.media`.

**Decision needed.**
- (a) `Presenter` plus the module merge.
- (b) Merge the two modules only, leave `GameService` alone. Half the value, a quarter of the
  churn.
- (c) Leave both.

### 13. The tool mark: less implicit, no protocol with one implementer

**Status:** open. **Raised by:** A, B, D, E, lead (5 of 6).

**Plain English.** The `@tool` mark is the codebase's one piece of metaprogramming and every
reviewer says the idea is right. Three things around it are not: `Tools` is a protocol in `core`
with exactly one implementer (`Turn`); `_args_of` finds the args model by parameter position
(`parameters[2]`), so reordering breaks it silently; and `TwentyfourxxEngine.kill` is a live
tool with no `@tool` on it (inherited via the MRO), which a reader cannot see.

**Code change.**
- `_args_of` looks the parameter up by name (`args`) and raises a `ValueError` naming the
  expected signature.
- `Tools` protocol: move it to `turn/run.py` beside `Turn`, or delete it and type `Turn | None`
  in `spawn.py` and `builtin.py` (app may import turn).
- One-line comment on `TwentyfourxxEngine.kill` saying it inherits the base's mark; or require
  `@tool` on every override and check name collisions across the MRO.
- Not recommended: replacing `_MARKED` with an attribute set on the function. It reads as `Any`
  under basedpyright strict, which trades one CLAUDE.md rule for another.

**LOC.** About -8. **Feature impact.** None; publication order is unchanged so the
`master_tools.json` goldens do not move. **Risk.** Low, except deleting `Tools` forces four test
stubs to build a real `Turn`.

**Decision needed.**
- (a) Move `Tools` next to `Turn` (no test churn).
- (b) Delete `Tools`; type against `Turn` (one fewer abstraction, four test files change).

### 14. UI reads the view, not the save; small UI tidies

**Status:** open. **Raised by:** C.

**Plain English.** The transcript takes the whole `GameService` and reaches past `PlayerView`
into the save file for facts the view already carries. Two pages walk `runtime.engines[...]`
directly and one re-implements a lookup `Runtime.rewrite_pack` already has. Seven pure
predicates are split between two modules for no reason. A 23-line module holds two unrelated
things.

**Code change.**
- `transcript.chat`: `session.state.pending` becomes `view.decision`; `session.state.scenario.premise`
  becomes `PlayerView.premise` (one new field) or a `GameService.premise` property.
- `Runtime` gains a few façade methods (`catalog()`, `look(engine_id)`, `pack_options`,
  `seeds`, `pack_boxes(engine_id, pack_id) -> (name, writable, boxes)` shared with
  `rewrite_pack`); `ui/create.py` and `ui/packs.py` stop walking `Engine`.
- `can_type`, `standing_proposal`, `clock`, `placeholder`, `near_end`, `draft_spent`,
  `whole_page` all live in one module.
- `ui/dice.py` dissolves: `DiceSound` to `widgets.py`, `rolled_since` to `transcript.py`.
- One `banner(icon, label, detail)` widget replaces the three hand-built call-to-action rows
  and the `DECISION_ROW` constant that crosses from `transcript` into `game`.
- One `typed(box) -> str` helper in `widgets.py` replaces 16 `(x.value or "").strip()` sites;
  the game composer's 16-character `BLANK` set applies everywhere.

**LOC.** About -40. **Feature impact.** A title of one non-breaking space stops being accepted.
**Risk.** Low; `tests/ui/test_game.py` imports the predicates by name (one import line).

### 15. Small renames, in one pass

**Status:** open. **Raised by:** A, B, D, E, lead.

**Plain English.** A batch of one-minute fixes, each removing a stumble.

**Code change.**
- `git mv <engine>/worldsmith.py <engine>/pack.py` for the three engines: those files hold pack
  models, not the worldsmith, unlike the identically named family files.
- `_scene_unmet`, `_map_unmet`, `_overlap_unmet`, `_named_unmet`, `_planted_unmet`,
  `required_unmet` become `*_needs` (they return unmet requirements); `World.unmet()` keeps
  meaning "entities the player has not met".
- `RunResult.session`, `SessionId`, `Spawner.run(session=)` become `conversation` (a "session"
  in `runtime.py` is a loaded game).
- `app/roles.py`: `master` becomes `run_master`, `narrate` becomes `run_narrator`, `interject`
  becomes `run_interjection`, `worldsmith(spawner)` becomes `worldsmith_answer` (it returns a
  `WorldsmithAnswer`).
- `PackSet.installed` becomes a `@property` instead of `object.__setattr__` in `__post_init__`.
- Free function `packs.options()` becomes `with_ids()` (three other things are called `options`).
- `Engine.render_request` folds into `render_worldsmith` (it is a 10-line adapter).
- `Turn.action` becomes `player_action`; `Engine.act(action=)` becomes `action_id`.
- Locals: `ds` becomes `difficulty`; `me = player.subject()` inlined; `resolved_id` /
  `_resolve_ids` become `resolved_id` / `resolved_ids`; `Loner3eEntity.lose()` becomes
  `run_out_of_luck()`.
- `Crewmate.raise_skill` stops catching and re-raising the `Refusal` from `raised()`: `raised`
  returns `SkillDie | None`.
- `Echoed` moves from `core/entities.py` to `app/builtin.py` (its only user); `providers.posting`
  becomes a plain module-level client instead of a `@cache` singleton.

**LOC.** About -20. **Feature impact.** None. **Risk.** Very low.

---

## Parked (raised once, or worth a separate conversation)

- **Split 24XX `job(verb=...)` into `find_job`, `take_job`, `finish_job`** (D). Matches "one
  tool per settled change" but changes the tool surface the model reads; rules.md and goldens
  change. Worth a play-quality check, not a refactor.
- **Unify `actor_id` on the optional form in Loner** (D). Loner requires it on every tool; the
  other two default to the player. +5 lines, schema goldens change.
- **Loner twists as one `twists: tuple[tuple[str, str], ...]`** instead of two paired optional
  columns (D). -18 Python lines, 13 JSON files edited.
- **Reference-id fields ending in `_id`** (E): `Way.to`, `Prop.on`, `Dweller.place`,
  `Scene.place`, `Commission.target`, `*.engine`. Most are serialised in scenarios and packs, so
  it is a content migration. `Commission.target` alone is free.
- **`Game[W: BaseModel]` bound** (E). `AnyGame.world` is `Any` above the engines. Option A moves
  `Game` into `engines/`; option C softens the CLAUDE.md sentence. Recommended: C.
- **`FeatureConfig` base for `MediaConfig`/`SpeechConfig`** (B). -8 lines; changes field order
  on the settings tab.
- **`tests/engines/test_scene_bar.py` shrink** (E). 602 lines running two parametrised cases
  through identical code paths; about -150 test lines.
- **A test that feeds an unmet name into every `str` field of every tool and expects a
  `Refusal`** (D). Guards the hidden-canon gate that 14 tool bodies call by hand. +30 test lines.
- **`Library` absorbs `PackStore` and `read_packs`** (A). File IO out of the engines layer;
  changes `Engine.__init__`'s signature, which every test subclass uses.
- **Split `Turn._consume` into a text path and an option path** (A). +3 lines.
- **`Gate`/`Busy` to `app/gate.py`** so `mcp.py` stops importing all of `runtime.py` (B).
- **Extract a `Composer` from `GamePage`** (C). +15 lines; removes four uninitialised attributes.
- **The scenario page restores every save to read one field** (C). `LauncherCatalog.read` is
  called where only `characters_for` is used.
- **`speech.voices` is hidden from the settings page** because `_shown` skips tuples (C). A
  real setting the page quietly omits.
- **Where do pacing rules live** (B): `World.tempo` is on the engine side, `INTERJECTION_ODDS`
  and the `interjections`/`meanwhile` booleans on the app side. A design question, not a
  refactor.
