# PLAN — the simplification

Four phases, in order: the turn and the spawn, the history, the world, the chores. Self-standing:
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
   how. Anything else is a bug. The shipped `scenarios/*/world.json` have no regen: a step that
   changes their shape rewrites them with a throwaway script in the scratchpad, never committed.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   ```
5. **If a phase runs far past its target, stop and say so.** Never pad, never invent a deletion.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** Never leave two versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **No phase adds a tool or an arm.** The cap stays fifteen, counted as tools plus
   `change_world` arms, the two party arms not counted; Phase 3 renames one tool. Every engine
   stays under 2,000 lines, imports flow `core <- engines <- turn <- app <- ui`, no `Any` beyond
   the `Game[P]` bound, every `__init__.py` empty.

| phase | what lands | `src` after (about) |
|---|---|---|
| start (`4fa8d4f`) | | 9,742 |
| 1 — the turn and the spawn | no suspension path, cold spawns, the guards gone, the page polls | 9,410 |
| 2 — the history | one `scenes()` record and one renderer, `left`, the write failure as a card, no pending art, the slug derived | 9,270 |
| 3 — the world | `world.jobs`, the run is the scene, `here`, the payload is the world, one `Board` | 9,050 |
| 4 — the chores | one `worldsmith.md`, one `CHANGE_WORLD`, three panels built once, the notes for Track G | 8,960 |

---

## Phase 1 — the turn and the spawn

### 1.1 Delete the suspension path; the resolved option is a note

1. `core/tools.py`: delete `MasterTool.during_suspension` and the `during_suspension` keyword of
   `master_tool`; `MasterTool(name, description, args, call)`. Drop `during_suspension=True` from
   the `change_world` entry in `twentyfourxx/tools.py`, `breathless/tools.py`, `loner3e/tools.py`
   and `tunnelgoons/tools.py`, and from Tunnel Goons' `unlock_way`.
2. `turn/run.py`: `Turn` loses `suspended_at_start` and `resumed` and gains `action: str = ""`,
   what the master reads as PLAYER ACTION. `Turn.begin` sets
   `turn.prompt, turn.action = consume_answer(turn, player_input)`. `consume_answer` returns
   `(player_input, player_input)` for a string, `(text, text)` for a written answer with today's
   note, and for a chosen option appends the note
   `f'The rules paused play to ask the player: "{consumed.prompt}" They chose: {option.label}. '
   f'Already resolved:\n{traces}'` to `draft.notes` and returns `(option.label, ANSWERED_BY_OPTION)`,
   imported from `turn/context.py`. `Turn.call`: a pending decision always answers
   "the rules are waiting on the player"; the `during_suspension and suspended_at_start` escape goes.
   `Turn.picture` passes `self.action` where it passed `self.prompt`.
3. `turn/context.py`: `render_picture` loses `resumed` and the
   "THE PLAYER'S DECISION, ALREADY RESOLVED" section; PLAYER ACTION prints the action given.
4. Tests: `tests/core/test_decisions.py` deletes `_chained`, `CHAIN_THE_HIT`, `CHAINING` and
   `test_a_re_suspended_continuation_keeps_the_rules_waiting`, and drops `CHAIN_THE_HIT` from
   `engine.tools` at line 90. `tests/core/test_context_boundary.py`: `_master_prompt` loses
   `resumed`; `test_a_chosen_option_is_not_shown_as_the_players_own_words` renders with the note
   in `notes` and `ANSWERED_BY_OPTION` as the action, and keeps both assertions.
5. `NEXT-SPECS.md`, G.3, after "answering one opens the next": "This re-adds the re-suspension
   path PLAN Phase 1 deleted: a tool that may run while the rules wait, and a turn that knows it
   opened suspended."

### 1.2 Cold spawns: the picture is the spawn prompt

1. `turn/context.py`: delete `render_picture`. `render_master(instructions: str,
   engine_sections: Sequence[tuple[str, str]], state: AnyGame, history: Sequence[Exchange],
   action: str, *, notes: Sequence[str] = (), recent: int = 0) -> str` renders YOUR ROLE, THE RULES
   OF THIS GAME, SCENARIO, `RECENT PLAY (this is turn N)`, the engine sections, NOTES FROM THE
   RULES, WAITING ON THE PLAYER, PLAYER ACTION, in that order. Docstring: "The whole spawn prompt:
   every spawn is cold, so the picture rides in it."
2. `turn/prompts/master.md`: delete the paragraph "Call `start_turn` first. ... `scene` gives it
   back." Nothing else changes.
3. `turn/run.py`: delete `START_FIRST`, `ALREADY_OPEN`, `TurnTool`, `TURN_TOOLS`,
   `Turn.start_turn`, `Turn.started` and the `start_turn`/`scene` branches of `Turn.call`, which
   now refuses on `engine.over`, looks the tool up, refuses a pending decision, then applies.
   `Turn.picture()` returns `render_master(self.engine.instructions, ...)` with the same
   arguments as today plus `self.action`. `NO_TURN` stays.
4. Delete `app/sessions.py` and `FileStore.sessions_path` in `core/io.py`. `app/runtime.py`:
   `GameService` loses `sessions`; `open()` loses its `else` branch; `play()` loses the
   `except BaseException` block; `restart()` loses `self.sessions.forget`; `_narrate` hands
   `answered` `partial(self.spawner.run, "narrator")`; `Runtime._open` stops building
   `Conversations`. `_act` becomes:
   ```python
   async def _act(self, turn: Turn) -> None:
       """A crashed game master still played the turn, if it applied anything legal first."""

       def nothing_landed() -> bool:
           return not turn.facts and turn.draft.pending is None

       prompt = turn.picture()
       for last in (False, True):
           try:
               _ = await self.spawner.run("master", prompt, None)
               return
           except (OSError, ValueError) as failed:
               if not nothing_landed():
                   LOGGER.warning("the game master failed after applying %d facts: %s", len(turn.facts), failed)
                   return
               if last:
                   raise
               LOGGER.warning("the game master landed nothing, spawning it again: %s", failed)
   ```
5. `Runtime.published_tools() -> tuple[MasterTool[AnyGame], ...]`: `()` with no turn in flight,
   else the playing engine's `tools`; delete the `require_unique` line and `default_engine`'s use
   there. `app/mcp.py`: `_published(tool: MasterTool[AnyGame])`, no `TurnTool` import.
6. `app/spawn.py`, `CodexDriver.command`: delete `carried` and its comment; the `resume` arm reads
   `session` for every role.
7. Tests: `tests/core/core_test_support.py`: `Table.plays(calls)` no longer prepends
   `start_turn` and loses `start`; `played` loses `start`; `_opened` builds no `Conversations`.
   `tests/loner3e/loner3e_test_support.py:85` drops `sessions=`. `tests/core/test_spawn.py`
   deletes `test_a_conversation_started_on_other_instructions_is_a_different_one`,
   `test_a_second_turn_carries_on_and_a_changed_model_starts_cold`,
   `test_a_session_file_that_does_not_validate_is_thrown_away`,
   `test_a_turn_thrown_away_takes_the_memory_of_it_with_it`,
   `test_a_restart_forgets_what_every_role_remembers`, the `sessions` import and the codex
   master assertion at lines 45 to 46. `tests/core/test_pipeline.py`:
   `test_a_resumed_master_is_not_run_again_once_a_tool_has_landed` becomes "a master that
   crashed after a tool landed is not spawned again" without its `start_turn` call;
   `test_a_resumed_master_that_landed_nothing_is_tried_again_cold` becomes "a master that landed
   nothing is spawned once more", asserting two master prompts, both with session `None`.
   `tests/core/test_tool_surface.py`: the tests that call `start_turn` or `scene` at lines 95 to
   160 go with the `ALREADY_OPEN`, `START_FIRST`, `TURN_TOOLS` imports; the last assertion of
   `test_the_surface_publishes_for_the_engine_whose_turn_is_in_flight` becomes `== []`.
   `tests/core/test_context_boundary.py`: `_master_prompt` calls `render_master` with
   `_engine().instructions` first. `tests/core/test_golden_turn.py` drops the `picture.txt`
   golden line; delete `tests/core/fixtures/prompts/{breathless,loner3e,tunnelgoons,twentyfourxx}/picture.txt`.
8. `CLAUDE.md` design decisions, replace the first bullet with: "Each role is a spawned CLI, cold
   every turn; the master's spawn prompt is the whole picture. The narrator and the worldsmith
   return typed proposals. The master's tools mutate a transactional draft: `_apply` in
   `turn/run.py` protects state with a candidate copy, an rng copy and `committed()`
   revalidation. Only resolver code changes state or rolls dice." `README.md` line 29: "Each
   returns typed proposals" becomes "The narrator and the worldsmith return typed proposals; the
   master plays through tools".

### 1.3 Delete the guards a gate already covers

1. `core/tools.py`: delete `Known` and the told-fact loop in `apply_to_draft`, which becomes
   `apply_to_draft(validate, draft, play, rng)`: the pending check, `validate(draft)`, return.
   `turn/run.py::_apply` drops `turn.engine.known`.
2. `engines/seam.py`: delete the abstract `known`. `engines/scenes/engine.py`: delete `known`.
   `engines/tunnelgoons/world.py`: delete `known`; `tunnelgoons/engine.py` drops the method and
   the import.
3. `engines/scenes/world.py::apply_scene`: delete the `scene_refusal` call and the docstring;
   the body opens at `finished = self.job_done`. `merged_cast` stays.
4. `engines/core.py`: delete `PLAYER_DEAD`. Delete the five `if not player.alive: raise
   ValueError(PLAYER_DEAD)` guards: 24XX `Skills.attempt`, `Skills.job_done`, `defend`;
   Breathless `Complications.catch_breath`, `check`.
5. Tests: the seven refusal tests that call `apply_scene` assert on `scene_refusal(draft, world)`
   instead, with their `match=` strings as `in` checks: `tests/loner3e/test_world.py`
   `test_the_player_is_in_every_scene_and_is_never_listed_in_one` and
   `test_a_scene_that_hides_someone_already_met_is_refused_whole`, whose "refused before the
   first write" assertions go; `tests/breathless/test_worldsmith.py`
   `test_apply_scene_refuses_a_scene_that_lists_the_player`,
   `test_apply_scene_refuses_a_draft_cast_entry_under_player_id`,
   `test_apply_scene_refuses_hiding_someone_met`; `tests/twentyfourxx/test_worldsmith.py`
   `test_apply_scene_refuses_a_draft_cast_entry_under_player_id`,
   `test_apply_scene_refuses_a_scene_that_lists_the_player`. Rename each `apply_scene_refuses` to
   `the_bar_refuses`.

### 1.4 The page polls; one phase

1. `turn/run.py`: delete `Turn.on_fact` and the callback loop in `_apply`;
   `Turn.begin(engine, state, player_input, rng, recent)`.
2. `app/runtime.py::GameService`: replace `busy: bool = False` and `step: TurnStep | None = None`
   with `phase: TurnStep | None = None` and a property `busy` returning `self.phase is not None`.
   Delete `_announce`. `open()`, `play(action, *, moving_on=False)` and `extend(intent)` take no
   callbacks and set `self.phase = "master"`, `"narrator"` or `"worldsmith"` where they announced;
   `_grow(intent, brief)` sets `"worldsmith"` and `"narrator"` itself; every `finally` clears
   `self.phase`, and `play`'s clears `self.turn` too. `play` no longer takes `on_commit`.
3. `ui/game.py`: `GameView` loses `live_prompt`, `live_facts` and gains
   `seen: tuple[TurnStep | None, int, int] = (None, 0, 0)`. Delete `on_step`, `on_fact`,
   `on_commit`, `tick_elapsed`. Add:
   ```python
   def poll_turn(view: GameView) -> None:
       """The page reads the turn once a second; the turn never calls the page."""
       session = view.session
       turn = session.turn
       now = (session.phase, 0 if turn is None else len(turn.facts), len(session.engine.history(session.state)))
       if now[0] != view.seen[0]:
           view.step_started = None if now[0] is None else monotonic()
       if now != view.seen:
           view.seen = now
           if view.composer is not None:
               view.composer.props(f'placeholder="{_composer_placeholder(view)}"')
           refresh_all()
           _scroll(view)
       ticker, started = view.ticker, view.step_started
       if ticker is not None and started is not None and not ticker.is_deleted:
           ticker.set_text(_clock(monotonic() - started))
   ```
   `live_turn(view)`: when `session.turn` is not `None`, the bubble is `turn.prompt` and the
   cards are `cards(turn.facts)`, the last one live; the ticker shows while `session.phase` is
   set. `_run(view, playing)`: `async with working(): await playing()`, then `poll_turn(view)`.
   `_open(view)` runs `view.session.open()`; `_send(view, player_input, *, moving_on=False)` runs
   `session.play(player_input, moving_on=moving_on)`; `submit`, `move_on` and
   `decision_panel.answer` stop passing a bubble; `restart` stops clearing live state. `game_page`
   replaces the `tick_elapsed` timer with `ui.timer(1.0, lambda: poll_turn(view))`. Every
   `bind_*_from(session, "busy", ...)` binds `"phase"`; `_can_type(session, phase: TurnStep | None)`
   reads `phase is None`.
4. Tests: `core_test_support.py`: `Table` gains `facts: list[Fact]`; `Table.plays` snapshots
   `list(self.service.turn.facts)` into it after the last call; `played` loses `on_step` and
   `on_fact`. `tests/core/test_golden_turn.py` reads `table.facts` for `turn/<engine>.json`.
   `tests/core/test_pipeline.py::test_on_fact_reports_the_visible_facts_in_resolver_order` becomes
   "the turn holds its facts in resolver order" on `table.facts`. Every `on_step`, `on_fact`,
   `.busy =` and `.step` in `tests/core/test_decisions.py`, `test_seam.py`, `test_tool_surface.py`
   and `test_session.py` reads or sets `phase`.
5. Recreate `PROGRESS.md` with this phase's entry.

### Done when

Green. Goldens: `prompts/*/master.txt` for all four engines gain, after THE RULES OF THIS GAME,
the sections `picture.txt` held, SCENARIO through PLAYER ACTION; the four `prompts/*/picture.txt`
are deleted; `prompts/*/narrator.txt`, `schemas/*/master_tools.json`, `state/*.json`,
`save/*.json` and `turn/*.json` unchanged. `uv run aidm`: a turn plays with the master spawned
once, cold; the MCP tool list is empty between turns; a chosen option shows the master one note
and `PLAYER ACTION: ` followed by `ANSWERED_BY_OPTION`; the bubble and each card reach the page
within a second; `saves/.sessions` is never written. `grep -rn
"during_suspension\|start_turn\|Conversations\|on_fact\|PLAYER_DEAD\|\.known(" src` finds
nothing. `src` about 9,410.

---

## Phase 2 — the history

### 2.1 The engine records an exchange; one run status

1. `engines/seam.py`: `record(self, state: G, exchange: Exchange) -> None`. `turn/run.py::close_segment`
   builds `Exchange(prompt=prompt, lines=_spoken(view, lines), facts=cards(facts), decision="" if
   draft.pending is None else draft.pending.prompt)`, calls `engine.record(draft, exchange)`,
   increments `draft.turn`, returns `draft.committed()`; the `notes` line goes.
2. `engines/scenes/world.py`: `SceneRun` loses `settled`, `spent`, `pursuit` and gains
   `left: str | None = None`, one comment: "None while open; "" once settled here; the player's
   words when they left for elsewhere". Delete `SCENE_TURN_CAP`, `SPENT_NOTE`, `record_exchange`.
   Keep `SCENE_SETTLED` and `SCENE_LEFT`: they are `settle`'s answer, not a nudge. `settle`:
   refuse when `self.run.left is not None`, then `self.run.left = pursuit`. `way_open`:
   `world.run.left is not None or world.at_hub`. `scene_rows`: `elif (left := self.run.left) is not
   None:` appends `PanelRow(label="Go on", detail=left, intent=left)` when `left`, else the
   "Way on" row, then `HOME_ROW` with a hub.
3. `engines/scenes/engine.py::record(state, exchange)` appends to `self.world(state).run.exchanges`.
   `engines/tunnelgoons/world.py::record(state, exchange)` appends to
   `state.payload.world.visit.exchanges`; `tunnelgoons/engine.py` follows.
4. `engines/loner3e/tools.py::_strike`: delete the `run.spent = ...` line.
5. Tests: `tests/core/test_scenes.py` deletes the two `record_exchange` tests and reads `left` in
   the `scene_rows` tests; `tests/loner3e/test_world.py` deletes
   `test_finding_everything_here_does_not_end_the_scene`,
   `test_a_scene_nobody_ends_is_ended_by_the_cap`,
   `test_the_turn_cap_ends_a_scene_that_kept_landing_things`, the `_spent` helper and the
   `run.spent == ""` assertion; `tests/core/test_tool_surface.py` deletes
   `test_the_spent_note_never_reaches_the_scene_it_is_not_about`; `tests/twentyfourxx/test_tools.py`,
   `tests/breathless/test_tools.py` and `tests/core/test_pipeline.py` read `run.left` where they
   read `run.settled` or `run.pursuit`.

### 2.2 One history, one renderer, scene by scene

1. `core/play.py`: delete `Exchange.where`. Add after `Exchange`:
   ```python
   class SceneRecord(Frozen):
       """One scene as every role reads it back; `recap` is empty while open or where none was written."""

       title: str
       question: str
       recap: str = ""
       exchanges: tuple[Exchange, ...] = ()
   ```
2. `core/views.py`: `SCENE_EXCHANGES = 20`, `TAIL_EXCHANGES = 3`.
   `render_history(scenes: Sequence[SceneRecord]) -> str`: "(the game has not started yet)" when
   no record holds an exchange; else one block per record, `SCENE: {title}` and the question on
   the next line, then for the last two records the last `SCENE_EXCHANGES` exchanges as
   `> {prompt}\n{narration}` or "(nothing yet)", and for an older record `what happened: {recap}`
   when set, else its last `TAIL_EXCHANGES` exchanges. `told_narration(scenes: Sequence[SceneRecord])
   -> tuple[str, ...]`: the non-empty narrations of the last two records' last `SCENE_EXCHANGES`
   exchanges, never a prompt, a marker or a recap.
3. `engines/seam.py`: abstract `scenes(self, state: G) -> tuple[SceneRecord, ...]`.
   `engines/scenes/world.py`: `SceneWorld.scenes()` maps `job_runs()` to
   `SceneRecord(title=run.scene.title, question=run.scene.question, recap=run.recap,
   exchanges=tuple(run.exchanges))`; `exchanges()` flattens `run.exchanges` over `runs` with no
   `model_copy`; `render_worldsmith` passes `history=render_history(self.scenes())`. Delete
   `scene_history`, `_told`, `recap_rows` and the `heading` import. `engines/scenes/engine.py`:
   `scenes(state)` delegates. The three `views.py` drop `*world.recap_rows()`.
4. `engines/tunnelgoons/world.py`: `TunnelWorld.scenes()` maps `job_visits()` to
   `SceneRecord(title=place.name, question=place.brief, exchanges=tuple(visit.exchanges))` with
   `place = self.require_place(visit.place)`; `exchanges()` flattens. `tunnelgoons/worldsmith.py`:
   THIS JOB in `_render_return` is `render_history(world.scenes())`; delete `_told_tail`,
   `TAIL_EXCHANGES`, the `Exchange` import. `tunnelgoons/engine.py` gains `scenes`.
   `engines/hub.py`: delete `heading`.
5. `core/views.py::NarratorView` loses `art_prompt`; `engines/scenes/views.py` and
   `engines/tunnelgoons/views.py` stop building it. `app/media.py::illustration_request` builds
   the line itself: `f"The place: {scene.title} — {scene.situation}"` then
   `f"Present: {one.name} — {one.brief}"` per subject.
6. `turn/context.py`: `render_master(instructions, engine_sections, state, scenes:
   Sequence[SceneRecord], action, *, notes)` prints `render_history(scenes)` under RECENT PLAY;
   `render_narrator(view, *, evidence, prompt, scenes: Sequence[SceneRecord])` prints
   `"\n\n".join(told_narration(scenes)) or "(nothing yet)"` under WHAT THE PLAYER HAS READ. Delete
   `_recent`, `_recent_exchange`, `told_passages`, `recent`. `turn/run.py`: `Turn` loses `recent`;
   `Turn.begin(engine, state, player_input, rng)`; `picture()` passes
   `self.engine.scenes(self.draft)`.
7. `config.py`: delete `Settings.recent_exchanges`. `app/runtime.py`: `GameService` loses
   `settings`; `Runtime._open` stops passing it; `play` calls `Turn.begin(self.engine, self.state,
   action, self.rng)`; `_narrate` passes `scenes=self.engine.scenes(draft)`.
8. `ui/game.py::chat`: delete the `heading` variable and the `exchange.where` block.
   `app/launch.py::load_catalog`: `scenes = engine.scenes(state)`; `where = scenes[-1].title if
   scenes else ""`.
9. Tests: `tests/core/test_scenes.py` asserts the flat order of `exchanges()` where it asserted
   `where`, and moves its `scene_history` and `recap_rows` tests to `tests/core/test_views.py` as
   three `render_history` tests: an older scene prints its recap, the last two print whole, an
   older scene with no recap prints its tail; one `told_narration` test: no prompt, no recap.
   `tests/ui/test_launcher.py::test_the_catalog_reports_where_a_save_left_off` needs no exchange.
   `tests/ui/test_settings.py:28` drops the `recent_exchanges` box. `tests/core/test_context_boundary.py`
   drops `art_prompt` from the field set and passes `scenes=` where it passed `passages=`.
   `tests/tunnelgoons/test_views.py` moves its `art_prompt` assertions onto
   `illustration_request` in `tests/core/test_media.py`. `tests/core/test_tool_surface.py:541`
   drops the trailing `1`.
10. `NEXT-SPECS.md` decision 2: "The platform's `recent_exchanges` stays at 20." becomes "The
    window is `SCENE_EXCHANGES` in `core/views.py`, 20, a constant and not a setting."

### 2.3 The write failure is a card

1. `app/runtime.py`: delete `GameService.write_failure` and its two clears. Add beside `CROSSED`:
   `UNWRITTEN = Fact(kind="way_unwritten", told=True, trace="the way on could not be written",
   card="The way on could not be written. You are still where you were.")`. `_grow`'s `except`
   logs as today, then `draft = self.state.draft()` and
   `self.commit(close_segment(self.engine, self.engine.narrator_view(draft), draft, intent, (),
   (UNWRITTEN,)))`, then returns.
2. `ui/panels.py`: delete `NO_WAY_ON` and the sidebar line. `ui/game.py::_run`: delete the toast.
3. Tests: `tests/core/test_crossing_integrity.py:75` and the three `write_failure` assertions in
   `tests/core/test_tool_surface.py` assert `history[-1].facts[0].kind == "way_unwritten"`, the
   scene unchanged, and the reason in `caplog.text` where it mattered.

### 2.4 Media has no pending state

1. `app/media.py`: delete `Illustrator.scene_pending`. `app/speech.py`: delete `Reader.pending`.
   `app/runtime.py`: delete `scene_pending`, `clip_pending`.
2. `ui/game.py`: `GameView.shown_art: Path | None = None`, `shown_clip: Path | None = None`;
   `poll_media` compares `session.scene_art()` and `session.newest_clip()` to them; `_scene_art`
   loses the skeleton branch; `game_page` sets `view.shown_clip = session.newest_clip()`.
3. Tests: `tests/core/test_speech.py` drops the `pending` and `clip_pending` assertions at lines
   104, 128 and 187.

### 2.5 The slug is derived

1. `app/launch.py`: `LaunchTarget(scenario_id, character_id)`; `slug` becomes a property
   returning `f"{self.scenario_id}--{self.character_id}"`; `path` returns
   `f"/game/{self.scenario_id}/{self.character_id}"`. `launch_target` and `load_catalog` build it
   from the two ids; `load_catalog` skips a save whose file stem is not `target.slug` with the
   warning "skipping save %r: filed under another name".
2. `ui/app.py`: the route is `/game/{scenario}/{character}`. `core/io.py`, above
   `_SAVE_SLUG_PATTERN`: "# Two content ids joined by `--`: a save name is not a `Slug`."
3. Tests: every `LaunchTarget(slug=...)` in `tests/core/core_test_support.py`,
   `tests/loner3e/loner3e_test_support.py` and `tests/ui/test_launcher.py` drops `slug`;
   `tests/core/test_session.py` saves under `TARGET.slug` where it saved under `"poc"`; the
   expected dict at `test_launcher.py:69` loses `slug`.
4. `PROGRESS.md` entry.

### Done when

Green. Goldens: `state/{breathless,breathless-campaign,loner3e,loner3e-campaign,twentyfourxx,twentyfourxx-campaign}.json`
and `save/{breathless,loner3e,twentyfourxx}.json` lose `settled`, `spent` and `pursuit` on every
run and gain `"left": null`; `prompts/*/master.txt` for all four engines print RECENT PLAY as
`SCENE: <title>`, the question, then the exchange, with no `[at ...]` tag; `prompts/*/narrator.txt`,
`schemas/*/master_tools.json`, `turn/*.json` and the Tunnel Goons state and save fixtures
unchanged. `uv run aidm`: a third scene's master picture shows the first scene as its recap and
the second whole; the narrator prompt holds narration only; a failed crossing lands a card in the
chat and the game plays on; a game opens at `/game/<scenario>/<character>`; no grey box while art
generates. `grep -rn "recent_exchanges\|told_passages\|art_prompt\|write_failure\|scene_pending\|\.where\b" src`
finds nothing. `src` about 9,270.

---

## Phase 3 — the world

### 3.1 Jobs are one stored list; `after_job`

1. `engines/hub.py`: delete `Debrief`, `Stop`, `job_titles`, `job_start`, `closed_jobs`. `Job`
   becomes:
   ```python
   class Job(Mutable):
       title: str
       place: Slug
       terms: str = ""  # as the scene that left the hub wrote them; empty for Tunnel Goons
       started: int | None = None  # index of the first run or visit away from the hub
       finished: bool = False  # the master's verdict
       debrief: str | None = None  # the hub's word on the return; the job is closed once set
   ```
   Add `check_jobs(hub: Slug | None, jobs: Sequence[Job]) -> None`: a job with no hub is refused;
   every job but the last has a `debrief`; a job with a `debrief` or `finished` has `started`.
   `ledger`, `jobs_panel` and `job_closed` read `job.debrief` and `job.finished`; `ledger` prints
   `  the job: {terms}` under an unfinished job with terms. `master_tail(hub, at_hub, board, jobs,
   open_job: Job | None)` prints THE JOB when `open_job is not None and open_job.terms`.
2. `engines/scenes/world.py`: `Scene` loses `debrief` and `job`. `SceneWorld.jobs: list[Job] =
   Field(default_factory=list)` after `board`. Delete `stops`, `jobs()`, the `job` property and
   `NextScene`'s stored twin `SceneRun.job_done`. Add `open_job() -> Job | None`, the last job
   while its `debrief` is `None`; `closed_jobs() -> tuple[Job, ...]`, those with a `debrief`;
   `job_done` becomes a property over `open_job().finished`. `job_runs()`: `self.runs[open.started:]`
   for an open job with `started`, else all runs with no hub, else `self.runs[-1:]`. `settle`:
   on `job_done`, refuse when `open_job()` is `None` or `at_hub`, else set `finished`.
   `apply_scene`: a `JobDraft` appends `Job(title=draft.title, place=draft.place, terms=draft.job,
   started=len(self.runs))` before the run is appended; a `ReturnDraft` sets `debrief` on the
   open job, refusing "no job is open to close" when none. `scene_of(draft)` loses `finished`.
   `check_hub(hub, board, runs, jobs)`: `check_board`, `check_jobs`, and run 0 at the hub when
   there is one. `SceneCanon` passes `()` for jobs. `scene_rows` reads the open job's `terms`;
   `hub_rows` passes `closed_jobs()` and `finished=self.job_done`.
3. `engines/scenes/worldsmith.py::install_scene`: the return branch reads `job = world.jobs[-1]`,
   `job.finished`, and returns `(job_closed(job), opened)`. The three engines' `views.py` call
   `master_tail(world.hub, world.at_hub, world.board, world.closed_jobs(), world.open_job())`;
   `engines/scenes/views.py` calls `jobs_panel(world.closed_jobs())`.
4. `engines/tunnelgoons/world.py`: `Visit(place, exchanges)`; `TunnelWorld` loses `job_done` and
   gains `jobs: list[Job]`; delete `stops`, `jobs()`, `check_hub`, the module `job_open`;
   `_playable` runs `check_board`, `check_jobs(self.hub, self.jobs)` and visit 0 at the hub;
   `open_job`, `closed_jobs`, `job_visits` as the scene world's; the `job_open` property is
   `open_job() is not None`. `tunnelgoons/tools.py::move`, after the visit is appended: when the
   last job has no `debrief` and no `started` and the destination is not the hub, `started =
   len(world.visits) - 1`; `level_up` sets `finished` on the open job. `tunnelgoons/worldsmith.py::install_extension`:
   a return sets `debrief` and the board on the open job, refusing "no job is open to report" when
   none, and returns `(job_closed(job),)`; taking a job pops a last job whose `started` is `None`,
   then appends `Job(title=start.name, place=written.start)`. `_render_return` reads
   `closed_jobs()` and the open job's `finished`. `tunnelgoons/views.py` passes `closed_jobs()`
   and `None` to `master_tail`, `closed_jobs()` to `jobs_panel`.
5. Rename 24XX's tool: `JobDone` becomes `AfterJob`, `Skills.job_done` becomes `after_job`, the
   tool is `"after_job"` with description "The SRD's after-a-job step, once per job, when the
   player's own words close it: raise the named skill and pay out its credits."; `JOB_DONE_NOTE`
   names `after_job`; `twentyfourxx/rules.md` says `after_job` at its "Job done" heading, lines
   54 to 55 and line 64, and `docs/24XX.md` at lines 48 and 74. The `job_done` flag of
   `next_scene` at `rules.md` line 62 keeps its name.
6. Tests: `tests/core/test_hub.py` deletes
   `test_the_job_walk_reads_titles_closed_jobs_and_start`,
   `test_the_job_walk_on_tunnel_goons_stops`, `test_check_hub_refuses_a_debrief_with_no_hub`,
   `test_check_hub_refuses_a_hub_run_right_after_a_hub_run`,
   `test_check_hub_accepts_a_job_between_two_hub_visits`,
   `test_heading_prefixes_the_job_only_when_it_differs_from_the_title`,
   `test_closed_jobs_carries_the_terms_the_leaving_scene_wrote`, and adds three `check_jobs`
   tests: a job with no hub, an earlier job without a debrief, a debrief on an unwalked job.
   `tests/tunnelgoons/test_tools.py` adds "a tavern visit mid-job keeps the job open". Every
   `Debrief(text=..., finished=...)` in `tests/core/test_scenes.py`, `test_hub.py`,
   `tests/tunnelgoons/test_world.py` and `test_worldsmith.py` becomes the text and a `finished`
   on the job; `tests/twentyfourxx/test_tools.py` lines 208 to 222 and `test_worldsmith.py` say
   `after_job`; `tests/core/test_scenes.py` lines 66 to 100 read `jobs[-1].finished`.

### 3.2 The run is the scene, and `here` is one list

1. `engines/scenes/world.py`: delete `Scene`. `SceneRun(Mutable)` carries, in this order:
   `place: Slug`, `title: str`, `question: str = Field(min_length=10)`, `situation: str =
   Field(min_length=40)`, `secret: str = ""`, `here: list[CheckedEntityId]`, `exchanges`,
   `left`, `recap`, with `Scene`'s comments on `place`, `question` and `secret`. `SceneCanon`
   loses `present` and `hidden`; `opening: SceneRun`. Delete `SceneWorld.current`; every
   `world.current.x` reads `world.run.x` and every `run.scene.x` reads `run.x`, in
   `scenes/world.py`, `scenes/worldsmith.py`, `scenes/views.py`, the three engines' `views.py`
   and `tools.py`, and the tests. `scene_of` becomes `run_of(draft) -> SceneRun`.
2. `SceneWorld.present() -> list[EntityId]` and `hidden() -> list[EntityId]` filter `run.here` by
   `cast[one].known`. `check_named(here, cast)`: unique, each in the cast. `_consistent`:
   `check_named(self.run.here, self.cast)`, the player not in `run.here`, the party within it.
   `require_here`: refuse when `one.id not in self.run.here or not one.known`. `reveal_hidden`:
   refuse "not hidden here" when not in `run.here` or already known, then `reveal` and the card.
   `enter`: refuse "already here" when in `run.here`, then append. `leave`: remove from `run.here`.
   `last_seen` scans `run.here`. `here()` yields the player then `present()`. `hidden_lines` reads
   `hidden()`. `apply_scene` appends `run_of(draft)` with `here=[*self.party, *present, *hidden]`
   after marking `present` known. `new_world`: `runs=[canon.opening]` from the deep copy.
   `opening_canon`: `here=[*present, *hidden]` on the opening after marking `present` known.
   `scene_unmet` keeps every draft check.
3. Rewrite the six scene `scenarios/*/world.json`, `amber-tap`, `buried-bell`, `drowned-road`,
   `silent-relay`, `waystation`, `whispering-vault`: `opening.here` is `present` followed by
   `hidden`; the canon's `present` and `hidden` keys go.
4. Tests: `core_test_support.with_entity` appends to `run.here`; `tests/loner3e/test_world.py`
   lines 245 to 248 set `known` on the entity instead of moving lists;
   `tests/core/test_tool_surface.py:394` asserts membership in `world.hidden()`;
   `tests/core/test_scenes.py::_run` builds a `SceneRun` directly; `tests/core/test_seam.py` and
   the engine `test_world.py` files build `SceneRun` where they built `Scene`.

### 3.3 The payload is the world

1. Delete `SceneState`, `SceneScenario` in `engines/scenes/world.py` and `TunnelGoonsState`,
   `TunnelGoonsScenario` in `engines/tunnelgoons/world.py`. `new_world[C: Person, P: Person](world_type:
   type[SceneWorld[C, P]], canon: SceneCanon[C], player: P) -> SceneWorld[C, P]` constructs
   `world_type(...)`. Every function typed on `SceneState[Any, Any]` is typed `[W: SceneWorld[Any,
   Any]](state: Game[W])`: `check_game`, `way_open`, `player_over`, `narrator_view`,
   `player_view`, `install_scene`; `build_scenario(file_type: type[Scenario[SceneCanon[C]]], ...)`
   passes `payload=opening_canon(written, source)`. `SceneEngine.world(state)` returns
   `state.payload`; `new_game` reads `scenario.payload` as the canon.
2. `twentyfourxx/world.py`: `TwentyfourxxGame(Game[TwentyfourxxWorld])`,
   `TwentyfourxxScenarioFile(Scenario[SceneCanon[Person]])`, `TwentyfourxxState` deleted;
   `breathless/world.py` the same with `BreathlessWorld`; `loner3e/world.py`:
   `class LonerWorld(SceneWorld[LonerCharacter, LonerCharacter])` carrying `twist` with its
   comment, `Loner3eGame(Game[LonerWorld])`, `Loner3eScenarioFile(Scenario[SceneCanon[LonerCharacter]])`.
   Each engine's `new_state` returns `new_world(<World>, canon, player_x(character))`.
   `tunnelgoons/world.py`: `TunnelGoonsGame(Game[TunnelWorld])`,
   `TunnelGoonsScenarioFile(Scenario[MapCanon])`; `tunnelgoons/engine.py::new_game` returns the
   `TunnelWorld`; `tunnelgoons/worldsmith.py::build_scenario` passes the `MapCanon` as `payload`.
3. Every `.payload.world` in `src` and `tests` becomes `.payload`; `draft.payload.twist` stays.
   `tests/core/test_seam.py` builds `FifthState` as a `SceneWorld` subclass and its scenario file
   on `SceneCanon`.
4. Rewrite all eight `scenarios/*/world.json`: `payload` holds what `payload.world` held.

### 3.4 One board rule

1. `engines/hub.py`: `type Board = Annotated[tuple[Offer, ...], Field(min_length=BOARD_MIN,
   max_length=BOARD_MAX)]`. `check_board(hub, board)` refuses only a non-empty board with no hub.
2. `engines/scenes/drafts.py::HubDraft.offers: Board`. `tunnelgoons/worldsmith.py`:
   `ReturnDraft.offers: Board`; `MapDraft.board: Board | None = None`; `_hub_unmet` refuses "a
   `board` of two or three offers" when `None`; `_board_unmet` refuses when not `None`;
   `opening_canon` passes `board=draft.board or ()`.
3. Tests: `tests/core/test_hub.py` deletes `test_check_board_accepts_two_or_three_offers_at_a_hub`
   and keeps only the no-hub case of `test_check_board_refuses_a_board_with_the_wrong_shape`;
   `tests/tunnelgoons/test_worldsmith.py` lines 276 to 297 read the new refusal text.
4. `NEXT-SPECS.md` G.2, "After a job": `JobDone.raises` becomes `AfterJob.raises`; "One call per
   job." becomes "One call per job: a `raised: bool` on the `Job` record refuses the second."
   G.4's done-when says `after_job`.
5. `PROGRESS.md` entry.

### Done when

Green. Goldens: every `state/*.json` and `save/*.json` holds `payload` as the world with no
`world` key, `"jobs": []` after `board`, and for the six scene fixtures each run carries `place`,
`title`, `question`, `situation`, `secret`, `here`, `exchanges`, `left`, `recap` with no `scene`,
`present`, `hidden`, `job_done`; the two Tunnel Goons fixtures' visits carry `place` and
`exchanges` only and the world no `job_done`; `loner3e*.json` carries `twist` beside the world's
fields; `schemas/twentyfourxx/master_tools.json` and `prompts/twentyfourxx/master.txt` say
`after_job`; the other `master.txt`, every `narrator.txt` and `turn/*.json` unchanged. The eight
`scenarios/*/world.json` load. `uv run aidm`: a campaign takes a job, plays it, goes home, and the
ledger lists it; a Tunnel Goons job left open at the tavern can be taken again; `enter` on
someone hidden here is refused. `grep -rn "Stop\b\|Debrief\|job_titles\|closed_jobs(hub\|SceneState\|payload\.world\|\.current\b" src`
finds nothing. `src` about 9,050; `engines/scenes/world.py` under 600.

---

## Phase 4 — the chores

### 4.1 One `worldsmith.md`; one `CHANGE_WORLD`

1. Create `engines/scenes/worldsmith.md` as `twentyfourxx/worldsmith.md` minus the paragraph
   "The cast carries no dice. ..."; delete `twentyfourxx/worldsmith.md`, `breathless/worldsmith.md`,
   `loner3e/worldsmith.md`. `engines/scenes/engine.py`: `WORLDSMITH = (Path(__file__).parent /
   "worldsmith.md").read_text(encoding=ENCODING)` replaces the `role` attribute; `author` and
   `advance` pass it. `loner3e/creation.py::_AUTHORING` gains "Every scene bears on the player's
   `goal`, or brings their `nemesis` nearer." and "Give a door or a storm the `skills` and
   `frailties` it resists with."
2. `engines/tunnelgoons/tools.py`: delete `CHANGE_WORLD`; import it from `aidm.engines.core`.

### 4.2 Character, Here and Trail panels built once

1. `engines/core.py`, beside `party_panel`: `character_panel(rows: Rows) -> Panel` titled
   "Character"; `here_panel(player: Subject, others: Iterable[Subject]) -> Panel` titled "Here"
   with `f"{player.name} (you)"` first and `icon_id` on every row; `trail_panel(titles:
   Iterable[str]) -> Panel` titled "Trail".
2. `engines/scenes/views.py::player_view` uses the three, with `subject_of` over `here()` minus
   the player and `run.title` over `job_runs()`; delete its `trail_panel`.
   `engines/tunnelgoons/views.py::player_view` uses them with `_character_rows`, `subject_of`
   over known npcs at the current place and place names over `job_visits()`; delete `_here_rows`.
3. `NEXT-SPECS.md`: under "Refused in this round" add "Folding the `Kill` arm into `engines/core.py`:
   24XX's succession (G.2) changes what a kill does, so the arm stays per engine." Under G.1,
   first bullet, add "Not a gap today: `NarratorView.party` and the two arms in 24XX and
   Breathless land here."
4. `PROGRESS.md` entry.

### Done when

Green; every golden unchanged. `ls src/aidm/engines/*/worldsmith.md` lists `tunnelgoons` alone;
`grep -rn "CHANGE_WORLD = " src` finds `engines/core.py` alone; `grep -rn "title=\"Here\"\|title=\"Trail\"\|title=\"Character\"" src`
finds `engines/core.py` alone. `uv run aidm`: a Loner scene is written with the same rules as
before, and the sidebar shows the three panels in every engine. `src` about 8,960.
