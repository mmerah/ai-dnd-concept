# PLAN: three cuts in three commits

This plan lands the three cuts decided on 2026-09-16: the browser dictation button goes and a
speech-to-text line joins `IDEAS.md`; the 3D dice tray goes and the dice chips on the fact cards,
which already tumble, gain the sound; the Breathless engine goes, with its scenario, its character
file, its notes, its fixtures and its qa scripts.

Decided and not in this plan, so no phase re-opens them: scope prose, interjections, speech,
illustration, the builtin completion loop, meanwhile, packs and supplements, the `qa/` harness and
the character axis all stay. The carry-forward of a grown character across scenarios is an idea,
not a phase.

Measured before any step: `src` **10,181** Python lines, `tests` **12,222**, `qa` **2,088**, at
`9d69793`. Every anchor below is as of that commit. The plan was reviewed adversarially once
before phase 1; the targets below are the reviewed numbers.

Not cut, with the reason:

- **`engines/base.py`** loses no line to the Breathless cut. `ItemSheet`, `Item`, `oracle_roll`,
  `banded` and `DropItem` keep a user in `twentyfourxx/`; `Sheeted` keeps `twentyfourxx/` and
  `tunnelgoons/`; `Gauge`'s two users are `loner3e/` and `tunnelgoons/`. The only override that
  disappears is `Engine.answer` (`breathless/engine.py:232`, the loot decision); the seam method
  stays because the runtime plays every pending decision through it, and
  `tests/turn/test_decisions.py:206` covers the base dispatcher.
- **`engines/tools.py`** loses no line: `AskWorld`, `DropItem`, `Hire` and `ACTOR` keep users.
- **`Look`** stays a model, not a `Mapping`: it is the validated boundary for `look.json`
  (`seam.py:87`), and `Frozen` is `extra="forbid"`, which is what forces every `look.json` and
  the two synthetic engines to change in the same phase as `DiceLook`.
- **`tests/core/fixtures/source/drowned-road.{md,pdf}`** stay. They are the PDF-ingestion fixtures
  for `tests/core/test_documents.py` and share only a name with the Breathless scenario.
- **`characters/kael/icons/player.jpg`** stays; the icon is per character, not per engine.
- **The 2D dice chips** (`_card`, `_dice_group`, `.game-die*` in `theme.css`) stay untouched.
  They are the dice the player reads; phase 2 adds a sound to them and removes the second renderer.
- **The sound button, `toggle_sound`, `sound_state` and the `localStorage` key** stay. The player
  who muted the tray stays muted, and `qa/s_loner.py:279-284` asserts the icon toggles.
- **`Observed.facts`** stays: `whole_page` (`game.py:664-666`) reads it too.
- **`DiceEvent`** and `Fact.dice` stay: the chips, the golden turn fixtures and `twentyfourxx`'s
  `earn` all read them.
- **`pyproject.toml`, `uv.lock`, `.github/workflows/check.yml`** need nothing: the wheel ships
  the whole package with no file list, and the dice library is vendored JS, not a dependency.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. Do the steps in order. Each is one action on the files it names. Every `file.py:line` anchor
   is as of `9d69793`; where an earlier step moved the code, find the named symbol and ignore the
   number.
2. Change a shape and its tests in the same step. One test per new behaviour. A test of a deleted
   behaviour is deleted with it, never kept alive by stubbing or retargeting for its own sake.
3. Count lines at the start and end of each phase and write both in `PROGRESS.md`, one entry per
   phase:
   ```bash
   find src -name '*.py' | xargs cat | wc -l
   find tests -name '*.py' | xargs cat | wc -l
   find qa -name '*.py' | xargs cat | wc -l
   ```
   A phase that misses its target by more than the stated tolerance stops and says so. Never pad,
   and never claim a cut the count does not show.
