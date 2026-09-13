# PLAN: the ten accepted proposals, in three phases

All ten proposals in `PROPOSALS.md` are accepted. Nothing under "Considered and excluded" is here.

The split is by blast radius, not by proposal number:

- **Phase 1 — tests and fixtures.** Proposals 1, 2, 3, 5, 7, 9. `src` is not touched. One golden
  regeneration, at the end.
- **Phase 2 — `core` and `engines`.** Proposals 4, 8, and the eleven rows of 10 that live in those
  two layers. One golden regeneration, at the end.
- **Phase 3 — `app` and `ui`.** Proposal 6 and the three rows of 10 that live there. No golden
  moves.

Phase 1 must run first. It replaces the spliced `rules.md` and the schema tails in every prompt
fixture with markers, so a later prompt or schema edit no longer rewrites 1,369 fixture lines.
Doing phases 2 or 3 first would regenerate the big fixtures twice.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

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
   with the reason. At the start `src` is 10,239, `tests` 10,757, `qa` 1,760, the thirteen prompt
   fixtures 2,269 and the four schema fixtures 1,495. Phase 1 creates the file.
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
| prompt fixtures | 1,369 | 4 | −1,365 |
| schema fixtures | 0 | 871 | +871 |
| `tests` Python | ~900 | ~250 | ~−650 |

Fixtures net **−494**, tests net **about −650**.

Measured for step 3, so you can check your work: the spliced `THE RULES OF THIS GAME` body is 84
lines in `breathless/master.txt`, 118 in `twentyfourxx`, 126 in `loner3e`, 78 in `tunnelgoons`. The
schema tail after `ANSWER WITH:` is 35 lines in all four `narrator.txt` (byte-identical, checksum
verified), 238 / 189 / 154 / 215 in `breathless` / `twentyfourxx` / `loner3e` / `tunnelgoons`
`worldsmith.txt`, and 40 in `twentyfourxx/interjection.txt`.

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

6. **Proposal 3 — the per-package fixtures.** Add `conftest.py` to `tests/breathless/`,
   `tests/twentyfourxx/` and `tests/tunnelgoons/`, each with a `draft` fixture returning
   `small_world().draft()` and a `world` fixture returning `small_world().payload`. Verified call
   counts: `small_world().draft()` 45 in `tests/twentyfourxx/test_tools.py`, 30 in
   `tests/tunnelgoons/test_tools.py`, 25 in `tests/breathless/test_tools.py`, 4 in
   `tests/tunnelgoons/test_world.py`; `small_world().payload` 17 in
   `tests/twentyfourxx/test_world.py`, 10 in `tests/twentyfourxx/test_worldsmith.py`, 6 in
   `tests/tunnelgoons/test_world.py`. Leave the ~15 tests that build two drafts in one body alone —
   they need the explicit call.

7. **Proposal 3 — one `_rolled` helper for the 24xx roll tests.** `tests/twentyfourxx/test_tools.py`
   has **34** `ENGINE.roll(draft, Roll(...), Random(n))` call sites, 26 of them wrapped across four
   to six lines because they pass 100 characters. Add, at the top of that file:

   ```python
   def _rolled(draft: TwentyfourxxGame, *, seed: int = 0, **args: object) -> list[Fact]:
       return ENGINE.roll(draft, Roll.model_validate(args), Random(seed))
   ```

   and rewrite the 34 sites onto one line each. **About −100.**

8. **Proposal 3 — the room fixture.** `_installed(tmp_path)` opens 13 of the tests in
   `tests/engines/test_rooms.py` (call sites at 133, 148, 167, 179, 189, 214, 227, 249, 263, 279,
   297, 323, 457) and 8 in `tests/engines/test_seam.py`. Turn each into a package fixture in a new
   `tests/engines/conftest.py`, together with the `create_character("Wren"…)` / `begin("the-keep"…)`
   preamble that follows it. Do this before step 10, which deletes some of those tests.

