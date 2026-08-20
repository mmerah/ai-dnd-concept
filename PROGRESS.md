# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 — simplification

- Step 1 — stale eval results deleted. `evals/results/` holds only `step-11-baseline.json`.
- Step 2 — memory system and Worldkeeper deleted. A turn is Interpreter -> Director -> hooks ->
  Narrator; the conversation window is unbounded. `SAVE_VERSION` 81 -> 82. `docs/MEMORY-SYSTEM.md`
  records the shape a re-implementation takes.
  - Trap found, then half-undone. Folding a deleted memory into an entity's `brief` leaked
    canon and `test_pipeline` caught Elena's name in player prose — but only because it was
    folded into **Mara**, who is `known`. `VisibleScene.of` builds the Narrator's view from
    `player`/`location`/`inventory`/`here`/`known_elsewhere`, all `known`-filtered, so a hidden
    entity's `brief` reaches the Director and Interpreter and never the Narrator. The Mara/Elena
    line now lives on `elena.brief` (`known: false`); the golden `narrator.txt` not moving when
    it was added is the standing proof. `Thread.note` is Director-only too.
- Step 3 — `Resolution` deleted; a `Play` returns `tuple[Fact, ...]`. `check_draft` could not go
  in `transact.py` as planned: `advancement -> transact -> engine -> advancement` is a real cycle.
  It ended up in `state/world.py`, beside the `draft()` and `committed()` it wraps. PLAN's reason
  for hoisting it into `engines` — that `state/hooks.py` imported it — was false; nothing did.
- Step 4 — `TurnLog.fired` and `Resolved` deleted; `apply_to_draft` returns `tuple[Fact, ...]`.
  The hooks trace step filters `fact.kind.startswith("hook")` over `log.facts`. The reveal and
  thread-advance facts a hook causes stay in `turn.facts`, so showing only the markers is a
  dedupe. Note the missing underscore: `hooks_capped` does not match `hook_`, and filtering on
  the longer prefix silently hid the one signal that a hook chain was truncated.
- Step 5 — the trace is in-memory only. No `.trace.jsonl`, no `save_version` on a trace entry,
  no version gate on it. `SAVE_VERSION` unchanged: the save's own bytes did not move. The Trace
  tab reads `GameSession.entries`, which now starts empty each session. Nothing reads or unlinks
  an existing `saves/*.trace.jsonl` any more, `discard` included: delete them by hand once.
- Step 6 — `begin_game` and `build_engine` live in `app/registry.py`, beside the `engine_class`
  they build on. Nothing under `app/authoring/` imports `app.session` any more, which was the
  point; the interim `app/newgame.py` was deleted in the review pass.
- Step 7 — each engine is six modules; `tools.py` folded into `actions.py`, `director_toolset`
  last. `mechanics.py` stays: merging it would make `actions.py` and `rules.py` import each other.

### Phase 1 review pass

An adversarial review of the staged phase found one bug and ~120 lines the phase walked past.
All applied:

- The `hooks_capped` filter bug above.
- `engines/checks.py` deleted — one 19-line function alone in a module.
- `app/views.py::JournalView` deleted. Step 2 took its third field and left a two-field wrapper
  every caller immediately unwrapped — the same shape as the `Resolution` step 3 removed. A
  deletion that removes a field should check whether the container still earns itself.
- `app/newgame.py` folded into `app/registry.py`.
- `state/trace.py`: no `TraceEntry` is serialised since step 5, so the Pydantic discriminator
  went. `Applied.entry` was only ever read as a display label.
- The Mara/Elena line restored to `elena.brief`.
- A per-role `max_input_tokens` ceiling (`RoleConfig`, default 96k) checked before each model
  call in `run_turn`. `UsageLimits(count_tokens_before_request=True)` cannot do this here:
  `OpenAIChatModel` — the only model class aidm builds — inherits `Model.count_tokens`, which
  raises `NotImplementedError`, and the one override that exists (`OpenAIResponsesModel`) needs
  a network call. The guard estimates locally at 4 chars/token instead.

Not applied, still on the bone: the duplicated `transact` call in `session.py::preview` and
`apply_proposal`, and two pass-through re-exports (`FileStore.load`'s double read was fixed in
phase 2). `docs/ui-mock/index.html` still specifies a "Known memories" panel and a
`WORLDKEEPER` pipeline stage, and `docs/ui-mock/README.md` still describes an "Engines"
authoring step producing per-engine overlays; both files are the accepted Phase 5 UI reference.

