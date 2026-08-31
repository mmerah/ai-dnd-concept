# PROGRESS

The record of work against `PLAN.md`. One entry per phase: the counts before and after, what was
decided along the way, and anything left known-and-accepted.

Phases 0–6 are done and their per-phase entries were pruned; `git log --stat` holds the detail.
What is below is what a later phase still needs to know.

## Counts

| phase | `src` | `tests` |
|---|---|---|
| start | 9,452 | 6,044 |
| 0 — the probes kept | 9,452 | 6,044 |
| 1 — one engine | 7,471 | 4,411 |
| 2 — the scene kit and the port | 5,806 | 3,408 |
| 3 — the three roles and the tool surface | 5,458 | 3,275 |
| 4 — the pages | 5,625 | 3,393 |
| 5 — the sweep | 5,627 | 3,386 |
| scene transitions rebuilt (off-plan) | 5,791 | 3,519 |
| 6 — the architecture deletion | 5,600 | 3,517 |
| 7A — the restructuring pass | 5,578 | 3,661 |
| 7B — the roles get drivers | 5,892 | 3,901 |

Every phase ended with the full check green — pytest, ruff check, ruff format, basedpyright — and
with a turn actually played, not only checked. Phase 4 is the one phase that grew `src`: it added
the new-scenario page, which did not exist before. Phase 6 came in 110 lines under the bottom of
its own range because its step 3 was refuted and added nothing back. **No deletion was ever
invented to reach a number.**

**Every phase was reviewed adversarially against its staged diff, and every review found real
defects.** That is the standing method, not a phase ritual: the reviews caught a scene installed
for the wrong turn, a `kill` that lost what the dead carried, a scene installed with no player in
it, a crash that orphaned the worldsmith, and a claim in this very file that was measured wrong.

## Standing decisions — settled, do not re-propose

1. **The union payload is refuted for good.** `SceneState[S]` is invariant, so a
   `SceneState[LonerSheet] | SceneState[TfxSheet]` gives three strict errors, at `narrator_view`,
   `apply_change` and `apply_scene`. Runtime passes, which is why it would have shipped as a
   silent type hole for anyone who reached for `Any`.
2. **Sheet erasure is refuted too, on the published schema.** Dropping `[S]` from `Entity`,
   `SceneState`, `SceneCanon` and `SceneDraft` passes every runtime check and reports zero type
   errors — but `PlainValidator` has no input schema, so `Entity.model_json_schema()` renders the
   sheet as `{}` and the worldsmith is handed a schema that says nothing about what a sheet is.
   The one untried alternative is a `SceneDraft` that stops reusing `Entity`.
3. **A two-parameter `Game[S, P: EnginePayload[S]]` is rejected by the type checker**: a bound may
   not reference another type parameter. A shared payload base also cannot declare `engine` and
   let engines narrow it to a `Literal` — that is `reportIncompatibleVariableOverride`.
4. **Route 2 works and is the shortest path open**: `Game[S]` with a `SerializeAsAny` payload plus
   a per-engine `Game` subclass. Byte-identical round trip, `twist` and `twist_pack` survive
   `committed()`, one narrow `pyright: ignore`. Cost is ~46 annotation sites; the payoff lands
   with engine two, which is why Phase 6 skipped it. **It was skipped on cost, not impossibility.**
5. **`_gain` + `_rewrite` (31 lines) stay**, and **the tag glossary (24 lines) stays.** Both were
   examined as fat and both are load-bearing: the glossary is the only place a tag's meaning
   reaches the master, and a keyed tag map would trade named sheet fields for string keys and
   change the save shape.
6. **`Scene.ways_out`, a travel tool, and a menu of destinations are all refused.** Authored exits
   rebuild the map ontology the vision threw out. The player's own sentence is the whole brief for
   the next scene.
7. **Speculative scene writing is deleted.** A scene written before the player chooses is a scene
   for the wrong place.
