# PLAN — the table: phone layout, a safe composer, physics dice, dictation

Four phases, in order. **Phase 1** makes the game page a Quasar layout that works on a phone,
a tablet and a wide screen, and gives the other pages the same wrapping rules. **Phase 2** makes
the composer safe: a draft survives a failed turn and a reload, Restart asks first, and the
transcript stops stealing the reader's place. **Phase 3** replaces the hand-built CSS polyhedra
with `@3d-dice/dice-box-threejs`, physics and sound included, driven by the values Python rolled.
**Phase 4** adds tap-to-dictate to the composer through the browser's own speech recognition.
Self-standing: an implementer needs this file, `CLAUDE.md` and the code. The 2026-09-07 UX
specification this plan was cut from is not in the repository; its findings are folded here.
Every library claim below was read in the 0.0.12 bundle, `dist/dice-box-threejs.es.js`; the
line numbers name that file.

What stays, everywhere: Python is the only game RNG; the browser draws what Python rolled and
never writes a result back; only the dice on `told` cards reach the browser (`core.facts.cards`);
the narrator reads revealed facts only; `PlayerView` and the engine-owned decisions are the one
shape the page reads; NiceGUI and Quasar are the UI, with no second frontend framework. What is
not built: server-side transcription, an HTTPS path in the app (the maintainer plays over a
tailnet; `tailscale serve` gives the phone HTTPS with no code), a dice tray that takes page
space, multiplayer, a resume summary, journal search, onboarding.

Saves are untouched: no phase adds a field to any game, scenario or character model.
Presentation preferences (sound on or off) live in the browser, never in a save.

## Decisions

1. **Quasar layout replaces the splitter.** `ui.header` (as now), `ui.right_drawer(value=None,
   bordered=True)` for Scene and Journal (Quasar shows it beside the page from 1024px and as an
   overlay below, opened by a header button), the story as the page body, and `ui.footer` for
   the decision, the way-on banner and the composer. The `calc(100vh - 6rem)` hack and the 55/45
   splitter go. The transcript stays a `ui.scroll_area`; it is the one scrolling element, and it
   fills the space the layout leaves, through CSS on the Quasar chain `.q-page-container >
   .q-page > .nicegui-content`, not a measured height. `.q-page` carries an inline `min-height`
   from Quasar, so the override is `!important`; only the container is `100dvh`.
2. **Quasar's breakpoints, nowhere else's.** Quasar switches `xs` to `sm` at 600px and opens
   the drawer at 1024px; every rule in this plan uses those two, through Quasar's `gt-xs` and
   `col-sm-*` classes or a media query at `599.98px`. Under 600px: no scene art, a compact
   scene heading, the drawer closed. 600 to 1023px: the drawer closed until opened. From 1024px:
   the drawer open beside a story column capped at the existing 46rem. The page is built once;
   no page rebuilds on resize, no second `GamePage` per width.
3. **Enter sends on a keyboard, not on a touch screen.** The `keydown.enter` handler sends only
   when `matchMedia("(pointer: fine)")` matches; on a coarse pointer Return inserts a newline
   and the Send button submits. The Send button is the primary path on a phone and stays at
   least 44px square.
4. **A draft clears only when the turn was accepted.** `submit` keeps the text in the box until
   `play` or `act` returns without raising; a `Refusal` or `OSError` leaves the text in place
   under the notification. The draft is bound to `app.storage.tab` under the game's slug, so a
   reload of the same tab brings it back. `app.storage.tab` needs no secret but does need the
   socket (`storage.py:174` raises before the handshake), so the game page awaits
   `ui.context.client.connected()` before it builds. Nothing is written to the save.
5. **The transcript follows only a reader who is at the end.** A scroll event on the
   `scroll_area` records whether the reader is within 48px of the end, in pixels: Quasar's
   percentage is 0 when the content fits and the event also fires on a content resize. The
   decision to follow is taken in `poll_turn` before `refresh()` grows the content, from that
   flag or from the change being the reader's own submission; otherwise a "New activity"
   button sits above the footer and scrolls on press.
6. **Restart asks first.** One `ui.dialog` naming the scenario and the turn count, "Restart"
   and "Keep playing"; the button moves into the header's overflow menu so a thumb cannot hit it.