9. **Proposal 9 — one `hooks` field replaces four delegating dataclasses.** Add to
   `ScriptedSpawner` (`tests/support/table.py:113-142`) a
   `hooks: list[Callable[[Role, str], Awaitable[None]]]` field, awaited at the top of `run` before
   `self.prompts.append`. Then delete `_Watched` (`tests/app/test_master_tools.py:57-69`),
   `_TurnLandsFirst` (`tests/app/test_game_service.py:301-316`), `_StillSpeaking` (`:318-335`) and
   `_Blocking` (`:480-494`), and rewrite each of their four users as a local `async def` appended to
   `spawner.hooks`. **−45.**

10. **Proposal 5 — move the room family's behaviour to the real engine.** `tests/engines/test_rooms.py`
    is 522 lines, of which 47-129 is the `SixthWorld` / `SixthGame` / `SixthScenario` /
    `SixthCharacter` / `SixthEngine` / `_installed` / `_place` / `_scenario` scaffold. Keep the
    scaffold and keep exactly one test on it: `test_a_sixth_room_engine_begins_a_playable_game`
    (`:132-145`) — the boundary that a second room engine can be built, begun and walked. Delete
    these, whose coverage already exists against the real engine:

    | delete from `test_rooms.py` | covered by |
    | --- | --- |
    | `:147` unlocking a way tells a card | `tests/tunnelgoons/test_tools.py:252` and `:261` |
    | `:166` a party member moves with the player | `tunnelgoons/test_tools.py:240` |
    | `:178` a `with_ids` entry who is not a member is refused | `tunnelgoons/test_tools.py:240` |
    | `:248` killing a party member drops them | `tunnelgoons/test_tools.py:297` |
    | `:278` a member not at the player's place is refused | `tunnelgoons/test_tools.py:240` |

    Everything from `:296` down (`a room game given a table set is refused`, the `meanwhile` block,
    the arm-guard block, `ELSEWHERE`) stays: no shipped engine exercises those states.
    **About −140.**

11. **Proposal 2 — the scene family, tested once.** Delete from the engine packages and add the
    parametrized equivalents to `tests/engines/test_scene_bar.py`, which already runs its `CASES`
    over breathless, twentyfourxx and loner3e:

    - `tests/twentyfourxx/test_worldsmith.py:79-192` (114 lines). Eight of these test
      `engines/scenes/worldsmith.py`'s bar and are already parametrized there — delete outright.
      The other six test `apply_scene` / `install` / `render_next` (`:79`, `:85`, `:91`, `:97`,
      `:109`, `:173`, `:180`, `:187`); give `SceneCase` an `apply` callable beside its `bar` and add
      them as parametrized cases. **+50 in `test_scene_bar.py`.**
    - `tests/twentyfourxx/test_world.py:72-129` (58 lines): the player-in-cast validator,
      `check_filing`, `require_here_alive` and `require_actor` ×3, all `engines/base.py:207` and
      `engines/scenes/world.py:59`.
    - `tests/breathless/test_world.py:62-107` (46 lines): the same four checks again.
    - `tests/breathless/test_world.py`'s local helpers — delete `_scene` (`:22-29`) and `_world`
      (`:43-44`), which only the deleted tests use. **Keep `_player` (`:32-40`)**: six sheet tests
      below still call it, and it rates `bash` 10 / `dash` 8 / `sneak` 6, not
      `support/breathless.SKILLS_RATED`, so `small_world()` is not a drop-in for it. That is 12
      lines, not the 23 the proposal estimated.
    - `test_join_party_lands_a_party_joined_fact_and_adds_the_member` from
      `tests/breathless/test_engine.py:41-48` and `tests/twentyfourxx/test_engine.py:34-41`;
      `seam.py:123` is already covered by `tests/engines/test_seam.py:187` and
      `tests/engines/test_rooms.py:204`.
    - `tests/twentyfourxx/test_engine.py:43-47`
      (`test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs`) tests
      `engines/scenes/packs.py:52`; move it to `test_scene_bar.py` beside
      `test_a_scenario_with_no_packs_is_refused_by_check_packs` (`:199`) as a parametrized case.

    This file overlaps step 6: `tests/breathless/test_world.py` and
    `tests/twentyfourxx/test_world.py` both take the `world` fixture there. Delete first, then
    re-fixture what is left. **Net about −200.**

