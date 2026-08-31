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
   update its tests in the same step. Never skip a test to make the check pass. Test lines are
   not budgeted and not counted: make them green and move on.
4. **Golden files** live in `tests/core/fixtures/`. To rebuild them:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest
   ```
   Do this **once**, at the end of a phase, then read every changed line before you continue.
   If a change surprises you, stop and ask.
5. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never invent extra deletions to hit
   a number.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive.

| phase | `src` after |
|---|---|
| start | 9,452 |
| 0–6 — the simplification | 5,600 |
| 7A — the restructuring pass | 5,578 |
| 7B — the roles get drivers | 5,892 |
| **8 — the second kit and its engine** | **about 7,900** |
| 9 — 24XX and Breathless return | about 9,700 |

Phase 8 and phase 9 **add** lines. They are feature phases. Five phases of deletion bought the
room; this is what the room was for.

---

# Phases 0–7 — done

The work is in the git log; the per-phase entries were pruned from `PROGRESS.md`. Read
`git log --stat` for the detail. In order: **0** kept the two probes under `docs/probes/`;
**1** cut the game to Loner 3e alone; **2** replaced the map with the scene kit and ported Loner
onto it; **3** made the three roles spawned CLIs behind one MCP surface; **4** made the browser the
whole game; **5** swept the prose and the last dependency; **6** collapsed the live-game lifecycle
into one session owner and fixed the four-file engine template; **7A** removed mirrored
persistence types, the split tool dispatcher and the two-graph chronology; **7B** gave the roles
typed CLI drivers, resumed sessions and a scrubbed child environment.

**What those phases settled, and what stays true.** Everything below was measured or paid for
once; do not re-litigate it.

1. **A sheet union is a plain assignment**, `Sheet = Annotated[A | B, Field(...)]`. `type Sheet =
   ...` breaks the discriminator and every sheet fails to parse.
2. **The four-file engine template is law**: `state.py`, `rules.py`, `creation.py`, `engine.py`,
   the same four names for every engine. A tool argument model stays in the same *file* as the
   resolver that reads it.
3. **One strict file order per module**: imports, constants and type aliases, models and classes,
   public functions, private helpers — with the exception in `CLAUDE.md`: a statement evaluated at
   module scope keeps its dependency order, and the section rank only breaks ties.
4. **A union payload is refuted, and so is sheet erasure.** `SceneState[S]` is invariant, so a
   union of two dies at `narrator_view`, `apply_change` and `apply_scene`. Erasing `[S]` type-checks
   but renders the worldsmith a sheet schema of `{}`. A two-parameter `Game[S, P: EnginePayload[S]]`
   is rejected: a bound may not name another type parameter.
5. **Route 2 works**: `Game[P]` with a `SerializeAsAny` payload plus a per-engine `Game` subclass.
   Byte-identical round trip, `twist` and `twist_pack` survive `committed()`, one narrow
   `pyright: ignore`. Phase 8 step 1 pays it.
6. **Save golden fixtures are the contract.** `tests/core/fixtures/save/loner3e.json` and
   `state/loner3e.json` are dumps of `Game`. If a refactor changes them, stop and ask.
7. **No backwards compatibility.** Stale saves are invalid, there is no version field and no
   migration path.
8. **`NarratorView`'s absence of hidden fields is a correctness boundary.** It stays one type,
   whatever else changes.
9. **`next_scene` is not a `PendingDecision`.** A decision blocks the master's tools and forces the
   player out of a scene they may still want to play. An offer does not.
10. **The codex master starts cold every turn.** `codex exec resume` refuses `--approve-for-me`,
    so a resumed thread answers every MCP call with "approval policy is never". Narrator and
    worldsmith resume.

---

# Phase 8 — the second kit and its engine

**Goal:** the world can be an authored map, not only a sequence of scenes. Maze Rats plays on it.

**Why now.** The scene kit invents the next place from the player's sentence. That is right for
Loner, and it cannot represent a dungeon: a loop, a shortcut or a flanking route is only a real
choice if both ways exist before the player walks them. Maze Rats' printed procedures — a 3-in-6
wandering check every ten dungeon minutes, travel rates by terrain, districts at 1-in-6 — are all
*about* a map. Without one they roll dice over nothing.

**This plan was reviewed adversarially against the tree and rewritten.** The review ran probes
under `basedpyright` strict and read the deleted rooms code. It found three blockers, and every one
is fixed below. Do not restore the earlier shape.

## Settled before you start. Do not re-open these inside the phase.

1. **The map is authored up front, not grown room by room as the player walks.** The worldsmith
   writes the whole map when the scenario is created: places, ways, loops, a shortcut, secrets.
   Places exist in state from turn one; most are not yet known to the player. Growing rooms as the
   player opens doors gives a scene sequence wearing a map, and no route is ever a decision. Step 6
   extends an exhausted map with a *new authored region*, which is the same act, not a retreat to
   frontier growth.
2. **"Authored exits are refused" applies to the scene kit only.** That standing decision was
   about rebuilding a map ontology under Loner. Rooms *is* the map ontology, on purpose, for an
   engine whose rules need one. Loner keeps its sentence-driven scenes and gains nothing here.
3. **A place is an `Entity` of kind `place`, and `carried_by` says where a thing is.** No new
   placement field. An actor is `carried_by` a place; an item is `carried_by` an actor or a place.
   **This is a rooms rule, not a shared one.** `VISION.md` §2 "one field, no new concept" says the
   opposite for scenes — there `carried_by` is inventory alone and "here" is scene membership. Both
   readings stand, one per kit; step 7 writes that down.
4. **The graph lives on the world, not on the entity.** `RoomWorld.ways`, not `Entity.exits`.
   `Entity` is shared substrate and must stay kit-free.
5. **No `kit_id` on a save.** Each engine has exactly one kit. `Engine`'s own fields carry it.
   Making engine and kit independently selectable builds a product of two sets nobody wants.
6. **No `WorldKit` type, and no `Transition` type.** `Engine` is already a dataclass of callables
   and that *is* the extension point. Two kits do not make one shared transition: a scene crossing
   moves the player and narrates an arrival, while a map extension adds latent places and leaves
   the player where they stand. They share a spawn and an install and nothing after it. Give each
   its own optional callback. Group fields into a `WorldKit` in a later phase only if the wiring
   proves repetitive — you will know after step 2, not before.
7. **Prior art is in git, and it is for parts.** `git show ca877aa^:src/aidm/world/` holds
   `topology.py` (106), `actions.py` (217) and `authoring.py` (236). Read `frontier`, `walk`,
   `_move_actor` and the reachability bar. Do not restore the containment tree or `Entity.exits`.

## Steps 1 and 2 are one checkpoint

Step 1 deletes `Game.world` and `Game.record()`; their replacements land in step 2. Neither can end
green alone. **Run the full check once, at the end of step 2, and commit the two together.** This is
the largest unit in the phase; nothing else in it is allowed to be this big.

## Step 1 — the engine owns its models

**Why:** `core/model.py` aliases `Payload`, `ScenarioPayload`, `CharacterPayload` and `SceneWrite`
straight at `engines.loner3e.state`, and `Game.world` is a `SceneState`. A second engine cannot be
persisted, and a second *kit* cannot exist, because `Game` asserts the world is scenes.

1. Make `Game`, `Scenario` and `Character` generic on their payloads: `Game[P: BaseModel]` with
   `payload` carrying `SerializeAsAny`. Each engine subclasses to narrow: `class Loner3eGame(
   Game[Loner3eState])`. Do **not** narrow a field in a non-generic subclass; that is
   `reportIncompatibleVariableOverride`, already measured.
2. **Delete the `self.engine != self.payload.engine` check in `Game._playable_game`.** A bound of
   `BaseModel` does not expose `payload.engine`, and a bound that does is the override error from
   item 4 of "Phases 0–7". The check is redundant once the subclass narrows the payload by
   construction, and `Engine.restored` still checks the header.
3. **`Engine` carries its three concrete model types**, because one type parameter cannot describe
   three different payloads and because every parse site needs to know which subclass to build:
   `game: type[Game[Any]]`, `scenario: type[Scenario[Any]]`, `character: type[Character[Any]]`.
   Route every boundary through them — `Engine.restored`, `core/io.read_scenario`,
   `core/io.load_character`, `registry.begin_game`. Without this the generic envelopes type-check
   and still cannot load a second engine's file.
4. **Name the erased aliases honestly, in one place.** The registry holds engines of different
   payloads, so `Any` appears at that boundary whatever you do. Declare `type AnyGame = Game[Any]`,
   `type AnyEngine = Engine` and friends in `core/model.py`, use those names everywhere below, and
   **do not write a bare `Game` or a bare `Entity`** — `reportMissingTypeArgument` is an error under
   `pyproject.toml`'s strict settings. The earlier draft claimed one `Any`; that was wrong.
5. Delete the four aliases and the `aidm.engines.loner3e.state` import from `core/model.py`.
   `ALLOWED` in `test_package_boundary.py` goes with them, and `ROOTS` drops `core/model.py`.
6. **Delete `Game.world` and `Game.record()`.** Both assert `SceneState`. Inside an engine the
   world is `state.payload.world`, typed once the subclass exists.
7. **`packs` stops being mandatory.** `Field(min_length=1)` on `Scenario.packs` and `Game.packs`,
   and the refusal in `Runtime.new_scenario`, are a Loner content-table rule wearing a platform
   rule. Let each engine's `validate` demand its own packs.
8. **The save golden fixtures must not change.** `world` is a property and `record` is a method, so
   neither is a field, and `FileStore.save` serializes fields only. **If they change, stop and ask.**

## Step 2 — the kit owns the world

**Why:** `turn/run.py` publishes `next_scene`, reads `run.settled` and calls `scene_spent`.
`turn/context.py` renders a `SceneState`. `app/runtime.py` owns the crossing *and the whole of
scenario creation*. `ui/game.py` and `ui/panels.py` walk scene runs to draw the transcript. None of
that can serve a map.

1. **`Entity`, `Thread`, `entity_fact` and `labeled` move to `kits/entities.py`**, the substrate
   both kits share. `Kind` gains `"place"`. **`Trait` does not move**: it is already in
   `core/entities.py`, which is its correct home. `kits/scenes/state.py` keeps `Scene`, `SceneRun`,
   `SceneCanon` and `SceneState`.
2. **`Engine` gains these kit-supplied fields.** Every one replaces a `kits.scenes` import in
   `core/`, `turn/`, `app/` or `ui/`. Type each one fully; no `Callable[...]` ellipsis survives
   into the commit.
   - `world_tools: tuple[MasterTool, ...]` — **`change_world` *and* `next_scene`** for scenes;
     `change_world`, `move` and `unlock_way` for rooms. `Engine.tools` is then engine mechanics
     **only**. The dispatcher publishes `TURN_TOOLS + engine.world_tools + engine.tools`, and
     `TURN_TOOLS` keeps `start_turn` and `scene` alone. Stop calling `scene_tools(...)` from inside
     the engine.
   - `entity_known: Callable[[AnyGame, EntityId], bool | None]` — `None` when no such entity. This
     is all `core/tools.apply_to_draft` needs for its told-fact gate, and it keeps `core` from
     naming `Entity` at all. Do not expose the whole cast.
   - `record: Callable[[AnyGame, str, tuple[SpokenLine, ...], Sequence[Fact]], tuple[str, ...]]` —
     files the exchange in the kit's own container and **returns the notes for the rules**. The
     scene recorder runs `scene_spent` after appending, which is where `SPENT_NOTE` now lives.
     There is no separate `after_segment`; one callback does both.
   - `history: Callable[[AnyGame], tuple[Exchange, ...]]` — the chronology reader. `ui/game.py`,
     `ui/panels.py` and `turn/context.py` all walk `world.runs` today and all must go through this.
   - `master_sections`, `narrator_view`, `player_view` — already `Engine` members, but they
     delegate to `kits.scenes.render` inside `engines/core.py`. Make them plain kit-supplied
     callables so rooms can supply its own `render.py`.
   - `authoring: Authoring` — a small record with the three things `Runtime.new_scenario` needs and
     cannot get from a schema alone: `prompt(source, guidance) -> str`, `refusal(written) -> str |
     None`, and `build(title, premise, packs, written, source) -> Scenario[Any]`. Today
     `Runtime.new_scenario` hard-codes `SceneWrite`, `opening_canon`, `scene.situation` and
     `ScenarioPayload`. A `type[BaseModel]` answer schema alone does not move any of that.
   - `crossing: Crossing | None` — the scene kit's own async transition, wired to today's
     behaviour, with `app/scene_write.py` moved into `kits/scenes/`. **Rooms sets it to `None`**
     and gets its own extension callback in step 6. Do not merge the two.
3. **`turn/run.py` loses** `next_scene` from `TURN_TOOLS`, `offer_the_way_on`, `SCENE_SETTLED`,
   `SPENT_NOTE`, `scene_spent`, and the `run.settled` read in `close_segment`. What is left is the
   transaction: open, picture, apply, refuse, narrate, commit.
4. **`core/views.py`**: `NarratorView.question` becomes `focus: str` — one field, not a split; the
   type stays whole because its no-hidden-canon guarantee is a boundary. `PlayerView` gets **no
   discriminated arm**; a display-only difference does not earn one, and it would make `ui` branch
   per kit. Replace `scenes` and `settled` with presentation fields both kits fill: `trail:
   tuple[str, ...]` (scene titles, or places visited) and `world_rows: Rows` (the kit's own panel —
   ways out and their state, for rooms). `ui/` still imports neither engine nor kit.
5. **Nothing in `core/`, `turn/`, `app/` or `ui/` imports `aidm.kits.scenes`.** Add that to
   `test_package_boundary.py`, so it cannot come back.
6. Full check — this is the checkpoint for steps 1 and 2 together — then play a Loner turn end to
   end: a decision, a crossing, the journal.

About **1,000 lines touched**, net **+250**. Almost all of it moves.

## Step 3 — `kits/rooms/`

The second kit. **Five substantive files, matching the scene kit**, which has five, not four.

1. `state.py` — `Way(to, known, locked)`, `RoomWorld[S]` with `cast`, `ways: dict[EntityId,
   tuple[Way, ...]]`, `player_id`, **`companions`**, `threads`, `visits`, `source`; `RoomCanon[S]`
   for the authored map. Ways are stored **directed**; a two-way passage is two entries, which is
   how a one-way drop or a door locked from one side is expressed.

   Invariants, and these are the ones the review found missing:
   - every way names a place that exists, and no way leads to its own place;
   - the holder matrix holds for **every** entity: a place is held by nothing, an actor is held by
     a place, an item is held by an actor or a place. An actor held by an item is refused.
   - `carried_by` has **no cycles**; walk holders up and refuse a repeat.
   - the player is held by a place, is not in `companions`, and no companion is dead.

   **`Way.known` means the player knows the door is there. It says nothing about the far side.**
   Do not require a known way to have two known ends; that invariant plus a `move` that refuses
   unknown ways makes every undiscovered place unreachable, which is the deadlock the review
   found. The authored *starting* map may still be required to open with its first ways known;
   that is a bar on the file, not an invariant on the world.
2. `verbs.py` — the `change_world` arms rooms needs, plus `move` and `unlock_way`.
   - `move` traverses **any unlocked way out of the player's place, known or not**. On arrival it
     reveals the destination, marks the way and its back-way known, and brings the companions.
     This is `ca877aa^:src/aidm/world/actions.py:_move_actor`, and it is what makes `frontier()`
     mean anything.
   - `unlock_way` clears `locked`. The done criterion "open a locked way" has no other operation.
   - **Do not reuse the scene verbs for drop and kill.** Scene `_move_item` and `_kill` express
     "loose here" as `carried_by = None`; in rooms that means "held by nothing", which only a place
     may be. Rooms reparents a dropped or dead-dropped item **to the actor's place**.
3. `render.py` — the narrator, player and master views. The master sees the whole current place,
   what is hidden in it, and the ways out with their known and locked state.
4. `worldsmith.py` — `MapDraft`, `apply_map`, and the map bar. The bar is where this kit earns its
   keep. Refuse a map that has no loop, no shortcut, no locked way, or nothing hidden — **and
   refuse any place no walk of ways reaches from the player's starting place**, counting locked and
   unknown ways, exactly as `ca877aa^:src/aidm/world/authoring.py` did. Without reachability,
   `frontier(world) == 0` can mean "the rest of the map is orphaned" instead of "the map is spent".
5. `boundary.py` — `frontier(world) -> int`, the count of unknown places a known place leads to.
   Lift it from `ca877aa^:src/aidm/world/topology.py`.
6. Full check.

About **+800**.

## Step 4 — Maze Rats walks

A minimal engine, so the kit is proved by play before the rules land on top of it.

1. Read `docs/NEXT-ENGINE-RESEARCH.md` for the **rules**. **Its "OPINION" section is stale** — it
   is dated 2026-08-28 and cites `Entity.exits`, `Engine.seed()`, `authoring/draft.py` and
   `player_action`, all deleted since. Take nothing architectural from it.
2. `state.py` — the sheet union, and the payload: `world: RoomWorld[MazeRatsSheet]`, `minutes: int`
   for elapsed dungeon time, `combat: CombatState | None` for the transient. Both live on the
   payload beside the world, exactly as Loner's `twist` and `twist_pack` do; neither belongs to the
   kit. The actor sheet carries STR/DEX/WIL, health, armour, attack bonus, level, XP, paths and
   spell slots. The item sheet carries weapon class **and armour, shield and medicine categories**,
   which the rules read.
3. `engine.py` and a stub `rules.py` — `new_game`, `validate`, `over`, the step-2 kit wiring, and
   `danger_roll` alone.
4. One character file, one authored map, `tests/mazerats` on `pythonpath`.
5. Full check, then **play the map**: walk three places, take the loop back, unlock a way, and read
   the journal. Fix the kit here, while the engine is small enough to see through.

## Step 5 — Maze Rats plays by its rules

1. `rules.py` — the procedure tools. **Seven, and the budget is decided here, not by the
   implementer**: `danger_roll`, `attack`, `morale`, `cast_spell`, `pass_time`, `rest`, `level_up`.
   `encounter` folds into `pass_time`, which advances minutes and rolls the 3-in-6 wandering check.
   `begin_combat` folds into `attack`, which opens `CombatState` on the first swing. That leaves
   one slot spare where 24XX has none. `change_world`, `move` and `unlock_way` are the kit's and do
   not count.
2. `creation.py` — the twelve SRD steps, nearly verbatim. A background is not a skill.
3. `packs/srd.json` — the CC BY tables: spell effects, elements and forms; monsters; NPCs;
   treasure; the dungeon, wilderness and city tables. **A spell name is generated by code**, by
   rolling the formula and joining the entries. Its general effect is a game-master ruling that
   then stays fixed, which is what the SRD says, not a deviation.
4. `docs/MAZE-RATS.md` — sources, licence and attribution, and every deviation with its reason.
   Two are known: no thirty-foot positioning inside a place, and an explicit end-of-session step
   that awards XP.
5. Full check, then fight something, cast a spell, rest, and level up.

Steps 4 and 5 together, about **+900**.

## Step 6 — the frontier

**Why:** an authored map runs out. When it does, the player should be asked, not stopped.

1. Rooms gains `extension: Extension | None`, its **own** callback — not the scene kit's
   `crossing`. It is ready when `frontier(world) == 0`: no unknown place is reachable from a known
   one.
2. When it is ready, the play page **offers** to push further: the same offer shape `next_scene`
   uses, never a `PendingDecision`. The player may still have things to do in the map they have.
3. The player writes what they want to pursue. That sentence is the worldsmith's whole brief.
4. The worldsmith writes a **new authored region** — places, ways, a loop, something hidden — and
   the install joins it to an existing known place and revalidates the whole graph, reachability
   included. A refused extension costs an extension, never the turn.
5. **It is not a crossing.** The player does not move, and nothing narrates an arrival. Do not
   reuse `CROSSING` from `turn/context.py`.
6. **No settings knob.** The old build fired this automatically at `growth_frontier: int = 1`.
   Asking the player is cheaper and better.

About **+120**.

## Step 7 — the enduring documents

The phase is not done while the rules that govern the repository still forbid it.

1. `CLAUDE.md` — "The world is a sequence of scenes, not a map" is now false. Rewrite the design
   rule to say the world is what its kit says it is, name both kits, and keep the rest.
2. `VISION.md` §2 — "one field, no new concept" defines `carried_by` as inventory and "here" as
   scene membership. Say that this is the scene kit's reading, and give the rooms reading beside it.
3. `VISION.md` §6 — the engine seam no longer matches `engines/core.py`. Bring it up to the fields
   step 2 settled.
4. Full check.

## 8 — done when

- `src` is about **7,900**, from 5,892. **This is not a deletion phase.** Never invent a deletion.
- Full check green at every checkpoint. Steps 1 and 2 share one.
- The save golden fixtures did not change in step 1.
- These six statements are all true:
  1. `core/` imports no concrete engine.
  2. `core/`, `turn/`, `app/` and `ui/` import no `kits.scenes` — enforced by
     `test_package_boundary.py`.
  3. Loner's `Engine.tools` holds Loner mechanics only; `change_world` and `next_scene` are in
     `world_tools`.
  4. A Loner game and a Maze Rats game both play from the browser, from the same build.
  5. No `if kit == ...` branch exists anywhere in `turn/`, `app/` or `ui/`.
  6. No bare `Game` or bare `Entity` annotation survives; the erased aliases are named in
     `core/model.py` and nowhere else.
- A Maze Rats dungeon plays: walk it, loop back, unlock a way, fight, cast, rest, run the map out,
  extend it.
- Counts and decisions written into `PROGRESS.md`.
- **Step 6 is the cut line.** If it runs long, ship steps 1–5 and 7, write the reason in
  `PROGRESS.md`, and carry step 6 forward.

---

# Phase 9 — 24XX and Breathless return

**Goal:** both play again, on the new design. Both are scene-kit engines; neither needs rooms.

Do them one at a time, and only after phase 8 is done and Maze Rats has been played for real.
**Phase 8 step 1 already paid the generic `Game`**, so this phase is additive: a new engine
package, a registry entry, and about **59 lines** of shared machinery — the engine choice and badge
on the home page (+26), `app/launch.py`'s `characters_for` and `CatalogEntry.engines` (+10), the
registry entries (+3), and the boundary-test tables (+2).

**They cost about 1,050 and about 770 `src` python lines, not 500 each.** Both were measured three
ways after phase 5. The floor needs no estimate: Loner 3e, the simplest engine here, is 818 lines,
and 24XX is larger at every comparable symbol. Each engine also regenerates 1,300–1,400 lines of
golden JSON, because the golden tests parametrize over `ENGINE_IDS`.

For each engine:

1. Read its notes in `docs/24XX.md` or `docs/BREATHLESS.md`. **`docs/24XX.md` deviation 1 is now
   false**: succession was deleted in phase 1, so a killed 24XX player no longer passes to a
   companion. Re-make that rules decision and rewrite the deviation.
2. Create `src/aidm/engines/<name>/` to the four-file template, with its typed state embedding
   `SceneState` with its own sheet union.
3. Write its procedure tools — one per SRD rule, never more than eight. **24XX has no headroom**:
   `defend` used to be hidden from the model and must now sit in the public list, taking 24XX to
   exactly eight.
4. Write its `guidance`, `scene_closed`, `over` and creation options.
5. Add its pack file and one character file, and write one scenario for it.
6. Full check, then play a turn.

**Let the engine prove a helper is shared before you move it into `engines/core.py`.** About 40
lines inside `loner3e` name no Loner rule — the party and advance-ledger cluster, and the pack and
option lookups. Move them when a second engine uses them, and keep the two clusters apart.

## Breathless, measured

**It is the smallest of the three: about 770 `src` python lines.** One thing drives that:
**Breathless has no advancement system at all.** Loner spends 119 lines on that ledger and its tag
glossary; Breathless writes none of it.

1. **It needs almost none of the shared helpers.** Verified by reading: zero uses of `party`,
   `party_member`, `advances_owed`, `ADVANCE_SPENT`, `find_entry`, `other_than` or `pack_meanings`.
   It shares `check_packs` and `pack_options`, about 5 lines.
2. **Do not bring player actions back. `catch_breath` goes on the scene boundary.** Measured, the
   `PlayerAction` route costs **118 lines**, of which 80 are core. The boundary route is **13**.
   **Saving: 105 lines, and `PlayerAction` never returns.** But **play a real session before
   committing to this**: dice stepping down *is* Breathless, and a free involuntary reset at every
   scene end defuses it. Keep it SRD-faithful — `scene_closed` must also write the complication
   note, because a breather is always paid for. The fallback is the +118 route.
3. **Fold the two loot tools into one.** `LOOT_ITEM` and `LOOT_MED_KIT` would both have to be
   public, putting Breathless at eight with no headroom. `PendingOption` carries `name` plus
   `args`, so both options can name one tool with `med_kit: true|false`.
4. **`improvise_item` breaks a Breathless invariant.** The kit publishes it to every engine and it
   creates an item with `sheet=None`, which Breathless's "every item is rated" `validate` refuses.
   Fix it in the engine: tolerate a sheet-less item and refuse to roll one. Two lines, plus a
   deviation in `docs/BREATHLESS.md`. Do not add a per-engine flag to the kit's tools for one
   engine.
5. **Two porting traps.** A worn-out item must be un-carried *and* left in the current scene, or it
   vanishes from every view. And Breathless was under-tested, not simple to test.

---

# Checklist

- [x] Phases 0–6 — the simplification. `src` 9,452 -> 5,600
- [x] Phase 7A — the restructuring pass. `src` 5,600 -> 5,578
- [x] Phase 7B — the roles get drivers. `src` 5,578 -> 5,892
- [ ] Phase 8 — the second kit and its engine. `src` 5,892 -> about 7,900
- [ ] Phase 9 — 24XX and Breathless return
- [ ] Full check green at every checkpoint
- [ ] The game plays from the browser at the end of every phase
- [ ] `src` counts in `PROGRESS.md` for every phase
- [ ] This file deleted in the last commit; `VISION.md` stays
