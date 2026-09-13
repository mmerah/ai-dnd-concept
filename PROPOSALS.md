# PROPOSALS

Ten proposals to simplify concepts and remove over-engineering. Ranked by lowest feature impact
against highest line reduction. Six Opus readers explored the codebase independently; every line
count below was measured, not estimated.

Baseline: `src` 10,239 lines, `tests` 10,757 lines, golden fixtures 3,858 lines, `qa` 1,788 lines.

Total on offer: **about −1,300 fixture lines and −1,050 to −1,270 Python lines, with no feature
lost.** Every proposal marked DECISION needs one word from you before it can be planned.

---

## 1. The goldens store text the code under test did not write

**LOC: −1,300 fixture lines. Feature impact: none. Risk: low.**

`tests/core/test_golden_turn.py` stores whole rendered prompts. Two large parts of every stored
prompt are spliced in from elsewhere, so the golden is policing files that are not the thing being
tested.

- **Schema dumps.** The `ANSWER WITH:` tail is a pretty-printed Pydantic schema. Measured:
  `breathless/worldsmith.txt` 239 of 307 lines, `tunnelgoons` 216 of 254, `twentyfourxx` 190 of
  252, `loner3e` 155 of 221. The four `narrator.txt` files carry the **same 36-line schema, stored
  four times** (verified: identical checksums). `interjection.txt` 41 of 94. **≈985 lines.**
- **The rules splice.** `turn/run.py:159` splices `rules.md` verbatim into the master prompt.
  Measured against the checked-in markdown: `loner3e/master.txt` 99 of 139 non-blank lines are
  verbatim, `twentyfourxx` 92 of 133, `breathless` 66 of 97, `tunnelgoons` 63 of 97. **≈320
  lines.** Today, editing one sentence of `rules.md` fails the golden and forces a regen round
  trip for a change the golden was never meant to police.

**Becomes:** substitute the spliced files and the schema tail with markers (`<<rules.md>>`,
`<<schema>>`) before `golden(...)`, and register the four answer models with
`tests/core/test_golden_schemas.py`, which already goldens `schema_of(...)` — once per model
instead of once per engine. If a splice ever stops happening, the substitution stops matching and
the golden diffs, so no drift detection is lost.

**DECISION:**
- **(a)** Full substitution, both parts. −1,300 fixture lines, +15 test lines. *Recommended.*
- **(b)** Schema tails only. −985, and the goldens keep no coupling to `rules.md`.
- **(c)** Keep as is. Defensible: `AIDM_GOLDEN_REGEN` plus the `pytest_sessionfinish` guard already
  make regeneration cheap.

---

## 2. Shared base-class behaviour is tested once per engine

**LOC: −267 deleted, +50 added, net −215. Feature impact: none. Risk: low.**

Duplicate test names across engine packages, grep-verified: `test_create_character_records_the_
picked_pack` ×3, `test_require_actor_refuses_an_unsheeted_member` ×2, `test_luck_facts_are_untold`
×2, `test_join_party_lands_a_party_joined_fact_and_adds_the_member` ×2, `test_a_cast_that_holds_
the_player_is_refused` ×2.

Concrete spans, all testing code in `engines/base.py` or `engines/scenes/`, not the engine:

| Where | Lines | What it actually tests |
| --- | --- | --- |
| `tests/twentyfourxx/test_worldsmith.py:79-192` | 114 | `apply_scene`, `check_scene`, `install`, `render_next` — 100% `engines/scenes/` |
| `tests/twentyfourxx/test_world.py:72-128` | 57 | `base.py:207`, `scenes/world.py:59`, `require_actor` ×3 |
| `tests/breathless/test_world.py:62-106` | 45 | the player-in-cast validator, `require`, `here()`, `require_actor` |
| `tests/breathless/test_world.py:20-42` | 23 | local `_scene`/`_player`/`_world` rebuilding `support/breathless.small_world()` |
| `tests/{breathless,twentyfourxx}/test_engine.py` | 28 | `seam.py:123` `join_party`, `check_packs` |

