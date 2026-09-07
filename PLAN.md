# PLAN — the table: phone layout, a safe composer, physics dice, dictation

Four phases, in order. **Phase 1** makes the game page a Quasar layout that works on a phone,
a tablet and a wide screen, and gives the other pages the same wrapping rules. **Phase 2** makes
the composer safe: a draft survives a failed turn and a reload, Restart asks first, and the
transcript stops stealing the reader's place. **Phase 3** replaces the hand-built CSS polyhedra
with `@3d-dice/dice-box-threejs`, physics and sound included, driven by the values Python rolled.
**Phase 4** adds tap-to-dictate to the composer through the browser's own speech recognition.
Self-standing: an implementer needs this file, `CLAUDE.md` and the code. The 2026-09-07 UX
specification this plan was cut from is not in the repository; its findings are folded here.

What stays, everywhere: Python is the only game RNG; the browser draws what Python rolled and
never writes a result back; only the dice on `told` cards reach the browser (`core.facts.cards`);
the narrator reads revealed facts only; `PlayerView` and the engine-owned decisions are the one
shape the page reads; NiceGUI and Quasar are the UI, with no second frontend framework. What is
not built: server-side transcription, an HTTPS path (the maintainer plays over a tailnet), a
dice tray that takes page space, multiplayer, a resume summary, journal search, onboarding.

Saves are untouched: no phase adds a field to any game, scenario or character model.
Presentation preferences (sound on or off) live in the browser, never in a save.

## Decisions

1. **Quasar layout replaces the splitter.** `ui.header` (as now), `ui.right_drawer(value=None,
   bordered=True)` for Scene and Journal (Quasar shows it beside the page from 1024px and as an
   overlay below, opened by a header button), the story as the page body, and `ui.footer` for
   the decision, the way-on banner and the composer. The `calc(100vh - 6rem)` hack and the 55/45
   splitter go. The transcript stays a `ui.scroll_area`; it is the one scrolling element, and it
   fills the space the layout leaves, through CSS on `.q-page-container` and `.q-page`, not a
   measured height.
2. **Three widths, one page build.** Under 768px: no scene art, a compact scene heading, the
   drawer closed. 768 to 1023px: the drawer closed until opened. From 1024px: the drawer open
   beside a story column capped at the existing 46rem. The page is built once; CSS media
   queries and Quasar's breakpoint do the rest. No page rebuilds on resize, no second
   `GamePage` per width.
3. **Enter sends on a keyboard, not on a touch screen.** The `keydown.enter` handler sends only
   when `matchMedia("(pointer: fine)")` matches; on a coarse pointer Return inserts a newline
   and the Send button submits. The Send button is the primary path on a phone and stays at
   least 44px square.
4. **A draft clears only when the turn was accepted.** `submit` keeps the text in the box until
   `play` or `act` returns without raising; a `Refusal` or `OSError` leaves the text in place
   under the notification. The draft is bound to `app.storage.tab` under the game's slug, so a
   reload of the same tab brings it back. Nothing is written to the save.
5. **The transcript follows only a reader who is at the bottom.** A scroll event on the
   `scroll_area` records whether the reader is within 5% of the end. A refresh scrolls to the
   end when they were, or when the change is their own submission; otherwise a "New activity"
   button sits above the footer and scrolls on press.
6. **Restart asks first.** One `ui.dialog` naming the scenario and the turn count, "Restart"
   and "Keep playing"; the button moves into the header's overflow menu so a thumb cannot hit it.
7. **The dice library is `@3d-dice/dice-box-threejs` 0.0.12**, MIT, 1.3 MB of ES module
   bundling Three.js 0.143 and cannon-es, vendored under `src/aidm/ui/lib/` with its LICENSE
   beside it, no npm toolchain. The Babylon `@3d-dice/dice-box` (11 MB, no documented
   prescribed-result API) is refused. The library rolls real physics and then relabels the
   resting face to the prescribed value (`roll("2d6@2,5")`), so the die always shows what
   Python rolled. Assets vendored are only what the game uses: the `plastic` hit sounds and the
   `felt` surface sounds; no texture images, the dice are flat colour from `DiceLook`.
8. **The dice stay a full-page transparent overlay**, as today, `pointer-events: none`, above
   the drawer and the footer, cleared about three seconds after the last die rests. A tray
   that takes page space is refused: on a phone the page has none to give. The overlay never
   encodes kept and not kept; the card below does, with its border and label. Reduced motion
   means no toss; a browser without WebGL means no toss; the card is always drawn first.
