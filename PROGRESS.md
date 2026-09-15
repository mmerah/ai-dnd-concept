# PROGRESS

Newest first. One entry per phase of `PLAN.md`.

## Phase 3 — `ui`

Findings 13–17 plus the one `IDEAS.md` line, in `src/aidm/ui` and the three modules the UI reads
for them (`config.py`, `app/launch.py`, `app/runtime.py`). No golden moved. Two implementers
(sonnet) in parallel on disjoint files: A (steps 1, 4, 6 — the bind address and the launcher) and
B (steps 2, 3, 5 — the game page, the settings page and the in-flight gate). Two adversarial
reviews, both opus — `codex` is not installed in this container, and the maintainer asked for opus
reviewers only.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,295 | 10,345 | +50 |
| `tests` | 11,939 | 12,068 | +129 |

`uv run pytest` 801 → 806 passing, none deleted. `uv run ruff check`, `uv run ruff format --check`
and `uv run basedpyright` (0 errors) all clean. `uv run aidm` serves `/` and `/settings` (HTTP 200)
and now reports `NiceGUI ready to go on http://127.0.0.1:8080`; no live turn — this container runs
no AI role — so the turn path rests on the suite.

`src` grew because four of the five findings are a guard the code did not have. The one place the
phase removes code is step 5, which deleted `_IN_FLIGHT_PREFIX` and two `.format()` calls.

### What landed

- **The app binds loopback.** `server_host` defaults to `127.0.0.1` and reaches `ui.run`. `/mcp`'s
  `allowed_hosts` is unchanged and was never the guard: a Host header is set freely by any
  non-browser client, which is how a network peer listed the master's tools and rolled dice into a
  live turn.
- **A non-`Refusal` role failure reaches the player and still propagates.** A fixed string, never
  `str(exception)`: a `Refusal` is the only exception written for the player to read, and any other
  may carry hidden canon or a filesystem path. The re-raise keeps the bug unhandled and logged.
- **A second save on the Settings page lands.** The snapshot the boxes are compared against is
  re-read after every write.
- **A save that exists and will not restore hides the Start button** instead of leading to the
  Home-only refusal page, and nothing is deleted or migrated (`README.md:56`).
- **The in-flight refusal names no slug.** `Runtime.admit` has both the caller and the holder, so
  it raises the own-turn message or the other-game one from there; `ui/game.py` compares against
  the constants instead of re-deriving them from a slug.

### Decisions made off-plan

- **`server_host` is `Literal["127.0.0.1", "0.0.0.0"]`, not PLAN's `str`.** `run_cli` hardcodes
  `url = f"http://localhost:{port}/mcp/"` (`app/spawn.py:166`), so any bind address other than
  loopback or all-interfaces leaves `localhost` unbound and every spawned master's tool calls
  unreachable — and `_widget` renders a plain `str` as a free text box that accepts anything. The
  `Literal` keeps PLAN's "set it to `0.0.0.0` to expose it" escape, is rejected at the boundary
  rather than at the first turn, and renders as a select (`ui/settings.py:129-131`).
- **Scenario drift is a fourth unresumable path.** PLAN step 4 names three, all inside
  `_save_option`. `Runtime._resumed` (`app/runtime.py:419-420`) also refuses on
  `state.scenario.drift(scenario.meta)`, which `_save_option` never compared — so hand-editing a
  scenario's title or premise recreated exactly the dead end the step exists to close, and it is
  the *readable* one: of PLAN's three, only the `Refusal` path can produce a stem equal to a
  rendered `LaunchTarget.slug`. `Library.read_scenarios` calls `read_scenario`, the same method
  `Runtime._open` uses, so the comparison is exact and cannot list a false positive. One reviewer
  found it.
- **`_opened` cancels its timer in a `finally`.** `build` arms a repeating `ui.timer(0.1, ...)`
  and NiceGUI swallows a raising callback and fires again, so the re-raise step 2 adds jumped over
  `opener.cancel()` — one non-`Refusal` failure in `session.open()` toasted forever at ten a
  second. The storm predates this phase; only the toast is new. Both reviewers found it
  independently, and it was the top finding in both.
