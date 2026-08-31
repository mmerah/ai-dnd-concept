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

Start: `src` 9,452 lines, `tests` 6,044 lines.

| phase | `src` after |
|---|---|
| 0 — keep the probe code | 9,452 |
| 1 — one engine | ≈ 7,530 |
| 2 — the scene kit and the port | ≈ 6,300 |
| 3 — the three roles and the tool surface | ≈ 5,650 |
| 4 — the pages | ≈ 5,400 |
| 5 — the sweep | ≈ 5,400 (this phase does not shrink `src`) |
| 6 — the engines return | + about 500 each |

---

# Phase 0 — Keep the probe code

Two working programs were written to prove the risky parts. They live in `/tmp` and one reboot
would lose them. Phase 2 tells you to copy from both.

1. Make `docs/probes/`.
2. Copy `/tmp/scene_probe/kit.py` to `docs/probes/scene_kit.py` and
   `/tmp/scene_probe/fixture.py` to `docs/probes/scene_fixture.py`.
3. Copy `/tmp/spike/spike.py` to `docs/probes/state_spike.py`.
4. Add `docs/probes` to `extend-exclude` in the `[tool.ruff]` section of `pyproject.toml`. This
   is reference code, not shipped code. `basedpyright` needs no change, because its `include`
   names `src`, `tests` and `evals` only.
5. Give each file a short header saying what it proved and what it lacks, and remove the `/tmp`
   paths from its imports.
6. Full check.

**Note what the probes do *not* contain.** `scene_kit.py` has `change_world`, `apply_change`,
`render_worldsmith` and `scene_unmet`. It has **no `apply_scene` and no `scene_spent`** — those
are new work in phase 2.

---

# Phase 1 — Cut to one engine

**Goal:** Loner 3e is the only engine. The game plays exactly as it does today, on the old map
world. This phase only deletes.

**Why:** every later phase costs three times as much with three engines. 24XX and Breathless
return in phase 6, rewritten. Git keeps the old code.

1. **Delete the eval suite.** Remove the `evals/` directory. It measured how a weak model uses
   the tools; every role is a strong CLI now. (`README.md` does not mention it, so nothing else
   to change.)

2. **Delete the two engines and their tests.**
   - `src/aidm/engines/twentyfourxx/`
   - `src/aidm/engines/breathless/`
   - `tests/twentyfourxx/`
   - `tests/breathless/`

   Then remove `"tests/twentyfourxx"` and `"tests/breathless"` from `pythonpath` in
   `pyproject.toml` (line 39).

3. **Delete their content.**
   - `scenarios/drowned-road/` (24XX)
   - `scenarios/saint-ivo/` (Breathless)
   - `characters/kael/twentyfourxx.json`
   - `characters/kael/breathless.json`

   Keep `scenarios/whispering-vault/` — it is the Loner scenario, and the only one left.

4. **Delete the hostile-engine test.** Remove `tests/hostile/`. It is a fake fourth engine that
   proved the seam could hold anything. We decided not to buy that generality: there is one
   engine and one kit. It would also break in phase 3, because it imports
   `build_turn_agents`.

5. **Simplify engine discovery.** In `src/aidm/engines/registry.py`, delete the `import_module`
   loop that finds engines by folder name; import `loner3e` directly and build it. Then fix
   `tests/core/test_package_boundary.py:6`, which imports `ENGINES` from that file — replace the
   import with the single engine name.

   **Leave `AnyEngine` alone.** It is only an alias, and deleting it now causes type errors,
   because the bare `Engine` protocol is generic and strict mode requires its type argument.
   Phase 2 removes it, when the engine's state type is concrete.

6. **Delete succession** (80 lines in `src/aidm/world/succession.py`, plus its test).
   - Remove `src/aidm/world/succession.py` and `tests/core/test_succession.py`.
   - In `src/aidm/world/actions.py`, `kill` no longer opens a succession choice. It just
     records the death.
   - `validate` was threaded through three levels only to serve that choice. Remove the
     parameter from `actions.kill`, from `apply_change` in `src/aidm/world/tools.py:134`, and
     from `rooms_tools` at line 160.
   - In `src/aidm/engines/loner3e/engine.py`, remove `resolvers=(TAKE_OVER,)` and replace
     `over=player_over` with a small local function: the game is over when the played character
     has the `dead` trait, and the message is `"You died."`.
   - Remove `speaker` from `Exchange` in `src/aidm/state/play.py`. It existed so succession
     could not rename old messages. Update the places that write and read it.

