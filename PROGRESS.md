# PROGRESS

One entry per phase of `PLAN.md`: counts before and after, decisions made off-plan, refuted
review findings and why, anything known and accepted.

## Phase 1 — one scene world

- `src` lines: 10,341 before, 9,972 after (target about 9,950). Tests: 453 before, 458 after.
- Goldens: `state/` and `save/` moved exactly as the phase's Done when says (`"party": []`
  after `"player"` for 24XX and Breathless; Loner's player out of `cast` and `present`, filed at
  `"player"`, `"party": []` for `"companions"`, no `"player_id"`; `"alive"` follows `"known"` in
  every sheet). `prompts/`, `schemas/`, `turn/` and every Tunnel Goons fixture unchanged.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).

### Decisions off-plan

- The seam that builds a world from a canon is `scenes.new_world`, not `new_game`: every
  `engine.py` already has a `new_game` that returns the state.
- `SceneWorld._consistent` refuses the player's id in `party` with "the player cannot travel
  with themselves" before `check_party`, keeping Loner's message; `check_party` alone would say
  "not in the cast".
- `Person.unwritten()` is wired into the three `_scene_unmet` bodies now, so one version of the
  rule is alive at the commit; the refusal texts are unchanged.
- `check_game` takes `packs: Collection[str]`: it reads only the pack ids.
- `new_world` has no `PLAYER_ID` guard: the world's validator already refuses a cast that
  holds the player's id, and nothing in the scene lifecycle spells `PLAYER_ID`.
- Loner's `apply_scene` gained 24XX's "the scene rewrites the player" guard: the old refusal
  relied on the player being a cast entry.
- Two tests of a rule the plan removes (`player.id == PLAYER_ID`, refused in the validator) are
  replaced by tests of the rule that replaces it ("the player is in the cast").
- A review found and fixed a bug the phase introduced: at the opening, `_scene_unmet` compared
  `resolved_id(...)` against `None`, so a stray id was dropped instead of refused. One
  regression test added (24XX).

### Refuted findings

- "`members()`, `party_rows`, `party_panel` have no caller": PLAN 1.1 and 1.2 put them in this
  phase; Phase 2 wires them.
- "The party symbols belong in `scenes.py`": PLAN 1.1 puts them in `engines/core.py` so they take
  `Person` rather than a second protocol.
- "`known` seam collides with `known` parameters in `cast_unmet`/`hub_unmet`": PLAN 1.2 names the
  seam `known` (it is `Engine.known`); those parameters are in Phase 2's fold.
- "The player's `last_seen` detail is always empty": kept the single generator over
  `(world.player, *world.cast.values())`; `last_seen` is cheap and Phase 2 folds the renderers.

### Known and accepted

- `world.py` is 121 (24XX), 121 (Breathless) and 128 (Loner) lines against "under 110". What
  remains is what PLAN 1.3 lists plus the rule helpers `tools.py` imports (`raised`, `stepped`,
  `tags_of`/`set_tags`). Not padded (PLAN rule 5); Phase 4's layout audit may move them.
- `uv run aidm` on shutdown by SIGTERM logs an MCP "cancel scope" RuntimeError; `app/` is
  untouched by this phase.

## Phase 2 — one worldsmith, one view

- `src` lines: 9,969 before, 9,419 after (target about 9,550). Tests: 458 before, 463 after.
  `scenes.py` 620 → 995; 24XX 1,224 → 922, Breathless 1,106 → 805, Loner 1,182 → 865.
- Goldens: every fixture unchanged, as the phase's Done when says.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves; a turn needs a spawned CLI the
  container lacks, so that check is manual.

### Decisions off-plan

