# PROGRESS

Newest first. One entry per phase of `PLAN.md`.

## Phase 3 — `app` and `ui`

Proposal 6 whole (6a, 6b, 6c) and the two rows of proposal 10 that live here. No golden moves,
and none drifted. The plan's only behaviour change lands: **settings apply at the next start,
not live.** Two implementers in parallel: part A took PLAN steps 1–5, 7, 8, part B step 6.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,176 | 10,100 | −76 |
| `tests` | 10,537 | 10,500 | −37 |
| `qa` | 1,760 | 1,760 | 0 |
| prompt fixtures | 813 | 813 | 0 |
| schema fixtures | 2,366 | 2,366 | 0 |

`uv run pytest` 711 → 708 passing: four tests of the deleted reload plumbing removed, one added
for the codex event models. `uv run basedpyright` 1,101 errors, every one in `qa/`, unchanged.
`uv run aidm` serves `/` and `/settings` (HTTP 200); no live turn — this container runs no AI
role — so the turn path rests on the suite.

PLAN predicted `src` −100 and the phase landed at −76. The gap is arithmetic, not retained fat,
and all of it was measured: the four cancelled `config.py` rows (−8 the maintainer refused, see
below), step 1's −32 against a ceiling near −20 once the free function stopped re-declaring the
caller's own fields, and step 6's −20 against a ceiling near −9 because the two Pydantic models
CLAUDE.md requires cost about eleven lines the untyped scavenger did not.

### Decisions made off-plan

- **PLAN step 7's first four rows are refused by the maintainer.** `SpeechConfig.voices` and
  `sample_rate`, `RoleConfig.max_rounds` and `Settings.source_max_chars` **stay settings**; they
  were not turned into constants. `src/aidm/config.py` is untouched by this phase. The
  `.env`-breakage line PLAN asks to record here does not apply: no key changed, so no stale
  `SPEECH__SAMPLE_RATE`, `SPEECH__VOICES`, `<ROLE>__MAX_ROUNDS` or `SOURCE_MAX_CHARS` starts
  refusing. Worth −8 of the predicted −100.
- **`Runtime.default_engine` became a property, not a deletion.** PLAN says delete it and
  "inline it at its caller"; it has **two** callers, `ui/create.py:26` and `:170`, so inlining
  pushes `next(iter(runtime.engines))` into `ui` twice. It takes no argument, has no side effect
  and reads its own field, which is CLAUDE.md's definition of a property. Net 0 against PLAN's
  −3.
- **`resumed` is `Runtime._resumed`, not the free function PLAN step 1 names.** Written as a free
  function it took six parameters, two of which — `store` and `meanwhile` — are constants at its
  one call site and already owned by the `Runtime` that calls it. Re-declaring a caller's own
  state to pass it straight through is the exact fault 6a set out to remove from the classmethod,
  so the free form reproduced it at a smaller scale. As a private method reading `self.store` and
  `self.settings.meanwhile` it is −3 and the call site fits on one line.
- **`GameService.unopened` became a property.** Same rule as `default_engine`, in the same file,
  which the phase would otherwise have applied to one construct and not the other; `busy`,
  `presents` and `speaking` beside it are already properties doing the same work.
- **`final_message` no longer reads codex event streams.** Its codex branch was reachable only
  from a test: `CodexDriver.read_result` is the sole holder of a stream and only falls back to
  `final_message` once `_said` has already returned `None`, while the other two callers pass a
  completion's text. Deleting it is what finally makes step 6's "parse once" true; the stream
  case moved onto `CodexDriver().read_result(...)`, where it belongs.
- **`GamePage._open` was inlined.** Once the admission fold landed it was a two-line
  pass-through to `self._run(self.session.open)` with two callers.
- **`README.md` gained a sentence.** It told the player to open Settings to change the AI
  commands, which is now only half true — the keys are written and apply at the next start. This
  phase's behaviour change had no other documentation.

### What the review fold bought

Two Opus reviews (no `codex` in this container, and the maintainer asked for Opus reviewers).
They agreed on twelve findings and split on two. The fold removed a further 16 `src` lines and
five docstrings, and fixed one behaviour the suite cannot see:

- **`ui/settings.py` reloaded the page onto stale values.** `ui.navigate.reload()` outlived the
  `await self.apply()` it belonged to. `settings_page` renders from `runtime.settings`, which is
  built once at startup and — with `reload_settings` gone — is never re-read, so a save wrote
  `.env` correctly and then repainted the form with the **pre-save** values under a
  "Wrote N keys." toast. Both reviews found it independently. The reload is deleted; the boxes
  keep what was typed, which is what `.env` now holds.

One bug was caught in verification, before the reviews: the disarm in `resumed` had been indented
into the restored-save branch, so a **fresh** opening started with `meanwhile` off was no longer
disarmed. `GameService.resume` applied it to both paths. The suite was green either way.

Two tests were rewritten because they could not fail. `tests/app/test_spawn.py`'s new case
asserted `final_message('{"lines": []}')` returns its input, which the pre-change code did too;
it now pins the rule the phase actually introduced — only an `agent_message` item is the answer,
where the old recursive scavenger took `text` from any event. Verified by breaking the filter in
`src` and watching it fail.

### Refuted findings

| finding | reason |
| --- | --- |
| Extract `admitted` + `admit` into an `Admission` class so `GameService` holds that instead of the whole `Runtime` | **Costs lines and an abstraction, against CLAUDE.md twice.** The reviewer measured it at **+4** in a phase whose purpose is removal, and "do not add an abstraction until two things need it" — one thing needs it. The same reviewer records that the cycle itself is harmless: slotted dataclasses are GC-tracked, and `Runtime.close()` never clears `_sessions`, so a session lives as long as its runtime either way. The real defect it named — the width of the reference — is `__repr__` dragging in every built engine and `__eq__` walking `_sessions` back into `GameService`. The other review's fix takes that at **zero** lines: `gate: "Runtime" = field(repr=False, compare=False)`, matching `_speaking` and `tasks` beside it. Landed. |

### Known and accepted

- `GameService` holds a back-reference to its `Runtime`. It is what lets the UI hold one object,
  which is the whole of 6b. It is kept out of the generated `repr` and `eq`; nothing else guards
  it.
- Dropping the session-identity check from `Runtime.admit` removed a guard nothing still needs:
  `_sessions` is only ever inserted into, by `session()`, and never replaced or cleared now that
  `reload_settings` is gone. Both reviews confirmed this independently.
- `SettingsForm.save` leaves the form holding the typed values while `self.settings` stays at
  the process-start snapshot. A second save of the same box therefore rewrites the same key and
  reports it as written again. Harmless — `set_key` is idempotent — and the alternative is
  re-reading settings into a page that no longer applies them.
- The phase changes what a player sees: a settings change needs a server restart. `README.md`
  and the settings page intro both say so; nothing else in the app does.

## Phase 2 — `core` and `engines`

Proposals 4, 8, and the rows of proposal 10 that live in those two layers. One golden
regeneration, at step 12. Two sequential implementers: part A took PLAN steps 1–4 (the seam),
part B steps 5–12.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,240 | 10,176 | −64 |
| `tests` | 10,540 | 10,537 | −3 |
| `qa` | 1,760 | 1,760 | 0 |
| prompt fixtures (13 files, `wc` under-reports by four) | 813 | 813 | 0 |
| schema fixtures | 2,366 | 2,366 | 0 |

`uv run pytest` 711 → 711 passing. `uv run basedpyright` 1,101 errors, every one in `qa/`,
unchanged. `uv run aidm` serves its page (HTTP 200); a live turn was not played — this container
runs no AI role — so the turn path rests on the suite.

PLAN predicted `src` −38. The actual is −64: the review fold found the rest, all of it fat the
phase's own shapes created and the plan had not priced. Only two fixture lines moved, both
step 8's rename: `"name": "test_luck"` → `"ask_world"` in the two `master_tools.json`. No
`turn/*.json` moved, so step 7's roll merge kept its `len(faces) > 1` computation; no
`prompts/*.txt` moved, so the hire sentence, the card-line fragment and the item-line collapse
all render byte-identically.

### Decisions made off-plan

- **PLAN step 10, row 1 — hoisting `drop_item` to `SceneEngine` — is refused.** It does not
  type-check. `SceneEngine[C: Person, ...]`, so `require_actor()` returns a `Person`, and
  `require_sheet` is declared on `Sheeted[S]` (`base.py:143`). `C` cannot be narrowed:
  `Loner3eEngine` is `SceneEngine[Loner3eCast, ...]` and `Loner3eCast(Person)` carries no sheet.
  Measured before implementation: the hoist written verbatim into `scenes/engine.py` gives four
  basedpyright errors, the load-bearing one `Cannot access attribute "require_sheet" for class
  "Person*"`. Landing it needs a new intermediate engine class over `Sheeted[ItemSheet[I]]`,
  whose header and generics cost more than the four lines the hoist saves. The same failure mode
  PLAN.md itself records for proposal 4 option (a). Worth −4 of the predicted −38.