Offline gate green throughout: 195 passed, ruff check, ruff format --check, basedpyright 0/0/0.
`src/` went 7,565 -> 7,277 lines across 65 files, a 3.8% reduction. Step 2 is 70% of it: the
memory deletion bought roughly a second off a 5.6s turn, and 192 lines came along. On tokens it
is a wash — the unbounded window overtakes the deleted round-trip's cost around turn 11, which
is what the new ceiling now fails loudly on.

### Phase 2 — the locked cuts

- Step 1 — save versioning gone. `SAVE_VERSION`, both `save_version` fields and the
  `FileStore.shell` version gate are deleted; `SavedGame`'s `extra="forbid"` is the whole
  compatibility gate, so a stale save now fails at resume rather than at listing. `SaveShell` stays
  for the launcher's tolerant partial read. `FIXTURE_SAVE_VERSION` and its test went with it; the
  state/save fixtures each lost one line and nothing else.
- Step 2 — the hook subsystem is gone; a consequence is authored text on the entity that triggers
  it. `state/hooks.py`, `Hook`, `WorldState.hooks`, `fired_hooks`, `ExpansionPatch.hooks`,
  `ScenarioPatch.hooks` and the `hooks` turn step are deleted; both shipped scenarios converted
  their hooks into `detail.when_reached` in the same commit. The Director now sees `detail` for
  every entity it is shown — here, elsewhere, hidden, and carried — so a consequence stays visible
  until acted on instead of firing once on discovery.
  - The Narrator stays blind for free: `VisibleScene.of` runs `_undetailed`, so every entity it
    holds carries `detail=None` and `_detail()` renders nothing. That is why `_scene_sections` and
    `_character` could turn detail on for both audiences at once.
  - A turn is interpreter -> director -> narrator. With hooks gone every remaining fact narrates,
    so `test_pipeline` now pins `outcomes == tuple(fact.trace for fact in facts)` rather than a
    strict-inequality count.

- Step 3 — a scenario overlay is optional enrichment; every scenario plays under every engine. An
  NPC with no authored mechanics gets a default sheet, exactly as a play-created one does.
  `_playable` split into `read_scenarios` / `read_characters` — they no longer share a rule, and
  the character half keeps the overlay probe because the player's own sheet is the point of
  creation. Generated scenarios ship no overlay at all: `TypedOverlay`, `overlay_agent`,
  `authored_overlay`, `ask_until_playable` and `scenario_overlay.md` are deleted, so authoring is
  one agent instead of one plus one per engine.
  - `Playtest.check` lost its overlay parameter with them; `load_scenario` still validates a
    hand-authored overlay file, which is where that check belonged all along.

- Step 4 — `ExpansionPolicy` is `closed | open`. `open` is the old `cited_or_invented`
  generalized: `OpenSource` searches the document where one exists and answers from the premise
  where it is silent, which subsumes `cited` and `invented`, so `WholeSource`, `read_source` and
  `require_source` are gone and `open_source` is a two-branch function. Deliberately lost: the
  strict `cited` refusal, and the "premise reaches the Expander whole" path — an `open` scenario
  with no document now prefixes the premise with the `SILENT` line, which is the same text the
  fallback always used.
  - `OpenSource.document` defaults to `RecordSource(records=())`, so no caller builds a null
    object; `premise` had to move first for the dataclass default to be legal.

### Phase 2 review pass

An adversarial review of the staged phase found two live prompt bugs and four dead shapes. All
applied:

- `interpreter.md` still told the Interpreter it is shown "what is remembered". Phase 1 deleted
  memories and fixed the identical phrase in `director.md`, missing its twin one file over — both
  golden `instructions/*/interpreter.txt` carried it for a whole phase. A prompt still naming a
  deleted concept is a live bug, not a doc nit: grep every `prompts/*.md` when a concept dies.
- "SCENARIO NOTES" is now "NOTES FROM THE RULES". Hooks were the only scenario-authored writer of
  `pending_notes`; what is left is engine mechanics alone — loner3e twist and defeat, 24XX bad
  luck — so the Director was told "instructions from the scenario" and handed "Bad luck has caught
  up with them".
- `read_scenarios` called `content_id(path.name)` outside its own `try`, so a directory named
  `whispering-vault copy` still took down the home screen — the exact case its comment claimed to
  cover. The `yield` stays outside the `try` deliberately: a `ValueError` raised by the consumer
  while the generator is suspended must not read as a bad scenario.