Verified by reading every engine's `world.py`: **no engine overrides** `require_actor`, `here`,
`present`, `kill`, `apply_scene`, or the player-in-cast validator. `tests/engines/test_scene_bar.py`
already parametrizes exactly these checks over three engines. Coverage genuinely lost: only
"does the subclass still inherit the method", which basedpyright answers.

---

## 3. The suite has zero pytest fixtures

**LOC: −250. Feature impact: none. Risk: none.**

`grep -c "@pytest.fixture" tests/` returns **0** across 10,757 lines. The setup is retyped instead:

- `small_world().draft()` — **104 byte-identical lines** (`twentyfourxx/test_tools.py` 45,
  `tunnelgoons/test_tools.py` 30, `breathless/test_tools.py` 25, `tunnelgoons/test_world.py` 4).
  `small_world().payload` — 27 more.
- `_installed(tmp_path)` / `create_character("Wren"…)` / `begin("the-keep"…)` — the identical
  three-line preamble opens **13 of 20 tests** in `tests/engines/test_rooms.py`, and 15 more lines
  in `test_seam.py`.
- `ENGINE.roll(draft, Roll(what=…, skill=…, risk=…), Random(2))` — **34 call sites spanning 199
  lines** in `tests/twentyfourxx/test_tools.py`, 26 of them wrapped over 4-6 lines because they
  exceed the 100-char limit. A three-line `_rolled(draft, seed=0, **args)` helper takes those 199
  lines to about 95.

**Becomes:** a `conftest.py` per engine test package with `draft` and `world` fixtures, one
`_rolled` helper, one room fixture. The ~15 tests that build several drafts in one body keep their
explicit calls.

---

## 4. The `rooms` family is a generic abstraction with one member

**LOC: −25 to −143 src. Feature impact: none. Risk: low to medium.**

`src/aidm/engines/rooms/` is **856 lines** (`world.py` 489, `engine.py` 241, `tools.py` 65,
`worldsmith.py` 61), generic over `[N: Dweller, P: Person, G: Game[Any]]` with **29 generic
spellings**. Its four extension points — `world: type[...]` (`rooms/engine.py:57`), `map_draft()`
(:63), `starting_items()` (:81), abstract `guidance()` (:240) — are each implemented exactly once,
by `TunnelGoonsEngine`. Verified: the only other consumer in the repo is a synthetic `SixthEngine`
at `tests/engines/test_rooms.py:63`, which exists to test the abstraction itself.

CLAUDE.md says *"Do not add an abstraction until two things need it."* README line 31 names only
`SceneEngine` as a family. `rooms/engine.py:63-65` `map_draft()` exists solely to subscript
`MapDraft[self.member]` at runtime because the type is not concrete.

**DECISION:**
- **(a)** De-generify in place: concrete `Dweller`/`Person`, keep the package. −25, near-zero risk,
  keeps the door open for a second dungeon crawler. *Recommended if IDEAS #18 (Maze Rats) or #19
  might land on this family.*
- **(b)** Merge `rooms/` into `tunnelgoons/`: concrete `RoomWorld[Npc, Goon]`, drop `map_draft()`,
  `starting_items()` and abstract `guidance()`; retarget `test_rooms.py` at the real engine.
  −143 src, plus proposal 5's test scaffold. Closes the second-room-engine door.
- **(c)** Leave it.

---

## 5. Room-family behaviour is tested twice — once against a fake engine, once against the real one

**LOC: −70 to −170. Feature impact: none. Risk: medium.**

`tests/engines/test_rooms.py` (522 lines) builds a fake `SixthEngine` at lines 45-130 — 86 lines of
`SixthWorld`/`SixthGame`/`SixthScenario`/`SixthCharacter`/`SixthEngine` scaffold — then tests
family behaviour through it. TunnelGoons is the only shipped room engine, and
`tests/tunnelgoons/test_tools.py` (397) tests the same family code through the real engine:

| `test_rooms.py` (fake) | `tunnelgoons/test_tools.py` (real) |
| --- | --- |
| `:147` unlocking a way tells a card (32 lines) | `:252` + `:261` (23 lines) |
| `:166` party member moves with the player | `:240` `move_with_ids…` |
| `:132` begins a playable game | `:223` `move_reveals_the_destination_and_adds_a_visit` |

**DECISION:**
- **(a)** Keep `SixthEngine` for one boundary test only; move family behaviour to
  `tests/tunnelgoons/`. −140. *Recommended: a family test against a fake engine cannot catch a
  family/engine integration break.*
- **(b)** Keep the fake, delete the TunnelGoons duplicates. −70.
- **(c)** Keep both, add the fixture from proposal 3 only. −26, zero risk.

Note: the same argument applies weakly to `FifthEngine` in `test_seam.py`, but three real scene
engines make that fake worth keeping.

---

## 6. `Runtime` and `GameService` are one concept wearing two coats

**LOC: −131. Feature impact: one small behaviour change (see the decision). Risk: low.**

Three findings in `app/runtime.py` (517 lines):

- **`GameService.resume` (`:97-134`)** is a 38-line classmethod whose body is 6 lines of logic
  wrapped in a re-declaration of ten constructor parameters passed straight through. One caller.
  Becomes a 10-line free function, folding `_resumable` (`:504-517`) in. **−28.**
- **`Runtime.open/play/act/restart` (`:407-424`)** are 18 lines whose only content is
  `async with self.admit(session): await session.<same name>(...)`. The UI consequently holds both
  objects and must remember which verb goes where: `ui/game.py` calls `runtime.play/act/restart`
  but `session.player_view/history/icon/busy/…`. Fold the admission mutex into `GameService`.
  **−18.**
- **Live settings reload (`:365-373`, `:426-435`, `:397-398`, plus `ui/settings.py:74-82` and 46
  test lines)** exists so a settings save applies without an app restart. It brings with it the
  `__post_init__`/`_mount` split, the session-eviction race, the "The settings changed. Reload this
  page" refusal, and the "a late image from an evicted session lands where the new session reads"
  hazard. **−85.** The settings page already says *"The server port applies at the next start."*

**DECISION on the third item only:**
- **(a)** Drop live reload; settings apply on restart. −85, and three bug classes disappear with it.
  *Recommended.*
- **(b)** Keep it, take the other two items. −46, zero behaviour change.

---

## 7. The golden-turn runner is five files and a dynamic import

**LOC: −50. Feature impact: none. Risk: none.**

`tests/core/test_golden_turn.py:20-27` reaches four satellite modules by string-built dynamic
import (`import_module(f"tests.{engine_id}.golden_turn")`), needing two `cast()` calls to get past
the type checker, through a namespace package. The satellites: `loner3e/golden_turn.py` 60,
`tunnelgoons` 30, `twentyfourxx` 25, `breathless` 24, `support/golden_turn.py` 18 — **157 lines
across five files.**

Its stated reason, "so a new engine needs no core edit", is building for a future need: adding an
engine already requires editing `engines/registry.py`, which CLAUDE.md names as the one join point.
One `SCRIPTS: dict[EngineId, ...]` table in `support/golden_turn.py` deletes four files, two
helpers, two `cast()` calls and four import headers.

---

## 8. Three indirections in the engine seam that carry nothing

**LOC: −55. Feature impact: none. Risk: low.**

- **`engines/hiring.py` (50 lines).** A currying factory (`:38-49`) whose only job is to close over
  three engine methods and return an async closure, typed as `Hiring[G, M]`, threaded through
  `seam.py` at 8 sites and checked for `None` three times — the third raising `ValueError` for an
  unreachable branch (`seam.py:146`). Three near-identical overrides in the engines. Replace with
  `hires: bool` plus an overridable `write_sheet`. **−25.** The sentence *"The player has hired
  {name}, {brief}, on these terms: {terms}."* is also written out verbatim in three worldsmith
  modules; one constant fixes that. Safe: hire prompts are deliberately not goldened
  (`test_golden_turn.py:69`).