8. **`next_scene` is not a `PendingDecision`.** A decision blocks the master's tools and forces the
   player out of a scene they may still want to play.
9. **A projection type must earn itself.** `NarratorView`'s absence of hidden fields is a real
   correctness boundary and it stays. `PlayerView` fields are read by the page, which imports
   neither the engine nor the kit — that is `VISION.md` §5, not drift.

## Open — known and accepted

2. **The tag glossary only explains pack tags.** A scenario-invented tag such as "A Guttering
   Lantern" reaches the master unexplained.
3. **`scene_spent` runs after the exchange is recorded**, so `SCENE_TURN_CAP = 12` fires on the
   twelfth exchange in a scene. It is a safety net and the number is not load-bearing.
4. `IDEAS.md` entries I5 and I7 still say "builtin mode"; `docs/24XX.md` and
   `docs/NEXT-ENGINE-RESEARCH.md` cite the deleted `twentyfourxx/director.md` by path. The engine
   phase rewrites the latter two.
5. The local `saves/whispering-vault--kael.json` does not load and never did after phase 2. The
   home page logs it and skips it; `saves/` is untracked.
6. `tests/core/fixtures/source/drowned-road.{md,pdf}` are kept — `test_documents` reads them to
   test PDF and markdown parsing, not 24XX. `docs/24XX.md` and `docs/BREATHLESS.md` are kept for
   the engine phase.

## Measured before the engines return

No code changed for either measurement; `PLAN.md` phase 8 carries the conclusions.

**24XX: ~1,050 `src` python lines, not the 500 the plan first claimed.** Three methods agree —
scale the old 24XX (932) by Loner's measured port delta (+21.5%) -> 1,132; walk all sixty old
symbols -> 1,035; fixed cost -> 1,005. The cleanest refutation needs no estimate at all: Loner 3e,
the simplest engine here, is 823 lines, and 24XX is larger at every comparable symbol. The port
makes an engine grow: Loner went 675 -> 823, because the engine now owns its typed state, three
payload models, `new_game`, `guidance`, `scene_closed`, and ~34 lines of helpers that came back
when `engines/core.py` fell from 483 to 141.

**Loner is not fat.** By category: 74 imports (9%), ~80 lines of prompt prose (10%), ~104 of state
and pack schema (13%), ~180 of SRD mechanics (22%), ~82 advancement, ~62 creation, ~109 seam
wiring.

**About 40 lines inside `loner3e` name no Loner rule** — `owed_notes`, `party_member`,
`check_packs`, `find_entry`, `ADVANCE_SPENT`, `describe_rows`. They were `engines/core.py` code at
`c9dbf9f`. With one engine that reads as engine code; with two it is duplication. Move them when
the second engine proves each one, and keep the party/ledger cluster apart from the pack and option
lookups.

**Breathless: ~770 `src` python lines**, below Loner and 27% below 24XX. Two methods agree (767,
801); the port-delta method was rejected because it assumes helpers Breathless does not use — a
read confirms zero uses of `party`, `party_member`, `advances_owed`, `ADVANCE_SPENT`, `find_entry`,
`other_than` or `pack_meanings`. It is smaller because **it has no advancement system at all**,
and Loner spends 119 lines on that ledger and its glossary.

**Each engine also regenerates ~1,300–1,400 lines of golden JSON**, because the golden tests
parametrize over `ENGINE_IDS`. Machine-written, but a real diff to read.

## Phase 7A — the restructuring pass — done

`src` 5,600 -> **5,578**, inside the plan's 5,500-5,610 band. `tests` 3,517 -> 3,661. Full check
green at every step, and the game opens end to end on the new shape.

**7A was never a deletion phase, and it did not become one.** Steps 1, 4 and 5 add lines on
purpose; step 6 moves five fields into a wrapper. Nothing was invented to reach a number, and no
named deletion was skipped to protect one.

### What each step did

1. **Four cards in the scene tab.** `sheet_panel` -> `scene_sidebar`, four `game-card` helpers,
   `_threads` folded into `_threads_card`. No new CSS.