- Two dead flags and a dead alias: `read_scenarios`' `engines` parameter (pure pass-through once
  every scenario played under every engine, so `Playable` collapsed with it), and `_entities`'
  `ids`, which threaded through eight functions with no caller ever passing `False` — the same
  shape as the `detail` flag step 2 had just removed. A deletion that makes one flag constant
  should check its neighbours.
- `FileStore.load` parsed the save twice: the inner `shell()` call existed only for the version
  gate step 1 deleted. Phase 1's review had parked this as "still on the bone"; step 1 removed its
  last defence.
- `scenario_world.md` still told the author rules mechanics are "authored separately"; after step
  3 nothing authors them at all.

### Phase 2 follow-on — a hook reaches the Director when it becomes actionable

The Director's prompt is rendered once, from a `SceneSnapshot` taken before its tool calls; every
result after that is a `- {fact.trace}` line. So an authored consequence was only ever readable at
the top of the turn, and Expander-written canon's `detail.when_reached` was invisible for the
whole turn it was created in. Two additions, both riding the return channel `pending_notes`
already used:

- `transact.act` appends `_reached(...)`: the `detail.when_reached` of every entity the call
  discovered. That is what the `open-the-way-and-climb` and `take-the-chart` eval cases need —
  `reveal`'s own result now hands back the thread advance at the moment it applies.
- `expansion.written` gives each materialized entity its `when reached` line, not just id, kind
  and name.

This is not the hook subsystem returning. A hook changed state deterministically at a moment the
fiction had not reached; this tells the Director at the moment it has, and the Director still
decides. No fixture moved — tool return strings are not recorded in the turn trace.

It was not enough on its own: `take-the-chart` and `open-the-way-and-climb` still scored 0/9, and
the causes were all in the authored text, not the code.

- **The Interpreter was never told what a hook is.** Phase 2 added the hook rule to `director.md`
  only. The Interpreter decides the turn's mechanics, sees the `when reached:` line, and has
  `advance_thread` in its vocabulary — but with no rule it planned `reveal, move`, and
  `director.md` orders plan fidelity ("never drop a step, never put a different mechanic in its
  place"). The consequence has to survive both roles now; only one of them knew about it.
- **Every converted hook read "do the fiction thing, *and* advance the thread"**, so the advance
  read as conditional on something the turn had not finished. They now lead with the unconditional
  consequence and put the steering after. Written into `scenario_world.md` and `expander.md` so
  generated scenarios inherit the rule.
- **A stage was being advanced to before it was true.** `archivist-found` is new: the old hook
  jumped `vault-seal` to `rite-known` the moment Elena is *seen*, skipping the whole negotiation —
  exactly the IDEAS.md complaint, which determinism had hidden. The Director declining to advance
  was correct judgment scored as a miss. `take-the-chart` needed no such change: having the chart
  *is* the stair being charted, so its `stair-charted` expectation stands untouched — which makes
  it the clean signal for whether the Interpreter rule was the real cause.
- **The conversion had invented canon.** `EntityDetail.description` is required and these entities
  had `detail: null`, so phase 2 made descriptions up; the `vault_map` one named where the stair
  is, answering a later beat. Rewritten to what each entity's own `brief` supports. A required
  field turns a mechanical conversion into an authoring act — watch for it.

Offline gate green throughout: 185 passed, ruff check, ruff format --check, basedpyright 0/0/0.
`src/` went 7,277 -> 7,006 lines across 64 files, a 3.7% reduction on top of phase 1's 3.8%.
Two smoke checks beyond the suite: both shipped scenarios begin under both engines, and
whispering-vault with its `loner3e.json` renamed away still starts, on default sheets.

`EntityDetail.hook` was later renamed to `EntityDetail.when_reached`: it collided with the
deleted `Hook` model and with "hook" in the software sense, and the new name states the trigger
the Director prompt already used.

## Next

- Manual verification neither phase has had: one live `evals/turn_eval.py` run and `uv run aidm` —
  three turns of each scenario, watching a converted `detail.when_reached` land at a sensible
  moment and an `open` scenario expand. PLAN.md still holds both phase sections; move them out
  once that passes.
- Re-run the eval. `take-the-chart`'s `stair-charted` is the clean signal: its expectation never
  moved, so if it recovers, the Interpreter `when reached` rule was the cause.
  `open-the-way-and-climb` now expects `archivist-found`. Watch the other direction too — a hidden
  entity's `when reached` text is visible to the Director every turn, so it may advance a thread
  before the player reaches it, guarded only by prose in `director.md`.