- **The settings write and re-read moved inside the existing `try`.** `read_settings()` is a fresh
  boundary read of a file the in-memory `merged` check never covered, so a `.env` hand-edited to
  something invalid raised past the player *after* the write landed, with no confirmation and no
  `refusal_text` line.
- **One `_alert(message)` for the player-facing negative toast.** The same
  `type="negative", multi_line=True, position="top"` spelling reached three call sites with step
  2's; three clears CLAUDE.md's "two things need it" bar.
- **The carried slugs are a marker model, `UnresumableSave`.** PLAN says "carry on the catalog, as
  a new field, the slugs"; the shape was the orchestrator's.

### Refused proposals (`PLAN.md` "How to work" §7)

Both were put to the maintainer and refused; recorded here so neither is re-proposed.

- **Pruning the save log.** Measured 5 KB → 88 KB over 100 turns with short narration, the whole
  file rewritten each turn. The log *is* the journal the player reads, so pruning removes a
  feature, and 88 KB is negligible in absolute terms.
- **Paging the transcript in the UI** — the fix for the `IDEAS.md` line step 6 adds. ~30–50 lines
  of new UI for a cost invisible below ~150 turns; CLAUDE.md says "do not build for future needs".
  Recorded as idea 21 instead.

### Refuted review findings

- **"Name the save file, not the slug, in the launcher's line."** Refused. `LauncherCatalog` does
  not hold the store — only `read` is handed one — so printing a path means carrying a new field
  for one label, and `saves_dir` is configurable, so the path is not `saves/<slug>.json` in
  general. The line states a fact and asks the player to do nothing; the warning the launcher
  already logs names the file for whoever can act on it.
- **"Drop `UnresumableSave`; keep the slug in hand in one loop over `store.slugs()`."** Refused.
  Without a distinct type `read` cannot tell "the file vanished between `slugs()` and `read`",
  which must be ignored, from "on disk and unopenable", which must be carried — and that
  distinction is exactly what PLAN step 4 spends a paragraph on. A `str` return or a bool flag
  spells the same thing with weaker types.
- **"Shorten the settings toast to 'Saved to .env.'; the rest repeats `page_intro`."** Refused.
  PLAN writes that sentence, and the intro is read once at the top of a long scrolling page while
  the toast is read at the moment it matters.

### Known and accepted

- Two of the three unresumable paths PLAN names can never match a rendered target: "filed under
  another name" carries a stem that by construction differs from every `LaunchTarget.slug`, and
  "scenario or character gone" means the pair is no longer offered. They are carried because PLAN
  says to; one line on the field says which entries are ever read, so nobody deletes them as dead.
- `server_host` binds the game page and `/mcp` together. There is no way to publish one without
  the other, and PLAN did not ask for one.
- A save whose scenario drifted is hidden from the launcher, not repaired. Reverting the edit
  brings it back; nothing on disk is touched either way.

### Settled after the phase

The three calls that rest on the orchestrator's reading rather than on PLAN's letter — the
`server_host` `Literal`, scenario drift as a fourth unresumable path, and keeping `UnresumableSave`
against a reviewer's cut — were put to the maintainer and confirmed. The clean reading wins over
the plan's literal one, as in phase 1.

The phase also broke one thing outside the four commands, found and fixed after the reviews:
`qa/s_settings.py` pins the settings page's tab list exactly, and `server_host` adds a ninth tab
between "source max chars" and "server port". `qa/server.py` now passes `host=settings.server_host`
to its own `ui.run` as well, so the QA server binds what the app binds; the suite drives
`http://localhost:8123`, which loopback still serves. Nothing in `qa/` is covered by the four
commands beyond `basedpyright`, so a string the UI owns can only be caught by reading it.

## Phase 2 — `core` and `app`

