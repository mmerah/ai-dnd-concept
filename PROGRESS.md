# PROGRESS

Newest first. One entry per phase of `PLAN.md`.

## Phase 2 — `core` and `engines`

Proposals 4, 8, and the rows of proposal 10 that live in those two layers. One golden
regeneration, at step 12. Two sequential implementers: part A took PLAN steps 1–4 (the seam),
part B steps 5–12.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,240 | 10,177 | −63 |
| `tests` | 10,540 | 10,537 | −3 |
| `qa` | 1,760 | 1,760 | 0 |
| prompt fixtures (13 files, `wc` under-reports by four) | 813 | 813 | 0 |
| schema fixtures | 2,366 | 2,366 | 0 |

`uv run pytest` 711 → 711 passing. `uv run basedpyright` 1,101 errors, every one in `qa/`,
unchanged. `uv run aidm` serves its page (HTTP 200); a live turn was not played — this container
runs no AI role — so the turn path rests on the suite.

PLAN predicted `src` −38. The actual is −63: the review fold found 25 lines of fat the plan had
not priced, all of it created by the phase's own shapes. Only two fixture lines moved, both
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
| `changed_tags` should be a `Person` method | Its first argument is a `str`, not one of our objects, so CLAUDE.md's "first argument is one of our objects" rule does not reach it. It owns no storage either: loner3e assigns the result to `self.tags[kind]`, twentyfourxx to `sheet.hindrances`. PLAN specifies a free function. |
| Guard `hires` against a missing `write_sheet` override in `__init__` | +2 lines of `type(self).write_sheet is Engine.write_sheet` reflection in a phase whose point is removal, and it catches only one of the two directions the finding names — an override without `hires = True` still registers no hire tool silently. The failure it does catch already raises a named `ValueError` naming the engine. |
| Rename `luck_test` to `oracle_roll` | `luck_test` is an internal helper name; it never reaches a role, the player or a schema. The collision step 8 fixed was the tool string `test_luck` that the master reads beside loner3e's luck gauge. Zero lines either way. |
| Make `_render`'s `intent`, `guidance`, `answer` keyword-only | It would cost back the six lines one-lining the `render_request` call buys, by exploding it to one argument per line again. `_render` is private with two callers in the same file, and both public entry points, `render_request` and `render_opening`, already take those three keyword-only, so a transposition cannot reach a caller outside `seam.py`. |

### Known and accepted

- `hires = True` and a `write_sheet` override are two spellings of one fact and nothing holds
  them together; the deleted `hiring()` hook could not disagree with itself. See the refutation
  above. If a fourth hiring engine is ever written, this is the trap.
- `tests/core/test_dice.py` was edited although no PLAN step names it: it imported `roll_pool`
  directly, so step 7 could not land without it.
- `hire_prompt` and `install_sheet` now have exactly one caller each, their own `write_sheet`.
  Inlining them is about six lines, but it would bury three different prompt shapes inside three
  `write_sheet` bodies; left as they are.

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
