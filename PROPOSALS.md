# MVP0 code quality proposals

Scope: `src/aidm` only. Branch `claude/code-quality-proposals-1fkr4f`, base commit `076c820`.
Baseline on this commit: 595 tests pass, `ruff check` and `ruff format --check` clean,
`basedpyright` clean on `src` (the errors it prints without `--all-groups` are all in `qa/`,
which needs the playwright group installed).

Every finding below was verified against the current code. The earlier review file
(`MVP0-code-quality-review.md`) is folded in and deleted: F1 to F5, D1 to D5 and Q1 to Q4 keep
their ids. N1 to N12 are new. Section 5 lists things a reviewer may flag that should stay as
they are, with the reason, so those can be closed without discussion.

Sizes: S is under an hour of agent work, M is half a day, L is a day or more.

Preference applied throughout: a proposal that makes `src` smaller or removes a concept wins
over one that adds machinery. The "src" column says what each does to the code: `-` fewer
lines or concepts, `=` moved or renamed only, `+` more. Where the first review's choice adds
machinery, the simpler option is now recommended and the original is kept as an option.

## 1. Decision table

Fill the last column. "Accept" means do it as written. Where a proposal has options, write the
option letter.

| ID | Proposal | Kind | Size | src | Recommendation | Your decision |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | `Claims.hold` context manager replaces three try/finally blocks | bug | S | - | Accept | Accepted |
| F2 | One `close()` replaces `stop()` and `settled()`; errors get logged | bug | M | = | Accept | Accepted |
| F3 | One `publish` helper replaces three staging implementations | bug | S | - | Accept | Accepted |
| F4 | Expected file errors handled at the read and write helpers only | bug | S | = | Accept | Accepted |
| F5 | One `admit` in `Runtime` replaces three refusal methods and the UI checks | bug | M | - | Accept, option A | Accepted, A |
| D1 | Strict scalar validation | decided | M | = | Implement as written | Decided |
| D2 | Commit dice with the turn; separate cosmetic RNG | decided | S | = | Implement as written | Decided |
| D3 | Precise types through the chain | decided | L | + | Re-decide: option B (family `W` only) | |
| D4 | One explicit pack selection policy | decided | L | - | Implement, option B (no fingerprints) | |
| D5 | Shallow freezing: document it and pin it with a test | decided | S | = | Implement as written | Decided |
| Q1 | Typed CLI events replace the recursive text search | quality | M | - | Accept | Refused |
| Q2 | Upload: one directory per form, deleted on success only | quality | S | - | Accept, option B | Accepted, B |
| Q3 | Helpers that mutate become methods | quality | M | = | Accept, widened list | |
| Q4 | Delete compressed expressions and duplicate closures | quality | S | - | Accept, option B | Accepted, B |
| N1 | Constructor style | consistency | S | = | Option B (leave, write the rule) | |
| N2 | `Runtime` takes a spawner factory defaulting to `RoleRunner` | consistency | S | - | Accept, option C | Accepted, C |
| N3 | Take PDF extraction off the event loop | pattern | S | = | Accept, option A | |
| N4 | Share `rows()` on `Sheeted`; keep the other duplicates | consistency | S | - | Accept, option A | Accepted, A |
| N5 | One retry constant, one timeout idiom | consistency | S | - | Accept | Accepted |
| N6 | Drop the `world_of` narrowing overrides | consistency | S | - | Fold into D3 option B | |
| N7 | `Rolled` carries its dice once | naming | S | - | Accept, option A | Accepted, A |
| N8 | Split the `Pairs` alias into `Sections` and `Rows` | naming | S | = | Accept | |
| N9 | `Slug` stays `Annotated[str]`; say so in CLAUDE.md | naming | S | = | Option A (leave) | |
| N10 | `Hiring` packaging | consistency | S | = | Option B (leave) | |
| N11 | Comment and naming sweep against CLAUDE.md rules | style | S | = | Accept | |
| N12 | Write the constructor and return-shape rules into CLAUDE.md | docs | S | = | Accept | |
| N13 | Move the 350-line CSS string out of `ui/theme.py` into `theme.css` | simplify | S | - | Accept | Accepted |
| N14 | Delete thin pass-through methods | simplify | S | - | Accept | Accepted |

## 2. Fixes: wrong behaviour hiding in a pattern

### F1. Release the image claim on every exit