- **The `G | None` threaded through the worldsmith prompt path.** `seam.py:203-233`
  (`render_request`/`render_opening`/`_render`) → `family_sections(draft: G | None)` → 
  `scene_sections(world | None)` / `map_sections(world | None)`. One Optional re-tested at four
  layers to mean "this is the opening". Replace with an abstract `opening_sections()`. **−25.**
- **`compose()` (`seam.py:360`).** A one-expression helper with two callers. **−6.**

---

## 9. Test scaffolding that a hook or a parametrize replaces

**LOC: −110. Feature impact: none. Risk: none.**

- **Four hand-written delegating dataclasses**, ~14 lines each, existing only to run a callback
  before forwarding to `ScriptedSpawner.run`: `_Watched` (`test_master_tools.py:57-69`),
  `_TurnLandsFirst` (`test_game_service.py:301-316`), `_StillSpeaking` (`:318-335`), `_Blocking`
  (`:481-494`). One `hooks` field on `ScriptedSpawner` (`support/table.py:113`) turns all four into
  local `async def`s. **−45.**
- **Assertion-per-field clusters.** `tests/twentyfourxx/test_engine.py:49-64` is four separate
  tests for one two-line function (`Gear.notes()`); one parametrize is 6 lines.
  `tests/twentyfourxx/test_create.py:18-56` is six tests whose whole body is one list comprehension
  against an expected list. **−30.**
- **Wiring tests, which CLAUDE.md forbids.** `test_builtin.py:224-235` is a strict subset of
  `test_builtin.py:84-96` — same setup, same two assertions. `test_game_service.py:544-550` asserts
  that the test's own injection survived. `test_speech.py:255-261` re-asserts, key by key, the
  four-key dict literal at `speech.py:105-106`. **−35.**
- Related and worth folding in: three tests assert an **exact ordered list of panel titles**
  (`tunnelgoons/test_views.py:20`, `engines/test_views.py:156`, `engines/test_rooms.py:139`). Those
  are goldens written as assertions; a UI-copy change breaks them for no behavioural reason.

---

## 10. Small collapses, each removing a concept rather than a line

**LOC: −150 total. Feature impact: none. Risk: low.**

| What | Where | LOC |
| --- | --- | --- |
| The Codex JSON scavenger: `_last_said`/`_object`/`_string`/`_found`, 36 lines of untyped recursive tree search, parsing the same output twice. Two `Loose` models replace it — and CLAUDE.md requires exactly that ("validate model output with strict Pydantic V2 models"). | `spawn.py:261-296` | −25 |
| One item renderer instead of six spellings. `breathless/engine.py:166` and `twentyfourxx/engine.py:541` already produce byte-identical output; verified against the fixtures. | 7 sites across 3 engines | −16 |
| `test_luck` declared twice on top of `base.py:361`'s `luck_test`. Also a naming clash: loner3e's `luck` is a health gauge, this is an oracle question — rename the tool `ask_world`. | breathless + 24xx | −12 |
| `change_tags` and `change_hindrances` are one algorithm with two names — and they **disagree** on whether a string in both `gained` and `lost` survives. One of them is a bug; sharing the code forces the question. | `loner3e/world.py:85`, `twentyfourxx/world.py:102` | −12 |
| Flatten `DiceLook` into `Look`: a two-field wrapper inside a two-field wrapper, one reader, constructed by all four engines. | `core/views.py:129-141` | −11 |
| `roll` and `roll_pool`: identical signatures, both delegating to `_rolled`, differing by one bool. | `core/facts.py:69-90` | −8 |
| `drop_item` is byte-identical in two engines, on top of the base implementation. | breathless + 24xx | −8 |
| The roll card prefix `"" if actor is world.player else f"{actor.name}: "` written three times — the same rule as `Thing.card_line` (`base.py:88`), keyed on identity instead of id. | 3 engines | −8 |
| Settings fields nobody varies, several invisible in the settings UI: `SpeechConfig.voices`, `sample_rate`, `RoleConfig.max_rounds`, `source_max_chars`. Constants beside their readers. | `config.py` | −10 |
| `Game.commit()` has exactly one production caller; fold it into `Engine.land()`. Three names for one transaction becomes two. | `model.py:120`, `seam.py:280` | −5 |
| `preview_character` is the same expression in three engines. | 3 engines | −5 |
| `check_picks(self.creation_steps(picks), picks)` opens `create_character` in all four engines. Making `Engine.create_character` concrete also makes `creation.py:31`'s docstring true — it currently claims a shared rule the create page does not use, and the two have already drifted. | 4 engines | −4 |
| Move the bare `Actor(Frozen)` shape to `base.py`. Do **not** make the 14 duplicated `actor_id` fields inherit it — pydantic puts inherited fields first and every schema golden would drift. | `breathless/tools.py:99` | −3 |
| `Runtime.default_engine()` is `next(iter(self.engines))` behind a method. `entities._refused` and `ui/settings.refusal_text` are the same function under two names. | mixed | −5 |