9. **Dice sound is on by default, one mute button in the header**, remembered in
   `localStorage` by the browser component, never by Python. The toss is silent while a
   narration `<audio>` is playing. There is no effects volume slider and no fanfare.
10. **Dictation is the browser's `SpeechRecognition`**, no key, no server, no upload. The
    microphone button appears only where `window.SpeechRecognition ||
    window.webkitSpeechRecognition` exists (Chrome, Edge, Safari; not Firefox). Recognised
    text is inserted into the draft at the caret when the player presses Stop; nothing is ever
    submitted by speech. Every failure (denied, no microphone, no speech, insecure context)
    becomes one `ui.notify` and the typed path continues.

## How to work

Run these four from the repository root, with `UV_CACHE_DIR` unset. "Full check" means all four
pass:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
```

1. **Do the steps in order.** Each is one action on the files it names. Finish it before the next.
2. **Change a shape and its tests in the same step.** One test per new behaviour; no test of prose
   or wiring. A test of a deleted behaviour is deleted with it, never kept alive by stubbing.
   Browser behaviour (layout, animation, speech events) has no Python test; the Python tests
   cover the seams: what is sent to the browser, when the composer opens, what a draft does.
3. **Look at it.** Every phase that touches `ui/` ends with `uv run aidm` opened in Chromium at
   390px, 768px and 1280px wide (Playwright is installed; a throwaway script in the scratch
   directory, never committed). A layout phase is not done until the three screenshots were read.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file. `src` is 9,698 lines at the start of Phase 1,
   Python and JavaScript together, the vendored library excluded:
   ```bash
   find src -name '*.py' -o -name '*.js' -not -path '*/lib/*' | xargs cat | wc -l
   ```
5. **If a phase runs half again past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** The full check is green before the commit. Never leave two
   versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **The standing limits hold.** Imports flow `core <- engines <- turn <- app <- ui`; nothing
   below `ui` changes in this plan; no `Any`; every `__init__.py` empty; tests never start a
   process; `Refusal` stays the one message-bearing exception; NiceGUI gap is set with
   `.style("gap: ...")`, never a Tailwind `gap-*` class.
10. **Delete, do not preserve.** When the library lands, `dice_overlay.js` and the polyhedron
    CSS go the same day; no flag chooses between two renderers.

---

## Phase 1 — the page fits the screen

Target: about +60 lines in `ui/`. The game page becomes a Quasar layout; the other pages get
the wrapping rules; nothing about play changes.

### Steps

1. **`ui/theme.py` — layout and breakpoints.** Add to `_CSS`: `.q-page-container` and
   `.q-page` as flex columns filling `100dvh` (`box-sizing: border-box`; `min-height: 0` on the
   children) so a `flex-grow` `scroll_area` gets the space between header and footer;
   `.q-footer` padding of `env(safe-area-inset-bottom)`; `.game-drawer` background
   `var(--game-surface)`; under 768px `.game-scene-art { display: none }` and `.game-scene
   .text-h6 { font-size: 1rem }`; the `.game-transcript` cap stays 46rem. Delete
   `_SCENE_HEIGHT` and `_ART_BOX` from `game.py` in favour of classes `game-scene` and
   `game-scene-art` with the same rules moved into `_CSS`.
2. **`ui/game.py` — the layout.** `GamePage.build` builds, in this order: `page_header` (with
   a `menu_book` button toggling the drawer, `props("flat color=white round")`), then the story
   column as the page body (`scene_header`, the `scroll_area` transcript with `chat` and
   `live_turn`, `classes("w-full flex-grow game-transcript")`), then
   `ui.right_drawer(value=None, bordered=True).props("width=420").classes("game-drawer")` with
   the Scene and Journal tabs as now, then `ui.footer().classes("game-footer")` holding
   `decision_panel`, `way_on_panel` and `composer` inside a column capped at 46rem and centred.
   The footer's own max height is `50dvh`; the decision panel scrolls inside it when a prompt
   is long. Delete the splitter. `_scroll` keeps scrolling the `scroll_area` to the end (Phase 2
   changes when).
3. **`ui/game.py` — the composer on a touch screen.** The `keydown.enter` `js_handler` becomes
   `(e) => { if (e.shiftKey || !matchMedia("(pointer: fine)").matches) return;
   e.preventDefault(); emit(); }`. Send gets `props("round flat size=lg")` and an
   `aria-label="Send"`; the action button keeps its label. The `ui.input` gets
   `props("... input-style=\"max-height: 9rem\"")` so a long draft scrolls inside the box.
4. **`ui/widgets.py` — `decision_widget` on touch.** An option with `detail` shows it as a
   second line under the label (`ui.button` with a nested column: label, then `text-xs
   opacity-70` detail) instead of a tooltip only; the buttons row wraps (`classes("w-full
   items-start")`, no `no-wrap`). Every option button has `no-caps`, `min-height: 44px`.
5. **Home, Create, Settings wrap.** `ui/app.py`: the header's "Choose your game" label hides
   under 768px (`classes("gt-xs")`); `_saved_card`'s row wraps and the Resume button takes the
   full width under 768px (`classes("col-12 col-sm-auto")`). `ui/settings.py`: the vertical
   tabs become one horizontal, scrollable `ui.tabs().props("dense outside-arrows
   mobile-arrows").classes("w-full")` above the panels at every width; the `no-wrap` row goes.
   `ui/create.py`: every `ui.row` of form controls drops `no-wrap` and every input gets
   `classes("w-full")` where it has not got it.
6. **Look at it** (How to work 3): a pending decision, a long draft and an open drawer at
   390px and 1280px; the keyboard open on a phone emulation (`--window-size` and Playwright's
   `iPhone 13` device). Fix what the screenshots show before the review.

### Done when

- `uv run aidm` at 390px: header, scene heading without art, transcript, footer with composer
  and Send all visible; no horizontal scroll; the drawer opens as an overlay from the header.
- At 1280px: drawer beside the story, story column at most 46rem, footer under it.
- Return on a coarse pointer inserts a newline; Enter on a fine pointer sends.
- Full check green; `tests/ui/test_game.py` unchanged (nothing in `can_type` or
  `standing_proposal` moved).

## Phase 2 — a safe composer, a still page

Target: about +70 lines in `ui/game.py` and `ui/widgets.py`, +25 in `tests/ui/test_game.py`.

### Steps

1. **`ui/game.py` — the draft outlives a failed turn.** `GamePage._run(self, playing) ->
   bool`: `True` when `playing()` returned, `False` when it raised `OSError` or `Refusal`, which
   `_run` notifies itself (`ui.notify(f"{type(error).__name__}: {error}", type="negative",
   multi_line=True)`). `submit` no longer clears the box before awaiting; it clears (`box.value =
   ""`, `run_method("updateValue")`) only when `_run` returned `True`. `widgets.working()` had
   that one caller and is deleted.
2. **`ui/game.py` — the draft outlives a reload.** In `composer`, `self.box.bind_value(
   app.storage.tab, f"draft:{self.session.slug}")`. Nothing else: `app.storage.tab` is
   server-side per tab and needs no secret.
3. **`ui/game.py` — the transcript follows a reader at the end.** `GamePage.at_end: bool =
   True`, set by `transcript.on_scroll(lambda e: ...)` from `e.vertical_percentage >= 0.95`.
   `GamePage.follow: bool = False`, set `True` by `submit` and the decision and proposal
   handlers before `_run`, cleared after `_scroll`. `_scroll` scrolls when `should_follow(
   self.at_end, self.follow)` (a free function in `game.py`: `at_end or own`), else shows
   `self.new_activity`, a `ui.button("New activity", icon="arrow_downward")` built once in the
   footer above the decision panel, hidden by default, that scrolls to the end and hides on
   press. `poll_turn` passes through `_scroll` as now.
4. **`ui/game.py` — Restart asks.** The header's `restart` button becomes a `ui.button(icon=
   "more_vert")` with a `ui.menu` holding one `ui.menu_item("Restart this game")`. Pressing it
   opens a `ui.dialog` with `f"Restart {title}? {turns} turns are erased."`, "Restart" (calls
   the existing `restart`) and "Keep playing". A game with no history restarts without asking.
5. **`tests/ui/test_game.py` — the seams.** One test that `should_follow` is true at the end
   or on the reader's own move and false otherwise. One test, through a `GamePage` built under
   NiceGUI's `Client` test context if the repository already has one, else through `submit`'s
   pure part extracted as `accepted(typed, action, acting) -> Answer | tuple[Slug, str] |
   None`: a refused turn leaves the box's value; an accepted one clears it. The implementer
   picks the smaller of the two and says which in `PROGRESS.md`.
6. **Look at it**: fail a turn on purpose (kill the spawner's command in Settings) and see the
   text stay; reload and see it return; scroll up mid-turn and see the page hold; press Restart
   and cancel.

### Done when

- A `Refusal` leaves the typed text in the box; a reload of the tab brings it back.
- Reviewing history during a turn is not interrupted; "New activity" appears and works.
- Restart shows the dialog; "Keep playing" changes nothing.
- Full check green; two new tests.

## Phase 3 — the dice library

Target: about −120 lines of our own code (`dice_overlay.js` and its CSS go; `dice_tray.js` is
about 80 lines). The vendored library and its assets are not counted.

### Steps

1. **Vendor.** `src/aidm/ui/lib/dice-box-threejs.es.js` and `src/aidm/ui/lib/
   dice-box-threejs.LICENSE`, both byte-for-byte from the npm tarball of 0.0.12
   (`https://registry.npmjs.org/@3d-dice/dice-box-threejs/-/dice-box-threejs-0.0.12.tgz`).
   `src/aidm/ui/dice_assets/sounds/dicehit/dicehit_plastic1..15.mp3` and
   `src/aidm/ui/dice_assets/sounds/surfaces/surface_felt1..7.mp3` from the tarball's `public/`.
   No textures. `pyproject.toml` needs no change: hatch ships every file under `src/aidm`.
   `README.md` gets one line under the dependencies naming the library and its licence.