2. **The envelope stack is gone.** `core/envelope.py` deleted. `Header` sits in `core/entities.py`;
   `EngineHeader`, `SaveHeader` and `CharacterHeader` in `core/model.py`. `io.decoded` is the one
   JSON decode, and every reader goes through it, so the duplicate-key guard covers saves and
   character files too. The save, scenario and character JSON did **not** change.
3. **One dispatcher, owned by `Turn`.** `Turn.call` holds the whole gate. `TurnTool` and
   `TURN_TOOLS` live in `turn/run.py`. Deleted: `ServerTool`, `SERVER_TOOLS`, `_DISPATCH`,
   `GameService.call_tool`, `_tool_refusal`, `_engine_call`, `_require_turn`, `turn_started` and
   `draft_refusal`. `_apply` is copy-and-swap, so **an engine tool body runs once, not twice**, and
   a refused call consumes no dice.
4. **The engine id is an explicit coordinate.** `CatalogEntry.engine`,
   `LauncherCatalog.characters_for`, `read_characters` yielding one row per character *and* engine,
   `Runtime.engine` deleted, `new_scenario` takes an `engine_id`. Both create pages carry an engine
   select that appears only when a second engine is installed.
5. **Authoring left the composition root, and the ABC is gone.** `app/scene_write.py` holds
   `write_next` and `write_opening`. `CharacterCreation` became three plain callables on `Engine`.
6. **The world is a list of played scenes.** `SceneRun` holds the scene, who was in it and what
   happened. `SceneState.runs` is the only chronology; `Game.history`, `Game.turn_facts`,
   `Exchange.scene`, `Scene.id`, `SceneState.played/current/opened_at/spent/settled` are all gone.
   `apply_scene` lost its `turn` parameter and `render_worldsmith` its `played` parameter.
7. **Three dead branches.** `Loner3eState.twist_pack` is a required `Slug`; the `or state.packs[0]`
   fallback and the `is not None` guard are gone. `answered`'s `check` parameter lost its `| None`
   too — no caller ever passed one.

### Decisions taken inside the phase

1. **A header routes a document; it does not validate it.** A save whose *payload* is stale now
   lists on the home page and fails loudly when opened. Only a broken header hides it.
   `test_a_save_the_app_cannot_read_does_not_hide_the_others` was rewritten to break the header
   (`turn: -1`), which also survives step 6 deleting `Game.history`.
2. **`created` was not added.** `ui` may not import `aidm.engines` (`test_package_boundary.TOPS`),
   so the plan's `created(engine, ...)` call from `ui/create.py` could not compile. The page calls
   `engine.create_character` and `engine.preview_character` instead. Smaller, and it needs no
   bundling function.
3. **`Turn.tools()` was dropped as dead.** `Runtime.published_tools` is the only caller of that
   list.
4. **`close_segment`'s "not on the turn a scene opened" guard is now structural**:
   `len(world.run.exchanges) <= 1`, which `opened_at` measured before. Same behaviour, one less
   field.
5. **`scene_spent` counts `len(run.exchanges)` against `SCENE_TURN_CAP`.** A crossing still counts
   as one of the twelve, exactly as it did.

### An adversarial review closed every gap it found

The review found **no functional defect**: the `Turn.call` gate is line-by-line equivalent to the
old five-place logic, both guard rewrites are provably identical (`len(run.exchanges) ==
turn - opened_at` holds invariantly, because `close_segment` is the only writer of `turn` and the
only caller of `record`), and there is no list aliasing. It found one real regression and a set of
invariants no test could fail. All are fixed:

1. **The authored `world.json` carried play state.** `SceneCanon.opening` had become a full
   `SceneRun`, so every scenario the worldsmith wrote got `exchanges`, `settled` and `spent` —
   three fields `new_game` silently discarded. `SceneCanon` now holds `opening: Scene` with its own
   `present`/`hidden`. `SceneRun._each_id_once` is gone; `_check_named` does the id check for both.