7. **Delete the `resolvers` field.** In `src/aidm/engines/core.py`, remove `resolvers` from the
   `Engine` dataclass, from the `tool()` lookup and from `__post_init__`. In `restored()`,
   delete the loop that re-validates each pending option's arguments. Update
   `tests/core/test_decisions.py`.

8. **Delete player actions.** From `src/aidm/engines/core.py`: the `PlayerAction` class, the
   `player_action()` helper, `offered()`, `play_action()`, and the `player_actions` field. Then
   every caller:
   - `src/aidm/app/runtime.py` — `offers()` and `act()`
   - `src/aidm/ui/game.py` — `player_actions()` and `_act()`
   - `src/aidm/harness/mcp.py` and `codemode.py` — the `player_action` tool
   - `tests/core/test_player_actions.py`

   Only Breathless ever had any. They return with it in phase 6.

9. **Full check. Then `uv run aidm`, open `whispering-vault`, take one turn.**

**Done when:** the check is green, the game plays, `src` ≈ **7,530**.

---

# Phase 2 — The scene kit, and Loner ported onto it

**Goal:** the world is a sequence of scenes. The map is gone.

This is the biggest phase and it cannot be split: a half-ported world would need the old map and
the new scenes alive together.

**Steps 1–4 are checked one by one. Steps 5–10 are one atomic group — the build is red inside it
and that is expected. Check at the end of step 10.**

### Build the kit (check after each)

1. **Create `src/aidm/kits/scenes/state.py`** with `Scene`, `Thread`, `Entity[S]` and
   `SceneState[S]` from `VISION.md` §2. Copy the working shapes from
   `docs/probes/state_spike.py`. Two traps:
   - Write sheet unions as a **plain assignment**: `Sheet = Annotated[A | B, Field(...)]`. If you
     write `type Sheet = ...`, the discriminator stops working and every sheet fails to parse.
   - `Entity` has **no** `exits`, `parent_id` or `when_reached`. It gains `sheet: S | None` and
     `carried_by: EntityId | None`.

2. **Create `src/aidm/kits/scenes/tools.py`** with the `change_world` union. Copy it from
   `docs/probes/scene_kit.py`, which has all eleven arms and their `apply_change` already
   written: `reveal`, `enter`, `leave`, `move_item`, `improvise_item`, `add_trait`,
   `remove_trait`, `kill`, `join_party`, `leave_party`, `advance_thread`.

   The item rule, which looks like it needs a third field and does not: an item is **carried**
   when `carried_by` is set, and **here** when its id is in `current.present`. Dropping clears
   `carried_by` and leaves the id in `present`.

3. **Create `src/aidm/kits/scenes/boundary.py`** with `scene_spent(state) -> str | None`, using
   the five signals in `VISION.md` §2. It returns why the scene looks finished, or `None`. This
   is new code; the probe does not have it.

4. **Create `src/aidm/kits/scenes/worldsmith.py`** and `source.py`.
   - `render_worldsmith(...)` and `scene_unmet(...)` come from `docs/probes/scene_kit.py`.
   - `apply_scene(...)` is new: it validates a scene and installs it. The player is added by
     code and never named by the model; an unknown id is matched against cast names
     case-insensitively before it is refused; what the player and companions carry follows them
     while everything else stays behind; an entity's last known place is found by scanning
     `played` backwards.
   - `source.py` holds `whole_text`, `_pdf_pages`, `_passages` and `given_text`, moved from
     `src/aidm/authoring/draft.py`. Nothing else in that file survives.

### The switchover (one group; check at the end of step 10)

5. **Port Loner 3e.** In `src/aidm/engines/loner3e/`:
   - define `Loner3eState` with `engine: Literal["loner3e"]` and
     `world: SceneState[LonerSheet]`, where `LonerSheet` is the union of the actor sheet and the
     item sheet
   - put each sheet on its entity and delete the `sheets` dictionary
   - add `guidance(state)` and `scene_closed(draft)`
   - the rules themselves do not change; only the state they read does

6. **Make the payload a discriminated union.** Now that `Loner3eState` exists and carries
   `engine`, change these three `payload: SerializeAsAny[BaseModel]` fields in
   `src/aidm/state/model.py` (lines 177, 230, 267) to a discriminated union on that field, and
   change `payload: Payload` in `src/aidm/kernel/envelope.py:22` — that one is the real save
   boundary. Then delete `require_parsed_payload`, every `_legacy` property, `WorldPayload`,
   `ScenarioPayload`, `CharacterPayload`, and the two-stage parse in `src/aidm/content/io.py`.
   One `TypeAdapter` now reads a save. Delete `AnyEngine` from `src/aidm/kernel/protocol.py`
   here, and use `Engine[Loner3eState]` where it was.