- **`opening_sections` is a class attribute, not the abstract method PLAN step 3 names.** Both
  reviews caught that a constant-returning abstract method is the exact shape steps 5 and 6
  remove for `RoomEngine.guidance()`; the phase would have applied opposite rules to two
  identical constructs in one diff. Taken on the standing decision that the cleanest fix wins.
- **`scene_sections` and `map_sections` are gone, folded into each family's `family_sections`.**
  Once step 3 stripped their `| None` branch, each had exactly one caller and `family_sections`
  was a two-line pass-through. Folding them also puts a family's request sections in the same
  file as the opening sections the decision above moved there.
- **The merged roll flag is `highlight_kept`, not PLAN's `keep_highest`.** `Rolled.kept` is
  `max(self.event.rolled)` whatever the flag; the flag only fills `DiceEvent.highlight`. A call
  site reading `keep_highest=True` beside `rolled.kept` would believe the dice rule changed.
- **`_break` in `twentyfourxx/world.py` now goes through `changed_tags` too.** Step 9 changed
  `change_hindrances` to loner3e's wording and left `_break` and `check_defenses` saying
  `'X' is already among NAME's hindrances` — two messages for one rejected state, invisible to a
  suite that only asserts `"already"`. Both reworded; `_break`'s guard and `append` became one
  `changed_tags` assignment.
- **`changed_tags` is a `Person` method, not the free function PLAN step 9 names.** It took
  `name: str` only because it wanted the person's name for its two refusals; on `Person` it reads
  `self.name` and all three call sites shorten. It still returns the new list rather than mutating,
  because the two callers keep it in different places — `self.tags[kind]` and `sheet.hindrances`.
- **`luck_test` is now `oracle_roll`.** Step 8 renamed the tool away from "luck" because the word
  collides with loner3e's luck gauge; the helper that implements the tool kept it. `oracle_roll` is
  the vocabulary the engines already use for a question the dice answer.
- **`item_line` was added by step 10 row 3 and then deleted.** It landed in `engines/base.py`
  with exactly one caller, and the collapse measured net **+1** line, not a cut. The other two
  candidate sites are the `carried()` pair PLAN refuses, so a second user can never arrive.

### What the review fold bought

Two Opus reviews (no `codex` in this container, and the maintainer asked for Opus reviewers).
They agreed on six findings and split on five. The fold removed 25 lines and two docstrings, and
fixed two behaviours the suite could not see: the split hindrance wording above, and
`docs/BREATHLESS.md` / `docs/24XX.md`, which still listed the master tool as `test_luck`.

### Refuted findings

| finding | reason |
| --- | --- |
| Reconcile `hires` with the `write_sheet` override | **Measured, not judged.** The clean form is to stop declaring `hires` and derive it: `return type(self).write_sheet is not Engine.write_sheet`, which deletes the three `hires = True` lines and makes disagreement impossible. `basedpyright --strict` rejects it — `Type of "write_sheet" is partially unknown (reportUnknownMemberType)`, because `Engine` is generic and the bare class access loses its parameters. That is one new error in `src`, which the project holds at zero, and every other reflective spelling (`getattr_static`, a module-level alias) fails the same way or returns `Any`. The reviewer's `__init__` guard fails identically. Registering the hire tool and request in each hiring engine instead costs +9 lines and scatters the wiring. The bool stays; see **Known and accepted**. |
| Make `_render`'s parameters keyword-only | **Measured, not judged.** Written out and formatted, `seam.py` goes 361 → 375 lines: +14, because neither call site fits in 100 characters once the six arguments are named, so both explode to one argument per line. `_render` is private, has two callers seven lines above its own definition, and every positional argument's name matches the parameter at that index. +14 lines in a phase whose purpose is removal is the wrong trade. |

### Known and accepted