2. **`ui/dice.py` — the tray.** `class DiceTray(ui.element, component="dice_tray.js",
   dependencies=["lib/dice-box-threejs.es.js"])`, replacing `DiceOverlay`; `__init__(self,
   look: DiceLook)` passes `self._props["look"] = look.model_dump()` and keeps the
   `game-dice-overlay` class. `toss(self, events)` calls `run_method("toss", thrown(events))`.
   `thrown(events) -> list[dict[str, int | list[int]]]`: one entry per `DiceEvent`, `{"faces":
   6, "values": [2, 5]}` (kept is no longer sent: decision 8). Constants `DICE_ASSETS = Path(
   __file__).parent / "dice_assets"` and `DICE_ASSETS_ROUTE = "/dice/"`. `ui/app.py`
   `_register_pages` calls `app.add_static_files(DICE_ASSETS_ROUTE, DICE_ASSETS)`.
   `tests/ui/test_dice.py`: `thrown` test rewritten to the new shape; `rolled_since` test
   unchanged.
3. **`ui/dice_tray.js`.** `import DiceBox from "dice-box-threejs.es"`. Template: a `<div>`
   with a unique id (`"dice-" + Math.random().toString(36).slice(2)`). `mounted()`: return
   at once when `matchMedia("(prefers-reduced-motion: reduce)")` matches or when a test
   `canvas.getContext("webgl2") ?? canvas.getContext("webgl")` is null; otherwise `this.box =
   new DiceBox("#" + id, {assetPath: "/dice/", sounds: this.soundOn(), theme_customColorset:
   {name: "aidm", foreground: look.ink, background: look.body, outline: look.glow, texture:
   "none", material: "plastic"}, theme_material: "plastic", theme_surface: "felt", shadows:
   false, strength: 1.5, onRollComplete: () => this.rested()})` then `await
   this.box.initialize()`; any rejection logs once and leaves `this.box` null. `toss(groups)`:
   no-op without a box; else `this.box.sounds = this.soundOn() && !narrating()`, then
   `this.box.roll(groups.map(g => `${g.values.length}d${g.faces}@${g.values.join(",")}`).join(
   "+"))`. `rested()`: after 2500ms, fade the element (`opacity 0` over 500ms) and
   `this.box.clearDice()`, then reset opacity; a toss that lands during the wait cancels the
   pending clear. `narrating()`: `[...document.querySelectorAll("audio")].some(a => !a.paused)`.
   `soundOn()`: `localStorage.getItem("aidm.dice.sound") !== "off"`. `toggleSound()`: flips
   and stores it, returns the new state. `unmounted()`: `clearDice()` and drop the box.