12. **Proposal 9 — the assertion-per-field clusters.** Replace `tests/twentyfourxx/test_engine.py:49-64`
    (four tests for the two-line `Gear.notes()`) with one parametrize, and
    `tests/twentyfourxx/test_create.py:17-56` (six tests whose whole body is one comprehension
    against an expected list) with one parametrize over `(picks, expected)`. **−30.**

13. **Proposal 9 — the wiring tests.** Delete `tests/app/test_builtin.py:224-235`
    (`test_the_runtime_sends_each_role_where_its_settings_say`): same setup and same two assertions
    as `:84-96`, which is strictly larger. Delete `tests/app/test_speech.py:40-46`
    (`test_speech_body_carries_the_request_shape`): it re-asserts, key by key, the four-key dict
    literal at `src/aidm/app/speech.py:105-106`. `tests/app/test_game_service.py:544-550` is also on
    this list; it goes in **phase 3 step 8**, with the live-reload deletion it belongs to.
    Correction to the proposal: the test was at `test_speech.py:40-46`, not `:255-261` — that file
    is 156 lines. **−20.**

14. **Proposal 9 — the two ordered panel-title lists.** `tests/tunnelgoons/test_views.py:20` and
    `tests/engines/test_views.py:156` assert an exact ordered tuple of panel titles; a UI-copy
    change breaks them for no behavioural reason. Cut each down to what its own name claims — the
    player is left out of "Also here", and the panels carry icon ids — by looking up the panel it
    needs by title instead of asserting the whole list. Correction: the proposal names a third at
    `tests/engines/test_rooms.py:139`; that line selects the "Ways out" panel by title and asserts
    its rows, which is a behaviour test. Leave it. **−15.**

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 2 — `core` and `engines`

Proposals 4, 8, and the eleven rows of proposal 10 that live in `core/` or `engines/`. Two ui lines
are touched by step 8 and are named there.

| count | removed | added | net |
| --- | --- | --- | --- |
| `src` | ~200 | ~45 | ~−155 |
| `tests` | ~60 | ~30 | ~−30 |

One golden regeneration, step 15.

### Steps

1. **Proposal 8 — `hires: bool` replaces the currying factory.** Delete `hiring()` from
   `src/aidm/engines/hiring.py:38-49` and the `Hiring` type alias (`:35`); the file keeps `HIRE`,
   `SIGNED_ON`, `HIRE_TOOL`, `HIRE_UNWRITTEN` and `Hire`. On `Engine` (`src/aidm/engines/seam.py`)
   replace the `hire_writer: Hiring[G, M] | None` field (`:82`), its assignment (`:89`) and the
   `hiring()` hook (`:129-131`) with a class attribute `hires: bool = False` and an overridable

   ```python
   async def write_sheet(self, draft: G, member: M, terms: str, worldsmith: WorldsmithAnswer) -> str
   ```

   Update the three `is None` guards at `seam.py:107`, `:113` and `:145` to read `self.hires`; the
   third can then go entirely, because `write_hire` is only reachable through a request the
   `hires`-false engine never registers, which is what makes its `ValueError` unreachable today.
   Rewrite the three overrides (`breathless/engine.py:93-94`, `tunnelgoons/engine.py:92-93`,
   `twentyfourxx/engine.py:123-124`) as `write_sheet` bodies; twentyfourxx's is the only one that
   needs its `hire_check`. **−25.**

2. **Proposal 8 — one hire sentence.** `"The player has hired {name}, {brief}, on these terms:
   {terms}. "` opens the `HIRING` constant in `breathless/worldsmith.py:18`,
   `tunnelgoons/worldsmith.py:20` and `twentyfourxx/worldsmith.py:19`. Put that sentence in
   `engines/hiring.py` beside `SIGNED_ON` and have the three constants format it in. Safe: hire
   prompts are deliberately not goldened (`tests/core/test_golden_turn.py:68`).

