# PLAN

The order of work to MVP0. `VISION.md` says what we build and why; read it once, first. This
file says what to do, step by step, and is self-standing.

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
   checked together. Never carry a red check past a checkpoint.
3. **Tests must be green.** Delete a feature and its tests in the same step. Change a shape and
   update its tests in the same step. Test lines are not budgeted.
4. **Golden files** live in `tests/core/fixtures/`. Rebuild them **once**, at the end of a phase:
   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest
   ```
   Then read every changed line. If a change surprises you, stop and ask.
5. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
6. **If a phase runs far past its target, stop and say so.** Never invent a deletion to hit a
   number, and never pad to fill one.
7. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
8. **One commit per phase.** Never leave two versions of one thing alive.
9. **Review each phase adversarially against its staged diff before the commit.** Every review so
   far found real defects.

| phase | `src` after |
|---|---|
| start (`2c3e8a5`) | 8,913 |
| 1 — Maze Rats and the rooms kit deleted | about 6,350 |
| 2 — the seam and the player view | about 6,270 |
| 3 — Loner owns its world; `kits/` deleted | about 5,970 |
| 4 — Tunnel Goons | about 6,920 |
| 5 — the enduring documents | about 6,920 |

---

## Settled. Do not re-open these inside a phase.

1. **No shared world layer, in any name.** No `kits/`, no `World` protocol, no generic
   `Entity[S]`. Each engine owns its world model. Two engines may duplicate a small verb; a
   helper moves to `engines/core.py` only when both engines hold the identical function.
2. **An engine is self-contained and at most 2,000 Python lines.** State, world, verbs, rules,
   creation, worldsmith, render, recording, `rules.md`, packs — all under `engines/<id>/`.
3. **At most eight game-master tools per engine, world verbs included.** `Engine.tools` is one
   tuple. The turn tools `start_turn` and `scene` are the platform's and do not count.
4. **`core/` knows no world shape.** It knows an entity only as the id the told-fact gate checks:
   `EntityId`, `Fact.entity_id` and the gate stay, because they are the "no unknown name reaches
   the narrator" boundary. Counter, Trait, `DEAD` and `PLAYER_ID` are engine-tier and live in
   `engines/core.py`.
5. **`Engine` stays a frozen dataclass of typed callables.** `build()` passes module functions.
   One `partial(fn, packs)` per member that reads the loaded packs is allowed; what is banned is
   an adapter whose only job is to re-route a call — no `lambda`, no `cast(...)`, no `_record`-style
   wrapper. The member list is the one in `VISION.md`.
6. **A sheet union is a plain assignment**, `Sheet = Annotated[A | B, Field(...)]`. `type Sheet =
   ...` breaks the discriminator.
7. **One strict file order per module**: imports, constants and type aliases, models and classes,
   public functions, private helpers; a statement evaluated at module scope keeps its dependency
   order.
8. **Save golden fixtures are the contract.** Regenerate once per phase, read every line.
9. **No backwards compatibility.** Stale saves are invalid; no version field, no migration.
10. **`NarratorView` has no field that can hold hidden canon.** It stays one type.
11. **`next_scene` is not a `PendingDecision`.** An offer does not block the master's tools.
12. **Verify a rule against the rulebook before you build on it.** Phase 8 built a dungeon clock
    Maze Rats does not print, from a stale research note.
13. **The codex master starts cold every turn.** `codex exec resume` refuses
    `--approve-for-me`. Narrator and worldsmith resume.

---

# Phase 1 — Maze Rats and the rooms kit deleted

**Goal:** the tree holds one engine again, and every later diff is smaller.

1. `git rm -r src/aidm/engines/mazerats src/aidm/kits/rooms tests/mazerats tests/kits
   tools/import_mazerats_pack.py scenarios/blackglass-maze characters/kael/mazerats.json` and
   every `mazerats` fixture under `tests/core/fixtures/`. Keep `docs/MAZE-RATS.md`: it is the
   return's notes.
2. `engines/registry.py` builds Loner alone. Drop `mazerats` from `ENGINE_IDS`, from the boundary
   test's `ENGINES`, from `pyproject.toml`'s `pythonpath` **and** `basedpyright.extraPaths`, and
   delete the `MazeRatsGame` arm of `_behind` in `tests/core/test_golden_turn.py`.
3. Leave `kits/entities.py`, `kits/verbs.py`, `kits/render.py` and `kits/scenes/` untouched. Phase
   3 folds them.
4. Full check. **The Loner goldens must not change.** Play a Loner turn.

About **−2,550**.

---

# Phase 2 — the seam and the player view

**Goal:** the platform reads the seam `VISION.md` lists, and the page stops knowing what a
companion is. Loner still runs on the scene kit; the Loner save goldens do not change.

1. **One tool tuple.** Merge `world_tools` into `tools`. `Turn.call`, `Runtime.published_tools`
   and `Engine.__post_init__` read one tuple. `MasterTool.during_suspension` stays: a world verb
   may run in a suspended turn, a mechanic may not.
2. **One transition.** `crossing` and `extension` become `transition: Transition[G]`, required.
   `Transition.arrival_brief` is `Callable[[str], str] | None`, given the player's pursuit: a
   brief means the player moves and the arrival is narrated; `None` means places were added and
   the player stands still. `GameService.play` and `extend` route on that one field; delete
   `_ready` and `transition_available`'s two arms. Loner supplies its crossing.
3. `entity_known` is renamed `known`. `Exchange.scene` is renamed `where`; it is excluded from the
   dump, so no golden moves.
4. **`Engine.guidance` is deleted.** It was a round trip: the platform asked the engine for text
   and handed it back to the same engine. `Transition.write(state, intent, answer)` reads
   `state.packs` itself; `Authoring.prompt(source, packs)` takes the picks.
5. **`Authoring` is `answer`, `prompt`, `build`.** `refusal` goes: `build` raises on an unmet bar,
   and `Runtime.new_scenario`'s refusal closure already catches `ValueError` from `build` and
   `begin_game`.
6. **`Scenario.art_style` is deleted.** Nothing writes it; the illustrator reads
   `settings.media.style`.
7. **`PlayerView` collapses** to `player`, `sheet: Rows`, `panels: tuple[Panel, ...]`, `prompt`,
   `over`, where `Panel(title, rows: tuple[PanelRow, ...])` and `PanelRow(label, detail,
   icon_id: EntityId | None = None)`, so the sidebar keeps its NPC icons. Delete `focus`, `trail`,
   `traits`, `carrying`, `present`, `companions`, `threads`, `world_rows` and `ThreadRow`; the
   breadcrumb goes. `ui/game.py` and `ui/panels.py` draw each panel from its title and rows. The
   scene kit's `player_view` fills "This scene", "Trail" and the rest as panels.
8. Delete `docs/NEXT-ENGINE-RESEARCH.md`. It is stale in every part.
9. Full check. **All goldens unchanged**: nothing this phase touches is serialised or rendered into
   a prompt. Play a turn.

About **−80**.

---

# Phase 3 — Loner owns its world

**Goal:** `kits/` is gone. Loner's world is the SRD's: everything is a character.

1. **Move**, do not rewrite yet: `kits/scenes/state.py` -> `engines/loner3e/world.py`;
   `kits/scenes/verbs.py` + `kits/verbs.py` -> `engines/loner3e/verbs.py`; `kits/scenes/render.py`
   + `kits/render.py` -> `render.py`; `kits/scenes/worldsmith.py` + its `worldsmith.md` ->
   `worldsmith.py`; `kits/scenes/boundary.py` (`record`, `history`, `scene_spent`) into `world.py`.
   `kits/entities.py` is split across `world.py` and `verbs.py`. Delete `kits/`, the
   `test_consumers_do_not_name_a_kit` test and `kits` from `LAYERS`. Full check: goldens unchanged.
2. **The platform stops naming `next_scene`.** Move the "let the player choose where the story
   goes" section of `turn/prompts/master.md` into `engines/loner3e/rules.md`; delete the
   `next_scene` arm of `Turn.call` (the `during_suspension` path already answers); make the
   `start_turn` and `scene` tool descriptions engine-neutral (no "scene", "hidden here", "threads").
3. **Make the world Loner's.** `LonerCharacter` replaces `Entity[S]` (`Character` is the core
   envelope): `id`, `name`, `brief`, `known`, and the sheet's fields inline — concept, skills,
   frailties, luck, gear, chapters, milestones, the traits. No `kind`, no `sheet: S | None`, no
   `carried_by`: an object, a vehicle or a curse is a character present in the scene, which is what
   the SRD says. **Everyone present may speak and be drawn**: with no `kind`, `narrator_view` stops
   filtering actors. The verbs that survive: `reveal`, `enter`, `leave`, `add_trait`,
   `remove_trait`, `kill`, `join_party`, `leave_party`, `advance_thread`; `MoveItem` and
   `ImproviseItem` go, and taking or losing a thing is an edit of `gear`, one verb. Delete the
   `[S]` parameter everywhere in the engine. In `docs/LONER-3E.md`, rewrite deviation 2 (it should
   vanish) and fix deviation 4 (the counter is `Loner3eState.twist`, not a sheet field).
4. **Delete the adapters.** `_record`, `_history`, `_world_of`, `_entity_known`, `_narrator_view`,
   `_player_view`, `_authoring_refusal`, `_build_scenario`, `_write_next`, `_install_scene` go;
   `build()` names module functions. `Engine.tools` is `change_world`, `next_scene` and the four
   mechanics.
5. **Move `Counter`, `pool`, `Trait`, `DEAD` and `PLAYER_ID`** from `core/entities.py` to
   `engines/core.py`. No platform module reads them today; if one does by then, stop and say which.
6. Full check. **Regenerate the goldens once**, read every line: the save shape, the master prompt
   and the narrator prompt change here and nowhere else in this plan. Play a decision, a crossing
   and the journal.

Loner lands at about **1,950**; 2,000 is the ceiling, not the target. About **−300** overall.

---

# Phase 4 — Tunnel Goons

**Goal:** a game-master-driven dungeon crawl on an authored map, from the same build.

1. **Read the rulebook first.** Download the PDF from <https://natetreme.itch.io/tunnelgoons>
   (CC BY 4.0) and write `docs/TUNNEL-GOONS.md`: sources, licence line verbatim, and every
   deviation with its reason. Two are expected: level-up is "every 2 game sessions", which here is
   an end-of-adventure step; and monsters need a written statline (HP and a Difficulty Score) —
   verify what the PDF prints before deciding the shape.
2. `engines/tunnelgoons/state.py` and `world.py` — the payload and a strict world: `Goon` (Brute,
   Skulker, Erudite, HP `Counter(10)`, Inventory Score 8), `Monster` (HP, DS), `Item` (the ability
   it helps, and `on: EntityId` — a goon, a monster or a place, checked by one validator), `Place`,
   `Way(to, known, locked)`, the companions, the visits. **No threads**: no Tunnel Goons rule reads
   one. Actors have a `place` field and items an `on` field, so the holder matrix is in the types,
   and a validator checks each id names something of the right kind. Lift `move`, `unlock_way`,
   reachability, `frontier` and `_has_shortcut` from `git show 2c3e8a5:src/aidm/kits/rooms/`; they
   were reviewed twice.
3. `rules.py` — three tools: `action_roll` (2d6 + ability + relevant items against DS 8/10/12;
   with risk, the difference is damage, to the goon on a miss or to the monster on a hit; over-
   inventory penalty), `rest` (a night in a safe spot heals), `level_up` (a `PendingDecision` with
   options: which ability, then HP or Inventory). `verbs.py` — `change_world` with the arms
   `reveal`, `move_item`, `kill`, `join_party`, `leave_party`; plus `move` and `unlock_way`.
   **Six tools.**
4. `creation.py` — the SRD's five steps. `worldsmith.py` — the opening map and the extension, with
   the bar: reachability from the start, a shortcut, a locked way, something hidden. `render.py`,
   `engine.py`, `rules.md`. `packs=()`, and `ui/create.py` hides the pack select when
   `engine.packs` is empty.
5. One character, one authored map, `tests/tunnelgoons` on `pythonpath`, goldens for the engine.
   Full check, then **play**: walk three places, take the route back, unlock a way, fight, rest,
   run the map out, extend it.

Tunnel Goons lands at or under **1,000**. About **+950**.

---

# Phase 5 — the enduring documents

1. `CLAUDE.md` design rules: the world is the engine's; the import flow is `core <- engines <-
   turn <- app <- ui`; an engine is self-contained under 2,000 lines with at most eight tools.
2. `README.md`: two engines, one build. `docs/MAZE-RATS.md`'s "Where the rules live" points at
   `2c3e8a5`.
3. Delete `IDEAS.md` and `docs/COMPETITOR-RESEARCH.md`: `VISION.md` carries the future features,
   and the one competitor idea worth keeping (a recap on resume) is the per-place memory feature.
4. Delete this file and `PROGRESS.md` in the last commit. `VISION.md` stays.
5. Full check.

---

# Checklist

- [x] Phase 8 committed as the checkpoint, `2c3e8a5`
- [x] Phase 1 — Maze Rats and the rooms kit deleted. `src` 8,913 -> 6,365
- [x] Phase 2 — the seam and the player view. `src` 6,365 -> 6,334
- [ ] Phase 3 — Loner owns its world; `kits/` deleted. about 5,970
- [ ] Phase 4 — Tunnel Goons. about 6,920
- [ ] Phase 5 — the enduring documents
- [ ] Full check green at every checkpoint; a turn played at the end of every phase
- [ ] `src` counts in `PROGRESS.md` for every phase
- [ ] This file and `PROGRESS.md` deleted in the last commit; `VISION.md` stays