4. Every line target is a count after `uv run ruff format`.
5. Golden files live in `tests/core/fixtures/`. **No phase regenerates one.** Phase 3 deletes the
   three Breathless fixture folders and the golden tests iterate `ENGINE_IDS`
   (`tests/core/test_golden_schemas.py:10`, `test_golden_turn.py:18,55`), so the remaining
   fixtures must not move. A changed fixture is a bug in the step that changed it.
6. One commit per phase, full check green, reviewed adversarially against the staged diff first.
   Before the commit, run `uv sync --all-groups --locked` once and then the four commands on the
   staged tree: CI runs exactly that. `ruff format` also formats the Python fences in this file,
   so run `uv run ruff format PLAN.md` after editing it. Leave the game playable at the end of
   every phase: `uv run aidm`, open each shipped scenario, take a turn.
7. Delete, do not preserve. No compatibility path reads an old save, scenario or character file.
   No constant, helper, prompt line, CSS rule, asset or test stays for a caller that is gone.
8. The standing limits hold. Imports flow `core <- engines <- turn <- app <- ui` with no cycles.
   No `Any` beyond the `Game[P]` bound. Every `__init__.py` stays empty. Tests never start a
   process and stub roles with `ScriptedSpawner`. `Refusal` stays the one message-bearing
   exception. Only code changes state or rolls dice. The narrator reads revealed facts only.
   Module layout is imports, constants, classes, public functions, private functions. A comment
   is one line, only where the reason is not visible in the code.

## Phase 1: the dictation button

The mic button dictates into the composer through the browser's own `SpeechRecognition`. It has
no setting, no server side and no test of its own beyond two payload checks. It goes whole, and
the want it stood for is written down as an idea.

Target: `src` about **10,143**, within 10,136 to 10,150 (`game.py` minus 30, `widgets.py` minus
8). `tests` about **12,182**, within 12,176 to 12,188 (three tests and two imports out of
`tests/ui/test_game.py`). `qa` stays 2,088. About one hour.

### Steps

1. Delete `src/aidm/ui/dictation.js`.
2. `src/aidm/ui/widgets.py:20-26`: delete the `Dictation` class. Nothing else in the file names
   it.
3. `src/aidm/ui/game.py`: delete `DICTATION_FAILURES` (`:51-55`), `DictatedSpeech` (`:77-81`),
   the `Dictation(self.box)...` line in the composer (`:426`), `dictated` and `dictation_failed`
   (`:550-557`), and `insert_at_caret` (`:669` to the end of the function). Drop `Dictation` from
   the `aidm.ui.widgets` import (`:21`). `Frozen` and `parse` (`:16`) lose their only callers with
   `DictatedSpeech` and `dictated`: drop both, keep `Refusal, Slug`. `GenericEventArguments`
   (`:12`) stays; `sound_state` (`:536`) reads it.
4. `src/aidm/ui/theme.css:276-277`: delete `.game-dictating` and `@keyframes game-pulse`. In the
   reduced-motion block at `:332`, the rule becomes `.game-die-live { animation: none }`.
5. `tests/ui/test_game.py`: delete `test_insert_at_caret_spaces_only_against_a_non_space_neighbour`
   (`:107-111`), `test_dictated_rejects_a_payload_missing_what_dictation_js_promises` (`:518`) and
   `test_dictated_inserts_a_well_formed_payload_at_the_caret` (`:533`), `insert_at_caret` from
   the import at `:43`, and `GenericEventArguments` from `:9`, whose last two callers are those
   two tests.
6. `IDEAS.md`: one unchecked line, number 22, in the file's own voice: speech-to-text for the
   composer, a server-side transcription with its own provider key like speech and illustration,
   since the browser's own recogniser only works in Chrome over a secure context.
7. `README.md`: nothing names dictation; confirm with `grep -i dictat README.md docs` and move on.
8. Full check. `PROGRESS.md` entry with both counts.

## Phase 2: the dice land on the card