- basedpyright refuses `isinstance(written, model)` on a parametrized draft class and narrows
  `isinstance(written, SceneDraft)` to `SceneDraft[Unknown]`, so the brief's spellings did not
  type-check. One private `TypeIs` guard, `_is_draft(written, model)`, restores the wrong-subclass
  refusal in `write_next` and narrows without `typing.cast`; it checks against the class the type
  argument was applied to, since pydantic parametrizes by copying, not subclassing.
  `build_scenario` takes a `cast_type` to name its draft, as `write_next` and `render_opening` do;
  `install_scene` keeps PLAN 2.2's one `SceneDraft[Any]`.
- The bar refuses a draft that names the party (PLAN 2.1), and `cast_unmet` demanded "one
  existing cast member brought back" from a cast that could be the party alone: with every cast
  member travelling, no draft could pass. The demand now stands only while someone outside the
  party could come back: `cast_unmet`'s `opening` keyword became `needs_return`, false at the
  opening and false when every cast member travels with the player. The maintainer chose this
  over "a party satisfies the demand".
- `install_scene`'s trace reads "the player travelling with A, B": number-neutral, since the
  brief's "and A travel there" was wrong for one companion.
- `subject_of` is private to `scenes.py`; Tunnel Goons keeps its own.
- The three `views.py` import `scenes` as a module and call `scenes.entity_line` and friends.

### Refuted findings

- "The staged `PLAN.md` edit is not part of this phase": the maintainer asked for it in this
  session (the Phase 4 split of `scenes.py` and `engines/seam.py`); one commit per phase.
- "Loner's master prompt now prints `(dead)`": PLAN 2.3 defines the one `entity_line` with it.
- "Fold `scene_unmet` into `scene_refusal`": PLAN 2.1 names both.
- "Replace the 24XX and Breathless `install_scene` wrappers with `partial`": PLAN 2.4 prescribes
  the wrapper, and the three engines' wiring files read alike.
- "Delete the Breathless and Loner tests that run the shared functions through their fixtures":
  this phase's test rule is green plus one test per new behaviour; the audit is Phase 4.

### Known and accepted

- `scenes.py` is 995 lines against "about 700": the file was 620 before the move and the PLAN's
  own function list adds about 370. Phase 4 splits it into a package.
- The three engines land under their "about 1,050" targets; nothing was padded (PLAN rule 5).

## Phase 3 — the recap and the refinements

- `src` lines: 9,419 before, 9,480 after (target about 9,625; nothing padded, PLAN rule 5).
  Tests: 463 before, 469 after.
- Goldens: the nine `state/` and `save/` fixtures of 24XX, Breathless and Loner gain
  `"recap": ""` per run, as the phase's Done when says. `prompts/`, `schemas/`, `turn/` and
  every Tunnel Goons fixture unchanged.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves; a turn needs a spawned CLI the
  container lacks, so that check is manual.

### Decisions off-plan

- `scene_history` prints a run through a private `_told(run)`: the recap branch and the
  exchange branch, so the comprehension stays one expression.
- `told_tail` lands in `tunnelgoons/worldsmith.py` as the private `_told_tail`; the constant
  keeps its name `TAIL_EXCHANGES`.
- The launcher test "a save that lists but will not open still reaches the player" is replaced
  by "a save that fails to restore is skipped, not listed": its premise (the payload is read only
  when the game opens) is what PLAN 3.5 changes.
- `tests/core/test_tool_surface.py` keeps its `A_SCENE` without a recap; `_scene` adds `RECAP`
  for the drafts written in play and `_bare_scene` validates an opening against `SceneDraft`.

### Refuted findings

- "The `ui.timer(0.5, ...)` in `game_page` duplicates `_scroll` and carries a magic number":
  PLAN 3.4 prescribes that exact line.
- "`_told` prints every exchange of the open run, uncapped, where the worldsmith prompt held
  three": PLAN 3.1 says a run without a recap prints every exchange; the recap bounds every
  closed run, and the open run is the one the worldsmith must read whole. Known and accepted
  below.
- "`IDEAS.md` item 12 is deleted though a session recap on resume did not land": PLAN 3.6 says
  delete item 12, its second half being 3.4 (resume at the end).
