# PLAN: the ten accepted proposals, in three phases

Ten simplification proposals were accepted; every one is folded in below, so this plan is the
whole of the work. Seven rows the review measured at zero or positive are refused and are not in
this plan.
Record them in `PROGRESS.md` with these reasons: `starting_items` → abstract (src 0, tests
+2); flatten `DiceLook` into `Look` (`views.py` −5 against +8 in four exploded `Look(...)`
calls, and it silently breaks `src/aidm/ui/dice_tray.js:28-30`, which reads `look.ink` /
`look.body` / `look.glow` off `ui/dice.py:18`'s `look.model_dump()`); fold `Game.commit()`
into `Engine.land()` (src −1 against 40 `.commit()` sites in twenty test files); one
`preview_character` on the seam (three 3-line overrides become three 3-line hooks plus a seam
method, net 0); move `Actor(Frozen)` to `base.py` (one `class Actor`; moving a file deletes no
line); the two `carried()` item-line sites (output changes, zero lines); and merging
`ui/settings.refusal_text` into `core/entities._refused` (they differ — see phase 3 step 7).

The split is by blast radius, not by proposal number:

- **Phase 1 — tests and fixtures.** Proposals 1, 2, 3, 5, 7, 9. `src` is not touched. One golden
  regeneration, at the end.
- **Phase 2 — `core` and `engines`.** Proposals 4, 8, and the rows of 10 that live in those two
  layers. One golden regeneration, at the end.
- **Phase 3 — `app` and `ui`.** Proposal 6 and the rows of 10 that live there. No golden moves.

Phase 1 must run first. It replaces the spliced `rules.md` and the schema tails in every prompt
fixture with markers, so a later prompt or schema edit no longer rewrites 1,382 fixture lines.
Doing phases 2 or 3 first would regenerate the big fixtures twice.

Whole plan: about **−498 fixture lines** and **−780 Python lines**.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

At baseline `uv run pytest` is **675 passing** and `uv run basedpyright` reports **1,101 errors,
every one of them in `qa/`** — playwright ships no stubs. `src` and `tests` are clean. Do not chase
the `qa/` errors; hold `src` and `tests` at zero and hold the `qa/` count where it is.

1. Do the phases in order, and the steps in a phase in order. Line numbers were measured against
   the tree at `258687c`; a step earlier in the same phase may have shifted them, so find the
   symbol the step names and treat the number as a pointer.
2. Where two accepted proposals touch the same file, the step says so. Do not fix the same line
   twice.
3. Regenerating a golden:

   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest tests/core/test_golden_turn.py tests/core/test_golden_schemas.py
   uv run pytest
   ```

   `tests/conftest.py`'s `pytest_sessionfinish` fails any run with the flag set, so the second run
   is what proves the tree green. Each phase names the **one** step where a regeneration is
   allowed. A golden that drifts at any other step is a bug in the step, not a fixture to refresh.
4. `PROGRESS.md` gets one entry per phase, newest first: `src`, `tests`, `qa` and fixture line
   counts before and after, decisions made off-plan with the reason, and refuted review findings
   with the reason. At the start `src` is 10,239, `tests` 10,757, `qa` 1,760, the four schema
   fixtures 1,495 and the thirteen prompt fixtures **2,182** — those thirteen carry no trailing
   newline, so `wc -l` under-reports them as 2,169; record 2,182. Phase 1 creates the file.
5. `pyproject.toml` already excludes `PLAN.md` from `ruff format`. Leave that line alone.
6. The standing rules hold: no `Any` beyond the `Game[P]` bound; exact types; `Refusal` is the one
   message-bearing exception and an unreachable state is a `ValueError`; a class owns its state;
   side effects stay at the edges; nothing under `engines/` reads settings; imports flow
   `core <- engines <- turn <- app <- ui`; `__init__.py` files stay empty; 100-character lines; no
   comment unless the reason is invisible in the code, and then one line.
7. The game stays playable at the end of every phase: `uv run aidm`, open a scenario, take a turn.

---

## Phase 1 — the goldens and the test scaffold

Proposals 1, 2, 3, 5, 7, 9. `src` untouched.

| count | removed | added | net |
| --- | --- | --- | --- |
| prompt fixtures | 1,382 | 13 | −1,369 |
| schema fixtures | 0 | 871 | +871 |
| `tests` Python | ~820 | ~250 | ~−570 |

Fixtures net **−498**, tests net **about −570**.

Measured for step 3, so you can check your work: the spliced `THE RULES OF THIS GAME` body is 84
lines in `breathless/master.txt`, 118 in `twentyfourxx`, 126 in `loner3e`, 78 in `tunnelgoons`. The
schema tail after `ANSWER WITH:` is 35 lines in all four `narrator.txt` (byte-identical, checksum
verified), 238 / 189 / 154 / 215 in `breathless` / `twentyfourxx` / `loner3e` / `tunnelgoons`
`worldsmith.txt`, and 40 in `twentyfourxx/interjection.txt`.

The deletions run before the fixture work: steps 6 and 7 remove tests, steps 8 and 9 then fixture
what is left. Do not reverse that order — you would fixture tests you are about to delete.

### Steps

1. **Proposal 7 — kill the dynamic import.** In `tests/support/golden_turn.py` (18 lines) add,
   below `LISTENING`:

   - one private helper for the three engines whose `behind` is the same body —
     `tests/breathless/golden_turn.py:14-24`, `tests/tunnelgoons/golden_turn.py:20-30` and
     `tests/twentyfourxx/golden_turn.py:15-25` differ only in the words and the spoken line:

     ```python
     def _one_exchange(state: AnyGame, words: str, said: str) -> AnyGame:
         """One prior exchange at the starting scene: RECENT PLAY has to render it."""
         draft = state.draft()
         draft.log[0].exchanges.append(Exchange(words=words, lines=(SpokenLine(text=said),)))
         return draft.commit()
     ```

     Drop the `narrowed(state, …)` call each satellite makes: it only narrows for the type checker
     and nothing in the body needs the engine's game type.
   - `_loner3e_behind(state)`, the body of `tests/loner3e/golden_turn.py:24-59` verbatim, minus
     `narrowed`. It is genuinely different — it inserts a whole prior `SceneRun` and `Chapter` — so
     it keeps its own function.
   - the table, after the four scripts:

     ```python
     SCRIPTS: dict[EngineId, tuple[tuple[Call, ...], Callable[[AnyGame], AnyGame]]] = {...}
     ```

2. **Proposal 7 — delete the four satellites and the two `cast()` calls.** Delete
   `tests/breathless/golden_turn.py`, `tests/loner3e/golden_turn.py`,
   `tests/tunnelgoons/golden_turn.py`, `tests/twentyfourxx/golden_turn.py` (139 lines). In
   `tests/core/test_golden_turn.py` delete `_script` (20-22) and `_behind` (25-27), drop
   `from importlib import import_module` and `from typing import cast` (lines 1 and 4), and read
   `SCRIPTS[engine_id]` in the test body instead. **−50 net.**

3. **Proposal 1 — substitute the two splices.** In `tests/core/test_golden_turn.py`, before each
   `golden(...)` call:

   - master: replace `engine.instructions.strip()` in the rendered prompt with `<<rules.md>>`. The
     spliced text is `turn/run.py:159`'s `("THE RULES OF THIS GAME", instructions)` and
     `core/prompt.py:14` strips the body, so `.strip()` is the exact needle. Verified present
     verbatim in all four `master.txt`.
   - narrator, interjection, worldsmith: replace everything after `"ANSWER WITH:\n"` with
     `<<schema>>`. `ANSWER WITH` is the last section of all three, so the tail runs to the end of
     the string.

   Write one helper in `tests/support/golden.py` and call it from both tests. Anything else — the
   `YOUR ROLE` splice from `app/prompts/*.md`, the pack content — stays in the fixture; the
   decision covers these two parts only.

4. **Proposal 1 — golden the answer models instead.** The worldsmith answer type is already handed
   to the recording callable in `test_a_worldsmith_request_renders_unchanged`
   (`tests/core/test_golden_turn.py:62`, the `_model` parameter). Capture it and add
   `golden_json(FIXTURES / "schemas" / engine_id / "worldsmith_answer.json", schema_of(model))`
   beside the prompt golden. In `tests/core/test_golden_schemas.py` add one unparametrized test
   goldening `schema_of(Narration)` and `schema_of(Interjection)` to
   `fixtures/schemas/narration.json` and `fixtures/schemas/interjection.json`. Six new fixtures,
   871 lines; each schema is now stored once instead of once per engine. **+15 test lines.**

5. **Proposal 1 — regenerate.** This is the one regeneration in phase 1. Run the two commands from
   "How to work" §3. Thirteen prompt fixtures shrink; six schema fixtures appear. The four
   `fixtures/turn/*.json` must not move — they carry facts, not prompts.

6. **Proposal 5 — move the room family's behaviour to the real engine.** `tests/engines/test_rooms.py`
   is 522 lines, of which 47-129 is the `SixthWorld` / `SixthGame` / `SixthScenario` /
   `SixthCharacter` / `SixthEngine` / `_installed` / `_place` / `_scenario` scaffold. Keep the
   scaffold and keep exactly one test on it: `test_a_sixth_room_engine_begins_a_playable_game`
   (`:132-145`) — the boundary that a second room engine can be built, begun and walked.

   Proposal 5(a) says move, not delete, and it is right: four of the five tests below are covered
   nowhere else. **Move** these four to `tests/tunnelgoons/`, rewritten against `small_world()`:

   | move from `test_rooms.py` | what it pins, uncovered elsewhere |
   | --- | --- |
   | `:166` a party member moves with the player | `rooms/world.py:245` `travelers` |
   | `:178` a `with_ids` entry who is not a member is refused | `rooms/world.py:242`, the no-`with_ids` path |
   | `:248` killing a party member drops them | `rooms/world.py:379-380`, party removal |
   | `:278` a member not at the player's place is refused | a model-validator `ValueError` from `rooms/world.py:138`, not a tool `Refusal` |

   `:147` (unlocking a way tells a card) is half covered: its card and `known` assertions are the
   same as `tests/tunnelgoons/test_tools.py:252` and `:261`, but its "the Ways out panel gains the
   row" assertion is not. Move it too and keep that assertion when you do.

   Everything from `:296` down (`a room game given a table set is refused`, the `meanwhile` block,
   the arm-guard block, `ELSEWHERE`) stays: no shipped engine exercises those states.
   **About −60**, not the −140 the proposal claimed: these are moves, not deletions.

7. **Proposal 2 — the scene family, tested once.** Delete from the engine packages and add the
   parametrized equivalents to `tests/engines/test_scene_bar.py`, which already runs its `CASES`
   over breathless, twentyfourxx and loner3e.

   `tests/twentyfourxx/test_worldsmith.py:79-192` holds **thirteen** tests, not fourteen. Eight of
   them test `apply_scene` / `install` / `render_next` — `:79`, `:85`, `:91`, `:97`, `:109`,
   `:173`, `:180`, `:187`. Give `SceneCase` an `apply` callable beside its `bar` and move those
   eight in as parametrized cases. The other five test `engines/scenes/worldsmith.py`'s bar and are
   already parametrized there — `:121`, `:133`, `:141`, `:147`, `:162` — so delete them outright.
   **+50 in `test_scene_bar.py`.**

   `tests/twentyfourxx/test_world.py:72-129` holds **eight** tests, not six, and every one of them
   exercises `engines/base.py:207` or `engines/scenes/world.py:59` rather than anything
   twentyfourxx owns. Move all eight to `test_scene_bar.py` as parametrized cases:

   | test | what it pins |
   | --- | --- |
   | `:72` `a_player_with_no_sheet_is_refused` | the world validator on the player's sheet |
   | `:79` `a_cast_that_holds_the_player_is_refused` | the player-in-cast validator |
   | `:88` `player_is_never_listed_in_the_scene` | the player-in-`here` validator |
   | `:95` `check_filing_rejects_mis_filed_cast` | `check_filing` |
   | `:105` `require_here_alive_refuses_dead_cast_member` | `require_living_here` |
   | `:112` `require_actor_none_is_the_player` | `require_actor` |
   | `:118` `require_actor_accepts_a_living_sheeted_party_member` | `require_actor` |
   | `:123` `require_actor_refuses_an_unsheeted_member` | `require_actor` |

   Then:

   - `tests/breathless/test_world.py:62-107` (46 lines) repeats four of those eight against
     breathless. Delete it outright; the moved cases now run over breathless too.
   - `tests/breathless/test_world.py`'s local helpers — delete `_scene` (`:22-29`) and `_world`
     (`:43-44`), which only the deleted tests use. **Keep `_player` (`:32-40`)**: six sheet tests
     below still call it, and it rates `bash` 10 / `dash` 8 / `sneak` 6, not
     `support/breathless.SKILLS_RATED`, so `small_world()` is not a drop-in for it. That is 12
     lines, not the 23 the proposal estimated.
   - `test_join_party_lands_a_party_joined_fact_and_adds_the_member` from
     `tests/breathless/test_engine.py:41-48` and `tests/twentyfourxx/test_engine.py:34-41`.
     `seam.py:123` stays covered by `tests/engines/test_rooms.py:204-210`, which survives step 6 —
     not by `tests/engines/test_seam.py:187`, which the proposal named in error.
   - `tests/twentyfourxx/test_engine.py:43-47`
     (`test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs`) tests
     `engines/scenes/packs.py:52`; move it to `test_scene_bar.py` beside
     `test_a_scenario_with_no_packs_is_refused_by_check_packs` (`:199`) as a parametrized case.

   **Net about −200.**

8. **Proposal 3 — the per-package fixtures.** Add `conftest.py` to `tests/breathless/`,
   `tests/twentyfourxx/` and `tests/tunnelgoons/`, each with a `draft` fixture returning
   `small_world().draft()` and a `world` fixture returning **`draft.payload`** — take `draft` as an
   argument, do not call `small_world()` a second time. Two independent fixtures would hand back
   two different worlds and any test taking both would silently stop testing one object.
   Verified call counts: `small_world().draft()` 45 in `tests/twentyfourxx/test_tools.py`, 30 in
   `tests/tunnelgoons/test_tools.py`, 25 in `tests/breathless/test_tools.py`, 4 in
   `tests/tunnelgoons/test_world.py`; `small_world().payload` 17 in
   `tests/twentyfourxx/test_world.py`, 10 in `tests/twentyfourxx/test_worldsmith.py`, 6 in
   `tests/tunnelgoons/test_world.py`. Steps 6 and 7 already removed some of those call sites;
   fixture what is left. Leave the ~15 tests that build two drafts in one body alone — they need
   the explicit call.

9. **Proposal 3 — the room fixture.** `_installed(tmp_path)` opens 13 of the tests in
   `tests/engines/test_rooms.py` (call sites at 133, 148, 167, 179, 189, 214, 227, 249, 263, 279,
   297, 323, 457) and **7** in `tests/engines/test_seam.py`. Turn each into a package fixture in a
   new `tests/engines/conftest.py`, together with the `create_character("Wren"…)` /
   `begin("the-keep"…)` preamble that follows it. Step 6 moved five of the `test_rooms.py` sites out
   of the file; fixture the eight that remain.

10. **Proposal 3 — one `_rolled` helper for the 24xx roll tests.** `tests/twentyfourxx/test_tools.py`
    has **34** `ENGINE.roll(draft, Roll(...), Random(n))` call sites, 26 of them wrapped across four
    to six lines because they pass 100 characters. Add, at the top of that file:

    ```python
    def _rolled(draft: TwentyfourxxGame, *, seed: int = 0, **args: object) -> list[Fact]:
        return ENGINE.roll(draft, Roll.model_validate(args), Random(seed))
    ```

    and rewrite the 34 sites onto one line each. **About −100.**

11. **Proposal 9 — one `hooks` field replaces four delegating dataclasses.** Add to
    `ScriptedSpawner` (`tests/support/table.py:113-142`) a
    `hooks: list[Callable[[Role, str], Awaitable[None]]]` field, awaited at the top of `run` before
    `self.prompts.append`. Then delete `_Watched` (`tests/app/test_master_tools.py:57-69`),
    `_TurnLandsFirst` (`tests/app/test_game_service.py:301-316`), `_StillSpeaking` (`:318-335`) and
    `_Blocking` (`:480-494`), and rewrite each of their four users as a local `async def` appended to
    `spawner.hooks`. **−45.**

12. **Proposal 9 — the assertion-per-field clusters.** Replace `tests/twentyfourxx/test_engine.py:49-64`
    (four tests for the two-line `Gear.notes()`) with one parametrize, and
    `tests/twentyfourxx/test_create.py:17-56` (six tests whose whole body is one comprehension
    against an expected list) with one parametrize over `(picks, expected)`. **−30.**

13. **Proposal 9 — the wiring tests.** Delete `tests/app/test_builtin.py:224-234`
    (`test_the_runtime_sends_each_role_where_its_settings_say`): same setup and same two assertions
    as `:84-96`, which is strictly larger. That file is 234 lines, so the test runs to EOF — the
    proposal's `:224-235` was one line past the end. Delete `tests/app/test_speech.py:40-46`
    (`test_speech_body_carries_the_request_shape`): it re-asserts, key by key, the four-key dict
    literal at `src/aidm/app/speech.py:105-106`. `tests/app/test_game_service.py:544-550` is also on
    this list; it goes in **phase 3 step 8**, with the live-reload deletion it belongs to.
    Correction to the proposal: the speech test was at `test_speech.py:40-46`, not `:255-261` — that
    file is 156 lines. **−20.**

14. **Proposal 9 — the two ordered panel-title lists.** `tests/tunnelgoons/test_views.py:20` and
    `tests/engines/test_views.py:156` assert an exact ordered tuple of panel titles; a UI-copy
    change breaks them for no behavioural reason. Cut each down to what its own name claims — the
    player is left out of "Also here", and the panels carry icon ids — by looking up the panel it
    needs by title instead of asserting the whole list. `test_views.py:20` is named
    `test_player_view_has_the_five_panels_in_order_and_here_leaves_out_the_player`, so rename it to
    drop the `has_the_five_panels_in_order` half you are removing. Correction: the proposal names a
    third at `tests/engines/test_rooms.py:139`; that line selects the "Ways out" panel by title and
    asserts its rows, which is a behaviour test. Leave it. **−15.**

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 2 — `core` and `engines`

Proposals 4, 8, and the rows of proposal 10 that live in `core/` or `engines/`.

| count | removed | added | net |
| --- | --- | --- | --- |
| `src` | ~85 | ~47 | ~−38 |
| `tests` | ~40 | ~20 | ~−20 |

Itemised `src`: `hires` −10, hire sentence −4, `opening_sections` −2, inline `compose` −4,
`guidance` attribute −3, `map_model` −2, roll merge −6, `ask_world` −1, `changed_tags` −4,
`drop_item` hoisted to `SceneEngine` −4, card-line fragment 0, `create_character` 0.

One golden regeneration, step 12.

### Steps

1. **Proposal 8 — `hires: bool` replaces the currying factory.** Delete `hiring()` from
   `src/aidm/engines/hiring.py:38-49` and the `Hiring` type alias (`:35`); the file keeps `HIRE`,
   `SIGNED_ON`, `HIRE_TOOL`, `HIRE_UNWRITTEN` and `Hire`. Its import block then loses `Awaitable`,
   `Callable`, `Any`, `BaseModel`, `Check`, `Game`, `WorldsmithAnswer` and `Person` — `ruff check`
   will name them. On `Engine` (`src/aidm/engines/seam.py`) replace the
   `hire_writer: Hiring[G, M] | None` field (`:82`), its assignment (`:89`) and the `hiring()` hook
   (`:129-131`) with a class attribute `hires: bool = False` and an overridable

   ```python
   async def write_sheet(self, draft: G, member: M, terms: str, worldsmith: WorldsmithAnswer) -> str
   ```

   whose base body is `raise ValueError(...)`. Keep that raise: `write_hire` still has to call
   something on a `hires`-false engine, so the guard is not deleted, only moved. Update the three
   `is None` guards at `seam.py:107`, `:113` and `:145` to read `self.hires`. Rewrite the three
   overrides (`breathless/engine.py:93-94`, `tunnelgoons/engine.py:92-93`,
   `twentyfourxx/engine.py:123-124`) as `write_sheet` bodies; twentyfourxx's is the only one that
   needs its `hire_check`. **−10.**

2. **Proposal 8 — one hire sentence.** `"The player has hired {name}, {brief}, on these terms:
   {terms}. "` opens the `HIRING` constant in `breathless/worldsmith.py:18`,
   `tunnelgoons/worldsmith.py:20` and `twentyfourxx/worldsmith.py:19`. Put that sentence in
   `engines/hiring.py` beside `SIGNED_ON` and have the three constants format it in. Safe: hire
   prompts are deliberately not goldened (`tests/core/test_golden_turn.py:68`). **−4.**

3. **Proposal 8 — `opening_sections()` replaces the `G | None`.** In `src/aidm/engines/seam.py`,
   split `_render` (`:214-232`): `render_request` (`:203-207`) keeps calling
   `self.family_sections(draft)` with `draft: G`, and `render_opening` (`:209-212`) calls a new
   abstract `opening_sections(self) -> Sections`. Then `family_sections` (`:341`) drops its
   `| None`, and the two family implementations drop theirs:
   `engines/scenes/engine.py`'s `scene_sections(world | None)` and
   `engines/rooms/engine.py:83-86`'s `map_sections(world | None, log)`. Move each family's
   three no-world sections into its own `opening_sections`. Check `hiring.py`'s imports again here:
   this step is the other half of what empties them. **−2.**

4. **Proposal 8 — inline `compose()`.** `seam.py:360-367` is one expression with two callers,
   `engines/scenes/engine.py:294` and `engines/rooms/engine.py:172`. Inline it at both and delete
   the function. Step 6 rewrites the rooms call site as well — do that one once. **−4.**

5. **Proposal 4 — `guidance` becomes a class attribute.** `RoomEngine.guidance` is abstract at
   `engines/rooms/engine.py:240` and its one implementation, `tunnelgoons/engine.py:145-146`,
   returns the constant `AUTHORING`. Declare `guidance: str` in the `RoomEngine` attribute block
   beside `family_dir`, set `guidance = AUTHORING` in `TunnelGoonsEngine`, and update the **two**
   readers, `rooms/engine.py:170` and `:230` — the plan said three. `SixthEngine.guidance`
   (`tests/engines/test_rooms.py:86`) becomes an incompatible method override the moment the
   attribute lands; turn it into `guidance = "..."` in the same commit or basedpyright fails.
   Do not touch `SceneEngine.guidance` (`scenes/engine.py:324`): it takes a `PackSelection` and has
   three real implementations. **−3.**

6. **Proposal 4 — the map model becomes a class attribute.** `map_draft()`
   (`engines/rooms/engine.py:62-65`) exists only to subscript `MapDraft[self.member]` at runtime.
   Declare `map_model: type[MapDraft[N]]` in the attribute block, set `map_model = MapDraft[Npc]` in
   `TunnelGoonsEngine` and `MapDraft[Dweller]` in `tests/engines/test_rooms.py`'s `SixthEngine`, and
   read `self.map_model` at `rooms/engine.py:170`, `:172`, `:230` and `:233`. Do not name the
   attribute `draft`: that word is the game draft everywhere else in this package. **−2.**

   **Do not go further with proposal 4.** Option (a)'s literal form — `RoomWorld` over concrete
   `Dweller` / `Person` — does not type-check: `TunnelGoonsWorld` would have to narrow `npcs` to
   `dict[Slug, Npc]` and `player` to `Goon`, which `reportIncompatibleVariableOverride` rejects
   under `typeCheckingMode = "strict"`, and `tunnelgoons/engine.py:167-205` reads `.hp`,
   `.require_sheet()` and `.hired` off what those methods return. The package stays generic; what
   goes is the two extension points that were genericity workarounds. The third,
   `starting_items` → `@abstractmethod`, is **refused**: it removes no source line and adds two to
   `SixthEngine`, a net **+2**. **Proposal 4 nets −5, not −25.**

7. **Proposal 10 — `roll` and `roll_pool` collapse.** `core/facts.py:69-74` are two identical
   signatures delegating to `_rolled`. They differ by a **computed** flag, not a constant:
   `roll` passes `highlight_kept=False`, `roll_pool` passes `highlight_kept=len(faces) > 1`. Keep
   one public `roll(faces, reason, rng, *, label="", keep_highest=False)`, fold `_rolled` into it,
   and preserve the computation — either write `keep_highest=len(faces) > 1` at each pool call site
   or spell the body `if keep_highest and len(faces) > 1`. Writing a plain `keep_highest=True`
   changes the output for a one-die pool and moves `tests/core/fixtures/turn/*.json`; if those
   fixtures drift, this is why. Four callers: `twentyfourxx/engine.py:413`,
   `breathless/engine.py:224`, `loner3e/engine.py:223` and `:224`. **−6.**

8. **Proposal 10 — `test_luck` becomes `ask_world`.** loner3e's `luck` is a health gauge; this
   tool is an oracle question, and the name collides. Move the shared args model to
   `engines/base.py` beside `luck_test` (`:361`):

   ```python
   class AskWorld(Frozen):
       question: str = Field(
           min_length=1, description="A closed question about the world where nobody is acting."
       )
   ```

   `breathless/tools.py:92-96` subclasses it to add `die` — keep that field order, `question` then
   `die`, which is what it is today. Delete `twentyfourxx/tools.py:135-138`. Rename the tool string,
   the two methods (`breathless/engine.py:295`, `twentyfourxx/engine.py:476`) and the two
   registrations (`breathless/engine.py:105`, `twentyfourxx/engine.py:140`) to `ask_world`. This
   moves `schemas/breathless/master_tools.json` and `schemas/twentyfourxx/master_tools.json`.
   **−1.**

9. **Proposal 10 — `change_tags` and `change_hindrances` share one algorithm.**
   `loner3e/world.py:85-102` and `twentyfourxx/world.py:102-120`. **Decision: a string in both
   `gained` and `lost` is refused, and the shared code refuses it explicitly with
   `check_unique(label, (*gained, *lost))` — loner3e's guard, not twentyfourxx's.** Reason: both
   implementations already refuse that call today by accident (whichever of the two membership
   loops the tag fails), so the merge order they disagree on is unreachable and neither behaviour
   is load-bearing; loner3e's guard is the one that says why, and it is also the only one that
   catches a repeat inside `lost`, which today walks past twentyfourxx's checks and then raises an
   uncaught `ValueError` out of the second `list.remove`. Put a free
   `changed_tags(name, kind, current, gained, lost) -> list[str]` in `engines/base.py` that runs the
   guard and the three refusals and returns the new list; each caller keeps its own trace and card
   text, which differ. Sharing loner3e's wording changes what twentyfourxx says: step 11 lists the
   test that has to move with it. **−4.**

10. **Proposal 10 — the rest of the small collapses in these two layers.**

    | do | where |
    | --- | --- |
    | Hoist **one** copy of the `drop_item` master-tool handler to `SceneEngine`. The two overrides have identical bodies and differ only in the game-type annotation, which `SceneEngine`'s `G` already covers. Do **not** delete them and lean on `base.py:191` — that is `Sheet.drop_item(self, item_id, owner)`, the sheet method these handlers call, and deleting both leaves `self.drop_item` unresolvable and every engine build broken | `breathless/engine.py:211`, `twentyfourxx/engine.py:317`, registered at `breathless/engine.py:99` and `twentyfourxx/engine.py:133` |
    | Wrap only the **fragment** in `actor.card_line(...)`: `f"{args.what} — {actor.card_line(sentence(pool.label))} d{pool.die}"`. `base.py:88-89` prepends to the whole string, and the three sites splice the prefix mid-string, so `actor.card_line(line)` reorders the output and fails `tests/twentyfourxx/test_tools.py:102`. No golden moves: the scripted turns roll for the player, whose `card_line` is the identity | `breathless/engine.py:235-236`, `twentyfourxx/engine.py:416-417`, `tunnelgoons/engine.py:185-191` |
    | Collapse `_item_lines` onto `item_line(key, item.name, item.notes())` — a new free helper in `engines/base.py`, `f"{name}[{key}]" + (f" — {detail}" if detail else "")`. Only this one site: the `carried()` sites in `breathless/world.py:179` and `twentyfourxx/world.py:179` are **refused**, they change the rendered separator for zero net lines | `twentyfourxx/engine.py:540-544` |
    | Make `Engine.create_character` concrete: it runs `check_picks(self.creation_steps(picks), picks)` then calls an abstract `build_character`. Four engines drop the opening line, and `core/creation.py:31`'s docstring becomes true | `seam.py`, the four `engine.py` |

11. **Fix the tests these steps move.** Expect `tests/engines/test_rooms.py` (steps 5-6),
    `tests/engines/test_hiring.py` (step 1), and `tests/twentyfourxx/test_tools.py:525` (step 9) —
    that line asserts `"not among" in ...` and loner3e's shared wording says `carries no {kind}`,
    so it fails by design; rewrite the assertion, do not revert the step. Anything else that fails
    is a step that went wrong.

12. **Regenerate.** The one regeneration in phase 2. Only three fixtures can move:
    `schemas/breathless/master_tools.json` and `schemas/twentyfourxx/master_tools.json` (step 8's
    rename), and `prompts/twentyfourxx/master.txt` (step 10's `_item_lines` collapse, if it renders
    a hired member's gear). No `worldsmith.txt` can move — that would have needed the `carried()`
    change, which is refused. No `fixtures/turn/*.json` can move — if one does, step 7's roll merge
    lost the `len(faces) > 1` computation. The `<<rules.md>>` and `<<schema>>` markers from phase 1
    mean nothing else in the prompt fixtures can move; if a fixture you did not expect drifts, read
    the diff before accepting it.

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 3 — `app` and `ui`

Proposal 6 whole (6a, 6b, 6c option (a)) and the rows of proposal 10 that live here. This is
the only phase with a behaviour change: **settings apply at the next start, not live.**

| count | removed | added | net |
| --- | --- | --- | --- |
| `src` | ~145 | ~45 | ~−100 |
| `tests` | ~70 | ~20 | ~−50 |

Itemised `src`: `resumed` −32, live reload −17, settings page −12, admission fold −11, Codex
scavenger −20, settings constants and `default_engine` −8.

No golden moves.

### Steps

1. **6a — `GameService.resume` becomes a free function.** `src/aidm/app/runtime.py:97-134` is a
   38-line classmethod re-declaring ten constructor parameters to pass them straight through; its
   only logic is choosing the state. Replace it and `_resumable` (`:504-517`) with one module-level

   ```python
   def resumed(engine: AnyEngine, store: FileStore, target: LaunchTarget, scenario: AnyScenario,
               character: AnyCharacter, *, meanwhile: bool) -> AnyGame
   ```

   holding the save/opening choice, the two identity refusals and the `disarm()` line. `_open`
   (`:470-503`), the one caller, then constructs `GameService(...)` directly. **−32.**

2. **6c — live settings reload goes.** Delete `Runtime.reload_settings` (`:426-435`), the
   `_sessions` identity check and its refusal in `admit` (`:396-398`), and the
   `__post_init__` / `_mount` split (`:365-373`) — `__post_init__` now does both jobs in one body.
   The session-eviction race, the "The settings changed. Reload this page" refusal and the
   late-image-into-a-new-session hazard go with them. **−17**; the tests are step 8.

3. **6c — the settings page stops applying.** `src/aidm/ui/settings.py`: drop the
   `apply: Callable[[], Awaitable[None]]` parameter from `SettingsForm` and `settings_page`, delete
   the `await self.apply()` try/except at `:74-82`, and reword the intro at `:71-76` to say the
   keys are written and apply at the next start — the sentence "The server port applies at the next
   start" is already there. Update the one call site, `src/aidm/ui/app.py:212`. **−12.**

4. **6b — fold the admission into `GameService`.** `Runtime.open` / `play` / `act` / `restart`
   (`:407-424`) are `async with self.admit(session): await session.<same name>(...)`. Give
   `GameService` a `gate: "Runtime"` field, set by `_open`, and move each body into the matching
   `GameService` method wrapped in `async with self.gate.admit(self)` — `open`'s `unopened()` guard
   moves with it. Delete the four `Runtime` methods. `admit`, `admitted` and `turn` stay on
   `Runtime`: `published_tools` and `call` read `self.admitted.turn` for MCP. The UI then holds one
   object: `src/aidm/ui/game.py:460`, `:471`, `:483`, `:487` and `:582` become
   `self.session.play/act/restart/open`.

   `GameService.restart` (`runtime.py:343`) is **sync** today. Folding admission in makes it a
   coroutine, so every caller has to await it. **−11.**

5. **Fix the callers.** `tests/support/table.py:244` and `:247`, `tests/app/test_master_tools.py:132`,
   `tests/app/test_mcp.py:96`, `tests/app/test_game_service.py:106`, `:112`, `:120`, `:141`,
   `tests/turn/test_turn.py:89`, `:195`, `:221`, `:237`, `:249`, `:263` and
   `tests/turn/test_decisions.py:121` all call `runtime.play/act/open`; they become
   `service.play/act/open`. `tests/app/test_game_service.py:54` and `:65` call the now-async
   `restart`: both tests become `async def` and `await game.restart()` — `asyncio_mode = "auto"`
   means no marker is needed. `tests/app/test_master_tools.py:510`'s `async with runtime.admit(...)`
   stays as it is.

6. **Proposal 10 — the Codex JSON scavenger.** `src/aidm/app/spawn.py:261-296` is 36 lines of
   untyped recursive tree search (`_last_said`, `_object`, `_string`, `_found`) that parses the same
   output twice. Replace it with two strict Pydantic V2 models — a `Loose` event shape and the
   envelope — as CLAUDE.md requires of model output, and parse once. **−20.**

7. **Proposal 10 — the settings nobody varies, and the duplicate method.**

    | do | where |
    | --- | --- |
    | `SpeechConfig.voices` and `sample_rate` become constants beside their readers | `config.py:54`, `:57`; readers `app/speech.py:81`, `:72` |
    | `RoleConfig.max_rounds` becomes a constant | `config.py:38`; reader `app/builtin.py:81`, `:94` |
    | `Settings.source_max_chars` becomes a constant | `config.py:113`; reader `app/runtime.py:453` |
    | Delete `Runtime.default_engine()` (`:375-377`), a method around `next(iter(self.engines))`; inline it at its caller | `app/runtime.py` |

    `tests/app/test_builtin.py:162` passes `max_rounds=3` to `RoleConfig` and
    `tests/app/test_speech.py:92` reads `reader.config.sample_rate`; both change with their field.

    **This breaks an existing `.env`.** `Configured` inherits `Frozen`'s `extra="forbid"`, so a
    stale `AIDM_SPEECH__SAMPLE_RATE=`, `AIDM_SPEECH__VOICES=`, `AIDM_<ROLE>__MAX_ROUNDS=` or
    `AIDM_SOURCE_MAX_CHARS=` key starts refusing at startup instead of being ignored. Record that
    as a line in `PROGRESS.md`.

    Refused: merging `ui/settings.refusal_text` (`:104`) into `core/entities._refused` (`:74`). They
    are not the same function — `_refused` returns a `Refusal` built from the **first** error,
    `refusal_text` returns a string joining **all** of them. Merging changes what the settings page
    shows. **−8.**

8. **Delete the tests that tested the deleted plumbing.** In `tests/app/test_game_service.py`:
   `test_reload_settings_cancels_an_evicted_sessions_background_task` (`:440-457`),
   `test_a_page_holding_an_evicted_session_is_refused` (`:460-470`),
   `test_a_reload_under_a_turn_in_flight_is_refused` (`:472-478`) and
   `test_reload_settings_keeps_the_injected_spawner` (`:544-550`) — the last is also phase 1
   step 13's third wiring test: it asserts that the test's own injection survived.
   `test_two_concurrent_plays_on_different_sessions_cannot_both_open_a_turn` (`:496`) **stays**; it
   pins the admission mutex, which is not going anywhere. Check `tests/ui/test_settings.py` (70
   lines) for anything reaching the deleted `apply`. **−50.**

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```
