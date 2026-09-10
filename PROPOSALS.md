# PROPOSALS — conceptual simplifications and drastic cuts

Ten proposals, best first, from four independent reads of the whole codebase (three Fable
subagents with different lenses, plus the lead). Baseline: `src` 10,199 lines, `tests` 10.2k,
`qa` 2.4k, plus 17,248 lines of vendored dice JS. 575 tests pass in 7 s.

Every proposal keeps the four engines playing as they do and keeps the safety properties (only
code changes state or rolls dice; the narrator reads revealed facts only; strict validation at
every boundary; engine-typed saves). Where a proposal touches something the player sees, the
"Player change" line says exactly what.

**Do first:** 1, 2, 6. All three are mechanical, need no decision, and clear the ground for 3, 4, 5.
About half a day together.

**Decide first:** 3, 4, 10. They change file shapes or what the player sees, and they gate whether
saves and the four `scenarios/*/world.json` are rewritten in one pass or two.

---

## 1. One id type

**What.** Five spellings of "a lowercase slug": `Slug` (`Annotated[str, pattern]`), `EntityId`
(`NewType`), `CheckedEntityId` (`Annotated[EntityId, pattern]`), `content_id()`, and
`_SAVE_SLUG_PATTERN` (`core/entities.py:6-14`, `core/io.py:20`). The comment says
`CheckedEntityId` is "an id a model writes" and `EntityId` "one the world checked", but nothing
enforces that: `resolved_id` casts bare strings (`scenes/world.py:297,299`), every `slug()` result
is cast (`tunnelgoons/world.py:67`, `breathless/engine.py:155`, `twentyfourxx/engine.py:519`).
The runtime `require()` calls are what stop a bad id, not the type.

**Do.** `EntityId = Slug` (or delete `EntityId` and use `Slug`). Delete `CheckedEntityId` (74 uses)
and the `EntityId(...)` casts (13 in `src`, 134 in `tests`). Bonus: `dict[Slug, C]` keys get
pydantic-validated, which `dict[EntityId, C]` keys never were.

**Delta.** About −40 `src`, −130 test casts. **Risk.** None at runtime; basedpyright loses a
distinction that was never real. **Confidence.** High. **Time.** 1–2 h, mechanical.

## 2. The world-request mechanism: one dict, and stop persisting the request

**What.** A worldsmith request is `Game.generation` with an `operation` string. Around it:
`Engine.operations` tuple (`seam.py:44`), `Hiring.__init_subclass__` mutating that tuple
(`hiring.py:94-97`), two family `validate` membership checks (`scenes/engine.py:110-111`,
`rooms/engine.py:69-70`), `Hiring.validate` re-checking the hire target (`hiring.py:111-115`),
and `unwritten()` as three if-chains (`seam.py:181-183`, `scenes/engine.py:207-212`,
`rooms/engine.py:166-169`, `hiring.py:108-109`). Meanwhile `_resumable` clears `generation` on
every reload (`runtime.py:474`), so the on-restore checks validate a field about to be discarded;
the only writer of `generation` is the engine's own tool, and `hire()`/`advance` already check
`hireable` themselves.

**Do.** Replace `operations` + the if-chains with one class attribute
`unwritten: dict[Slug, Fact]` per engine; `Engine.validate` refuses an operation not in it (one
line, in the seam); `GameService._generate` reads `engine.unwritten[request.operation]`. Delete
`__init_subclass__`; `Hiring` contributes `{HIRE: HIRE_UNWRITTEN}` by explicit merge.

**Delta.** About −45. **Risk.** Low; the two existing refusal tests keep their messages.
**Confidence.** High. **Time.** 1–2 h.

**Decision (persist the request or not):**
- (a) Also mark `Game.generation` `Field(exclude=True)` and delete the `_resumable` clear and
  `Hiring.validate`. A save never carries a request, which is what the README promises. −25 more.
  Check that `exclude=True` survives `draft()` (deepcopy: yes) and `commit()` (re-parse of
  `__dict__`: yes) with the golden turn.