7. **The dice library is `@3d-dice/dice-box-threejs` 0.0.12**, MIT, a 697 KB ES module
   bundling Three.js 0.143 and cannon-es, vendored under `src/aidm/ui/lib/` with its LICENSE
   beside it, no npm toolchain. The Babylon `@3d-dice/dice-box` (11 MB, no documented
   prescribed-result API) is refused. The library rolls real physics and then relabels the
   resting face to the prescribed value (`swapDiceFace`, 16949 and 17239-17243), so the die
   always shows what Python rolled. Its notation has one `@`: sets before it, every prescribed
   value after it, in spawn order (`parseNotation` splits on `@` once, 15018, and reads values
   only from the tail, 15024); same-type sets merge into one (`addSet`, 15038-15039). So the
   browser groups the dice by face in first-appearance order and sends `"2d6+1d8@2,5,3"`, never
   one `@` per group. Assets vendored are only what the game uses: the `plastic` and `coin` hit
   sounds (`loadSounds` fetches the coin set unconditionally, 16826-16832) and the `felt`
   surface sounds; no texture images, the dice are flat colour from `DiceLook`.
8. **The dice stay a full-page transparent overlay**, as today, `pointer-events: none`,
   `z-index: 5000`: above the header, footer and drawer (2000 and 1000 to 3000), below dialogs,
   menus and notifications (6000 and 9500), so a roll never covers the Restart dialog. The
   renderer is `alpha` with a clear colour of 0 and the desk is a `ShadowMaterial`, so with
   shadows off nothing paints but the dice. Cleared about three seconds after the last die
   rests. A tray that takes page space is refused: on a phone the page has none to give. The
   overlay never encodes kept and not kept; the card below does, with its border and label.
   Reduced motion means no toss; a browser without WebGL means no toss; the card is always
   drawn first.
9. **Dice sound is on by default, one mute button in the header**, remembered in
   `localStorage` by the browser component, never by Python. The library loads its sounds only
   inside `initialize()` when `sounds` is true (16792) and indexes them unguarded on every hit
   (17025), so the box is always built with `sounds: true` and muting flips `box.sounds` per
   toss (read at collide time, 17016). The toss is silent while a narration `<audio>` is
   playing. There is no effects volume slider and no fanfare.
10. **Dictation is the browser's `SpeechRecognition`**, no key, no server of ours, no upload to
    us: Chrome streams the audio to Google's recogniser, Safari to Apple's, and the plan says so
    where the button is explained. The microphone button appears only where
    `window.SpeechRecognition || window.webkitSpeechRecognition` exists (Chrome, Edge, Safari;
    not Firefox). Recognition needs a secure context: `localhost` on the computer, `tailscale
    serve` on the phone; on a plain `http://100.x.y.z:port` every press ends in `not-allowed`,
    which the button reports and nothing more. Recognised text is inserted into the draft at the
    caret when the player presses Stop; nothing is ever submitted by speech. Every failure
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
   Browser behaviour (layout, animation, speech events, what a draft does in the box) has no
   Python test and none is faked: the repository has no NiceGUI client fixture and tests never
   start a process. The Python tests cover the seams: what is sent to the browser and the rules
   the page computes.
3. **Look at it.** Every phase that touches `ui/` ends with `uv run aidm` opened in Chromium at
   390px, 768px and 1280px wide (Playwright is installed; a throwaway script in the scratch
   directory, never committed). A layout phase is not done until the three screenshots were read.
4. **Count `src` lines** at the start and end of each phase; write both in `PROGRESS.md`, one
   entry per phase. Phase 1 recreates the file. `src` is 9,698 lines at the start of Phase 1,
   Python and JavaScript together, the vendored library excluded:
   ```bash
   find src \( -name '*.py' -o -name '*.js' \) -not -path '*/lib/*' | xargs cat | wc -l
   ```
5. **If a phase runs half again past its target, stop and say so.** Never pad.
6. **Leave the game playable** at the end of every phase: `uv run aidm`, open a game, take a turn.
7. **One commit per phase.** The full check is green before the commit. Never leave two
   versions of one thing alive at a commit.