The chips on a fact card already show every die, tumble through `.game-die-live` for the live
turn, and stop tumbling under `prefers-reduced-motion`. The 3D tray shows the same numbers a
second time, relabelled to the value Python rolled, for a 692 KB vendored library, 28 sound files
and a `DiceLook` every engine must ship. The tray goes. One click sound stays, played when dice
land, muted by the same button and while a narration clip plays.

Target: `src` about **10,118**, within 10,110 to 10,126 (`dice.py` 35 to about 18, `views.py`
minus 8, `game.py` minus 2, `app.py` unchanged). `tests` about **12,183**, within 12,176 to 12,190
(two tests go from `tests/ui/test_dice.py`, one is rewritten, one is added). `qa` stays 2,088.
Non-Python: `ui/lib/` (two files, 692 KB), `dice_tray.js` and 27 of the 28 sound files go. About
half a day.

### Steps

1. One sound. Move `src/aidm/ui/dice_assets/sounds/dicehit/dicehit_plastic1.mp3` to
   `src/aidm/ui/roll.mp3`; delete `dice_assets/` whole. `src/aidm/ui/app.py:14,188`: the import
   becomes `DICE_SOUND, DICE_SOUND_ROUTE` and the mount becomes
   `app.add_static_file(local_file=DICE_SOUND, url_path=DICE_SOUND_ROUTE)` (NiceGUI 3.16,
   `nicegui/app/app.py:241`).
2. Delete `src/aidm/ui/lib/dice-box-threejs.es.js` and `src/aidm/ui/lib/dice-box-threejs.LICENSE`,
   then the empty `lib/` directory.
3. `src/aidm/ui/dice_tray.js` becomes `src/aidm/ui/dice_sound.js`, with no import, no props and
   no canvas. It keeps the `mounted()` emit of `sound` (`:19`, what sets the button's first icon),
   `SOUND_KEY`, `soundOn()`, `toggleSound()` with the same `"sound"` emit, and `narrating()`
   (`:77-79`). `this.audio = null` is declared in `created()`, outside `data()` for the reason the
   file's own comment at `:15` gives, and `mounted()` builds it once as `new Audio("/dice/roll.mp3")`.
   `toss` becomes `play()`: when `soundOn() && !narrating()`, set `currentTime = 0` and call
   `play()`, its promise's rejection ignored (autoplay policy before the first gesture is not an
   error the player reads). The reduced-motion and WebGL probes, `rested`, `REST_MS`, `FADE_MS`
   and `notation` go. About 35 lines.
4. `src/aidm/ui/dice.py`: constants `DICE_SOUND = Path(__file__).parent / "roll.mp3"` and
   `DICE_SOUND_ROUTE = "/dice/roll.mp3"`. `DiceTray` becomes
   `DiceSound(ui.element, component="dice_sound.js")` with no `dependencies`, no `__init__` and no
   CSS class, and one method `play(self, *, landed: bool) -> None` that calls
   `self.run_method("play")` when `landed`. Delete `thrown`. `rolled_since(facts, seen)` returns
   `bool`: whether any told card fact after `seen` carries dice. Drop the `DiceEvent` and
   `DiceLook` imports.
5. `src/aidm/core/views.py:119-129`: delete `DiceLook` (`:119-125`) and the `dice` field
   (`:129`); `Look` keeps only `palette`.
6. The four `look.json` files (`engines/{loner3e,tunnelgoons,breathless,twentyfourxx}/look.json`):
   delete the `"dice"` object and the comma before it. Phase 3 deletes the Breathless one anyway;
   edit it here so this phase's check is green on its own.
7. `src/aidm/ui/game.py`: `self.dice: DiceSound` (`:116`), `self.dice = DiceSound()` (`:196`),
   `self.dice.play(landed=self._dice_landed(now))` (`:444`). `_landed` (`:573-581`) becomes
   `_dice_landed(self, now: Observed) -> bool` with the same two reads, `or`-ed instead of
   concatenated; the `DiceEvent` import at `:17` goes if `Fact, cards` are its only remaining
   neighbours. `toggle_sound` and `sound_state` stay. Update the import at `:20`.