Findings 9–12, in `src/aidm/core`, `src/aidm/config.py` and `src/aidm/app`. No golden moved. One
implementer (sonnet) on the whole phase; two adversarial reviews, both opus — `codex` is not
installed in this container, and the maintainer asked for opus reviewers only.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,290 | 10,295 | +5 |
| `tests` | 11,831 | 11,939 | +108 |

`uv run pytest` 796 → 801 passing. `uv run ruff check`, `uv run ruff format --check` and
`uv run basedpyright` (0 errors) all clean. `uv run aidm` serves `/` and `/settings` (HTTP 200) with
a clean log; no live turn — this container runs no AI role — so the turn path rests on the suite.

### What landed

- **A stand-alone all-caps heading never reaches `SOURCE MATERIAL`.** One clause on the filter
  `_passages` already runs (`core/source.py:50`). `MIN_PASSAGE` already dropped the short ones; this
  covers `WHAT THE PLAYER HAS READ:` and its kin at 24 characters or more.
- **An IDN base url is refused at the config boundary.** `AnyHttpUrl` punycodes and accepts it,
  `httpx.URL` does not, and `httpx.InvalidURL` is not an `HTTPError`, so it used to escape every
  `except HTTPError` in `app/builtin.py`, `app/media.py`, `app/speech.py` and `ui/game.py` as a 500.
  Both checks stay: they reject different urls.
- **A disk failure is no longer reported as a failed worldsmith.** `_grow`'s `try` now holds
  `advance` and `_narrated` only; the three `save(...)` calls are one `self.save(landed)` after the
  `try/finally`. A `Refusal` from the write propagates to the player instead of discarding the scene
  the worldsmith just wrote and attempting a second save that fails identically.
- **A scenario-drift refusal names the fields that differ.** `ScenarioMeta.drift`
  (`core/model.py:36`) is the comparison; `_resumed` names the joined field names and no values — a
  `premise` is long and a matching `title` must not appear. The guard stays strict: `scope` is read
  by the master and the worldsmith every turn.

### Decisions made off-plan

- **The config check is `httpx.URL(base_url)`, without PLAN's `/chat/completions` suffix.** Both
  reviewers raised it independently. The suffix is inert — verified: `httpx.URL` raises
  `Invalid IDNA hostname` on `http://☃.example`, `…/v1` and `…/v1/chat/completions` alike, because
  the host is what fails — so the suffix bought only a third copy of a route literal `config.py` does
  not own (`app/builtin.py:116`, `app/media.py:127`), and the wrong one for `app/speech.py:60`, which
  posts to `/audio/speech`. PLAN's stated purpose, "the real request url the providers build", is
  served by the part of it that can actually be rejected.
- **`ScenarioMeta.drift` is a method on the value model, not a diff built in `_resumed`.** It reads
  its own fields and another of its own kind, and `core` sits below `app`.
- **`CAPS_HEADING` is unanchored with `fullmatch`, not `^…$` with `match`.** Identical on text
  `_passages` has already collapsed to a single whitespace-normalised line; two fewer metacharacters
  and no escaped hyphen.
- **The IDN proof matches the refusal, not the field name.** `match="base_url"` would pass on any
  validation failure; `match="ascii host name"` pins the check the step adds.

### Refuted review findings

None. Both reviews returned "phase complete: yes", and every finding and cut was taken.

### The orchestrator's own error, recorded so it is not re-derived

The brief spelled `_grow`'s hoist as moving `engine.close`/`engine.land` out of the `try` as well as
`self.save`. PLAN says to hoist the three `save(...)` calls, and the difference is real: `close` ends
in `land` → `draft.commit()` → `parse`, which raises `Refusal("the state this leaves is invalid: …")`
(`core/model.py:126-131`), and `advance` never lands the draft itself. That refusal used to be caught
and answered with the request's `unwritten` fact; under the briefed shape it escaped to the player
with `generation` still set, so the next turn would re-run the same request. One reviewer found it by
reading — the suite could not, because nothing covered a write that lands invalid. The fix binds
`landed` inside each branch and hoists only `self.save(landed)`, and the phase adds the missing test.

