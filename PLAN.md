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
| 7 — to be drafted | ? |
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
   `core/model.py` still aliases four types straight at `engines.loner3e.state`, and
   `core/envelope.py` still stands. What five probes proved: a union payload dies on invariance at
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

# Phase 7 — to be drafted

Not written yet. Draft it here before starting it, to the same shape as the phases above: a goal,
a why, numbered steps each ending in a full check, and a "done when" with a line-count target.

Inputs on the table: `INVESTIGATION.md` (sidebar cards, resumed provider sessions,
provider/model/effort settings, the Codex tool-isolation proof) and `REFACTOR-OPINION-1.md` /
`REFACTOR-OPINION-2.md` (the envelope stack, `SceneRun` as the played-scene aggregate, a
turn-scoped MCP, engine-dispatched persisted types).

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
4. **Delete `core/envelope.py`** once 0.3 lands. `SaveEnvelope` restates `Game` field for field,
   and `engines/core.py` parses the same raw string twice. `SaveEnvelope = Game[RawPayload]` fixes
   that path.
5. **Do not "just persist `Game`/`Scenario`/`Character` directly."** The raw-payload read is what
   lets the app open a file *before* it knows which engine wrote it: `core/io.py` skips scenarios
   whose engine is not installed, and `app/launch.py` reads a save with no engine built. Deleting
   that breaks engine discovery in this phase.
6. **The save golden fixtures must not change.** A correct `Game[S]` dumps byte-identically. They
   are the only place the dropped-payload-field trap shows up — a `Payload[S]` base with `Game[S]`
   keeping `world` type-checks green and silently drops `twist` and `twist_pack` on every commit.
   **If they change, stop and ask.**
7. Full check.

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
- [ ] Phase 7 — not drafted
- [ ] Phase 8 — the engines return
- [ ] Full check green at every checkpoint
- [ ] The game plays from the browser at the end of every phase
- [ ] Line counts in `PROGRESS.md` for every phase
- [ ] This file deleted in the last commit; `VISION.md` stays