8. `src/aidm/ui/theme.css:271-274`: delete `.game-dice-overlay`; drop it from the reduced-motion
   transition rule at `:333`.
9. Tests. `tests/ui/test_dice.py`: delete `test_every_rolled_value_is_one_die_in_event_order` and
   `test_dice_look_keys_match_what_dice_tray_js_reads_off_look` and their imports; rewrite
   `test_only_the_told_dice_landing_after_the_seen_facts_are_thrown` for the `bool` (`seen=1`
   true, `seen=0` true, `seen=3` false). Add one test: `DiceSound().play(landed=False)` runs no
   method and `play(landed=True)` runs `"play"`, through a spy on `run_method`, built inside
   `Client(ui.page("/"))` under `_nicegui_loop()` the way `tests/ui/test_game.py:174-180` does
   (`run_method` returns a `NullResponse` with no loop, so the spy is the only observable).
   `tests/ui/test_game.py:35,164`: `DiceTray(...)` becomes `DiceSound()`. `tests/support/fifth.py:82`
   and `tests/support/sixth.py:68`: the look string becomes `'{"palette": {}}'`.
10. `README.md:78`: the 3D dice line goes. `IDEAS.md:14` (item 17) is rewritten as done
    differently: the chips on the card tumble and click; the physics canvas was tried and removed.
11. Full check, then `uv run aidm`, take a turn that rolls, hear one click, mute, roll, silence.
    `PROGRESS.md` entry with both counts.

## Phase 3: Breathless leaves

Breathless is the only engine with no progression: no drive, no job, no level. It is a one-shot
game on a platform built for long saves, and the smallest of the three scene engines. It goes
whole: package, scenario, character file, notes, fixtures, support module, qa scripts, licence
line. Three engines remain and the seam does not change.

Target: `src` about **9,459**, within 9,445 to 9,475 (658 lines of `engines/breathless/*.py`, 1
import in `registry.py`; the `BreathlessEngine()` entry is inline in a tuple and costs no line).
`tests` about **11,457**, within 11,430 to 11,490 (592 in `tests/breathless/`, 89 in
`tests/support/breathless.py`, about 45 across the six shared test files below). `qa` about
**2,019**, within 2,010 to 2,028 (42 in `s_breathless.py`, 16 in `s_create.py`, 10 in
`s_endure.py`, 1 in `agents.py`; `s_requests.py` is retargeted, not shortened). Two days.

### Steps

1. `src/aidm/engines/registry.py:2,10`: drop the import and the `BreathlessEngine()` entry.
2. Delete `src/aidm/engines/breathless/` whole: `__init__.py`, `engine.py`, `world.py`,
   `tools.py`, `worldsmith.py`, `rules.md`, `look.json`, `packs/srd.json`.
