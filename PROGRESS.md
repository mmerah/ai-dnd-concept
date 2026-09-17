# PROGRESS

One entry per `PLAN.md` phase: the counts it moved, what was decided off-plan, and what is known
and accepted.

## Phase 1: the dictation button

The mic button, its `SpeechRecognition` component, the page handlers, the CSS pulse and the three
tests went whole. The want is `IDEAS.md` item 22: a server-side transcription with its own key.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,181 | **10,143** | about 10,143, within 10,136 to 10,150 |
| `tests` | 12,222 | **12,182** | about 12,182, within 12,176 to 12,188 |
| `qa` | 2,088 | **2,088** | unchanged |

Both counts landed on the plan's number.

### Decided off-plan

None. Every step landed as written.

### Reviews

Phases 1 and 2 were run in one pass and reviewed together as one staged diff by two Opus
reviewers (no `codex` on the machine, and the maintainer asked for Opus only). No finding named
phase 1. The two phases are two commits: the phase 1 tree was rebuilt from the shared files
(`game.py`, `theme.css`, `tests/ui/test_game.py`, `IDEAS.md`) and checked on its own.

### Known and accepted

Nothing.

## Phase 2: the dice land on the card

The 3D tray went: the vendored `dice-box-threejs` (two files, 692 KB), `dice_tray.js`, its canvas
and 27 of its 28 sound files. The 28th is `ui/roll.mp3` (4 KB), played once when dice land, muted
by the same button and while a clip narrates. The chips wear the engine's `DiceLook` colours
through `--game-die-body`, `--game-die-ink` and `--game-die-glow`, which `theme.set_look` writes
beside the palette.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,143 | **10,137** | about 10,128, within 10,120 to 10,136 |
| `tests` | 12,182 | **12,180** | about 12,188, within 12,180 to 12,196 |
| `qa` | 2,088 | **2,088** | unchanged |

**`src` is one line over the plan's cap, and this entry is the "stops and says so" the plan asks
for.** The implementer's tree measured 10,133. The fold of the two reviews then added
`DiceSound.__init__` (the route reaches the browser as a prop, not as a second copy of the path)
and `theme.dice_variables` (the three variable names in one place, read by `set_look` and by the
drift test), and removed the `landed` branch and a one-use alias: net plus four. Neither addition
is padding; each closes a seam a reviewer named. `tests` sits on the floor of its band because the
spy test the plan added went with the flag it pinned.

### Decided off-plan

1. **`DiceSound.play()` takes no `landed` flag.** The plan's `play(self, *, landed: bool)` was a
   `play` that does not play; the caller in `poll_turn` now reads `if self._dice_landed(now):
   self.dice.play()`. The spy test that proved that one `if` through a real `Client` went with it.
   Both reviewers.
2. **The sound route is a prop.** `DiceSound.__init__` sets `src` to `DICE_SOUND_ROUTE` and
   `dice_sound.js` builds `new Audio(this.src)`. The plan had the component hardcode
   `"/dice/roll.mp3"` beside the same string in `dice.py`, a silent 404 the moment either moved.
   Both reviewers.
3. **`theme.dice_variables(DiceLook) -> dict[str, str]`** names the three variables once.
   `set_look` writes it and the drift test in `tests/ui/test_dice.py` reads it, so a prefix change
   on the writer's side fails the test, and `model_dump()`'s `Any` values are gone. The plan's step
   5 built the mapping inline off `model_dump()`. Both reviewers.
4. **`dice_sound.js` has no `created()` hook.** The tray's reason for it (Three.js objects under a
   Vue proxy) does not apply to an `HTMLAudioElement` that only `mounted()` writes.
5. **`poll_turn`'s local `landed` is `closed`.** It means "an exchange closed", and `_dice_landed`
   one line above gave the word a second meaning.
6. **No `_nicegui_loop` copy in `test_dice.py`.** The plan asked for one; with the flag gone the
   test went, and it never needed the loop: the spy replaced `run_method`.

### Refuted findings

None. All thirteen findings across the two Opus reviews were fixed.

### Known and accepted

- The click plays under `prefers-reduced-motion`. The tray's probe used to skip the whole tray,
  sound included; that preference is about motion, and the chips already stop tumbling under it.