- "The home page now restores every save in full on every load": PLAN 3.5 prescribes
  `engines[game.engine].restored(raw)` in `load_catalog`. Known and accepted below.

### Known and accepted

- A scene played far past `SCENE_TURN_CAP` puts all of its exchanges into the worldsmith prompt
  at the crossing; only that one run is unbounded, and only until it is recapped.
- `load_catalog` decodes each save twice (the header, then `Engine.restored`); the home page
  reads N whole games where it read N headers. `Engine` is outside this phase.
- `src` lands 145 lines under the target: the recap and the terms cost about 60 lines, not 200.

## Phase 4 — the play issues

- `src` lines: 9,480 before, 9,609 after (target about 9,580). Tests: 469 before, 475 after.
- Goldens: every fixture unchanged, as the phase's Done when says (a regen run moved nothing).
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves, naming the four rules in its scenario
  select; a turn needs a spawned CLI the container lacks, so that check is manual.
- `uv run ruff format --check` reports `REFACTOR-PROPOSAL.md`, committed before this phase and
  outside it; every file the phase touched formats clean.

### Decisions off-plan

- `open()` forgets the role sessions when the narrator answers nothing, as `play` does on a
  failed turn: a resumed narrator must not remember an opening that never landed (review).
- `_open` returns at once when the game is no longer unopened, so a second tab's timer cannot
  run the page reset over an opening in flight (review). `_run` no longer nulls `session.step`:
  `play`, `extend` and `open` each do it in their own `finally`.
- The bar refuses an unknown id before `resolve_ids` does, so `tests/loner3e/test_world.py`'s
  "no such id or name" match became "these name nobody"; three card asserts in Breathless and
  Loner tests read the new `At stake:` line. `tests/core/test_scenes.py`'s recap test gives its
  world a cast member, since `apply_scene` now runs the bar.
- The `apply_scene`-level overlap and hidden-but-met tests became bar-level tests
  (`scene_refusal`), one per rule; `apply_scene`'s raising keeps the player-id and misfiling tests.

### Refuted findings

- "The opening exchange shows as a player-sent bubble reading `(the story begins)`": fixed on
  the maintainer's call. `chat` draws `BEGUN` and `CROSSED` as a centred caption, never as the
  player's words.
- "The newest live card re-tumbles on every `live_turn` refresh, one per step": PLAN 4.6 says
  "every step and fact refreshes it, so only the newest card tumbles"; tracking a seen fact on
  `GameView` is not in the plan. Handed to the maintainer as a call.
- "Rename `on_commit` to `_on_commit`": PLAN 4.3 names it beside `on_step` and `on_fact`; it now
  sits beside `on_step` in the public block. `on_fact`'s placement is PLAN 6.1's.
- "`apply_scene` builds the merged cast twice": PLAN 4.1 makes the install a safety net that
  re-runs the one bar; its docstring says so, and the merge is one comprehension over the cast.

### Known and accepted

- `resolve_ids`' raise is unreachable from `apply_scene` and `build_scenario` now that the bar
  runs first; only direct `opening_canon` calls reach it. Phase 6's dead-code pass.
- `src` lands 29 lines over the target: the bar's five checks and the opening cost about 130 lines
  where the plan counted 100; nothing was padded (PLAN rule 5).

## Phase 5 — the seam as classes

- `src` lines: 9,613 before, 9,557 after (target about 9,440; 117 over, nothing padded, PLAN rule 5).
  Tests: 475 before, 477 after.
- Goldens: as the phase intro says, the four `prompts/<engine>/narrator.txt` (the two length
  lines), the three scene engines' `schemas/<engine>/master_tools.json` (`next_scene.pursuit`),
  `prompts/<engine>/master.txt` (the "A scene is one place" paragraph), and `state/` and `save/`
  where every scene run gains `"pursuit": ""`. Beyond that list: `prompts/{breathless,twentyfourxx}/picture.txt`,
  a third `narrator.txt` line and a `state/` line in those two engines, all carrying the
  Drowned Road and Silent Relay questions 5.5 rewrites. Tunnel Goons `schemas/`, `state/`,
  `save/` and every `turn/` fixture unchanged.