3. Delete `scenarios/drowned-road/`, `characters/kael/breathless.json`, `docs/BREATHLESS.md`.
4. Delete `tests/breathless/` whole, `tests/support/breathless.py` (`SKILLS_RATED` goes with it;
   its only importer is step 6's file), and the three fixture folders
   `tests/core/fixtures/schemas/breathless/`, `tests/core/fixtures/prompts/breathless/` and the
   file `tests/core/fixtures/turn/breathless.json`. No other fixture moves; `git status` on
   `tests/core/fixtures/` shows deletions only.
5. `tests/support/table.py:41`: delete `BREATHLESS`. `tests/support/golden_turn.py:73-77,112-119`:
   delete `_BREATHLESS_SCRIPT` and its `SCRIPTS` entry. `tests/core/test_package_boundary.py:10`:
   drop the engine from `ENGINES`.
6. `tests/engines/test_hire_tool.py`: delete the Breathless `HireCase` (`:61-72`),
   `_breathless_sheeted` (`:42-44`), the five `support.breathless` imports (`:8-12`) and the
   `BreathlessGame` import (`:24`). The comment at `:59` now reads that only 24XX reads a pack off
   the game when hiring. Two cases remain, parametrised as before.
7. `tests/engines/test_scene_bar.py`: delete the Breathless `SceneCase` (`:109-120`),
   `_breathless_hire` (`:103-105`), `BREATHLESS_BASE` (`:38-44`), the six `support.breathless`
   imports (`:8-13`) and the `BreathlessWorld, Survivor` import (`:28`). The docstring at `:247`
   says only 24XX carries a sheet. The two tests at `:275-302`, a party member's own brief naming
   what is hidden and a stored brief naming an absent unmet neighbour, test the bar, not
   Breathless: rewrite both on `twentyfourxx_world()` with `KESTREL` joined to the party and
   `SABLE` as the unmet name (`tests/support/twentyfourxx.py:39-44`: both are in `run.here`, the
   same shape as Mira and Dax), `SceneDraft[Crewmate]` and `TWENTYFOURXX_BASE`. Same asserts,
   same names.
8. `tests/app/test_game_service.py:294` (`test_a_failed_write_after_a_hire_names_the_hire`): the
   table opens on `TWENTYFOURXX` with `TwentyfourxxGame`, and the hire names `vessa-rune`, who is
   in `scenarios/silent-relay`'s opening `present` list and so known and hireable at the first
   turn (`scenes/world.py:245` marks every present entity known; the golden script at
   `tests/support/golden_turn.py:106` already joins her). Keep the words and the assert on the
   filed fact. `tests/app/test_game_service.py:527` and `tests/ui/test_game.py:335`: the
   "elsewhere" session opens `scenario_for(TWENTYFOURXX)`; drop the `BREATHLESS` import in both
   files and the `BreathlessGame` import at `tests/app/test_game_service.py:31`.
9. `tests/app/test_launcher.py:40`: drop the `("kael", BREATHLESS)` pair and the import at `:10`.
   `:87` and `:129` follow `KAEL_FOR_EACH`; nothing else counts engines.
10. qa. Delete `qa/s_breathless.py`. `qa/agents.py:44`: drop the entry. `qa/run_all.sh:8`: drop
    `breathless` from the list. `qa/README.md:23-25`: drop it from the scenario list and "each of
    the four games" becomes three. `qa/s_create.py:117-132`: delete the Breathless block, blank
    line included. `qa/s_endure.py:33-42`: delete the `drowned-road` entry from `RUNS`; three runs
    remain. `qa/s_requests.py:30-50`: the departure case moves to `/game/silent-relay/kael` with
    `!next_scene pursuit="Up the ridge"`, `!roll what="Keep running" skill="Stealth"` and
    `!change_hindrances gained='["Bruised"]'` (the shape `s_endure.py:49` uses) in place of
    `!change_stress`; the note and screenshot names follow. Prove the harness still imports:
    `PYTHONPATH=qa uv run --group qa python -c "import art, agents"`.
11. `README.md`: delete the Breathless paragraph (`:23`), its notes link (`:63`) and its licence
    line (`:72`); "Four engines ship from one build" (`:16`) becomes three. `IDEAS.md` and
    `docs/COMPETITOR-RESEARCH.md` name neither Breathless nor the scenario; confirm with grep.
12. `grep -ri "breathless\|drowned" --exclude-dir=.venv --exclude-dir=.git .` returns only
    `PLAN.md`, `PROGRESS.md` and the two `tests/core/fixtures/source/drowned-road.*` fixtures.
13. Full check, then `uv run aidm`: the launcher lists three engines, kael has three sheets, the
    three scenarios each take a turn. `PROGRESS.md` entry with both counts.