- `hires = True` and a `write_sheet` override are two spellings of one fact and nothing holds
  them together; the deleted `hiring()` hook could not disagree with itself. The two ways to get it
  wrong are not equally loud: `hires = True` without an override raises
  `the 'x' engine hires nobody` at hire time, while an override without `hires = True` silently
  registers no hire tool at all. Reconciling them is blocked by the type checker — see the
  refutation above. If a fourth hiring engine is ever written, this is the trap.
- `tests/core/test_dice.py` was edited although no PLAN step names it: it imported `roll_pool`
  directly, so step 7 could not land without it.
- `hire_prompt` and `install_sheet` now have exactly one caller each, their own `write_sheet`.
  Inlining them is about six lines, but it would bury a 6-line prompt build and an 8-line sheet
  install inside a single `write_sheet`; the two names carry the two halves. Left as they are.
- Hoisting `drop_item` needs five type parameters, not one class. Beyond the `Person` bound
  recorded above, `Sheeted[S]` and `ItemSheet[I]` are both invariant in their parameters, so an
  intermediate class cannot be spelled `Sheeted[ItemSheet[Item]]`; it needs
  `[I: Item, S: ItemSheet[I], C: Sheeted[S], G, K]` and every engine restating all five. The
  refusal is structural, not a preference.

## Phase 1 — the goldens and the test scaffold

Proposals 1, 2, 3, 5, 7, 9, plus an audit of `tests/loner3e/` that no proposal covered.
Eleven commits, `2df4012..584f35b`.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,239 | 10,240 | +1 |
| `tests` | 10,757 | 10,540 | −217 |
| `qa` | 1,760 | 1,760 | 0 |
| prompt fixtures (13 files) | 2,182 | 813 | −1,369 |
| schema fixtures | 1,495 | 2,366 | +871 |
| **fixtures total** | **3,677** | **3,179** | **−498** |

`uv run pytest` 675 → 711 passing. `uv run basedpyright` 1,101 errors, every one in `qa/`, unchanged.
`uv run aidm` serves its page.

Both `wc -l` figures for the prompt fixtures are adjusted: the four `master.txt` carry no trailing
newline, so `wc` under-reports them by four. `wc` says 809.

### The line estimate was wrong, and by how much

PLAN.md predicted `tests` −570. The actual is −217. The fixture figure (−498) is exact. The
difference is not retained fat; it is four costs the plan did not price:

1. **PLAN double-counted step 1 against step 2.** The four `golden_turn.py` satellites had to move
   verbatim — the scripts and the loner3e `behind` body decide the golden fixtures — so
   consolidating them saved only the three duplicated bodies and three import headers. Steps 1–2
   netted +1, not −35.
2. **The step-9 decision costs two modules.** See below: `support/sixth.py` (102) +
   `support/fifth.py` (102) + `conftest.py` (27) against 278 lines of removed preamble.
3. **Three-engine parametrization is not free.** Step 7's `test_scene_bar.py` was budgeted +50 and
   came in at +242. Eight of the sixteen moved cases construct a world type directly or need a
   hired member, which needs real per-case setup where a single-engine test needed none.
4. **The review fold added 44 lines back** restoring assertions that pinned nothing. That was the
   right trade; see below.

Step 10's own claim was also wrong: PLAN said 34 `_rolled` sites on one line. Fourteen are. Passing
a real `Roll(...)` — see the refuted row below — costs the characters that used to make them fit.

### Decisions made off-plan

- **Step 9 does not put the scaffolds in `conftest.py`.** PLAN asks for "a package fixture in a new
  `tests/engines/conftest.py`" covering both `_installed` helpers, but they build two different
  scaffolds — `SixthEngine` for rooms, `FifthEngine` for scenes — and both test modules still need
  those class names for their own annotations. Asked the maintainer; they chose: the scaffolds move
  to `tests/support/sixth.py` and `tests/support/fifth.py`, matching the existing
  `support/{breathless,twentyfourxx,tunnelgoons,game}.py` pattern, and `conftest.py` holds only the
  four fixtures.
- **Step 6's "keep exactly one test on it" is not followed literally.** Its own move table names
  five tests, its closing paragraph keeps everything from `:296` down, and step 9 counts "the eight
  that remain" of thirteen `_installed` call sites — 13 − 5 = 8. The table is exhaustive; five
  tests moved and the rest stayed.