Now: `Illustrator.illustrate` (`app/media.py:54-64`) claims the scene key, then awaits
`_drawn_icon(player)` before entering the `try/finally` that releases it. A cancellation or an
error during that await leaves the claim held for the life of the session, so the scene is never
drawn again.

Change to: make `Claims` a context manager and use it at both claim sites.

```python
@contextmanager
def hold(self, key: str) -> Iterator[bool]:
    """Yields whether this caller won the claim; releases only what it won."""
    won = self.claim(key)
    try:
        yield won
    finally:
        if won:
            self.release(key)
```

`illustrate` becomes `with self.claims.hold(key) as drawing: await self._drawn_icon(player);
if drawing: await self._draw(...)`. `_drawn_icon` and `Reader.read` use the same shape. The
claim leak then cannot be written again.

Impact: control flow only. Retried art works after a failed or cancelled attempt. No save change.

Done when: a test cancels `illustrate` at the icon await and a second call draws the scene. The
existing duplicate-generation test stays.

### F2. Observe and drain background tasks

Now (`app/runtime.py:280-288`): `_retain` adds a done callback that only discards the task.
A task that raises is dropped from `_background` before `settled()` can gather it, so the error
surfaces only as asyncio's "exception was never retrieved" at garbage collection, if at all.
`stop()` cancels without awaiting, `reload_settings` calls it synchronously, and the app's
shutdown hook (`ui/app.py:183`) stops the MCP lifespan only.

Change to:

1. One done handler on `GameService`: discard the task, ignore `CancelledError`, log any other
   exception with `LOGGER.exception`.
2. `async def close(self)`: `hush()`, cancel every retained task, `await gather(..., return_exceptions=True)`.
   It replaces both `stop()` and `settled()` (`settled` is used by one test helper, which
   awaits `close` instead).
3. `Runtime.reload_settings` and a new `Runtime.close` become async and await each session's
   `close`. `ui/app.py` registers `runtime.close` on shutdown; `apply_settings` awaits the reload.

Impact: two methods become one. `reload_settings` and the settings page's apply path turn
async. Normal play unchanged.

Done when: a task that fails before `settled()` is logged; `close()` leaves no live task; both
tested with stub coroutines.

### F3. One safe file publication helper

Now: saves stage to a fixed `<name>.writing` (`core/io.py:145`), speech to a fixed `.part`
(`app/speech.py:58`), images write straight to the final path (`app/media.py:224-226`). Two
writers share one staging name, and `_existing()` treats a half-written image as cached.

Change to: one helper in `core/io.py`, used by all three.

```python
def publish(path: Path, write: Callable[[Path], None]) -> None:
    """Write beside, then replace: a reader never sees a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = mkstemp(dir=path.parent, prefix=f".{path.name}.")
    os.close(fd)
    staged = Path(name)
    try:
        write(staged)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)
```

`write_text` becomes `publish(path, lambda p: p.write_text(body, ...))`; media passes
`write_bytes`; speech opens the wave file on the staged path. Three callers justify the helper.

Impact: filenames and save format unchanged. This does not stop two processes editing one save;
that is F5's deployment decision.

Done when: a write that raises midway leaves the old file intact and no stray temp file; two
concurrent publishes never share a staging path.

### F4. Classify expected file errors at each boundary

Now, the same kind of failure is handled four different ways:

- `write_text` turns `OSError` into `Refusal`; `_read_text` (`core/io.py:168`) catches only
  `UnicodeDecodeError`, so a permission error or a file removed mid-read escapes `read_scenarios`
  and breaks the home page.
- `whole_text` (`core/source.py:23`) catches decode and PDF errors, not `OSError`.
- `Reader.read` catches `OSError` and logs with `LOGGER.exception`; `Illustrator._write` and
  `_data_uri` catch nothing, and `_generate` logs with `LOGGER.warning`.
- `FileStore.discard` and `Library.write_character` (the `path.exists()` and sibling read) are
  unguarded.

Change to, one rule per boundary kind:

| Boundary | Rule |
| --- | --- |
| User content read (save, scenario, character, source document) | `OSError` and decode errors become `Refusal` naming the file |
| User content write (save, scenario, character) | already `Refusal`; extend to `discard` and the sibling read |
| Optional media (image, clip) | catch `HTTPError`, `OSError`, `Refusal`; `LOGGER.warning("... failed: %s")`; no cache entry written |
| Bundled resources (`rules.md`, `packs/*.json`, prompts) | not caught; a broken install fails at start |