4. **`ui/game.py` — the mute button.** In the header, `ui.button(icon="volume_up",
   on_click=self.toggle_sound).props("flat color=white round")`; `toggle_sound` awaits
   `self.dice.run_method("toggleSound")` and sets the icon (`volume_up` / `volume_off`). On
   build a `ui.timer(0.5, once=True)` asks `run_method("soundOn")` the same way for the first
   icon. `self.dice` is a `DiceTray`.
5. **Delete.** `ui/dice_overlay.js`; from `theme.py` every `.game-dice-*` rule except
   `.game-dice-overlay` (fixed, inset 0, `pointer-events: none`, `z-index: 7000`, `transition:
   opacity .5s`); the `.game-die-live` tumble on the card stays. `IDEAS.md` 17 becomes `[x]`.
6. **Look at it**: a Loner turn with a roll at 390px and 1280px; a Breathless turn (two
   groups) and a 24XX turn with a kept die; the mute button; the card first, the dice after,
   the dice gone in about three seconds; reload does not re-roll.

### Done when

- Every rolled die lands showing the value on the card, in the engine's colours, with sound
  unless muted or narration is playing; the card is drawn before the dice move.
- A hidden roll (a `Fact` with `told=False`) never reaches `toss`: the existing `rolled_since`
  test still says so.