8. **Review each phase adversarially against its staged diff before the commit.**
9. **The standing limits hold.** Imports flow `core <- engines <- turn <- app <- ui`; nothing
   below `ui` changes in this plan; no `Any`; every `__init__.py` empty; tests never start a
   process; `Refusal` stays the one message-bearing exception; NiceGUI gap is set with
   `.style("gap: ...")`, never a Tailwind `gap-*` class; `ui.right_drawer` and `ui.footer` are
   built at the page's top level, never under a `with`.
10. **Delete, do not preserve.** When the library lands, `dice_overlay.js` and the polyhedron
    CSS go the same day; no flag chooses between two renderers. An import left without a user
    goes with the function that used it.

---

## Phase 1 — the page fits the screen

Target: about +60 lines in `ui/`. The game page becomes a Quasar layout; the other pages get
the wrapping rules; nothing about play changes.

### Steps

1. **`ui/theme.py` — layout and breakpoints.** Add to `_CSS`, exactly this chain:
   `.q-page-container { height: 100dvh; box-sizing: border-box; display: flex;
   flex-direction: column }`, `.q-page { flex: 1 1 0; min-height: 0 !important; display: flex;
   flex-direction: column }`, `.nicegui-content { flex: 1 1 0; min-height: 0 }`, so a
   `flex-grow` `scroll_area` under it gets the space between header and footer. `.q-footer`
   padding-bottom `env(safe-area-inset-bottom)`; `.game-drawer` background
   `var(--game-surface)`; `@media (max-width: 599.98px)`: `.game-scene-art { display: none }`
   and `.game-scene .text-h6 { font-size: 1rem }`. The `.game-transcript` cap stays 46rem. The
   art box rules of `_ART_BOX` move here under `.game-scene-art`, the row cap of
   `_SCENE_HEIGHT` under `.game-scene`; both constants leave `game.py`.
2. **`ui/game.py` — the layout.** `GamePage.build` builds, in this order: `page_header` (with
   a `menu_book` button, `props("flat color=white round")`, `on_click=lambda:
   self.drawer.toggle()`), then the story column as the page body (`scene_header`, the
   `scroll_area` transcript with `chat` and `live_turn`, `classes("w-full flex-grow
   game-transcript")`), then `self.drawer = ui.right_drawer(value=None, bordered=True)
   .props("width=420").classes("game-drawer")` with the Scene and Journal tabs as now, then
   `ui.footer().classes("game-footer")` holding `decision_panel`, `way_on_panel` and
   `composer` inside a column capped at 46rem and centred. The footer's own max height is
   `50dvh`, `overflow-y: auto`. Delete the splitter. `_scroll` keeps scrolling the
   `scroll_area` to the end (Phase 2 changes when).
3. **`ui/game.py` — the composer on a touch screen.** The `keydown.enter` `js_handler` becomes
   `(e) => { if (e.shiftKey || !matchMedia("(pointer: fine)").matches) return;
   e.preventDefault(); emit(); }`. Send gets `props("round flat size=lg aria-label=Send")`;
   the action button keeps its label. The `ui.input` gets `props('input-style="max-height:
   9rem"')` so a long draft scrolls inside the box.