- **Phase 1 touched `src`, once.** `scenes/world.py`'s `_consistent` ran `check_named` before the
  player-in-scene check, so that branch was unreachable: deleting it left all 703 tests green,
  including the three parametrized cases claiming to pin it. Reaching it needs the player in `cast`,
  which an earlier branch rejects. The two checks are now reordered so the specific message wins,
  which makes the branch live and its test able to fail. No valid state changes behaviour — only
  which error an already-invalid one reports. Taken on the maintainer's instruction to prefer the
  clean fix over the plan.
- **An audit of `tests/loner3e/` was added to this phase.** No proposal had covered it: 51 tests,
  775 lines, the largest engine package. Eight tests deleted against named surviving pins, six moved
  into `test_scene_bar.py` where they now run over three engines, and the repeated view-shape
  assertions collapsed into `test_views.py` over `ENGINE_IDS`. 775 → 613.
- **The hidden-entity view collapse was skipped.** It needs a four-row `{engine_id: hidden label}`
  table to net about five lines. Not worth the table.

### What the review fold actually bought

Two Opus reviews (no `codex` in this container, and the maintainer asked for Opus reviewers) found
six behaviours the suite could not see. Each fix was verified by breaking the behaviour in `src` and
watching a test fail:

| broken in `src` | failures before the fold | after |
| --- | --- | --- |
| `core/tools.schema_text` `indent=2` → `4` | 0 | 5 |
| `app/speech.speech_body` `"pcm"` → `"mp3"` | 0 | 1 |
| `app/roles` two `schema_text` calls swapped | 0 | 2 |
| `rooms/engine` `if way.known` removed | 0 | 1 |
| `scenes/world` player-in-scene branch removed | 0 | 3 |
| `scenes/world.reveal_hidden` guard removed | 1 (loner3e only) | 3 |

The first three were created by this phase: masking the `ANSWER WITH:` tails out of the prompt
fixtures removed the only coverage of `schema_text` and of which schema each role advertises.

### Refuted findings

None were refuted on their merits. Three reversed a PLAN.md instruction, on the maintainer's
standing decision that the cleanest fix wins:

| finding | PLAN said | done instead |
| --- | --- | --- |
| `speech_body` deleted (step 13) | "re-asserts the four-key dict literal" | it is an external wire contract; the three keys are asserted inside the test that actually sends them |
| `_rolled(**args: object)` (step 10) | that signature, verbatim | `_rolled(draft, roll: Roll, *, seed=0)` — `**args: object` removed static checking from 34 sites, against CLAUDE.md's "use exact types" |
| `src` untouched in phase 1 | hard rule | the one reorder above |

Two claims in PLAN.md are wrong and were not acted on as written:

- Step 7 says `tests/breathless/test_world.py:62-107` "repeats four of those eight". Only two do.
  `SceneWorld.require`'s player branch and `here()`'s player-first ordering are different methods;
  they lost their only direct tests and were restored as parametrized cases in the fold.
- Step 6's table says `tests/engines/test_rooms.py:94` pins the player-death card for the scene
  family. It does not — that is `rooms/world.py:388`, a different implementation. The scene-family
  line is pinned by `twentyfourxx/test_tools.py` and `breathless/test_tools.py`.

### Known and accepted

- `tests/loner3e/test_world.py:243` (`cast_lines`) is the sole pin of the met/unmet + last-seen
  detail and is partly prose. Kept in place; parametrizing it needs per-case labels not worth a table.
- Five `(draft, world)` signatures remain in `tunnelgoons/test_tools.py`. They are safe: `conftest`
  defines `world` as `draft.payload`, so both names are the same object.
- `_walked` still takes `room_engine`; it uses it to move, so it is not a pass-through.

### Proposals refused before this plan, recorded per PLAN.md

`starting_items` → abstract (src 0, tests +2); flatten `DiceLook` into `Look` (`views.py` −5 against
+8 in four exploded `Look(...)` calls, and it silently breaks `ui/dice_tray.js:28-30`, which reads
`look.ink` / `look.body` / `look.glow` off `ui/dice.py:18`'s `look.model_dump()`); fold
`Game.commit()` into `Engine.land()` (src −1 against 40 `.commit()` sites in twenty test files); one
`preview_character` on the seam (three 3-line overrides become three 3-line hooks plus a seam
method, net 0); move `Actor(Frozen)` to `base.py` (one `class Actor`; moving a file deletes no
line); the two `carried()` item-line sites (output changes, zero lines); and merging
`ui/settings.refusal_text` into `core/entities._refused` (they differ — see phase 3 step 7).