7. **Create `src/aidm/kits/scenes/views.py`.** Build `NarratorView` and `PlayerView` from kit
   state, using the shapes in `VISION.md` §5. The engine supplies its sheet rows through one
   callback. Update `src/aidm/kernel/views.py` to the new shapes. `Scene.note` must appear in
   neither.

8. **Delete the old world and the seam.**
   - `src/aidm/world/` — the whole directory
   - `src/aidm/authoring/` — the whole directory
   - `src/aidm/state/scene.py` — the scene projection is the kit's job now
   - from `src/aidm/engines/core.py`: `rules`, `mechanics_of`, `mechanics_patched`,
     `mechanics_delta`, `sheet_of`, and the `mechanics_patch`, `authoring_brief` and
     `growth_due` members
   - the `grows` field from `src/aidm/kernel/envelope.py` and everywhere it is read

9. **Fix everything that imported them.** These files break at step 8 and no other step covers
   them:
   - `src/aidm/app/runtime.py:10` imports `growth_run`; delete `growth_due()`, `_extend()` and
     `apply_growth()`
   - `src/aidm/ui/create.py:12` imports `ScenarioRun`, `scenario_run`; delete
     `scenario_page` and `agent_scenario_page`, and the route that serves them in
     `src/aidm/ui/app.py`
   - `src/aidm/ui/panels.py` imports `aidm.world.scene` and `aidm.world.topology`; rewrite it
     against `PlayerView`
   - `src/aidm/harness/mcp.py:16` and `src/aidm/harness/codemode.py:19` import `Draft` and the
     authoring run; delete the four authoring tools and the growth tools
   - `tests/core/test_package_boundary.py:11` hardcodes the layer list; remove `"world"` and
     `"authoring"`, add `"kits"`

10. **Rewrite the content files by hand.** Convert `scenarios/whispering-vault/world.json` and
    `characters/kael/loner3e.json` to the new shapes. Delete every file in `saves/` — old saves
    cannot load and there is no migration. Also rewrite the fixtures under
    `tests/core/fixtures/save/` and `tests/core/fixtures/state/`.

    **Now run the full check.** Fix until green.

11. **Rebuild the golden files once** with `AIDM_GOLDEN_REGEN=1 uv run pytest`, then read every
    changed line.

12. **Full check, then play a turn and force a scene change.**

**Done when:** the check is green, a turn plays, a scene change works, `src` ≈ **6,300**.

---

# Phase 3 — The three roles and the tool surface

**Goal:** the app spawns the game master, the narrator and the worldsmith. No model code runs
inside the app.

The tools and the spawns change together; splitting them would leave the game unplayable in
between. **Steps 1–4 are checked one by one. Steps 5–9 are one atomic group.**

1. **Create `src/aidm/app/spawn.py`.** The game master works through tools and returns nothing;
   the other two return a value. So the protocol has two methods:

   ```python
   class Spawner(Protocol):
       async def act(self, prompt: str) -> None: ...
       async def write[T](self, role: Role, prompt: str, expect: type[T]) -> T: ...
   ```

   - `CliSpawner` starts the configured command with the prompt as its last argument, reads the
     final message under a timeout, and for `write` parses and validates it against `expect`,
     re-prompting **once** with the error before raising. It kills the process group if
     abandoned. Copy the process handling from `src/aidm/harness/exec.py` before you delete it.
   - `ScriptedSpawner` answers from a per-role list and **records every prompt it was given**.
     Tests use this. Nothing else in the codebase may start a process.

2. **Move the schema helper.** `src/aidm/llm.py:14` defines `schema_of`, which the MCP surface
   needs and step 8 would otherwise delete. Write a replacement in `src/aidm/app/mcp.py` — about
   twenty lines, generating a JSON schema with `$defs` inlined — and check it against the schema
   golden files. Do this **before** step 8.

3. **Change the settings.** In `src/aidm/config.py` add `command`, `model` and `timeout` for
   each of the three roles. Delete `Roles`, `RoleConfig`, `Role`, `ReasoningEffort`, and the two
   things that consume them: `Settings.role()` (line 135) and the `_keys_present` validator
   (line 143). Keep `Providers` — the image generator still needs a key. The old `.env` keys are
   ignored automatically, so no one needs to edit their file.

