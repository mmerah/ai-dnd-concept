# Findings — full UI sweep with scripted roles, 2026-09-07

Method: the real app served with `qa/agents.py` in place of the three roles, driven in headless
Chromium at 1280×800, 390×664 (phone, touch) and 768×1024 (tablet, touch), plus the MCP path
with the master calling tools over HTTP. Every scenario in `qa/run_all.sh` passes its checks;
the items below are what the sweep surfaced. Baseline before the sweep: 547 tests, ruff and
basedpyright clean.

What works, end to end: home and launcher pairing; the opening; turns with rolls and 3D dice
whose faces match the cards; reveal, tags, items, health, luck; text decisions (Loner
conflict), option decisions (Breathless loot, Tunnel Goons level-up chain, 24XX succession);
the way on, crossings, complications, an unwritten way; more map and walking into it; hire on
three engines; interjections with an accepted proposal; restart with its dialog; death and the
closed composer; a crash or refusal keeping the draft; a bad narrator answer re-prompted once;
Enter vs Shift+Enter, Enter as newline on touch; the drawer, journal, sound toggle, New
activity from another tab; reload mid-turn showing the live turn; the draft surviving a reload;
two games at once refused; settings save, validation, secrets, busy and stale refusals;
character creation for all four engines with dependent picks; scenario creation from a premise
and from an uploaded document; saves listed with Resume and Continue; the MCP tool list empty
between turns and the engine's tools inside one.

## Do now