- (b) Keep persisting it; the dict alone.

## 3. Scenario payload is the worldsmith's draft: delete the canon layer

**What.** A scene exists in four shapes: `SceneDraft`/`NextDraft` (model output,
`scenes/drafts.py`), `SceneCanon` (the `world.json` payload, `scenes/world.py:52-65`), `SceneRun`
(state), `SceneRecord` (prompt projection). `opening_canon` converts draft→canon
(`scenes/engine.py:603-618`), `SceneWorld.begin` converts canon→world (`:97-109`), and
`apply_scene` converts draft→world the same way for every later scene (`:265-275`). Rooms mirror
it: `MapDraft` and `RoomCanon` (`rooms/world.py:115-129`) differ only by `source` and a
validator `map_refusal` already enforces. The source text is stored three times: as
`scenarios/<id>/source.<ext>` (written at `io.py:139`, never read again), as
`world.json payload.source`, and inside every save's `payload.source` (up to 120k characters
per save).

**Do.** `Scenario.payload` holds the accepted draft; `source: str` moves to the `Scenario`
envelope. `new_game` becomes "fresh world with the player, then `apply_scene(draft)`" and
"`RoomWorld` from `MapDraft` + player + starting items". Delete `SceneCanon`, `RoomCanon`, both
`opening_canon`, both `World.begin`, `run_of`, and the never-read `source.<ext>` copy.

**Files.** `scenes/world.py`, `scenes/engine.py`, `rooms/world.py`, `rooms/engine.py`,
`core/model.py:59-70`, `core/io.py:131-140`, the four `scenarios/*/world.json`,
`tests/support/*.py` builders.

**Delta.** About −110 / +25. **Risk.** Changes the scenario file shape (`opening.here` + `known`
flags become `present`/`hidden` lists). No version field, so the four shipped scenarios and any
user-written ones are rewritten by hand. `SceneWorld.runs` has `min_length=1`, so the fresh
world needs `_install_run(draft)` split out of `apply_scene`. **Player change.** None.
**Confidence.** Medium. **Time.** Half a day.

**Decision:**
- (a) Full: payload is the draft, `source` on the envelope. Cleanest; rewrites 4 content files.
- (b) `SceneCanon(SceneDraft)` and `RoomCanon(MapDraft)` as subclasses adding only `source`.
  Same file rewrite, half the deletion, keeps the "a draft is not a canon" type guarantee the
  previous plan valued.
- (c) Leave it; only delete the never-read `source.<ext>` file copy (−5, high, 10 min).
- Separately, for any option: keep `source` out of saves and read it from the scenario at
  worldsmith time? Saves shrink by up to 120k characters each; every save goes stale once.

## 4. Packs become engine data, not game data

**What.** The pack-selection path serves one engine with two packs. It runs through
`Scenario.packs` + validator and `Game.packs` + validator (`core/model.py:64-70, 105-114`),
`Engine.pack_options` on the seam (`seam.py:55-56`), `SceneEngine.validate`'s two pack checks
and `pack_step`/`srd_pack` (`scenes/engine.py`), the room family refusing any pack
(`rooms/engine.py:66-67`), `packs` threaded through `author`/`new_scenario`, and a "Table sets"
multi-select on the scenario page (`ui/create.py`). Breathless and 24XX ship only `srd`;
`twentyfourxx.guidance` ignores the picks; both hire prompts read `draft.packs[0]`; the twist and
complication tables always come from `srd`. Only Loner has a second pack (`ap01-fantasy`).

**Options:**
- (a) Packs are the engine's own data. Delete `Scenario.packs`, `Game.packs`, both validators,
  `pack_options`, the UI select, the room refusal. Loner keeps its `pack` creation step (it picks
  the skill/gear lists); `guidance`/`glossary` read every installed pack. About −90 `src`, −40
  tests, 4 data edits. Player change: the "Table sets" select disappears; Loner's worldsmith
  prompt grows by ap01-fantasy (about 3.5k tokens) on every scene; every save goes stale once.