- `.game-die-face` (the "d6" label) renders in the engine's ink, not `--game-muted`, as the plan's
  step 6 says.
- Smoke: `uv run aidm` came up; each of the three shipped scenarios opened headless carries its
  own `--game-die-*` triplet on `body`, a muted `localStorage` key survives a reload as
  `volume_off`, the page fetches `/dice/roll.mp3` on mount through the prop, the old
  `/dice/sounds/...` route answers 404, and the console is clean. A turn that rolls needs an AI
  CLI the container lacks, so the click was not heard; `play()`'s browser path is six lines.

## Phase 3: Breathless leaves

The engine went whole: the package, `scenarios/drowned-road`, `characters/kael/breathless.json`,
`docs/BREATHLESS.md`, `tests/breathless/`, `tests/support/breathless.py`, the three golden fixture
folders, `qa/s_breathless.py` and the README paragraph, link and licence line. Three engines
remain and the seam did not change. The shared tests that happened to run on Breathless now run
on 24XX; the qa departure case runs on `silent-relay` and the complication case on
`whispering-vault`.

### Counts

| | before | after | plan target |
|---|---|---|---|
| `src` | 10,137 | **9,464** | about 9,469, within 9,455 to 9,485 |
| `tests` | 12,180 | **11,406** | about 11,462, within 11,435 to 11,495 |
| `qa` | 2,088 | **2,004** | about 2,019, within 2,010 to 2,028 |

**`tests` and `qa` are under their floors, and this entry is the "stops and says so" the plan
asks for.** Nothing was cut beyond the plan's steps and the reviews' findings below; both bands
were estimates that missed. `tests`: the six shared files gave up 73 lines where the plan
budgeted about 45 (`test_scene_bar.py` 31, `test_hire_tool.py` 24, `golden_turn.py` 14, three
files 4), and the fold below took 20 more. `qa`: the plan missed two Breathless lines,
`s_home.py`'s count of four scenarios and the scripted worldsmith's 16-line survivor sheet in
`agents.py`; the qa smoke found both.

### Decided off-plan

1. **`Item`, `ItemSheet`, `banded` and `oracle_roll` left `engines/base.py`.** The plan kept them
   because each had a user in `twentyfourxx/`, but after the cut each had exactly one, so the
   generic was an abstraction with one implementer. `Gear` now carries `name`, `CrewSheet` carries
   `items`, `require` and `drop_item`, `ask_world` rolls its own d6 and `_banded` is private to
   the 24XX engine. `Sheeted`, `Gauge`, `DropItem` and `AskWorld` stay where they were. Both
   reviewers named the cut; the maintainer asked for the cleanest end state over the plan.
2. **`test_scene_bar.py` lost `sheets_the_player`, `hire`, `SHEETED_CASES` and `HIRING_CASES`.**
   Each selected the one 24XX case; the two tests they parametrised are plain 24XX tests now.
   Both reviewers.
3. **The qa complication case moved to Loner 3e.** With the departure case on `silent-relay`,
   case 4 reopened the same save after a departure, a doubled request and a crash, and its
   "installed a scene" check could no longer fail. It opens `whispering-vault` fresh and follows
   the complication with `!reveal entity_id=vault-map`. Both reviewers.
4. **The retargeted words describe the relay, not the flats.** "Guide us through the relay",
   "Down the docking ring", "Through the airlock", "Back to the hub", "Down the service shaft".
   One reviewer.

### Reviews

Two Opus reviewers on the staged diff (no `codex` on the machine, and the maintainer asked for
Opus only). Seven findings and five cuts across the two; all fixed or taken, none refuted.

### Known and accepted

- `qa/s_create.py:11` and `tests/app/test_launcher.py:240` read
  `tests/core/fixtures/source/drowned-road.md`, the PDF-ingestion fixture the plan keeps. The
  plan's step 12 grep list named only `test_documents.py` as its reader; these two are the
  same fixture and stay.
- Smoke: the qa harness with scripted roles ran `home`, `create`, `requests` and `endure` on
  fresh servers, 0 issues each: the launcher lists three scenarios, kael has three sheets, the
  three scenarios each take eight turns with reloads, and 24XX's `drop_item` and `ask_world`
  roll after the fold.