1. **A bad game URL, or a save that no longer matches its scenario, is a blank page.**
   `GET /game/nope/kael`, `/game/whispering-vault/nobody`, `/game/Bad Id/kael`, and any
   `Refusal` from `Runtime.session` (a save whose scenario was edited, "save is X, selected is
   Y") render an empty dark page with the traceback only in the server log. Cause: `_game` in
   `src/aidm/ui/app.py:171` awaits `client.connected()` before `runtime.session(...)`, so the
   HTML has already been delivered when the `Refusal` raises, and NiceGUI has no page exception
   handler to fall back on (`nicegui/page.py:142` re-raises). Fix: catch `Refusal` in the page
   and render the message with a way home, or resolve the session before the await.
   Evidence: `qa/shots/home/002-bad-route.png`, server log `create_500_error_page ... raise e`.

2. **The narrator is asked for exact speaker ids it is never shown.** `prompts/narrator.md`
   says "use the speaker's exact id", but WHO IS HERE (`turn/context.py:_picture`) lists names
   and briefs only. A model must guess `mara` from "Mara"; "Brother Tomas" → `tomas` fails, the
   one retry carries the id in the refusal, and a second miss raises and kills the whole turn
   (`_narrate(fatal=True)`). Dialogue from anyone here is a coin toss. Fix: print the id beside
   each subject in WHO IS HERE (the interjection prompt already does for its member).
   Evidence: `tests/core/fixtures/prompts/loner3e/narrator.txt` lines 32-34; `s_loner.py` step 17.

3. **After a reload mid-turn, the words already sent stay in the composer.** The draft is
   bound to `app.storage.tab` and only the page that submitted clears it (`submit` →
   `box.value = ""`). Reload while the roles work: the live turn shows, then when it lands the
   composer still holds the sent text, enabled, inviting a second send of the same action.
   Fix: clear the tab draft when the turn is committed (e.g. in `poll_turn` when
   `exchanges` grows and the draft equals the last prompt), or clear it on submit and restore
   it only on failure. Evidence: `qa/shots/loner/016-reload-settled.png`,
   `qa/shots/probe/004-after-reload-turn.png`.

4. **A failed hire (or any failed write) tells the player "The way on could not be
   written. You are still where you were."** `GameService._generate` files the one `UNWRITTEN`
   fact for every operation. After `!hire` with a failed worldsmith the card names no hire and
   talks about a way on. Fix: word the card from `request.operation` (hire, complication,
   departure, more map). Evidence: `qa/shots/probe/003-hire-failed.png`.

5. **Writing a scenario with no table set spends two worldsmith runs before refusing.**
   The page lets the multi-select go empty; `engine.author` writes, the playable check fails
   with "needs at least one table set", the worldsmith is re-prompted with that, fails again,
   and only then the toast appears. At real speed that is ten minutes. Fix: refuse in
   `ScenarioForm.write` before spawning. Evidence: `qa/shots/probe/006-no-packs.png`, log shows
   2 worldsmith spawns.

6. **The reader's own turn often does not follow to the end; "New activity" shows instead.**
   Reproduced on every engine at 1280 px on the first turn after the opening (`s_visual.py`:
   `scrollTop` stays 0 with 656 px of content in a 417 px box) and once on a phone. Cause, in
   `ui/game.py:poll_turn`: `own_move` is consumed by the first observed change of the turn
   (the phase flip to "master"), when the content still fits; when the roll and the narration
   land the transcript overflows, Quasar fires its resize-scroll event with position 0, so
   `at_end` reads false, and the later refresh runs `_scroll(False)`. Fix: keep `own_move`
   until the turn closes (`_run`'s `finally` already clears it), or treat a change while
   `session.busy` as the reader's own. Evidence: `qa/shots/visual/003-breathless-game.png`,
   `004-24xx-game.png`, `qa/shots/mobile/003-game-turn.png`.

## Next

7. **Game over leaves the composer asking "What do you do?"** After death the box is disabled
   but keeps the inviting placeholder; the only hint is a small red "You died." beside it, and
   nothing points at Restart in the overflow menu. `_placeholder` in `ui/game.py` never reads
   `player.over`. Evidence: `qa/shots/loner/021-dead.png`, `qa/shots/breathless/*-dead.png`.

8. **Tab out of a typed creation step loses the focus.** Every free-text step re-renders the
   whole form on blur (`create.py:67`), so Tab from "Item 1" lands nowhere (`activeElement` is
   the body) and the player has to click "Item 2". The typed value survives. Evidence:
   `s_probe.py` step 5.



9. **Unlocking a door the player has not walked is silent, and the Ways-out panel cannot show
    a locked door.** `RoomWorld.unlock_way` tells the fact only when the way is already known;
    ways become known only by moving through them, so a locked way out of the current room is
    invisible to the player until the master unlocks and moves them. No card, no panel row.
    Evidence: `s_goons.py` step 7 ("unlock card missing" on the first run).

10. **The journal renders the narrator's prose as markdown; the chat shows it verbatim.**
    `**bold**` is bold in the journal and literal in the chat. HTML and `<script>` are escaped
    in both. Harmless today, inconsistent once a model writes an asterisk.
    Evidence: `qa/shots/probe/001-journal-markdown.png`.

11. **`job finish` refuses the whole call with "the skill is already at d12"** without naming
    the operator or the skill, and the shipped Kael has Stealth at d12. Minor; the master gets
    a retry, but the message should name whose skill. Evidence: `s_24xx.py` first run.

12. **Settings validation shows raw pydantic text** including the `errors.pydantic.dev` URL
    (`qa/shots/settings/004-invalid-timeout.png`). A one-line "roles.master.timeout must be
    greater than 0" would do.

## The styling branch (`codex/engine-visual-identities`, merged here)

Reviewed by reading the diff and re-running `visual`, `loner` and `mobile` on the merge:
548 tests, ruff and basedpyright clean; every scenario still passes. Each engine gets its own
palette, radius and heading face on the game page, the launcher follows the picked scenario,
the creation pages follow the picked rules, settings stay neutral, and the phone layout holds
(`qa/shots/visual/`). The old blue footer is gone. Two things to fix:

- **Primary buttons are still Quasar blue under every theme.** `theme.py` sets `--q-primary:
  var(--game-accent)` on `body`, but NiceGUI writes its default `--q-primary: #5898d4` as an
  inline style on `body`, which wins. So Start/Continue game, Resume, Save, Restart, New
  activity, the outline buttons and the drawer's close icon keep the stock blue next to a
  purple, orange, teal or ice accent (`qa/shots/visual/001-loner-game.png`, `005-home.png`,
  `007-settings.png`). Fix: call `ui.colors(primary=<accent>)` from `set_engine` (per client),
  and drop the `--q-primary` line, or set the variable on `.q-layout` and scope the button
  rules under it. The same applies to `--q-negative`/`--q-positive`: toasts keep Quasar's red
  and green.
- **Notifications now sit at the very bottom edge, over the composer** and their text was
  clipped by the viewport in two screenshots (`qa/shots/visual/012-goons-crash-toast.png`);
  measured at rest they end 10 px above the bottom, so this may be the slide-in caught late.
  Worth a look by eye; a `bottom` offset on `.q-notifications` or `position="top"` on the
  game page's `ui.notify` calls would settle it either way.

Smaller notes: `.q-btn--flat.text-white` turns the header icons muted grey on every theme;
the `.q-message-text { color: <surface> }` trick colours the bubble tail and relies on
`.q-message-text-content` for the text, so any future bubble content outside that node
would inherit the invisible colour.

## Noted, no action asked

- Notifications stack bottom-centre over the composer, covering the draft they say was kept
  (`qa/shots/loner/008-narrator-failed.png`).
- The 3D dice overlay flies over the drawer and header text; pointer-events are off, so
  nothing is blocked (`qa/shots/loner/005-conflict-pending.png`).
- With illustration on, authored icons render inside `q-img`, which keeps a hidden spinner in
  the DOM; only matters to anyone automating the page.
- A settings save rebuilds the spawner from the new settings: correct, but any test double
  handed to `Runtime` is dropped at that point (the harness subclasses `reload_settings`).
- `Runtime.reload_settings` re-reads `.env` from the process working directory, which is also
  where the settings page writes it; starting the app from another directory splits the two.