4. **Write the three prompt builders** in `src/aidm/turn/context.py`: `render_master`,
   `render_narrator` and `render_worldsmith` (moved in from the kit). **Delete `render_director`
   and `director_instructions`** in the same step, or you will end with both. The narrator
   prompt takes the narrator view, the told facts, the last few told passages, and the player's
   action — and nothing else.

### The switchover (one group; check at the end of step 9)

5. **Rewrite the tool surface** in `src/aidm/harness/mcp.py`, moving the file to
   `src/aidm/app/mcp.py`. Publish exactly four tools plus the engine's own: `start_turn`,
   `scene`, `change_world`, `next_scene`. Delete `end_turn`, `open_game`, `list_games`, `rules`,
   `begin_growth`, `finish_growth`, `begin_scenario` and `finish_scenario`. Add the legality
   table from `VISION.md` §4: a call that does not fit the moment is refused with a message
   saying what to do instead.

6. **Serve the tools from the running app**, so the spawned CLI reaches the live game. Mount an
   HTTP MCP endpoint on the server NiceGUI already runs. This is the hardest single piece of
   integration in the plan: today's server is a stdio server
   (`mcp.server.Server`, `harness/mcp.py:178`). If the HTTP route does not work with your CLI,
   the fallback is the in-process SDK server that `src/aidm/harness/claude.py` builds — **in
   that case, keep that file and adjust step 9.**

7. **Write `GameService.play(action)`** in `src/aidm/app/runtime.py`, following `VISION.md` §1.2.
   Its signature is `play(self, action: str | Answer)` — a decision is answered with an `Answer`,
   not a string. Three rules:
   - **The game master's exit ends the turn.** If it applied legal changes, those are the turn,
     even if it crashed. Only a turn that applied nothing is refused.
   - **The narrator runs unless** a decision is waiting and no told fact landed.
   - **`next_scene` does not end the turn.** It starts the worldsmith in the background on a
     **deep copy** of the committed state, never the live state.

8. **Start the worldsmith early.** After a turn commits, if `scene_spent` returns a reason and no
   write is running, start one using that reason as a stand-in intent. If the game master later
   gives a different intent, discard the draft and write again.

9. **Delete the old model code.**
   - `src/aidm/llm.py`
   - from `src/aidm/turn/run.py`: `director_agent`, `narrator_agent`, `build_turn_agents`,
     `as_tool`, `director_toolset`, `run_segment`
   - `GameService.submit`
   - `src/aidm/harness/` entirely: `codemode.py`, `driver.py`, `exec.py`, `codex.py`, and
     `claude.py` unless step 6 needed it
   - the `harness` setting and `Settings.code_mode` (`config.py:131`), and its readers in
     `runtime.py:88`, `runtime.py:264` and `ui/game.py:504`

   **Now run the full check.**

10. **Delete the skills and update the MCP config.** All three name tools that no longer exist,
    and the game master's brief is now built into its prompt, so a skill would be a second copy
    of it with no reader. Point `.mcp.json` and `.codex/config.toml` at the new endpoint: those
    two files are how each spawned CLI finds the server.

11. **Full check, then play a turn from the page.**

**Done when:** a turn plays end to end through three spawns, `src` ≈ **5,650**.

---

# Phase 4 — The pages

**Goal:** the browser is the whole game.

1. **Rewrite the play page** in `src/aidm/ui/game.py` to the layout in `VISION.md` §5. For each
   turn the transcript shows the player's action, the cards and dice the rules produced, then
   the narrator's lines as named bubbles with portraits. The right column has three tabs: scene,
   journal, and dev — the dev tab shows the game master's output as plain text.

2. **Delete the polling.** Remove `poll_save` and `GameService.reload`. One process owns the
   game, so there is nothing to poll for. Keep `poll_art` — illustrations still arrive late.

3. **Point the illustrator at the new view.** `GameService.scene_art`, `scene_pending`,
   `_illustrate` and `icon` (`runtime.py:137-156`) key off `NarratorView.key`, which is now
   `place`. Update `src/aidm/app/media.py` to match. Two scenes sharing a `place` must share one
   image. Also call `_illustrate` when a new scene is installed, not only when a turn commits.

4. **Rewrite the home page** in `src/aidm/ui/app.py`. Delete `_new_content`,
   `_navigate_create(engine)` and the whole `driver_for` / `close_drivers` block (lines
   172–192). With one engine there is no engine to choose. What is left: the saves to resume,
   and buttons for "new character" and "new scenario".

5. **Simplify character creation.** In `src/aidm/ui/create.py` keep `character_page` and make it
   one flat form: name, brief, concept, and picks from the chosen pack. In
   `src/aidm/engines/core.py` delete `PackCreation`. In `src/aidm/state/creation.py` keep
   `CreationStep`, `picked` and `check_picks`; delete `numbered_steps`, which existed to build
   nested step trees.