3. **Proposal 8 — `opening_sections()` replaces the `G | None`.** In `src/aidm/engines/seam.py`,
   split `_render` (`:214-232`): `render_request` (`:203-207`) keeps calling
   `self.family_sections(draft)` with `draft: G`, and `render_opening` (`:209-212`) calls a new
   abstract `opening_sections(self) -> Sections`. Then `family_sections` (`:341`) drops its
   `| None`, and the two family implementations drop theirs:
   `engines/scenes/engine.py`'s `scene_sections(world | None)` and
   `engines/rooms/engine.py:83-86`'s `map_sections(world | None, log)`. Move each family's
   three no-world sections into its own `opening_sections`. **−25.**

4. **Proposal 8 — inline `compose()`.** `seam.py:360-367` is one expression with two callers,
   `engines/scenes/engine.py:294` and `engines/rooms/engine.py:172`. Inline it at both and delete
   the function. Step 6 rewrites the rooms call site as well — do that one once. **−6.**

5. **Proposal 4 — `guidance` becomes a class attribute.** `RoomEngine.guidance` is abstract at
   `engines/rooms/engine.py:240` and its one implementation,
   `tunnelgoons/engine.py:145-146`, returns the constant `AUTHORING`. Declare `guidance: str` in the
   `RoomEngine` attribute block beside `family_dir`, set `guidance = AUTHORING` in
   `TunnelGoonsEngine`, and update the three readers (`rooms/engine.py:170`, `:230`). Do not touch
   `SceneEngine.guidance` (`scenes/engine.py:324`): it takes a `PackSelection` and has three real
   implementations. **−3.**

6. **Proposal 4 — the map model becomes a class attribute.** `map_draft()`
   (`engines/rooms/engine.py:62-65`) exists only to subscript `MapDraft[self.member]` at runtime.
   Declare `map_model: type[MapDraft[N]]` in the attribute block, set `map_model = MapDraft[Npc]` in
   `TunnelGoonsEngine` and `MapDraft[Dweller]` in `tests/engines/test_rooms.py`'s `SixthEngine`, and
   read `self.map_model` at `rooms/engine.py:170`, `:172`, `:230` and `:233`. Do not name the
   attribute `draft`: that word is the game draft everywhere else in this package. **−2.**

7. **Proposal 4 — `starting_items` loses its dead default.** `engines/rooms/engine.py:80-82` returns
   `()` for a family with one member; `tunnelgoons/engine.py:142-143` is the only implementation.
   Mark it `@abstractmethod` and delete the body, and give `SixthEngine` a two-line implementation.
   **−1.**

   **Do not go further with proposal 4.** Option (a)'s literal form — `RoomWorld` over concrete
   `Dweller` / `Person` — does not type-check: `TunnelGoonsWorld` would have to narrow `npcs` to
   `dict[Slug, Npc]` and `player` to `Goon`, which `reportIncompatibleVariableOverride` rejects
   under `typeCheckingMode = "strict"`, and `tunnelgoons/engine.py:167-205` reads `.hp`,
   `.require_sheet()` and `.hired` off what those methods return. The package stays generic; what
   goes is the three extension points that were genericity workarounds. **Proposal 4 nets −6, not
   −25.**

8. **Proposal 10 — flatten `DiceLook` into `Look`.** `core/views.py:129-135` is a three-field model
   inside a two-field model with one reader. Move `body`, `ink`, `glow` onto `Look` as `dice_body`,
   `dice_ink`, `dice_glow`, delete `DiceLook`, and update the four constructions
   (`breathless/engine.py:83`, `twentyfourxx/engine.py:110`, `loner3e/engine.py:77`,
   `tunnelgoons/engine.py:80`) and the one reader, `DiceTray.__init__` (`ui/dice.py:16`) called from
   `ui/game.py:180`. Those two ui lines are the only ui edit in this phase. **−11.**