2. **`write_opening` was a pure argument shuffle** with one caller. Deleted and inlined.
3. **`runtime.py` gave up 32 lines it did not own**: `_installed` -> `scene_write.install_scene`,
   `_open_media` -> `media.open_illustrator`, `_narration_refusal` -> `turn/run.narration_refusal`.
   437 -> **405**.
4. **Two open-coded `next(iter(runtime.engines))`** replaced by one `Runtime.default_engine()`, so
   phase 8 has one place to change. `_lone_engine` deleted, `recent` made required.
5. **Five invariants had no failing test.** Every new test below was proved by mutating the `src`
   line it guards and watching it fail: `_apply`'s rng copy and write-back; `characters_for`'s
   filter; `load_catalog`'s three-way agreement; `read_characters` per-engine rows;
   `published_tools` reading the live turn; `close_segment`'s first-exchange guard;
   `Engine.restored`'s engine check; and a save that lists but will not open.
6. **The golden turn had lost its cross-scene case.** Both played exchanges had landed in one run,
   so forcing `_recent`'s label to the current scene passed. The played turn now sits in an earlier
   run, "The Vault Stair", and that mutation fails. It also fixes prose that read wrong: "I try the
   vault door" is now filed under the stair, not the study.

### The four behaviours the plan says have no automated check — now three do



1. A decision that re-suspends leaves the master's picture ending in `RULES_WAIT` —
   `test_a_re_suspended_continuation_keeps_the_rules_waiting`.
2. A save file and a character file with a duplicated JSON key are both refused —
   two new tests in `test_integrity_boundaries.py`.
3. A crossing counts as one turn against the twelve-turn cap —
   `test_the_players_own_answer_is_the_brief_and_the_crossing_lands_in_that_turn` asserts the
   crossing lands as the new run's own single exchange.
4. **Still unchecked: the chat prints no "Paused:" line directly above the live decision widget.**
   The rule is preserved in `ui/game.py` `chat`, but it is UI layout and has no test. Read it in
   the browser.

### The golden fixtures

Regenerated once. Every changed line was read. `state/loner3e.json` and `save/loner3e.json` show
only the intended move: the exchanges go inside the run, `Exchange.scene` and `Scene.id` go, and
`opened_at`/`spent`/`settled` move onto the run. **Every fact, die roll and spoken line survives
byte for byte.** `prompts/loner3e/picture.txt` changed two lines: the recent-play label now reads
`[at The Abbot's Study]` instead of the hand-written `[at the sealed vault]`, because the scene a
turn belongs to is now structural and no longer a string the fixture could set freely. That is the
point of the step.

`scenarios/whispering-vault/world.json` was hand-migrated: the opening is now a `SceneRun`.
`saves/` was already empty.

### Open — known and accepted

1. **`app/runtime.py` is 405 lines, not under 400.** Three helpers that were not composition root
   have left it. What remains is the live-game lifecycle and the composition root itself, plus the
   `new_scenario` body the plan keeps there on purpose. Nothing was invented to close the last five
   lines.
2. **`last_seen` still stops counting an entity as seen in a run they left.** An entity removed by
   `leave` is gone from `run.present`, so a later scan does not find them in that run. Behaviour is
   unchanged from before the phase; fixing it would need a field.
3. **Step 4 cost more than its +20 estimate.** The refreshable scenario form and the engine select
   are real page code the plan under-counted.
4. **`_check_named` no longer checks a *past* run's ids for uniqueness**, only the current one.
   Nothing writes a past run, and `apply_scene` and the verbs both dedupe, so no duplicate can
   arise. `SceneRun` lost its own validator in exchange for the authored file losing three fields.

## Phase 7B — the roles get drivers — done

`src` 5,578 -> **5,892**, against the plan's ~5,880. `tests` 3,661 -> **3,901**. Full check
green at every step, and a turn played in the browser on the new drivers.