### Known and accepted

- `CAPS_HEADING` also drops a genuine 24-character-plus passage written entirely in capitals and
  ending in a colon. A document that holds one is a document whose headings are indistinguishable
  from its prose; the prompt-section injection it prevents is the worse failure.
- The drift refusal names fields, not values, so a launcher comparing two saves by hand still has to
  open them. Values are unbounded — a `premise` is a paragraph.

## Phase 1 — `engines`

Findings 1–8, all inside `src/aidm/engines`. The phase's one golden regeneration ran at the end
and moved exactly the two fixtures the plan named. Three implementers: parts A (steps 1–3, rooms
and tunnelgoons) and B (steps 4–7, breathless, twentyfourxx, loner3e) in parallel on disjoint
files, then D (step 8 and the regeneration) on the finished tree.

### Counts

| count | before | after | net |
| --- | --- | --- | --- |
| `src` | 10,239 | 10,290 | +51 |
| `tests` | 11,559 | 11,831 | +272 |

`uv run pytest` 782 → 796 passing: 14 tests added, one deleted
(`a_place_walked_through_without_a_word_is_no_chapter`, which pinned nothing once `move` stopped
opening a chapter). `uv run ruff check`, `uv run ruff format --check` and `uv run basedpyright`
(0 errors) all clean. `uv run aidm` serves `/` and `/settings` (HTTP 200); no live turn — this
container runs no AI role — so the turn path rests on the suite.

`src` grew where the plan said it would shrink. Step 1 is the predicted net removal (`map_model`
gone from three places, one model added), but steps 2, 6 and 7 each add a refusal the engine did
not have, and those are the findings. The one place the phase could have been smaller is refuted
below.

### The three facts step 1 asks to record, so nobody re-derives them

- **The anchor place's title is required, not a caveat.** `attach` does not move the player
  (`rooms/world.py:405-415`), so `narrator_view()` titles the new chapter from the place the
  player still stands in. That is correct: `check_extension` forces the region's own `start` place
  to be hidden (`rooms/worldsmith.py` → `_map_unmet(start_known=False)`), so titling from the
  region would leak a hidden name into the narrator's "WHAT THE PLAYER HAS READ" header.
- **The empty-trailing-chapter pop** (`seam.py:277-278`) is right at the new call site: it is only
  reachable when MORE_MAP fires before any exchange, and the recap is then dropped with the empty
  chapter, which is what should happen.
- **Nothing persisted is invalidated.** `TunnelGoonsScenario = Scenario[MapDraft[Npc]]`
  (`tunnelgoons/world.py`) is what lands on disk; the region draft is consumed by `attach` and
  never stored, and `Game.generation` is `exclude=True` (`core/model.py:105`).

### Decisions made off-plan

- **The loner3e screen reads the whole cast, not `self.hidden()`.** PLAN step 7 spells the screen
  against "`self.hidden()`'s entities". `SceneWorld.hidden()` (`scenes/world.py:82-83`) is the
  unknown entities in the *current run's* `here`, so a cast member the player has never met who is
  not in this scene passed it — and the leak step 7 closes is the **stored sheet row**, which
  outlives the scene that wrote it. `check_unnamed` screens
  `[entry for entry in self.cast.values() if not entry.known]` instead. Both reviewers' severity
  ranking put this first; CLAUDE.md's "hidden facts have no path into" the narrator is the rule it
  serves, and the refusal text already promised "what the player has not met". One test added for
  the case `self.hidden()` missed. Confirmed by the maintainer after the phase: the clean reading
  wins over the plan's literal one.
- **The region model is named `RegionDraft`.** PLAN says "add a `MapDraft` subclass" without
  naming it. `RegionDraft[N](MapDraft[N])` mirrors `NextDraft(SceneDraft)` and matches the word
  PLAN itself uses throughout step 1 ("the region draft is consumed by `attach`").