Keep it small: the read rule lives in `_read_text` and `whole_text` only (one `except
(OSError, UnicodeDecodeError)` each); the write rule in `write_text`, `publish` (F3) and
`discard`; the media rule in the one `except` each of `Illustrator.illustrate` and
`Reader.read`, so `_write` and `_data_uri` need no handling of their own. Media logs with
`LOGGER.warning("... failed: %s", failed)` in both modules; the traceback is noise for an
expected failure.

Impact: a bad user file no longer breaks a page. Five `except` clauses in total, no new types.

Done when: a permission error on a scenario is skipped with a log line; a missing source
document refuses with its name; a full disk during an image write logs and caches nothing.

### F5. Put the single-turn rule inside `Runtime`

Now: `GameService.play`, `act`, `open`, `restart` enforce nothing. The rule lives in the UI:
`GamePage.refuse_play` asks `Runtime.play_refusal` first (`ui/game.py:476`). `GamePage._open`
checks only its own session. `Runtime.playing()` picks the first session with a turn, which
assumes there is never a second. A future eval, or any caller that is not the page, bypasses it.

Change to: `Runtime` owns admission.

1. `Runtime.admit(session) -> AbstractAsyncContextManager` refuses when another session is busy
   or the session was evicted, then marks the active session. Released in `finally`.
2. Public entry points on `Runtime`: `open(session)`, `play(session, answer)`,
   `act(session, action, words)`, `restart(session)`, `reload_settings()`. Each enters `admit`
   before its first await.
3. `GamePage` calls these and only displays the refusal. `refuse_play`, `play_refusal` and
   `busy_refusal` go, and `GamePage._open`'s `unopened` guard moves into `Runtime.open`: one
   `admit` replaces four checks.
4. `Runtime.call` and `published_tools` read the one active session; `playing()` goes.