9. **Proposal 10 — `roll` and `roll_pool` collapse.** `core/facts.py:69-74` are identical signatures
   both delegating to `_rolled` and differing by one bool. Keep one public
   `roll(faces, reason, rng, *, label="", keep_highest=False)` and delete `_rolled`'s separate
   existence by folding it in. Update every caller. **−8.**

10. **Proposal 10 — one item renderer.** `engines/base.py` gains

    ```python
    def item_line(key: Slug, name: str, detail: str = "") -> str:
        return f"{name}[{key}]" + (f" — {detail}" if detail else "")
    ```

    Four call sites: `breathless/engine.py:166` (detail `f"d{item.die}"`),
    `twentyfourxx/engine.py:542` (detail `item.notes()`) — these two already print byte-identical
    shapes, verified against `master.txt`, so they do not move a golden — and
    `breathless/world.py:179` and `twentyfourxx/world.py:179`, whose `carried()` uses a bare space
    and a parenthesis respectively. Those two change to ` — ` and **do** move goldens; step 15 picks
    them up. **−16.**

11. **Proposal 10 — `test_luck` becomes `ask_world`.** loner3e's `luck` is a health gauge; this
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
    **−12.**

12. **Proposal 10 — `change_tags` and `change_hindrances` share one algorithm.**
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
    text, which differ. **−12.**

13. **Proposal 10 — the rest of the small collapses in these two layers.**

    | do | where |
    | --- | --- |
    | Delete both `drop_item` overrides; the base at `base.py:191` already does it | `breathless/engine.py:211`, `twentyfourxx/engine.py:317` |
    | Replace the roll card prefix with `actor.card_line(line)`; `base.py:88-89` is the same rule keyed on id rather than identity, so the output does not change | `breathless/engine.py:235`, `twentyfourxx/engine.py:416`, `tunnelgoons/engine.py:185` |
    | Fold `Game.commit()` (`core/model.py:120`) into `Engine.land()` (`seam.py:282`); one production caller. 39 test call sites also change — grep `\.commit()` under `tests/` | `core/model.py`, `seam.py` |
    | One `preview_character` on the seam taking the row label and the names; three engines pass their own | `breathless/engine.py:156`, `twentyfourxx/engine.py:252`, `tunnelgoons/engine.py:138` |
    | Make `Engine.create_character` concrete: it runs `check_picks(self.creation_steps(picks), picks)` then calls an abstract `build_character`. Four engines drop the opening line, and `core/creation.py:31`'s docstring becomes true | `seam.py`, the four `engine.py` |
    | Move `Actor(Frozen)` to `base.py` beside `ACTOR` (`:18`). **Do not** make the fourteen duplicated `actor_id` fields inherit it: pydantic puts inherited fields first and every schema golden would drift | `breathless/tools.py:99-100` |

    **−25.**

14. **Fix the tests these steps move.** Expect `tests/engines/test_rooms.py` (steps 5-7),
    `tests/engines/test_hiring.py` (step 1), `tests/breathless/test_engine.py:78` (step 10's
    `carried()` change) and the `.commit()` sites (step 13). Anything else that fails is a step that
    went wrong.

15. **Regenerate.** The one regeneration in phase 2. Expect exactly:
    `schemas/breathless/master_tools.json` and `schemas/twentyfourxx/master_tools.json` (step 11's
    rename), and `prompts/breathless/master.txt` and `prompts/twentyfourxx/master.txt` if a hired
    member's `carried()` line renders there (step 10). The `<<rules.md>>` and `<<schema>>` markers
    from phase 1 mean nothing else in the prompt fixtures can move; if a fixture you did not expect
    drifts, read the diff before accepting it.

### Checks

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

---

## Phase 3 — `app` and `ui`

Proposal 6 whole (6a, 6b, 6c option (a)) and the three rows of proposal 10 that live here. This is
the only phase with a behaviour change: **settings apply at the next start, not live.**