### What each step did

1. **Provider, model and effort are settings.** `RoleConfig` is `provider` + `model` + `effort` +
   `timeout`, with `command` kept as an escape hatch that marks the role unresumable.
   `MASTER_COMMAND` and `WRITER_COMMAND` are gone, and so is the rule that an empty command
   inherited the master's.
2. **Typed drivers behind one boundary.** `ClaudeDriver` and `CodexDriver` build a command and
   parse the output; `CliSpawner` is still the only thing that starts a process. `RunResult`
   carries the text, the session and the token counts.
3. **A retry carries on its own attempt.** `answered` keeps the session the refused attempt
   returned and re-prompts with the error alone.
4. **A session per save, per role.** `app/sessions.py` holds `Conversations`, a sidecar at
   `saves/.sessions/<slug>.json`, a sha256 fingerprint of `provider|model|effort|instructions`,
   and a lock per save and role. The master and the narrator resume; the worldsmith stays one
   conversation per attempt.
5. **What a role can reach, measured.** The child environment is `PATH`, `HOME`, `LANG`, `TERM`
   and one provider key. Each role runs in an empty temporary directory. What the probe found is
   below; the probe itself was thrown away, as phase 5 threw away its own.
6. **One log line per spawn**: role, provider, model, effort, cold or resumed, duration, input
   and cached tokens. `Conversations` logs the fallback reason separately.

### Decisions taken inside the phase

1. **`--tools ""` disables nothing**, although `claude --help` says it does. Asked to run
   `echo REACHED` under it, a spawned role ran it. That flag was in `MASTER_COMMAND` and
   `WRITER_COMMAND` from phase 3, so **every role had a shell for three phases.** Two things work
   instead: `--tools <name>` restricts to that name, and `--restricted` drops the
   command-running tools and `WebFetch`, confines the file tools to the working directory, and
   ignores the user's own settings files. Under `--restricted --tools Read` the role answers
   `["Read"]` and says it has no shell. The master adds `--allowed-tools mcp__aidm` and
   `--mcp-config`, and reached `scene` on the live server. Measured on Claude Code 2.1.251.
2. **`Driver.command` takes the role.** Whether a role gets this game's MCP server is a fact about
   the role, not an operator knob, so it stays in code and never enters `Settings`.
3. **`answered` still returns the value alone.** The plan had it return the session too, for the
   caller to store. `Conversations.ask` owns resume, storage and the lock instead, so no caller
   holds a session: `answered` only threads one between its own two attempts.
4. **No generated configuration file.** `--mcp-config` takes a JSON string, so there is nothing to
   write and nothing to clean up. The temporary working directory is the only thing removed.
5. **`io._write` became public `io.write_text`**, and `FileStore.sessions_path` names the sidecar,
   so the sidecar is written with the same staged-then-replace method a save is.
6. **The memory note that `claude -p` has no model flag is out of date.** `--model` and `--effort`
   both exist in 2.1.251, which is what made this phase's settings possible.

### The adversarial review found eight real defects

Every one is fixed, and every fix was proved by mutating the `src` line and watching a test fail.

1. **A cold fallback replayed a continuation into a new conversation.** `answered` sends only the
   error when it holds a session. If that resume was rejected, `Conversations.ask` re-ran the same
   error text cold, so the role got a refusal with no brief. A session the caller names is now
   never retried cold.
2. **A thrown-away turn left the master remembering it.** The narrator raising discards the whole
   draft, but the master's session had already been stored — so the next turn resumed a
   conversation that believed it applied changes the game never received. `play` now forgets the
   save's sessions when it throws the turn away. `restart` forgetting them had no test either.
3. **`ClaudeDriver.parse` ignored `is_error`.** A failed run can exit 0 and put its error where
   the answer goes, so the master would have "played" a turn whose text was an error message.