---

## Considered and excluded

These came up, are real, and are **not** in the top ten — each is either a feature call or a bad
trade. Listed so nothing is lost, not as proposals.

- **Illustration and speech (≈−850 lines).** By far the largest deletion available anywhere. Both
  off by default, both cost money beyond the subscription. Cutting speech alone is ≈−290 and it is
  the weaker half (a fixed pool of five voice names, not even editable in the settings page).
  A feature call, not a simplification.
- **The completion-API role path (≈−405) or the CLI-spawn path (≈−590).** Genuinely two
  mechanisms, not one with a switch — and about 130 lines of `Runtime` (the admission mutex, the
  `Tools` protocol, `published_tools`, `call`) exist only because the CLI path reaches its tools
  out of band through MCP. Dropping the CLI path would destroy the product thesis. Feature calls.
- **`qa/` (1,788 lines).** A Playwright screenshot harness that is not run by CI, is maintained
  alongside every phase, and is the real UI coverage — `tests/ui/` is only 297 lines. Do not delete
  it, and do not add UI unit tests to compensate.
- **`PackSelection` → plain tuple (−20).** Correct in the abstract, but it changes the on-disk
  shape and **any user-authored scenario becomes unreadable**. A scenario costs minutes of
  worldsmith time. Only worth doing alongside another storage-shape change.
- **Dropping `_normalize`/`_collapse_nullable` from `core/tools.py` (−35 to −53).** Would strip
  constraint hints (`pattern` on a slug) out of every prompt the model reads. The effect on model
  behaviour is untestable offline. Not worth the risk for 35 lines.
- **`Settings._keys_present` (−50).** Today a missing API key stops `uv run aidm` from starting at
  all; after, the first call logs a provider error. Arguably better, but behavioural.
- **Hoisting `narrator_view`/`player_view`/`author` from the two families into the seam.** Costed:
  a unified version plus its 6-8 hooks nets **≤10 lines** and makes the seam more abstract. Two
  tests assert the different panel orders. Do not do this.
- **`tests/core/test_package_boundary.py` (97 lines).** A hand-rolled AST import linter. Replacing
  it with `import-linter` saves ~45 lines at the cost of a dependency and a transcription risk on
  the codebase's most central invariant. Not worth it.
- **The interjection feature (≈−200 across ten files).** A README headline, already off-switchable,
  and the code is tight. Keep.
- **Renames.** `Dungeon.carried()` returns props while `Sheeted.carried()` returns a string;
  `Pool` is defined twice with different fields; `support/game.py` is really `support/loner3e.py`
  plus the app-wide default table. All real, all out of scope here.

---

## Suggested order

1. **Proposals 1, 3, 7, 9** — tests and fixtures only, no argument needed. ≈−1,300 fixture lines
   and −410 Python lines.
2. **Proposals 2, 5** — need the two test decisions. ≈−355.
3. **Proposals 8, 10** — src cleanups that also fix two real bugs-in-waiting. ≈−205.
4. **Proposals 4, 6** — need your call on the room family and on live settings reload. ≈−110 to
   −228.