4. **`ui/widgets.py` — `decision_widget` on touch.** An option with `detail` shows it under
   the label: `ui.button().props("no-caps outline")` with a nested `ui.column` holding the
   label and a `text-xs opacity-70` detail (the label goes inside the column, not in the
   button's own slot, or Quasar draws them side by side). The tooltip goes. The buttons row
   drops `no-wrap` and gets `items-start`; every option button `min-height: 44px`.
5. **Home, Create, Settings wrap.** `ui/app.py`: the header's "Choose your game" label gets
   `classes("gt-xs")`; `_saved_card`'s row wraps and the Resume button gets `classes("col-12
   col-sm-auto")`. `ui/settings.py`: the vertical tabs become one horizontal, scrollable
   `ui.tabs().props("dense outside-arrows mobile-arrows").classes("w-full")` above the panels
   at every width; the `no-wrap` row goes. `ui/create.py`: every `ui.row` of form controls
   drops `no-wrap` and every input gets `classes("w-full")` where it has not got it.
6. **Look at it** (How to work 3): a pending decision, a long draft and an open drawer at
   390px and 1280px; the keyboard open on a phone emulation (Playwright's `iPhone 13` device).
   Fix what the screenshots show before the review.

### Done when

- `uv run aidm` at 390px: header, scene heading without art, transcript, footer with composer
  and Send all visible; no horizontal scroll; the drawer opens as an overlay from the header.
- At 1280px: drawer beside the story, story column at most 46rem, footer under it.
- Return on a coarse pointer inserts a newline; Enter on a fine pointer sends.
- Full check green; `tests/ui/test_game.py` unchanged (nothing in `can_type` or
  `standing_proposal` moved).

## Phase 2 — a safe composer, a still page

Target: about +70 lines in `ui/game.py`, `ui/widgets.py` and `ui/app.py`, +15 in
`tests/ui/test_game.py`.

### Steps

1. **`ui/game.py` — the draft outlives a failed turn.** `GamePage._run(self, playing) ->
   bool`: `True` when `playing()` returned, `False` when it raised `OSError` or `Refusal`, which
   `_run` notifies itself (`ui.notify(f"{type(error).__name__}: {error}", type="negative",
   multi_line=True)`). `submit` no longer clears the box before awaiting; it clears (`box.value =
   ""`, `run_method("updateValue")`) only when `_run` returned `True`. `widgets.working()` had
   that one caller and is deleted with its `asynccontextmanager`, `AsyncGenerator` and
   `Refusal` imports.
2. **`ui/app.py`, `ui/game.py` — the draft outlives a reload.** `_game` becomes `async def`
   and does `await ui.context.client.connected()` before `game_page(...)`: tab storage is
   readable only after the handshake. In `composer`, `self.box.bind_value(app.storage.tab,
   f"draft:{self.session.slug}")`; the bound value is applied before the box's own, so a
   stored draft wins over the empty box.
3. **`ui/game.py` — the transcript follows a reader at the end.** `GamePage.at_end: bool =
   True`, set by `transcript.on_scroll(self.scrolled)` where `scrolled` stores `near_end(
   e.vertical_position, e.vertical_size, e.vertical_container_size)`; `near_end(position,
   size, container, slack=48) -> bool` is a free function in `game.py`: `size - position -
   container <= slack`. `GamePage.own_move: bool = False`, set `True` by `submit` and the
   decision and proposal handlers before `_run`. `poll_turn` computes `follow = self.at_end or
   self.own_move` before `self.refresh()`, clears `own_move`, and passes `follow` to
   `_scroll(follow)`: scroll to the end when true, else show `self.new_activity`, a
   `ui.button("New activity", icon="arrow_downward")` built once in the footer above the
   decision panel, hidden by default, that scrolls to the end and hides on press.
4. **`ui/game.py` — Restart asks.** The header's `restart` button becomes a `ui.button(icon=
   "more_vert")` with a `ui.menu` holding one `ui.menu_item("Restart this game")`. Pressing it
   opens a `ui.dialog` with `f"Restart {title}? {turns} turns are erased."`, "Restart" (calls
   the existing `restart`) and "Keep playing". A game with no history restarts without asking.
5. **`tests/ui/test_game.py`.** One test of `near_end`: at the end, within the slack, a page
   above, and content shorter than its container. Draft-keeping and the dialog are
   browser-verified only (How to work 2).
6. **Look at it**: fail a turn on purpose (kill the spawner's command in Settings) and see the
   text stay; reload and see it return; scroll up mid-turn and see the page hold; press Restart
   and cancel.

### Done when

- A `Refusal` leaves the typed text in the box; a reload of the tab brings it back.
- Reviewing history during a turn is not interrupted; "New activity" appears and works.
- Restart shows the dialog; "Keep playing" changes nothing.
- Full check green; one new test.

## Phase 3 — the dice library

Target: about −120 lines of our own code (`dice_overlay.js` and its CSS go; `dice_tray.js` is
about 90 lines). The vendored library and its assets are not counted.

### Steps

1. **Vendor.** `src/aidm/ui/lib/dice-box-threejs.es.js` and `src/aidm/ui/lib/
   dice-box-threejs.LICENSE`, both byte-for-byte from the npm tarball of 0.0.12
   (`https://registry.npmjs.org/@3d-dice/dice-box-threejs/-/dice-box-threejs-0.0.12.tgz`).
   From the tarball's `public/sounds/` into `src/aidm/ui/dice_assets/sounds/`:
   `dicehit/dicehit_plastic1..15.mp3`, `dicehit/dicehit_coin1..6.mp3`,
   `surfaces/surface_felt1..7.mp3`. No textures. `pyproject.toml` needs no change: hatch ships
   every file under `src/aidm`. `README.md` gets one line under the dependencies naming the
   library and its licence.
2. **`ui/dice.py` — the tray.** `class DiceTray(ui.element, component="dice_tray.js",
   dependencies=["lib/dice-box-threejs.es.js"])`, replacing `DiceOverlay`; `__init__(self,
   look: DiceLook)` sets `self._props["look"] = look.model_dump()` and keeps the
   `game-dice-overlay` class. `toss(self, events)` calls `run_method("toss", thrown(events))`.
   `thrown(events) -> list[dict[str, int]]`: one entry per die, `{"faces": 6, "value": 2}`, in
   event order (`kept` is no longer sent: decision 8; a pool mixes faces, as 24XX's help die
   does, so grouping is the browser's). Constants `DICE_ASSETS = Path(__file__).parent /
   "dice_assets"` and `DICE_ASSETS_ROUTE = "/dice/"`. `ui/app.py` `_register_pages` calls
   `app.add_static_files(DICE_ASSETS_ROUTE, DICE_ASSETS)`. `tests/ui/test_dice.py`: the
   `thrown` test drops `kept`; the `rolled_since` test is unchanged.
3. **`ui/dice_tray.js`.** `import DiceBox from "dice-box-threejs"` (NiceGUI names a dependency
   by its file stem before the first dot). `props: { look: Object }`. Template: `<div></div>`;
   NiceGUI sets the root element's id, so the box is `new DiceBox("#" + this.$el.id, config)`.
   `mounted()`: emit `this.$emit("sound", this.soundOn())` first; return when
   `matchMedia("(prefers-reduced-motion: reduce)")` matches or a scratch canvas gives neither
   `webgl2` nor `webgl`; otherwise build the box with `{assetPath: "/dice/", sounds: true,
   theme_customColorset: {name: "aidm", foreground: look.ink, background: look.body, outline:
   look.glow, texture: "none", material: "none"}, theme_surface: "green-felt", shadows: false,
   strength: 1.5, onRollComplete: () => this.rested()}` ("none" is the library's plastic,
   `bp.none`, 15556; a custom colorset ignores `theme_material`, 16803; `"green-felt"` is the
   surface key whose sounds are `surface_felt*`, 16673), `await box.initialize()`, and only
   then `this.box = box`; a rejection logs once and leaves `this.box` null. `toss(dice)`: no-op
   without a box; else `this.box.sounds = this.soundOn() && !narrating()`, then
   `this.box.roll(notation(dice))`. `notation(dice)`: group by `faces` in first-appearance
   order, `sets = groups.map(g => `${g.length}d${faces}`).join("+")`, `values = groups.flat()
   .map(d => d.value).join(",")`, return `sets + "@" + values` (decision 7). `rested()`: after
   2500ms fade the element (`opacity 0` over 500ms) and `this.box.clearDice()`, then reset
   opacity; a toss during the wait cancels the pending clear. `narrating()`:
   `[...document.querySelectorAll("audio")].some(a => !a.paused)`. `soundOn()`:
   `localStorage.getItem("aidm.dice.sound") !== "off"`. `toggleSound()`: flips and stores it,
   returns the new state. `unmounted()`: `clearDice()` and drop the box.
4. **`ui/game.py` — the mute button.** In the header, `self.sound = ui.button(icon=
   "volume_up", on_click=self.toggle_sound).props("flat color=white round")`; `toggle_sound`
   awaits `self.dice.run_method("toggleSound")` and sets the icon (`volume_up` / `volume_off`);
   `self.dice.on("sound", ...)` sets it from the mount-time emit. `self.dice` is a `DiceTray`.
5. **Delete.** `ui/dice_overlay.js`; from `theme.py` every `.game-dice-*` rule except
   `.game-dice-overlay` (fixed, inset 0, `pointer-events: none`, `z-index: 5000`, `transition:
   opacity .5s`); the `.game-die-live` tumble on the card stays. `IDEAS.md` 17 becomes `[x]`.
6. **Look at it**: a Loner turn with a roll at 390px and 1280px; a Breathless turn (two
   groups) and a 24XX turn with a help die (a mixed pool); the mute button, muted and unmuted
   in one page; the card first, the dice after, the dice gone in about three seconds; reload
   does not re-roll; the Restart dialog over a rolling die.

### Done when

- Every rolled die lands showing the value on the card, in the engine's colours, with sound
  unless muted or narration is playing; the card is drawn before the dice move.
- A hidden roll (a `Fact` with `told=False`) never reaches `toss`: the existing `rolled_since`
  test still says so.
- No `dice_overlay.js`, no polyhedron CSS, no flag between renderers.
- Full check green; `src` line count down.

## Phase 4 — dictation

Target: about +90 lines: `ui/dictation.js` (about 60), `ui/dictation.py` (6), `ui/game.py`
(about 25). Precondition for the phone: the game is opened over `tailscale serve` (HTTPS);
on the computer, `localhost` is already a secure context.

### Steps

1. **`ui/dictation.js`.** A component whose template is one `q-btn` (round, flat, icon `mic`,
   `aria-label="Dictate"`) that is `hidden` when neither `SpeechRecognition` nor
   `webkitSpeechRecognition` exists. Press: `start()` a recogniser with `continuous: true,
   interimResults: true, lang: navigator.language`; the icon becomes `stop`, red, with a pulsing
   ring (`.game-dictating` CSS); interim text is shown in a small caption under the button
   (`this.interim`), never written to the draft. Press again, or the recogniser's own `end`,
   finalises: `this.$emit("dictated", {text, caret})` once, with the joined final results and
   the caret read from the composer's textarea (`document.getElementById(this.target)
   .querySelector("textarea").selectionStart`) at press time, and the caption clears. `onerror`
   emits `this.$emit("failed", event.error)` and resets; a second press while finalising is
   ignored. A 60-second `setTimeout` stops a forgotten recording. `unmounted()` aborts a running
   recogniser. `props: { target: String }`.
2. **`ui/dictation.py`, `ui/game.py` — the composer takes it.** `class Dictation(ui.element,
   component="dictation.js")` with `__init__(self, target: ui.element)` setting
   `self._props["target"] = f"c{target.id}"`; nothing else in the file. The composer row
   places `Dictation(self.box)` before Send. `on("dictated", self.dictated)`: `self.box.value =
   insert_at_caret(self.box.value or "", args["text"], args["caret"])`, then
   `run_method("updateValue")`. `insert_at_caret(draft: str, text: str, caret: int) -> str`: a
   free function that inserts with one space on each side where the neighbours are not
   whitespace. `on("failed", ...)`: one `ui.notify` mapping `not-allowed` to "The browser
   refused the microphone (a secure context is needed).", `audio-capture` to "No microphone.",
   `no-speech` to "Nothing was heard.", anything else to the raw error, `type="warning"`. The
   box is not disabled while recording: `_set_composer` would re-enable it on the next poll.
3. **`tests/ui/test_game.py`.** One test of `insert_at_caret`: mid-word, at the end, in an
   empty draft.
4. **Look at it**: in Chromium with a fake media stream (`--use-fake-ui-for-media-stream
   --use-fake-device-for-media-stream`): the button appears, records, the interim caption
   shows, Stop inserts, Send is the player's. In Firefox: no button, typing works. On the phone
   over `tailscale serve`: the permission prompt appears once.

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
- **HTTPS in the app, server transcription, provider keys for speech-to-text**: `tailscale
  serve` carries the phone; the browser carries recognition; nothing on the server.
- **Sheets for Scene and Journal, a resizable context pane**: Quasar's drawer does both jobs
  with its own breakpoint; a resizable pane is a splitter again.
- **A faked NiceGUI client in tests**: tests never start a process; browser behaviour is
  looked at (How to work 3), not stubbed.
- **Reading size, focus mode, journal search, a resume summary, onboarding**: after these
  four phases, if still wanted, each is one small plan of its own.