4. **Every codex isolation flag was untested.** Three mutations passed the suite: writers given an
   unsandboxed shell, `--disable apps` and `--ignore-user-config` deleted, and the master/writer
   privileges swapped. Now asserted.
5. **The fingerprint's `instructions` term was untested**, so an edit to `master.md` would have
   kept resuming a conversation briefed on the old text.
6. **`_found` never descended into arrays**, although two docstrings said "at any depth".
7. **`--allowed-tools mcp__aidm` and the `KEPT_ENV` list were unpinned.** Deleting the flag, or
   adding `SSH_AUTH_SOCK` and `AWS_SECRET_ACCESS_KEY` to the allowlist, failed nothing. The
   environment test now asserts the child's keys exactly.
8. **A sidecar that cannot be read or written broke the turn.** It is disposable memory, so both
   now log and carry on.

The review also cleared four categories: the lock cannot deadlock (`answered` calls `ask` twice
in sequence, never nested), the double-application gate reads `turn.facts` live through the turn
object, no secret or repository path reaches a command line, and the sidecar path cannot enter the
save catalog.

### Played, not only checked

Three turns of `The Whispering Vault`, from the browser:

1. **Claude, cold.** The master rolled the oracle, the dice landed, the narrator wrote the scene.
2. **Claude, resumed.** `master spawned: ... resumed in 27.0s, input=12 cached=87208` and
   `narrator spawned: ... resumed in 5.6s`. Both carried on their own conversation.
3. **Codex, all three roles.** `master spawned: provider=codex model=gpt-5.6-sol effort=high cold
   in 33.8s, input=51554 cached=32256`, then the narrator, then three spoken lines on the page.
   It started **cold** because the provider and the model had changed — the fingerprint doing its
   job, live.

`ui/app.py` now calls `logging.basicConfig`. Without it the root logger dropped every INFO record,
so no spawn line could ever be read.

### Open — known and accepted

1. **The codex master can never resume.** Measured: `codex exec resume` accepts neither
   `--sandbox` nor `--approve-for-me`, and a resumed thread answers every MCP call with "MCP tool
   call requires approval, but approval policy is never" — under `on-request`, `granular` and
   `untrusted` alike. Only `--approve-for-me` on a cold start lets a call through. So the codex
   master starts cold every turn, and only the narrator and the worldsmith resume. Their flag set
   was measured end to end: a cold spawn was told the word PLUM and a resumed one said it back.
2. **A cold retry can open on a refusal.** `start_turn` sets `started` but lands no fact, so a
   master that dies straight after it is retried cold, and that retry's first call answers
   `ALREADY_OPEN`. It is an answer, not a crash, and the gate is right to read facts rather than
   `started`.
3. **`HOME` is on the allowlist**, so a Claude role can still see `~/.claude`. `--restricted`
   ignores the settings files there; that is the flag's claim, not something the probe showed.
4. **Codex keeps a shell.** `--disable shell` and `--disable mcp` are both rejected as unknown
   feature flags, so the codex acceptance is least privilege, as the plan allowed: read-only
   sandbox (workspace-write for the master, which cannot take `--sandbox` beside
   `--approve-for-me`), empty working directory, `--ignore-user-config`, `--disable apps`,
   `web_search=disabled`, and a scrubbed environment. Under all of that the role still ran
   `/bin/bash -lc 'echo REACHED'`. **`--ignore-user-config` alone left the account's own MCP
   servers standing** — a corporate Polarion server, a site-deployment server and a
   workspace-agent server, about a hundred tools — which is what `--disable apps` removes.
   Measured on codex-cli 0.151.0.
5. **Claude keeps `Read`.** Naming no built-in tool re-enables all of them, so one harmless tool is
   the floor. `--restricted` confines it to the empty working directory.
6. **`master_log` is the parsed final message, not the raw stream.** The dev tab showed codex's
   whole event stream before; it now shows the answer.
7. **The default models are Claude aliases.** Moving a role to codex means changing `model` in the
   same edit; `opus` is not a codex model.