Deployment decision (needed for the README and for D4's resume checks):

- A. One process per save directory. No cross-process lock. Document it. Recommended for MVP0.
- B. Add a lock file per save and refuse a second process. Extra work, not needed for a single
  user.

Impact: page call sites move from `session.play` to `runtime.play(session, ...)`. Competing
actions get a clear refusal. No parallel games.

Done when: two concurrent `runtime.play` calls on different sessions cannot both open a turn; a
second game's automatic opening obeys the rule; tested without the UI.

## 3. Decided requirements (D1 to D5)

These are accepted. Each entry restates the concrete change so it converts to a plan.

### D1. Strict scalar validation

Verified: `parse(A, {"count": "4", "enabled": "false"})` on the `Frozen` base returns `4` and
`False`. `extra="forbid"` rejects unknown keys but does not reject wrong scalar types.

Change to: `strict=True` on `Frozen`, `Mutable` and `Loose` (`core/entities.py`). Then fix
what strict breaks, which is known:

- JSON arrays into `tuple[...]` fields: strict mode accepts a list for a tuple in JSON mode but
  not in Python mode. `parse` receives Python objects from `decode()`. Either validate with
  `model_validate_json` where the raw text is at hand (`_read`, `ask`, `restore`), or keep
  `model_validate` and add `strict=False` per tuple field. Recommendation: `model_validate_json`
  at the three text boundaries and `model_validate(..., strict=True)` elsewhere; `parse` grows a
  `parse_json(model, text)` sibling.
- `Settings` stays lax: it reads env strings. It does not inherit `Frozen`, so nothing changes.
- `Game.commit()` re-validates a Python instance: strict is fine there because the fields are
  already typed.

Impact: a save or pack with `"4"` for an int is refused. Model replies that coerce today get the
existing one retry.

Done when: tests reject numeric strings and string booleans on a `Frozen` model, accept JSON
arrays into tuple fields, and round-trip every save fixture.

### D2. Commit dice with the turn; separate cosmetic RNG

Verified: `Turn.begin` receives the service's `rng` directly (`app/runtime.py:130`), and
`Turn.apply` writes each successful tool's dice state back into it at once. A narrator or save
failure after a roll leaves the game unchanged but the dice advanced. `_speaks` draws from the
same generator, so companion chatter changes later gameplay rolls.

Change to:

- `Turn.begin` gets `deepcopy(service.rng)`. `GameService.save` after a successful turn sets
  `self.rng.setstate(turn.rng.getstate())`. `Turn.apply` keeps its per-call rollback.
- `GameService.chatter: Random = field(default_factory=Random)` for `_speaks`.

Impact: seeded test fixtures that depend on interjection rolls change. Nothing else.

Done when: a roll followed by a narrator failure or a save failure leaves the gameplay RNG
unchanged; enabling interjections does not change the gameplay sequence.

### D3. Carry precise types through engine, session and turn

Verified: `AnyEngine = Engine[Any, Any, Any]`; `player_of` returns `P` from an `Any` payload
after checking `id` and `known` only; `SceneEngine.new_game` annotates an `Any` as
`SceneDraft[C]`, which proves nothing. Three concrete engines override `world_of` with the same
one-line body only to narrow the return type (N6).

This is the one decided item that runs against the simplification preference: the full chain
adds two type parameters to `Engine`, one to `GameService`, `Turn` and `Roles`, and touches
every call site, for a static guarantee that the engine id checks in `begin` and `restore`
already give at runtime. CLAUDE.md already names this seam as the one allowed `Any`. So
re-decide:

- A. The full chain as first accepted: `Engine[P, M, G, S, C]`, generic `GameService`, `Turn`,
  `Roles`, erasure in the registry only, a negative typing check. L, `+`.
- B. Family engines only: `SceneEngine[C, W, G, K]` and `RoomEngine[N, P, W, G]` gain the world
  type `W`, `world_of` returns `W`, and the three concrete `world_of` overrides are deleted
  (N6). `AnyEngine`, `AnyGame`, `AnyScenario`, `AnyCharacter` stay at the seam as they are.
  S, `-`. Recommended.
- C. Leave everything. Nothing deleted.

Done when (B): the three overrides are gone and basedpyright is clean.

### D4. One explicit pack selection policy

Verified, four policies for one concept:

- Character creation picks one pack (`creation_steps`), and `Character` does not record it.
- Scenario creation defaults to every installed pack (`ui/create.py:193`).
- Hiring uses `first_pack(draft)`, so pack order decides (`scenes/engine.py:229`).
- `TwentyfourxxEngine.resolve_skill` searches every installed pack, selected or not.
- Loner meanings use the selected packs.

Change to: one frozen `PackSelection` value in `engines/scenes/packs.py` built once per game:
`primary: Slug`, `supplements: tuple[Slug, ...]`. It is the only object creation, launch
validation, prompts, skill lookup and hiring read, so `first_pack`, `pack_content`'s picks
argument and the all-packs scan in `resolve_skill` go.

- `Scenario.packs` becomes `Scenario.packs: PackSelection` (primary first, explicit).
- `Character` gains `pack: Slug`; launch refuses a character whose pack is not selected.
- Duplicate ids across selected packs are refused at selection time, not first-wins.
- `resolve_skill` searches the selection only.

Resume compatibility (C1 in the first review) has two shapes:

- A. Content fingerprints stored in the save; a changed pack refuses resume. Adds a field, a
  hash, and a message.
- B. No fingerprints. `SceneEngine.validate` already refuses a missing pack; an edited pack is
  accepted and plays with its new content, the same way an edited `rules.md` does. Nothing
  stored. Recommended: a pack author editing their own pack mid-game gets the edit, and no
  save carries a hash.

Impact: save and scenario format change. Under the no-migration rule, existing scenarios and
characters under `scenarios/` and `characters/` are regenerated. Implement together with pack
authoring, since that is when the format is touched anyway.

Done when: tests cover two packs with an overlapping id, a character from an unselected pack,
an installed-but-unselected skill, and a missing active pack on resume.

### D5. Shallow freezing with explicit ownership

Verified: `PendingOption.args["k"].append(2)` succeeds on a `Frozen` model. Also verified that
the two places a reviewer would suspect are already safe: `begin()` in both families builds the
world through `parse`, and `Mutable`'s `revalidate_instances="always"` copies every nested
model, so a draft never aliases the authored scenario; and `Engine.answer` hands
`PendingOption.args` to `parse`, which builds a fresh model, so a tool cannot edit the option.

Change to: documentation and a guard test, nothing else.

- Two lines in CLAUDE.md: "frozen means no field assignment; nested dicts and lists are still
  mutable; a value model never hands out a nested collection it did not copy. `Mutable`
  re-validates on parse, which is what keeps a draft from aliasing its scenario".
- One test per family: mutate the world after `begin` and assert the scenario payload is
  unchanged. This pins the `revalidate_instances` behaviour so a config change cannot remove it
  silently.
- Do not turn on `validate_assignment`; drafts are validated at commit on purpose.

Done when: the two tests pass and the rule is in CLAUDE.md.

## 4. Consistency and quality

### Q1. Parse CLI events by their real shape

Now: `_last_said` (`app/spawn.py:257`) walks every JSON line backwards and returns the first
`text` value found anywhere in the tree. Nothing checks that it belongs to a final assistant
message. `CodexDriver.read_result` reads the thread id the same way.

Change to: each driver declares the event models it understands as `Loose` classes
(`_CodexItemCompleted` with `item.type == "agent_message"` and `item.text`,
`_CodexThreadStarted` with `thread_id`); `read_result` filters by type and takes the last
agent message. `_last_said`, `_found`, `_string` and `_object` are deleted; `final_message`
keeps only the fenced and raw JSON extraction for message text. A stream with no final
message is a `Refusal`. Net: about forty lines of tree walking become two small models. Confirm the codex event names against the
installed CLI version before writing the fixtures; this review did not run either CLI.

Done when: fixtures cover a final answer, reasoning text after the answer, a failed event, and
no final answer, with no process spawned.

### Q2. Upload: one directory per form, deleted on success only

Now (`ui/create.py:173-282`): every upload calls `mkdtemp()`; replacing an upload drops the
only reference to the old directory; `write()` deletes the document in `finally`, so a failed
generation forces a new upload; leaving the page cleans nothing.

Options:

- A. An `Upload` owner class with `replace`, `path`, `dispose`, plus a disconnect hook. Adds a
  class.
- B. `ScenarioForm` creates one temp directory lazily on the first upload and saves every
  upload into it (a replacement overwrites by name, the previous file is unlinked). `write()`
  removes the directory after success only; a refused write keeps the document for the retry.
  An abandoned page leaves one temp directory to the OS, which is what `mkdtemp` is for.
  `_discard_upload` shrinks to one `rmtree`. Recommended: fewer lines than today.

Done when: a refused write keeps the document; a second upload leaves one file in the
directory; success removes the directory.

### Q3. Helpers that mutate become methods (widened)

The CLAUDE.md rule: a function whose first argument is one of our objects is a method, unless
its class lives in a lower layer, it renders, or it is unit-tested alone. These break it, and
two of them hide a mutation behind a calculation name:

| Now | Change to |
| --- | --- |
| `breathless/engine.py:291 _pool(world, actor, args)` spends the stunt | `BreathlessEngine._pool` pure; `sheet.spend_stunt` called in `roll` next to the wear calls |
| `twentyfourxx/engine.py:378 self._pool(...)` is a method | already right; the two `_pool`s then match |
| `loner3e/engine.py:263 _strike(draft, actor, opponent, outcome)` writes a note on `draft` | `Loner3eWorld.strike(actor, opponent, outcome) -> Struck` (facts, ended); the engine adds the note and the pending decision |
| `loner3e/engine.py:281 _check_ready(actor, opponent)` | `Loner3eWorld.check_conflict(actor, opponent)` |
| `loner3e/engine.py:294 _pair(args, rng)` | `Roll.faces() -> tuple[chance, risk]` on the tool model; the engine rolls |
| `tunnelgoons/engine.py:222 _level_decision(actor)` | `Adventurer.level_decision()` |
| `app/roles.py:179 _landed(turn)` | `Turn.landed()` beside `told`, `handed_over`, `narrates` |

Impact: no dice, fact order or rules change; existing engine tests pass unchanged.

### Q4. Delete compressed expressions and duplicate closures

Now: `app/roles.py:170`, `scenes/engine.py:118,124`, `twentyfourxx/engine.py:229,236` and
`twentyfourxx/world.py:202` build optional prompt sections with
`*((("TITLE", body),) if body else ())`; `twentyfourxx/engine.py:195-200` builds kits with
chained conditional tuple additions; `hiring.py:49` defaults to a lambda returning a lambda;
`ui/game.py:688` constructs `Observed(None, 0, 0, None, None)` positionally; `ui/game.py`
carries two inner closures (`accept` at 284, `answer` at 346) and `_send` that all do
`refuse_play; own_move = True; await _run(play)`; `twentyfourxx/engine.py:433-464` spends
thirty lines producing a three-way diff (missing, extra, repeated) for one refusal message.

Change to:

- `section_if(title, body) -> Sections` in `core/prompt.py` replaces the starred idiom at its
  six sites.
- Kits: a list appended in named steps.
- `Observed` becomes `kw_only=True`; the default check in `hiring()` becomes a named function.
- One `GamePage.play(answer: Answer)` replaces the two closures and the lambda in `_send`
  (`act` keeps its own line because it calls `session.act`).
- `_finish`: one comparison, `sorted(got) != sorted(expected)`, and one message naming the
  expected operators and the given ones. The master reads two lists instead of three
  categories. About twenty lines deleted.

Options for `GamePage` itself (500 lines, twenty attributes assigned in `build`):

- A. Split into `Transcript`, `Drawer`, `Composer` classes. Adds three classes; the page is
  not growing, so the split buys structure without deleting anything.
- B. Leave the class whole; do the deletions above only. Recommended.

Renames from the first review (`Turn.picture()`, `Turn.told()`, `Engine.land()`): the current
names read fine in their modules and each rename touches tests and prompts of nothing. Decide
yes or no as a block; recommendation no.

Done when: golden prompt and schema fixtures are byte-identical; UI behaviour tests pass;
`ui/game.py` and `twentyfourxx/engine.py` are shorter.

### N1. One constructor style for objects that need I/O

Now, three styles for "build me from disk or settings":

- `__post_init__` doing I/O: `GameService` reads the save (`app/runtime.py:63`); `Runtime`
  reads every engine's prompts and packs (`app/runtime.py:326`).
- Classmethod named for the act: `LauncherCatalog.read`, `SceneWorld.opening`,
  `RoomWorld.opening`.
- Free function: `open_illustrator`, `open_reader`.

A dataclass whose `__post_init__` raises `Refusal` after reading a file surprises a reader; the
classmethods do not.

Options:

- A. Classmethods everywhere: `GameService.resume(target, ...)`, `Runtime.start(settings, ...)`,
  `Illustrator.open(settings, store, slug, ...)`, `Reader.open(...)`. Moves code, deletes none.
- B. Leave as is and write one line into CLAUDE.md: "an object that reads disk to exist does
  it in `__post_init__` or a classmethod named for the act; a free `open_*` function is for a
  thing that may be `None`". Recommended: the `open_*` functions exist because they return
  `None` when the feature is off, which a classmethod would spell less clearly.

### N2. `Runtime` takes a spawner factory defaulting to `RoleRunner`

Now: `Runtime(settings, spawner)` takes an injected `Spawner`, but `reload_settings`
(`app/runtime.py:369`) replaces it with a hard-wired `RoleRunner(self.settings)`. Tests that
inject a `ScriptedSpawner` lose it on reload. Ten test sites and one production site construct
`Runtime`.

Options:

- A. `Runtime(settings, spawn: Callable[[Settings], Spawner])`, always passed. Touches every
  site.
- B. Drop injection; tests assign `runtime.spawner` after construction. Touches every site and
  leaves a window where the wrong spawner is live.
- C. `spawn: Callable[[Settings], Spawner] = RoleRunner`. `RoleRunner(settings)` already has
  that signature, so production becomes `Runtime(settings)` and reload calls
  `self.spawn(self.settings)`. Tests pass `lambda _: ScriptedSpawner()`. Recommended: one
  parameter fewer at the production site, and reload can no longer forget the injection.

### N3. Take PDF extraction off the event loop

Now: `Runtime.new_scenario` is async but calls `given_text` synchronously, which runs
`PdfReader` over a document of up to 120,000 characters. Every page and timer on the server
stalls for those seconds. Saves (`write_text`), image writes and `_data_uri` reads are also
synchronous inside coroutines, but they are milliseconds.

Options:

- A. `await asyncio.to_thread(given_text, ...)` for the document only. Recommended.
- B. Also wrap the save and media writes. Not needed at these sizes.
- C. Leave. The stall is once per scenario.

### N4. Share `rows()` on `Sheeted`; keep the other duplicates

Verified duplicates:

- `Survivor.rows` and `Crewmate.rows` are the same line: `self.sheet.rows() if self.sheet is not None else ()`.
- `drop_item` tool method is identical in `breathless/engine.py:203` and `twentyfourxx/engine.py:280`.
- `preview_character` is the same shape in three engines with a different item label.
- `carried()` differs (med kit), so it is not a duplicate.

Options:

- A. Give the `S` bound of `Sheeted[S]` a `SheetRows` protocol with `rows() -> Pairs`, and
  move `rows()` up. Leave `drop_item` and `preview_character`: four lines each, and the "two
  things" rule is met but the shared home would need a new mixin. Recommended.
- B. Add an `ItemSheetEngine` mixin holding `drop_item` and `preview_character(items_label)`.

### N5. One retry constant, one timeout idiom

Now: `spawn.ask` loops `range(RETRIES + 1)`; `Roles.master` loops `for attempt in (1, 2)` with
`if attempt == 2: raise`. `spawn._spawn` uses `wait_for(...)`; `builtin.run_builtin` uses
`async with timeout(...)`.

Change to: `Roles.master` uses `RETRIES`; both timeouts use `asyncio.timeout`. Mechanical.

### N6. Drop the `world_of` narrowing overrides

`loner3e/engine.py:80`, `twentyfourxx/engine.py:97`, `tunnelgoons/engine.py:91` each repeat
`return state.payload` only so pyright sees the concrete world type. D3 step 2 removes the need.
No separate work.

### N7. `Rolled` carries its dice once

Now: `Rolled.rolled` duplicates `Rolled.event.rolled`, and `rolled.rolled[0]` appears seven
times for single-die rolls.

Options:

- A. Drop `Rolled.rolled`; add `Rolled.face` (the one die of a single roll, raises on a pool)
  and keep `kept` and `total` reading `event.rolled`. Recommended.
- B. Leave.

### N8. Split the `Pairs` alias into `Sections` and `Rows`

Now: `type Pairs = tuple[tuple[str, str], ...]` names both prompt sections (heading, body) in
`core/prompt.py` and sheet rows (label, value) in `Thing.rows`, `Companion.sheet`,
`NarratorView.sheet`. 34 return sites say `-> Pairs` without saying which.

Change to: `type Sections = tuple[tuple[str, str], ...]` and `type Rows = ...` with the same
shape, in `core/prompt.py` and `core/views.py`. A rename only.

### N9. `Slug` stays `Annotated[str]`; say so in CLAUDE.md

Now: `EngineId` is a `NewType`, `Slug` is `Annotated[str, Field(pattern=...)]`. Statically a
`Slug` is any `str`, so `content_id()` narrows nothing for the checker; only pydantic enforces
the pattern.

Options:

- A. Leave, and add one line to CLAUDE.md: "`Slug` is checked by pydantic at boundaries and by
  `content_id` on routed values; it is not a distinct static type". Recommended: making it a
  `NewType` would force a call around every literal id in engines and tests.
- B. `NewType` plus `Annotated` for pydantic. Touches every id literal.

### N10. `Hiring` becomes a frozen dataclass like `Request`

Now: two packagings of "a worldsmith write". `Request` is a frozen dataclass with `unwritten`
and `write`. `Hiring` is a `Callable` alias produced by the `hiring()` factory, whose `check`
default is a lambda returning a lambda (`engines/hiring.py:49`).

Options:

- A. `@dataclass(frozen=True) class Hiring[G, M, A]` with `answer`, `prompt`, `install`,
  `check` and an `async def write(...)`. The default check becomes a named function.
- B. Leave; only rename the default to a named `_no_check`. Recommended: the factory is
  eight lines and read once.

### N11. Comment and naming sweep against CLAUDE.md rules

Violations of the repo's own rules, all mechanical:

- Comments longer than one line: `ui/create.py:51-52`, `ui/game.py:143-144`,
  `ui/game.py:254-256`, `ui/game.py:369-370`, `ui/theme.py:388-389`. Shorten to one line or
  move the reason into a docstring.
- The `Refusal` docstring (`core/entities.py:39-40`) is the one multi-line docstring; fine as
  a docstring, but it is the class every reader meets first, so keep it to one line.
- Single-letter names: `n, f` in `ui/settings.py:112-113`, `p` in `core/io.py:73,88`, `e` in
  `ui/game.py` event handlers and `rooms/world.py:357`, `n` in `tunnelgoons/engine.py:116,134`.
- `from re import fullmatch` in `core/io.py` where every other module does `import re`.

### N12. Write the constructor and return-shape rules into CLAUDE.md

Two conventions are followed consistently but not written down, so a reviewer cannot tell
intent from accident:

- World and entity methods return `list[Fact]` (85 sites); the seam boundary (`MasterTool.call`,
  `Engine.answer`, `Turn.apply`) returns `tuple[Fact, ...]` (5 sites); `master_tool` accepts
  `Sequence[Fact]`. Rule: "facts are built in a list and frozen to a tuple where they leave
  the engine".
- Services are dataclasses, boundaries are pydantic, UI pages are plain classes holding
  widgets. Rule: state that.
- Add whatever N1 decides.

### N13. Move the CSS string out of `ui/theme.py`

Now: `ui/theme.py` is 391 lines, of which 320 are one Python string of CSS (`STATIC_CSS`).
No editor lints it, and the Python module's real content (the palette, `set_look`, `install`)
is forty lines at the bottom.

Change to: `ui/theme.css` beside the module, read once in `install()` with
`read_prompt(Path(__file__).parent / "theme.css")` (it caches). `ui/dice_assets/` already sets
the precedent for assets next to code. The `:root` palette line stays generated in Python
because it comes from `NEUTRAL_PALETTE`.

Impact: none at runtime. `theme.py` drops to about seventy lines.

### N14. Delete thin pass-through methods

Each of these is a method whose whole body is a call to another method with the same
arguments:

| Delete | Replace with |
| --- | --- |
| `Engine._render` (`engines/seam.py:327`) | the two callers call `render_worldsmith` directly |
| `Runtime.scenario_models` (`app/runtime.py:338`) | `LauncherCatalog.read(library, store, engines)` derives the models itself from `engines[id].scenario`; `_open` does the same inline |
| `GameService.stop` and `settled` | F2's `close` |
| `Runtime.playing`, `busy_refusal`, `play_refusal` | F5's `admit` |
| `SceneEngine.first_pack` | D4's `PackSelection.primary` |

Impact: none at runtime; about thirty lines and three names fewer.

## 5. Leave as is

A reviewer may raise these. Each has a reason in the code or in this repo's rules.

| Pattern | Where | Why it stays |
| --- | --- | --- |
| Engine attributes declared without `ClassVar` and set on subclasses | `engines/seam.py:64` | `type[G]` cannot be a `ClassVar`; a test sets them per instance; the comment says so |
| `Turn.call` returns a plain string for "waiting" instead of raising | `turn/run.py:113` | A refusal would make the model retry; the comment says so |
| Preview builds a full character and catches `Refusal` on every blur | `ui/create.py:125` | One legality rule for the page and for `create`; cheap |
| One-second polling timers instead of push | `ui/game.py:188` | Several tabs share one session; polling is the simplest correct sync |
| `Settings` has `extra="ignore"` while boundary models forbid extras | `config.py:92` | It reads env vars, which carry unrelated keys |
| `killpg` and `start_new_session` are POSIX only | `app/spawn.py` | The spawned CLIs are POSIX tools; add one line to the README if it does not say so |
| `Runtime._sessions` is never evicted except on reload | `app/runtime.py:321` | One process, one player, a handful of games; eviction would drop a turn in flight |
| `CreationStep.hint` rather than `detail` | `core/creation.py:15` | It is a placeholder, not a description of the step |
| Prompt strings as module constants with a distinct prose voice | everywhere | Rewritten in idea 10; the eval judges them, not the code review |
| Dataclasses for services, pydantic for boundaries | `app/`, `core/` | A deliberate distinction, not an inconsistency |

## 6. Order and cost

1. Deletions and fixes in one behaviour-preserving phase: F1, F3, N5, N7, N13, N14, Q4, then
   D2 and D5 (one day).
2. F2, F5, N2 together, since all three touch `Runtime` and `GameService` (one day).
3. F4, D1, N3 (half a day). Q3, N4, N8, N11, N12 in one phase (half a day).
4. D3 option B with N6 (under an hour). Q1, Q2 (half a day).
5. D4 with pack authoring, then the eval and the README GIF.

If every recommendation is taken, the Python under `src` ends about four hundred lines
smaller: Q1, Q4 and N14 delete around a hundred, N13 moves three hundred of CSS into a `.css`
file, and only D4 adds a type.

Next: fill the decision column in section 1.