- **The npc bar lives in `_map_unmet`, not in both room checks.** PLAN says "Call it from
  `scene_unmet` and from both room checks… Each caller keeps its own sentence." Written literally
  that pasted one identical clause and one identical sentence into `check_map` and
  `check_extension`, and forced both from a single expression into four lines. Both reviewers
  raised it independently. The clause moved into `_map_unmet`, which both checks already call;
  `scene_unmet` still keeps its own sentence, which is what the instruction was for. The
  extension-only item bar became `_planted_unmet` beside it, so both checks stay one expression.
- **The 24XX harmless-gear sentence is `_harmless(item)`.** Steps 5 and 6 leave the same
  player-facing string in `check_defenses` and in `_break`, in one file, where the whole point is
  that the pre-roll and post-roll refusals say the same thing. One helper beside the existing
  `_broken(item)`.
- **`CROSSING`'s format key is `{asked}`, not `{pursuit}`.** Step 8 removes the master's
  `pursuit` from that path; leaving the key named after the field that no longer feeds it made the
  name say the opposite of the value. No prompt wording changed, so no fixture moved.
- **`docs/TUNNEL-GOONS.md` lost "adventure" in two places, not one.** PLAN names only deviation 1's
  "once per adventure" → "once per game". That alone left the sentence contradicting itself ("an
  end-of-adventure step the master calls once per game… an adventure is the closest thing this app
  has to a session"), and the tool list at `:52` still read "once, at the adventure's end". The
  code has no notion of an adventure — which is why the refusal string dropped it — so the doc no
  longer asserts one.
- **One test outside both parts' scope was reworded.** `tests/turn/test_turn.py:301` set a drive
  goal of "Get the vault map out safely", which literally names the shipped scenario's hidden
  entity `the vault map`; the new screen correctly refuses it, so the drive never landed. Same
  rewording part B made in `tests/loner3e/test_world.py`. The screen catching a leak in the test
  data is the fix working.

- **The answer model is bound once per method, in both families.** A reviewer asked for
  `model = MapDraft[self.member]` in `rooms/engine.py` instead of spelling it twice per method.
  Refusing it on PLAN's "the scenes family spells it inline" would have kept a duplication in
  both families rather than removing it from either, so the alias landed in `RoomEngine.author`,
  `RoomEngine.write_next` and `SceneEngine.author` together. The families still match, each
  method names its model once, and `author` and `write_next` lose their wrapped call sites: −9
  `src`. `SceneEngine.render_next` and `SceneEngine.write_next` keep `NextDraft[self.member]`
  spelled once each — that is one use per method, not a duplication.

### Refuted review findings

- **"Read `draft.log[-1].exchanges` instead of `draft.exchanges()` in `depart`."** Refused. PLAN
  step 8 names `Game.exchanges()` as "the flat read" for exactly this, and the flat read is the
  correct one: when the current chapter is empty but earlier chapters are not — reachable, since
  `install` opens a fresh chapter — `log[-1].exchanges` yields `""` and silently drops the
  player's words. The saving is one tuple build per scene change, not per turn.

### Known and accepted

- A rooms player who never triggers MORE_MAP has one chapter for the whole game, capped at
  `exchanges[-20:]`. Scene engines have the same gap inside one long scene.
- The worldsmith can no longer author an already-dead or zero-HP NPC entity; a corpse belongs in
  the place's `description`. The shipped `buried-keep` map has 3 npcs, all alive, all HP > 0, none
  sheeted, so nothing migrates.
- `CROSSING` renders `They asked for this: ""` when `depart` runs on a game with no exchange at
  all. Unreachable in play — a departure always follows a player turn — and the guard exists
  because `tests/core/test_golden_turn.py:56` calls `advance` on a freshly begun game.
- Broadening the loner3e screen to the whole cast can refuse master text that happens to contain
  an unmet entity's name innocently. A refusal is a message the master reads and rewrites; the
  sheet row it would otherwise write is permanent.
