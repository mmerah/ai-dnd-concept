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