- Reviews: two Fable reviewers (the maintainer's call for this phase; no `codex` on the machine),
  then a Fable implementer for the fold's second round (the partials, one more cut pass).
- Smoke: `uv run aidm` starts and the home page serves; a turn needs a spawned CLI the
  container lacks, so opening a game in each engine and reading the opening against the four
  questions (5.4) is manual.
- Implemented as two sequential parts: 5.1–5.3 (opus), then 5.4–5.5 (sonnet), since the second
  edits `engines/scenes/world.py`, which the first creates.

### Decisions off-plan

- Layout: the scene package has a fourth module, `engines/scenes/drafts.py`, holding the five
  drafts with `MIN_SITUATION` and `MIN_RECAP`: they are the worldsmith's answer schema, not the
  world, and `world.py` and `worldsmith.py` both need them. The bar, `worldsmith_prompt`,
  `scene_history`, `entity_line` and `SURPRISE` live in `world.py`, not `worldsmith.py`/`views.py`:
  5.3 makes `apply_scene`, `merged_cast`, `render_worldsmith` and `here_lines` methods of
  `SceneWorld`, and importing them from the other modules would cycle. `worldsmith.py` keeps
  `CROSSING`, `opening_draft`, `opening_canon`, `write_next`, `install_scene`, `render_opening`,
  `build_scenario`; `views.py` keeps `trail_panel`, `narrator_view`, `player_view`.
- The base `Pack` and one shared `pack_options(packs)` sit in `engines/core.py` beside
  `load_packs`, not in `scenes/engine.py`: the three `creation.py` need them and must not import
  the lifecycle module (review). The three per-engine `pack_options` copies are gone.
- `_Worldsmith(spawner)` is a frozen dataclass in `app/runtime.py`, the one `WorldsmithAnswer`
  the platform hands an engine; `GameService._grow` and `Runtime.new_scenario` share it. A review
  moved it to `app/spawn.py` to keep `BaseModel` out of `runtime.py`; the maintainer moved it back:
  `spawn.py` starts processes, and the generic bound `M: BaseModel` is not the untyped draft PLAN
  5.2's grep was written against.
- `authored(worldsmith, prompt, model, build, playable)` in `engines/seam.py` is the one place an
  unbuildable opening is turned into a refusal (review); both `author` call it.
- `SceneEngine.known`, `record`, `history` hold their bodies; the module functions had no other
  caller (review). `way_open` and `player_over` stay module functions: tests and `views.py` call them.
- `_scene` became `scene_of`, since `worldsmith.py` calls it across the module boundary.
- `build_scenario` lost its `cast_type` once the typed `WorldsmithAnswer` made `_is_draft` moot.
- `new_game`'s refusals read `self.title`: "BREATHLESS received ..." and "LONER 3E received ...".
- Every remaining `partial` in `engines/` went too (the maintainer's call mid-phase). The four
  resolvers that read the table sets are bound methods of one frozen dataclass per engine holding
  `packs`: 24XX `Skills.attempt`/`job_done`, Breathless `Complications.catch_breath`, Loner
  `Oracle.resolve_question`; `tools(packs)` builds the one instance, so `self` carries the packs
  as the phase's principle says. The four `default_factory=partial(Counter, ...)` are
  `lambda: Counter(...)`: pydantic wants a zero-argument factory, so a named `Counter` factory
  would still sit inside a lambda. `grep -rn "partial(" src/aidm/engines` is empty. About 36
  test call sites moved with the shape (PLAN rule 2).
- `SceneWorld.settle(job_done, pursuit)` has no default: every caller passes both (cut pass).
- `test_authoring_build_raises_on_an_unmet_bar` became
  `test_authoring_raises_when_the_worldsmith_never_meets_the_bar`: it now runs `engine.author`
  with a scripted worldsmith.

### Refuted findings

- None outright. Both reviewers called the eight `partial` → lambda rewrites spelling churn; the
  maintainer kept the fold and had the resolver four done properly (bound methods, above). The
  `Counter` four stay lambdas by the pydantic argument above. Tunnel Goons's `world.py` changed
  one line for it against brief-A's "do not change".

### Known and accepted

- `src` lands 117 over the target: `Engine` declares fifteen abstract methods (`seam.py` 133
  lines), and each engine answers them one signature-bearing line each, so the three scene
  `engine.py` are 73/71/84 lines against "under 60" and Tunnel Goons's 144 against "about 100".
- `grep -n BaseModel src/aidm/engines/seam.py` hits `new_game`'s return, the import and the
  `authored[M: BaseModel]` bound; `src/aidm/app/runtime.py` hits the import and `_Worldsmith`'s
  bound: generic bounds, not an untyped draft.
- `scene_unmet` and `scene_refusal` keep their `[C: Person, P: Person]` headers: they take a draft
  and an optional world, and are not among the fourteen verbs 5.3 moves.
- 5.4 is prose: play one opening per engine and read it against where am I, what do I see, what
  am I here to do, what could I do first.

## Phase 6 — the audit and the docs

- `src` lines: 9,557 before, 9,535 after (target about 9,415; 120 over, nothing padded, PLAN
  rule 5: the cuts the phase names cost twelve lines, and no dead code beyond them was found).
  Tests: 477 before, 477 after (one renamed, none added).
- Goldens: every fixture unchanged, as the phase's Done when says (a regen run moved nothing).
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves; the create page shows "3 points across
  the three" under each Tunnel Goons ability select (Playwright); a turn needs a spawned CLI the
  container lacks, so that check is manual.

### Decisions off-plan

- Every alias is a lazy `type` alias in its constants block; none follows its classes with a
  comment (PLAN 6.1 kept the four `WorldChange` unions and Tunnel Goons' `Entity` plain). A review
  showed `Entity` is used in annotations only, and the four unions were tried as `type` aliases:
  full suite green, basedpyright clean, every `schemas/` golden unchanged, so the "must flatten
  for the discriminator" reason was stale. `DRIVERS` and `TURN_TOOLS` are instances and keep
  their one comment each. The maintainer chose this over the plan's letter.
- The create page shows a step's `hint` under a select (Quasar's `hint` prop), so Tunnel Goons'
  three ability steps keep "3 points across the three" and the player reads the budget before
  the submit refusal. PLAN 6.1 deleted the hint because an options step never showed it; the
  maintainer chose showing it over hiding the budget. One assert added.
- The two create pages carry no engine badge in the header: it was set once from the default
  engine and read "LONER 3E" after the player chose Tunnel Goons. The Rules select is the one
  place that names the engine, and it now shows with one engine installed too.
- PLAN 6.4's "the two items from 5.3" are Maze Rats and Pokémon–Showdown from 6.3: the number is
  stale from the renumbering that made Track R Phase 5. They are `IDEAS.md` 18 and 19.
- `CLAUDE.md` is unchanged: the maintainer struck PLAN 6.2's two bullets as useless.
- `IDEAS.md` deletes nothing: the maintainer keeps every item and marks 5, 6, 7, 8 and 14 done,
  against PLAN 6.4's prune; 18, 19 and 20 are the new items.
- Reviews found and fixed two factual errors in the new doc text: `README.md` named
  `engines/hub.py` as the registry (it is `engines/registry.py`), and the competitor note said
  `.agents/` was gone (`.agents/skills` holds two development skills; the playing skill is gone).
  `docs/LONER-3E.md`'s `roll_question` line now says a tie counts on the Twist Counter only outside
  a conflict, as `tools.py` has it.

### Refuted findings

- "`README.md`'s architecture paragraph repeats the roles paragraph": PLAN 6.4 names the three
  roles as spawned CLIs returning typed proposals as the paragraph's first content; the sentences
  were split short instead.
- "Delete the `DRIVERS` and `TURN_TOOLS` comments; the code shows the evaluation order": PLAN 6.1
  says one comment each says they must follow their classes.
- "`grep -rn clamped src tests` is not empty": the four hits are the word in fixture prose
  ("skiff sits clamped"); `clamped\(` finds nothing.

### Known and accepted

- `grep -r VISION.md` finds `PLAN.md` and `NEXT-SPECS.md`, both records of the decision to delete
  it; the tests' `NIGHT_VISION_GOGGLES` is a 24XX item.
- `src` lands 120 over the row: the row counted a dead-code pass that found nothing beyond
  `Counter.clamped` and the hint.

## Phase 7 — voices

- `src` lines: 9,535 before, 9,749 after (PLAN row 9,595 counts from Phase 6's row of 9,415,
  which landed 120 over; the row's +180 lands as +214, `speech.py` at 114 of it). Tests: 477
  before, 485 after (eight new: the speech refusal in `test_config.py`, seven in
  `test_speech.py`).
- Goldens: every fixture unchanged (a regen run after part A moved nothing; part B and the fold
  touched no fixture-producing code).
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves with speech off (the default). A spoken
  turn needs a key and a spawned CLI the container lacks, so that check is manual.

### Decisions off-plan

- `ui/settings.py` changed one line against PLAN 7.1's "the settings page renders all of it
  unchanged": `SpeechConfig.voices` is the first tuple field in `Settings`, and the page has no
  widget for one. Rendered as `str(tuple)`, every Save compared a string to a tuple, put the
  string into `merged`, and `Settings.model_validate` refused it, so no key on any tab could be
  saved. `_shown` now leaves a tuple out as it leaves a directory out; `voices` is set from
  `.env` as a JSON list (`SPEECH__VOICES='["Kore","Puck"]'`).
- The chat plays the newest exchange's clip only, not one under every exchange with a cached
  clip: each `ui.audio` registers a route and `chat.refresh()` rebuilds them all, so a long game
  would accumulate routes per turn. PLAN 7.5's "after an exchange's lines" is read with its
  goal, "played under the newest exchange".
- `autoplay_clip` is consumed by the render that used it (`chat` clears it after drawing the
  audio), not by `_send` before `refresh_all` as PLAN 7.5 says: on a moving-on turn the clip
  lands during the worldsmith's write, the poll autoplays it, and the turn's final `refresh_all`
  would have restarted it.
- `speak()` is also called after the opening's `illustrate()` in `GameService.open`, not only
  after the two calls in `play`: the opening is the first narration the player reads.
- The clip is written to a `.part` file and moved into place, so a write that dies half-way
  never caches a broken wav that `clip()` would serve forever.
- `GameService._illustrations` is `_background`, since it now retains speech tasks too;
  `newest_clip`, `clip_pending` and `speak` share `_newest()`. `poll_art` is `poll_media`.
- `README.md`'s cost line names illustration and speech as the two exceptions.
- `tests/ui/test_launcher.py`'s three `new_scenario` calls gained `voice=""`: the keyword is
  required, as `art_style` is.

### Refuted findings

- "`Providers.kokoro` has no user in the tree; drop it or record the exception": PLAN 7.1 adds
  it because `local` is Ollama's port and serves no speech; `speech.provider = "kokoro"` selects
  it. Recorded here as the plan's choice.
- "Inline `speech_body` into `read`'s one call site": PLAN 7.3 names `speech_body` as one of the
  four tested functions.

### Known and accepted

- `Reader.read` posts one request per line, in series; a five-line exchange is five round
  trips. Parallel posts would reorder nothing but were not asked for.
- The clip is one wav per exchange; a re-read of an old exchange after the voice pool changes is
  a new key, so the old file stays on disk unused.