- No `dice_overlay.js`, no polyhedron CSS, no flag between renderers.
- Full check green; `src` line count down.

## Phase 4 — dictation

Target: about +90 lines: `ui/dictation.js` (about 60), `ui/game.py` (about 30).

### Steps

1. **`ui/dictation.js`.** A component whose template is one `q-btn` (round, flat, icon `mic`,
   `aria-label="Dictate"`) that is `hidden` when neither `SpeechRecognition` nor
   `webkitSpeechRecognition` exists. Press: `start()` a recogniser with `continuous: true,
   interimResults: true, lang: navigator.language`; the icon becomes `stop`, red, with a pulsing
   ring (`.game-dictating` CSS); interim text is shown in a small caption under the button
   (`this.interim`), never written to the draft. Press again, or the recogniser's own `end`,
   finalises: `this.$emit("dictated", finalText)` once, with the joined final results, and the
   caption clears. `onerror` emits `this.$emit("failed", event.error)` and resets; a second
   press while finalising is ignored. A 60-second `setTimeout` stops a forgotten recording.
   `unmounted()` aborts a running recogniser.
2. **`ui/game.py` — the composer takes it.** `Dictation(ui.element, component="dictation.js")`
   in `ui/dice.py`'s sibling `ui/dictation.py` (six lines: the class and nothing else). The
   composer row places it before Send. `on("dictated", self.dictated)`: `self.box.value =
   insert_at_caret(self.box.value or "", text, caret)` where the caret comes with the event as
   `event.args.caret`, read in JS from the input's `selectionStart` at press time (the composer
   passes its own element id to the component as a prop, `target`). `insert_at_caret(draft: str,
   text: str, caret: int) -> str`: a free function that inserts with one space on each side
   where the neighbours are not whitespace. `on("failed", ...)`: one `ui.notify` mapping
   `not-allowed` to "The browser refused the microphone.", `audio-capture` to "No microphone.",
   `no-speech` to "Nothing was heard.", anything else to the raw error, `type="warning"`. The
   box is disabled while recording, through the existing `set_enabled`, and re-enabled on
   `dictated` or `failed`; Send stays enabled so a player can send what was typed before.
3. **`tests/ui/test_game.py`.** One test of `insert_at_caret`: mid-word, at the end, in an
   empty draft.
4. **Look at it**: in Chromium with a fake media stream (`--use-fake-ui-for-media-stream
   --use-fake-device-for-media-stream`): the button appears, records, the interim caption
   shows, Stop inserts, Send is the player's. In Firefox: no button, typing works.

### Done when

- Recognised text lands in the draft at the caret, and only after Stop; nothing is sent.
- Every error path is one notification and typing continues; Firefox shows no button.
- Full check green; one new test.

## Refused in this plan, with the reason

- **A contained dice tray**: page space a phone does not have (decision 8).
- **Kept and not-kept dice in the 3D overlay**: the library labels a die, it does not dim one;
  the card carries the meaning and did before.
- **Sound off by default, an effects slider, fanfares**: the maintainer asked for sound; one
  button is the whole control.
- **HTTPS, server transcription, provider keys for speech-to-text**: the tailnet carries the
  phone; the browser carries recognition; nothing on the server.
- **Sheets for Scene and Journal, a resizable context pane**: Quasar's drawer does both jobs
  with its own breakpoint; a resizable pane is a splitter again.
- **Reading size, focus mode, journal search, a resume summary, onboarding**: after these
  four phases, if still wanted, each is one small plan of its own.