6. **Add the new-scenario page.** A small form: packs, a title, and either a premise or an
   uploaded `.md`, `.txt` or `.pdf`. On submit it reads the source, spawns the worldsmith for the
   opening scene, checks it against the scene bar, writes `scenarios/<id>/world.json`, copies
   the source beside it, and opens the game. Show a spinner; it takes several minutes.

7. **Trim the settings page.** Delete `BUILTIN_ONLY` and `CODE_MODE_ONLY` from
   `src/aidm/config.py:16-17` and the `json_schema_extra` that uses them. The rendering code in
   `src/aidm/ui/settings.py:74-82` then has nothing to show and can go too. Everything else on
   that page stays.

8. **Delete the raw-state panel** — `state_panel` in `src/aidm/ui/panels.py` and its tab.

9. **Rebuild the golden files once**, since every view changed. Read every changed line.

10. **Full check, then play a full session:** make a character, start a scenario from a premise,
    play through one scene change.

**Done when:** the whole game works from the browser, `src` ≈ **5,400**.

---

# Phase 5 — The sweep

**Goal:** nothing left behind. **This phase does not shrink `src`** — it removes a dependency and
rewrites prose. Expect the count to stay near 5,400.

1. **Remove `pydantic-ai`** from `pyproject.toml`. `ModelRetry` becomes a plain `ValueError`.
   (The schema helper was already replaced in phase 3.)

2. **Rewrite the prompt files.** Four remain: a game-master brief, a narrator brief, a
   worldsmith brief, and one short rules note for Loner. Delete every other `.md` under `src/`.
   None may mention locations, exits or the map.

3. **Rewrite `README.md` and `CLAUDE.md`** for this design. In `CLAUDE.md`, remove the rule about
   a weak model being the design bar — the roles are strong CLIs now. Update `AGENTS.md` to
   match.

4. **Prune `docs/`.** `ROADMAP.md` and `MEMORY-SYSTEM.md` describe the dead design. Keep
   `24XX.md` and `BREATHLESS.md` — phase 6 needs them.

5. **Search for leftovers.** Grep `src` and `tests` for: `mechanics`, `exits`, `parent_id`,
   `when_reached`, `frontier`, `PlayerAction`, `resolvers`, `succession`, `grows`, `harness`,
   `builtin`, `external`, `code_mode`, `director`. Delete what is dead.

6. **Full check, then play a session.**

---

# Phase 6 — The engines return

**Goal:** 24XX and Breathless play again, on the new design.

Do them one at a time, and only after phase 5 is done and the game has been played for real.
Each should cost about **500 lines**: there is no untyped state and no map to fight.

For each engine:

1. Read its notes in `docs/24XX.md` or `docs/BREATHLESS.md`.
2. Create `src/aidm/engines/<name>/` with its typed state, embedding `SceneState` with its own
   sheet union. 24XX's ship is a sheet on an entity, not a place.
3. Write its procedure tools — one per SRD rule, never more than eight.
4. Write its `guidance`, `scene_closed`, `over`, and creation options. A scene-ending signal
   no predicate can see is written to `SceneState.spent` by the rule that causes it — see phase 2.
5. Add its pack file under `src/aidm/engines/<name>/packs/` and one character file.
6. Write one scenario for it.
7. Add its test directory to `pythonpath` in `pyproject.toml`.
8. Full check, then play a turn.

**With the second engine**, bring back the little that holds more than one: the `AnyEngine`
alias for the composition root, engine discovery in the registry, and the engine choice on the
home page.

**With Breathless**, bring back player actions — `catch_breath` and `use_med_kit`. Check first
whether `catch_breath` belongs on the scene boundary instead. That may be all it needs.

---

# Checklist

- [x] Phase 0 — probe code in `docs/probes/`
- [x] Phase 1 — one engine. `src` 7,471
- [x] Phase 2 — the scene kit and the port. `src` 5,806
- [x] Phase 3 — the three roles and the tool surface. `src` 5,458
- [x] Phase 4 — the pages. `src` 5,625
- [ ] Phase 5 — the sweep. `src` ≈ 5,400
- [ ] Phase 6 — the engines return
- [ ] Full check green at every checkpoint
- [ ] The game plays from the browser at the end of every phase
- [ ] Line counts in `PROGRESS.md` for every phase
- [ ] This file deleted in the last commit; `VISION.md` stays