| count | removed | added | net |
| --- | --- | --- | --- |
| `src` | ~215 | ~45 | ~−170 |
| `tests` | ~80 | ~20 | ~−60 |

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
   (`:470-503`), the one caller, then constructs `GameService(...)` directly. **−28.**

2. **6c — live settings reload goes.** Delete `Runtime.reload_settings` (`:426-435`), the
   `_sessions` identity check and its refusal in `admit` (`:396-398`), and the
   `__post_init__` / `_mount` split (`:365-373`) — `__post_init__` now does both jobs in one body.
   The session-eviction race, the "The settings changed. Reload this page" refusal and the
   late-image-into-a-new-session hazard go with them. **−85 including the tests in step 8.**

3. **6c — the settings page stops applying.** `src/aidm/ui/settings.py`: drop the
   `apply: Callable[[], Awaitable[None]]` parameter from `SettingsForm` and `settings_page`, delete
   the `await self.apply()` try/except at `:74-82`, and reword the intro at `:71-76` to say the
   keys are written and apply at the next start — the sentence "The server port applies at the next
   start" is already there. Update the one call site, `src/aidm/ui/app.py:212`.

4. **6b — fold the admission into `GameService`.** `Runtime.open` / `play` / `act` / `restart`
   (`:407-424`) are `async with self.admit(session): await session.<same name>(...)`. Give
   `GameService` a `gate: "Runtime"` field, set by `_open`, and move each body into the matching
   `GameService` method wrapped in `async with self.gate.admit(self)` — `open`'s `unopened()` guard
   moves with it. Delete the four `Runtime` methods. `admit`, `admitted` and `turn` stay on
   `Runtime`: `published_tools` and `call` read `self.admitted.turn` for MCP. The UI then holds one
   object: `src/aidm/ui/game.py:460`, `:471`, `:483`, `:487` and `:582` become
   `self.session.play/act/restart/open`. **−18.**

5. **Fix the callers.** `tests/support/table.py:244` and `:247`, `tests/app/test_master_tools.py:132`,
   `tests/app/test_mcp.py:96`, `tests/app/test_game_service.py:106`, `:112`, `:120`, `:141`,
   `tests/turn/test_turn.py:89`, `:195`, `:221`, `:237`, `:249`, `:263` and
   `tests/turn/test_decisions.py:121` all call `runtime.play/act/open`; they become
   `service.play/act/open`. `tests/app/test_master_tools.py:510`'s `async with runtime.admit(...)`
   stays as it is.

6. **Proposal 10 — the Codex JSON scavenger.** `src/aidm/app/spawn.py:261-296` is 36 lines of
   untyped recursive tree search (`_last_said`, `_object`, `_string`, `_found`) that parses the same
   output twice. Replace it with two strict Pydantic V2 models — a `Loose` event shape and the
   envelope — as CLAUDE.md requires of model output, and parse once. **−25.**

7. **Proposal 10 — the settings nobody varies, and the two duplicate names.**

    | do | where |
    | --- | --- |
    | `SpeechConfig.voices` and `sample_rate` become constants beside their readers | `config.py:54`, `:57`; readers `app/speech.py:81`, `:72` |
    | `RoleConfig.max_rounds` becomes a constant | `config.py:38`; reader `app/builtin.py:81`, `:94` |
    | `Settings.source_max_chars` becomes a constant | `config.py:113`; reader `app/runtime.py:453` |
    | Delete `Runtime.default_engine()` (`:375-377`), a method around `next(iter(self.engines))`; inline it at its caller | `app/runtime.py` |
    | `ui/settings.refusal_text` (`:104`) and `core/entities._refused` (`:74`) are the same function; export the core one and import it in the ui | `core/entities.py`, `ui/settings.py` |

    `tests/app/test_builtin.py:162` passes `max_rounds=3` to `RoleConfig` and
    `tests/app/test_speech.py:92` reads `reader.config.sample_rate`; both change with their field.
    **−15.**

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