- (b) Same UI removal, but Loner's `guidance` dumps only the packs whose entries the player's
  sheet uses, so no prompt bloat. About −60. **Recommended.**
- (c) Keep the mechanism; move `pack_options` off the seam into `SceneEngine` and delete the
  room validator line (−6).

**Confidence.** Medium. **Time.** 2–3 h for (a) or (b).

## 5. Hiring: one rule, fewer type parameters, one scene-world type

**What.** "The player, or a living party member with a sheet" is written twice:
`SheetedWorld.require_actor/require_hireable` (`hiring.py:66-78`, scenes only) and
`TunnelGoonsWorld.require_actor_and_sheet/require_hireable` (`tunnelgoons/world.py:83-97`),
because `SheetedWorld` subclasses `SceneWorld`. `hireable()` is the same one-liner in all three
engines. `Hiring[P, M, G, A]` carries four type parameters and an MRO trick ("List it first in
the bases"). Every scene engine binds `SceneWorld[C, P]`'s two parameters to the same class
(`loner3e/world.py:104`, `breathless/world.py:166`, `twentyfourxx/world.py:163`), and
`SceneEngine[C, P, G, K]` and `SheetedWorld[C, P]` repeat that.

**Do.** `World` gains abstract `require_here(entity_id, *, alive=False)` (rooms already has
`require_npc_here`); `require_actor`/`require_hireable` move to `World`. `Goon` and `Npc` become
`Sheeted[Abilities]`; the `_player_carries_a_sheet` validator moves to `World`; `member_noun` goes.
`Hiring` drops `M` and `A` and `__init_subclass__` (after 2). `SceneWorld[C, P]` becomes
`SceneWorld[C]` and the `C | P` unions in `require`, `require_here`, `here`, `shared_change`,
`scene_refusal` collapse.

**Delta.** About −90. **Risk.** `TunnelGoonsEngine.roll/level_up` switch from a tuple to
`actor = ...; sheet = actor.dice()`; a future scene engine whose cast type differs from its
player type re-adds the parameter. **Confidence.** Medium-high. **Time.** 3–4 h, after 2.

## 6. Seam and pipeline tidy: delete what a second check or a wrapper repeats

One bundle, all high confidence, about −100 in total, 2 h.

- `check_scenario` (`seam.py:165-167`): only caller is `new_game`, which only `begin` calls,
  and `begin` already refused a foreign scenario with a better message. The engine-id half of
  `check_character` likewise; keep only "the sheet is the player's" inside `player_of`. Move the
  two tests to `begin`.
- `instructions` is assigned twice in `Engine.__init__` (`seam.py:47,53`); `family_rules()`
  abstract becomes a `family_prompt: Path` class attribute read once.
- `Engine.record/history/scenes` (`seam.py:172-179`) are wrappers over
  `World.record/exchanges/records`; `app` already imports `engines.base`, so the 8 call sites
  can read `engine.world(state)`. Delete `record`; decide on `history`/`scenes`.
- `Engine.compose` (`seam.py:89-110`) caches one pure `build` with a `nonlocal` closure. Build
  twice: `answer = await worldsmith(prompt, model, lambda a: bar(build(a)))`, then
  `return build(answer)`. −14 and one test.
- `Roles.master` (`roles.py:52-73`): a `for last in (False, True)` loop with a nested closure
  encodes "spawn; if nothing landed, spawn once more; then raise". Two explicit tries.
- `turn/run.py:102` `*self.draft.notes` is always empty (swapped out at line 48; nothing writes
  a note before the one `picture()` call at `roles.py:58`).
- `scenes/drafts.py` exists so drafts do not import the world; it is model-output schema, same as
  `scenes/tools.py`. Merge.
- `banded(face, low, mid, high)` in `base.py` replaces `outcome()` in `breathless/tools.py`,
  `twentyfourxx/tools.py`, and the two inline bands in `twentyfourxx/engine.py:404-409, 429-434`.

## 7. Transport plumbing: one runner, the turn instead of the runtime, one layer fewer

**What.** Three spawner classes stand between a role and a process: `RoleSpawner` dispatches
(`roles.py:35-44`), `CliSpawner` and `BuiltinSpawner` each guard against being handed the other's
role (`spawn.py:141-142`, `builtin.py:65-66`). `BuiltinSpawner` is built with the whole `Runtime`
(`runtime.py:497`) so it can reach `published_tools`/`call`, which is why `Runtime` takes a
`stub: InitVar` for tests. `Runtime.lock` and `playing()` exist for the MCP transport alone.
`turn/` is one 161-line module with three callers, all in `app`, and knows no more world shape
than `app` does.

**Do.**
1. One `RoleRunner.run()` reads `settings.roles.for_name(role)` once and branches on
   `config.cli`; delete the dispatcher and both guards. −30, 30 min.
2. `Spawner.run(role, prompt, session, tools: Tools | None = None)`; `Turn` satisfies `Tools`
   (`published_tools` = `engine.tools.values()`, `call` = `Turn.call`). `Runtime` stops passing
   itself into its own spawner; `stub` goes. −20, 45 min.
3. `Runtime.lock` and the in-flight guard move into `mcp.py`'s closure; `playing()` becomes one
   `next(...)`. −12, 20 min.

**Decision (the `turn` layer):**
- (a) Fold `turn/run.py` into `app/turn.py`, `render_master` beside `render_narrator` in
  `roles.py`, `turn/prompts/master.md` into `app/prompts/`. Import flow becomes
  `core <- engines <- app <- ui`; `test_package_boundary.py` `LAYERS`, CLAUDE.md and README
  change. 0 lines, −1 layer, −1 prompts directory.
- (b) Keep the layer; do 1–3 only.

**Confidence.** High on 1–3, decision on the layer. **Time.** 2 h.

## 8. One worldsmith prompt renderer and one copy of the party prose

**What.** `scenes/worldsmith.py:123-148` and `rooms/worldsmith.py:10-34` build the same
`sections((YOUR ROLE, SOURCE MATERIAL, THE SCOPE OF PLAY, ...family..., WHAT COMES NEXT, ENGINE
GUIDANCE, ANSWER WITH))` with two or three middle sections swapped; `render_request` /
`render_opening` / `render_next` in both engines are the second copy of the same plumbing with
different signatures. In prose, the "## The party" paragraph appears in all four engine
`rules.md` with one engine-specific sentence each, and "## Hiring" opens with the same two lines
in three.

**Do.** `render_worldsmith(*, role, source, scope, family: Pairs, intent, guidance, answer)` once
in `engines/base.py`; each family supplies its middle `Pairs` and its "no scenes yet"
placeholders, in the same order so the substring tests hold. Move the shared party and hiring
lines into `scenes/rules.md` and `rooms/rules.md` (already appended after the engine's rules) and
regenerate the four master goldens.

**Delta.** About −35 `src`, −18 lines of prose. **Risk.** Worldsmith prompts have no golden;
add one per family before the refactor so a wording slip is visible. The party rule moves from
mid-rules to the end. **Confidence.** Medium-high. **Time.** 2–3 h.

## 9. Tests and qa: write each rule once

**What.** 17 test names appear two or three times across the four engine test packages
(`test_restored_round_trips` ×3, `test_advance_on_a_hire_installs_the_sheet_and_joins_the_party`
×3, `test_hire_refuses_a_sheeted_member`, `test_validate_refuses_a_stale_hire_target`, seven
scene-bar tests shared by Loner, Breathless and 24XX, and more). Five test files are under 60
lines. Three files assert "the narrator view holds no hidden canon" three ways. `qa/agents.py`
(300 lines, a `!roll` grammar and canned worldsmith answers) and `tests/support/table.py`
`ScriptedSpawner` (30 lines) stub the same seam. In `qa/`, `s_mcp.py` re-proves a unit test over
HTTP, `s_visual.py` re-shoots what the engine scripts shoot, `s_probe.py` items 3–4 repeat
`test_game_service.py` and `s_loner` step 13, and the three engine scripts replay rules the unit
tests already prove.

**Do.**
1. `tests/engines/test_hiring.py` and `tests/engines/test_scene_bar.py`, parametrized over the
   engine supports; fold the five small files into their engine's `test_engine.py`. −200, −10
   files, high.
2. Keep one "no hidden canon" assertion (the one pinning the field set); keep one of the two
   twist-priming tests. −40, high.
3. Decision on `qa/`: (a) delete `s_mcp`, `s_visual`, `s_probe` (fold its markdown and long-word
   checks into `s_loner`), shrink the three engine scripts to open → one option-only decision →
   drawer → screenshot, and add one in-process `httpx.ASGITransport` test against
   `mcp.endpoint(runtime)`. About −700 of 2,433, fewer screenshots per engine, medium-high.
   (b) Leave `qa/` as is. (c) Also make tests script masters with qa's `!` grammar and delete
   `Table.plays`; −150 more, only worth it if qa runs often.

**Time.** 3–4 h for 1–2; half a day for 3(a).

## 10. Decision: the 3D dice stack

**What.** `ui/lib/dice-box-threejs.es.js` (17,248 lines, 692 KB), `ui/dice_assets/` (28 mp3,
232 KB), `ui/dice_tray.js` (95), `ui/dice.py` (38), about 35 lines of wiring in `ui/game.py`,
the sound toggle, and `Observed.facts`. It is 63 % of the repository's non-test lines for one
animation. The per-card die faces with the CSS tumble (`theme.py:274-292`, `game.py:_dice_group`)
already show every roll and which die was kept.

**Options:**
- (a) Delete it all: −17,700 lines. Player change: no dice rolling across the page and no sound;
  the animated card faces stay. This reverses IDEAS #17, which is marked done, so it does not
  keep the feature intact; it is on the list only because of its size.
- (b) Keep the physics, drop the sounds, the toggle and the `sound` event: −232 KB of assets,
  about −25 lines. Player change: silent dice.
- (c) Keep as is.

**Confidence.** High on the mechanics, low on what the maintainer wants.

---

## Looked at and left (so nobody reopens them)

- **The scene/room family split, and folding `rooms/` into `tunnelgoons/`.** Decided in the
  previous plan (Decision 1): `rooms/` stays for the next map game. The two families share only
  `World`; a merge is a rewrite of one onto the other's model.
- **One transport.** CLI-only deletes about 260 lines and loses OpenRouter/Ollama roles; API-only
  deletes about 350 and loses "play on the subscription you already have". Both are README
  promises. Keep both until usage shows one side idle.
- **`Engine[P, G]`'s `P`, and `Game[P]`.** Dropping `P` types `world(state)` as `World[Any]` and
  leaks `Any` into every tool body. `Scenario[P]`/`Character[P]` are already erased at the seam.
- **`Line` vs `SpokenLine`, `Subject` vs `Thing`, `SceneRecord` projection, `render_history` vs
  `told_history`.** Each is one reader's boundary; `Visit` has no title without a place lookup,
  so the projection cannot become a shared base.
- **Interjection machinery, `MountedLifespan`, `Turn._apply`'s copy-then-land, `_normalize`.**
  Each is a promised feature or a stated property with no shorter spelling.
- **"More map" as a master tool** (−35 in `GameService.act`/`intent`/`_generate(words)`): costs
  one extra master spawn per push-on; a play-feel change, not a simplification.
- **Dropping session resume from the one re-prompt** (−45): a cold retry re-reads a prompt of up
  to 30k tokens; near-free under prompt caching, unmeasured on Codex.
- **Theme tokens on the layout instead of generated CSS** (−45), **one generate-once cache for
  `Illustrator` and `Reader`** (−20), **`CharacterHeader`/`SheetHeader` deletion** (−12),
  **`schema_of` normalization** (measure a prompt first). Real but small; below the top ten.
