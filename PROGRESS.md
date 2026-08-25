# Refactor progress

Tracking `PLAN.md`. One line per numbered step; only what is done or in flight.

## Phase 0 — Free deletions — DONE (`920d5c9`)

- Shipped before this log started. `TurnRecord.steps`, `Advancement.id` gone; `Slug` lives in `config.py`.

## Phase 0b — Delete `CharacterOverlay` — DONE (`69f0a2c`)

- [x] 1. `Character.rules` / `CreatedCharacter.rules: dict[str, JsonValue]`; `CharacterOverlay` deleted.
- [x] 2. `characters/kael/{loner3e,twentyfourxx}.json` unwrapped (one nesting level gone).
- [x] 3. Six readers updated: `content/io.py`, `app/launch.py`, `ui/create.py`, both engines' `create()`.
- [x] 4. Suite green: 259 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.
- Net: −10 lines in `src`; `io.py` gained `_read_text` so the rules dict and the models share the missing-file error. Rules read with `json.loads` and validated by `Character` itself; written with `json.dumps`.

## Phase 1 — Typed facts and resolver-built events — DONE (staged, uncommitted)

- [x] 1. `MechanicEvent.source` deleted. Save format changed on purpose: `Exchange.events` no longer
      carries it, so old saves fail loudly.
- [x] 2. `Fact.narrator: str | None` -> `Fact.told: bool`; `narrator_lines` reads `fact.trace`.
- [x] 3. `Fact.entity_id: EntityId | None` promoted to a field; `_seed_created` and `_reached` read it.
- [x] 4. `Chip` folded into `MechanicEvent`; `Fact.chip` -> `Fact.event`. `EventBadge`/`DiceEvent`/
      `MechanicEvent` moved from `state/play.py` to `state/facts.py` (play imports facts, so the
      event types had to sit under the cycle). `Engine.player_events`, `EventCause` and both engine
      overrides deleted for the free `facts.player_events(facts)`.
- [x] 5. Composite events built in their resolvers: `resolve_question` attaches the Oracle card,
      `_twist` the Twist card, `resolve_attempt` the Attempt card, `resolve_luck_test` the Luck Test
      card. `question_events`, `_twist_event`, `attempt_events`, `luck_test_events`, `_skill_badge`,
      `_help_badge`, `_hindered_badge` deleted.
- [x] 6. `Fact.data` deleted with every reader: `dice_event`, `counter_effect`, `_ints`,
      `dice_by_slot`, `require_dice_slot`, `chipped`, `explained_fact`'s `data` argument.
      `roll_pool(..., slot=)` -> `roll_pool(..., label=)` returning `(DiceEvent, Fact)`.
- [x] 7. Tests and `evals/turn_eval.py` read the typed fields; `tests/twentyfourxx/test_twentyfourxx_events.py`
      lost `test_an_answered_stake_shows_the_same_attempt_card_as_the_tool` (with `source` gone the
      two causes are identical by construction).
- [x] 8. Golden fixtures regenerated. The diff is facts-only: `narrator`/`data`/`chip` out,
      `told`/`entity_id`/`event` in, and `source` off the saved `Exchange.events`. No `narration`,
      no `prompt` and no `output` key moved — the turn plays exactly as before.
- Suite: 258 passed, ruff clean, basedpyright 0 errors. `src` 8,638 -> 8,392 lines (-246).

Decisions taken inside the phase:

- `adjust`/`spend`/`counter_fact` take an `icon` and always attach the counter's card; `chipped` is
  gone. The Oracle card absorbs the exchange's cards into its `effects` and strips them, so a
  conflict still shows one card, not four.
- Behaviour changed on purpose, one case: a standalone `roll_luck_test` that comes up clear now
  shows no card. It used to show the die with an empty outcome, which was the one card that did not
  pass the narrator gate. Invariant 3 says cards pass that gate, so the gate won.

## Phase 2 — One turn envelope, notes taken not sliced — DONE (staged, uncommitted)

- [x] 1. `Game.take_notes()` replaces the saved index. `SceneSnapshot.from_game(state, notes=())`
      takes its notes instead of reading `world.pending_notes`; only the director's snapshot in
      `run_segment` passes any (`draft.take_notes()`), the narrator's and `player_scene` take the
      default. Both `shown = len(...)` locals and the builtin slice are gone.
- [x] 2. `close_segment(draft, prompt, lines, events)` in `turn/run.py` owns the `Exchange` append,
      the turn bump and `committed()`. `run_segment` and `Harness.end_turn` both call it; neither
      passes `place` or `decision` — it reads both off the draft.
- [x] 3. Stopped there: no shared turn object across the two harnesses.
- Suite: 258 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.

Decision taken inside the phase: `mcp.py`'s notes bookkeeping was left alone here (it passed
`state.world.pending_notes` explicitly, behaviour unchanged) rather than half-moved to `take_notes`
against committed state. Phase 2b moves the take to `start_turn`, which is where it belongs.

## Phase 2b — One way into a turn in code mode — DONE (staged, uncommitted)

- [x] 1. `start_turn(prompt, option_id=None)` drafts, calls `consume_answer` with the three shapes
      it already tells apart (bare string / `Answer(option_id=)` / `Answer(text=)`), takes the
      notes, commits, and opens `Turn`. It returns the same picture `scene()` returns, with the
      player's action rendered under PLAYER ACTION, plus what a closed answer resolved.
- [x] 2. `answer_decision`, `AnswerDecision` and `ACTION_IS_IN_THE_CHAT` deleted. `Answer`'s own
      "an option or text, never both" validator is the only copy left; `_unavailable` names
      `start_turn`.
- [x] 3. `end_turn(lines)` only — the prompt comes off `Turn`, so it cannot disagree with the
      scene. `Harness.turn` is `Turn | None`; `started()` refuses `end_turn` and every director
      tool with a `ModelRetry` naming `start_turn` when no turn is open.
- [x] 4. `Turn.notes` holds what `take_notes` took; `scene()` renders those first and whatever
      `world.pending_notes` holds now, so a compaction mid-turn still reads the rules notes.
- [x] 5. `PREAMBLE` and steps 4-6 of `playing-aidm/SKILL.md` are now
      `start_turn(message)` -> director tools one at a time -> `end_turn(lines)`.
- Suite: 259 passed (one new test: no tool runs a turn before `start_turn` opens one), ruff clean,
  basedpyright 0 errors. No golden fixture moved — code mode is not in them.

Adversarial review pass (fable), on top of both phases:

- `consume_answer` pops `draft.pending` itself. Both callers ran the identical pop-and-comment
  before calling it, where forgetting the pop let a decision survive its own answer.
- The resumed-decision section is rendered once, by `render_director`'s own `resumed=` parameter,
  so code mode places it where builtin does instead of appending its own header.
- `render_director as render_scene` alias and `_player_input` deleted: `Answer(text=prompt)` with
  nothing pending already behaves exactly as a bare string inside `consume_answer`.
- Rejected after pricing: an `open_segment` beside `close_segment` (the shared head is four
  one-line calls that cannot drift, and an extractor would return six values); merging `Turn` into
  `DirectorContext` (per-turn vs per-call draft lifetime — the merge would reintroduce the bug the
  fresh-draft-per-call rule prevents); an always-present `Turn` with a sentinel prompt.
- `src/aidm` ends at 8,389 lines, below the 8,392 the two phases started from.

Decisions taken inside the phase:

- `scene()` survives as the compaction path only. With no turn open it renders
  `NO_TURN_OPEN` under PLAYER ACTION rather than refusing, because the growth-due notice and the
  picture are both worth reading between turns.
- Listing tools needs no open turn (`_director_tools` falls back to a throwaway `Turn`): gating
  reads committed state, and a driver must see what is offered before it opens anything.
- A second `start_turn` while one is open replaces it, discarding that turn's uncommitted cards.
  Left as is: the driver's escape hatch is `scene()`, and a guard here would block recovery.

## Phase 3 — One authoring driver — DONE (staged, uncommitted)

- [x] 1. `AuthoringRun` is the single holder: `settings`, `draft`, `playing`, `brief`, `toolset`,
      `prompt`, `history`, `busy`, plus `send()` and `refusal()`. `GrowthRun` still adds `base` +
      `patch()`, `ScenarioRun` still adds `slug`/`premise`/`document`/`engines` + `write()`.
- [x] 2. The agent is a `cached_property` on the run, not a field: builtin builds one on its first
      `send`, code mode never touches it (and may hold no api key, which `Settings.role` refuses).
      Replaces the plan's `agent: Agent | None`; nothing has to pass or check a None.
- [x] 3. `AuthoringSession` deleted. `ui/create.py` builds a `ScenarioRun` through `scenario_run`,
      which gained keyword-only `brief` (the form's "how much to author" select is its own control,
      not `grows`) and `art_style`. Both survivors of the move are on `ScenarioRun`: `busy`, which
      the UI binds to and nothing else reads, and `write()`'s form-style override plus its refusal
      check.
- [x] 4. `author_extension` deleted. `GameSession._extend` is now `growth_run(...)` ->
      `await run.send(run.prompt)` -> `apply_growth(run.patch())`, the three lines code mode runs.
- [x] 5. The draft trio (`ScenarioDraft`, `ScenarioPatch`, `ExtensionPatch`) left alone.
- [x] 6. `growth_run`/`scenario_run` return the bare run. Only `mcp.py` wanted the briefing string
      and it holds everything that builds one, so `_briefing` is public `briefing` and MCP calls it.
      The field is `opening_prompt`: it is sent once, every later `send` takes a fresh instruction.
- `tests/core/test_extension.py`'s `_stub_author` now stubs `GrowthRun.send` and writes the crypt
  and the way into it, so the real `growth_run`/`extension_patch`/`apply_growth` path runs under it,
  `_added_exit` included.
- `authoring.py` 713 -> 673 lines.

## Phase 4 — A sheet-shaped engine base — DONE (staged, uncommitted)

- [x] 1. `src/aidm/engines/sheets.py` holds `SheetEngine[S: SheetBase]` with `check_overlay`,
      `opening_mechanics`, `validate` and `seed` written once. Both engines are
      `SheetEngine[Sheet]` with `sheet_type` beside `mechanics_type`; `Loner3eEngine.validate`
      calls `super()` and keeps its pack check.
- [x] 2. `Advancement.earned` is concrete in core (`SheetMechanics.of_game(state).completed`);
      both overrides and the `@abstractmethod` gone.
- [x] 3. The whole sheet family moved to `sheets.py`: `SheetBase`, `SheetMechanics`,
      `complete_chapter`, `actor_sheets`, `check_sheets`, `require_sheet`, `render_counters`, and
      `SheetAdvancement`, which is where the concrete `earned` went. `Advancement.earned` in core
      stays abstract, so `grep -n Sheet src/aidm/engines/core.py` returns nothing and the flow is
      one-way, `sheets -> core`. Both engine advancements subclass `SheetAdvancement`.
- Suite: 259 passed, ruff clean, basedpyright 0 errors. No fixture regeneration needed.
  `src/aidm` 8,389 -> 8,347 lines; `engines/core.py` 445 -> 415.

Decisions taken inside the phase:

- The counter helpers (`pool`, `counter_fact`, `adjust`, `spend`) stay in `core.py`: they are
  written on an entity, not on a sheet, and `Advancement.resolve` is their caller.
- `describe` did not move. The plan's rule is "identical modulo one named ClassVar", and the two
  bodies differ by a second name too: each engine's own `describe_entity`. Moving it would trade
  one 2-line method for a callable ClassVar in every engine.
- `SheetEngine` narrows `Engine.mechanics_type`, which pyright reads as an invariant mutable
  attribute. One narrow `reportIncompatibleVariableOverride` ignore, rather than making `Engine`
  generic and spelling a type argument at ~30 call sites that do not care.
- `seed` orders itself as the plan spelled out: the default sheet lands first, then
  `advancement.ledger(...).current` is brought level with `completed` (skipped when an engine has
  no advancement). `test_an_actor_seeded_after_an_adventure_is_not_owed_the_growth_they_missed`
  pins it.

Adversarial review pass (fable), on top of both phases:

- It found one real regression and it was mine: the rewritten `_stub_author` left `apply_patch`'s
  `_added_exit` branch with no test driving it. Fixed above.
- The `core -> sheets -> core` cycle had a better answer than the deviation I took. Concrete
  `earned` on core's `Advancement` was the only thing holding the vocabulary in `core.py`;
  `SheetAdvancement` in `sheets.py` dissolves it, and both `rules.py` stop split-importing sheet
  vocabulary from two modules.
- Nothing deleted: every comment and docstring in the diff is a one-line why. `SheetAdvancement`'s
  own docstring, added by the move, went — it restated its one-line body.
- Rejected: refusing `grows=False` with an opening-slice brief. The combination authors an opening
  of a world that will never grow, but the two form controls predate this work and the rule was not
  asked for.
- Deviations that stand: `describe` (differs by a second name, each engine's `describe_entity`,
  which the plan's own rule refuses to move) and the `reportIncompatibleVariableOverride` ignore
  (the alternatives are a generic `Engine` spelled at ~30 indifferent call sites, or a weaker
  `of_game` engine-mismatch check).

## Phase 5 — Config roles and a flat `stake_attempt` — DONE (staged, uncommitted)

- [x] 1. `Roles` replaces `roles: dict[Role, RoleConfig]` + `ROLE_DEFAULTS` + the `model_fields_set`
      merge: four named fields with their own defaults, and a `for_name` match mirroring
      `Providers.for_name` in the same file. `extra="forbid"` keeps the "a role no stage is built
      for is refused" test passing. Env var names are unchanged —
      `nested_model_default_partial_update=True` already made `ROLES__DIRECTOR__MODEL=x` keep the
      director's other defaults.
- [x] 2. `StakedAttempt(Attempt)` carries `risk`, so `stake_attempt(ctx, attempt)` is one model
      argument and pydantic-ai inlines it. `_with_skills` lost its `inside="Attempt"` branch, and
      `with_enum` lost the `inside` parameter with its `$defs` branch. `resume` and `check_pending`
      validate the stake payload as `StakedAttempt` — `Frozen` forbids extras, so `Attempt` would
      now reject the saved `risk`.
- [x] 3. `Attempt.goal` is "The actor's goal, in one line." A staked attempt no longer asks for the
      risk twice in two places that could disagree.
- [x] 4. `tests/core/fixtures/schemas/twentyfourxx/director_tools.json` regenerated: 12,321 ->
      11,740 bytes. `stake_attempt` loses its `$defs`/`Attempt` nesting and gains a flat `risk`,
      both `goal` descriptions shorten. Two side effects of flattening, both shared with every
      other single-model tool: the `attempt:` docstring line no longer reaches the schema (it
      still satisfies `require_parameter_descriptions`), and the schema gains
      `title: StakedAttempt` plus `minLength` on `risk`.
- Suite: 259 passed, ruff clean, basedpyright 0 errors.

Decisions taken inside the phase:

- `_enumerated` folded into `with_enum`. The plan kept it; with the `inside` branch gone it had one
  caller and one two-line body.
- `Settings.role` is `self.roles.for_name(name)`, not the plan's `getattr(self.roles, name)`: the
  match is the file's own idiom and returns `RoleConfig` instead of `Any`.
- `_keys_present` still checks only the roles the user configured — a role is configured when it
  differs from its default. `model_fields_set` cannot say: one `ROLES__*` env var makes
  `nested_model_default_partial_update` fill all four. Checking all four unconditionally would
  refuse to build `Settings` on a keyless install, which the app supports up to the first agent
  build.

- [x] 5. Eval run (`evals/results/after-stake-flatten.json`): 98/99, 0 errors. Against
      `baseline-interruptible`, the newest stored run, score 97% -> 99%, director_calls
      1.22 -> 1.19, 13.8s -> 11.7s per case. Not a clean before/after for the flatten alone — that
      baseline predates phases 1-6 — but the shrunk schema costs nothing, and 24XX `risky-climb`
      scores 100% on `staked`, which is `stake_attempt` itself. The one miss is 24XX
      `open-the-way-and-climb` at 8/9, up from 7/9.

## Phase 6 — Split the three files that do two jobs — DONE (staged, uncommitted)

- [x] 1. `app/mcp.py` 711 -> 246, new `app/codemode.py` 491. The controller and its typed inputs
      (`ToolArgs` and every arg model, `Turn`, `Harness`, the prose helpers) are in `codemode.py`;
      the protocol (`ServerTool`, `SERVER_TOOLS`, `DISPATCH`, `PUBLISHED`, `AUTHORING`,
      `build_server`, `serve`, `main`) stays in `mcp.py`. `python -m aidm.app.mcp` is unchanged, so
      `.mcp.json` and `.codex/config.toml` needed no edit.
- [x] 2. `app/authoring.py` 673 -> 449, new `app/authoring_run.py` 250: the draft, the patches, the
      briefs and the refusals in the first; `authoring_toolset`, `scenario_agent` and the three run
      classes in the second. `_PROMPTS_DIR` and `_instructions` moved with them — the two functions
      that call them both moved.
- [x] 3. New `engines/packs.py` (50 lines) holds `PackName`, `pack_step`, `pack_paths`,
      `load_packs`. `engines/core.py` 372 -> 328 and lost eight imports with them (`logging`,
      `Mapping`, `fullmatch`, `Protocol`, `BaseModel`, `ENCODING`, `CreationOption`,
      `CreationStep`).
- Suite: 259 passed, ruff clean, basedpyright 0 errors. No golden fixture moved, which is the
  proof the moves were pure. `src/aidm` 8,347 -> 8,401: three new import blocks cost more than
  Phase 5 deleted.

Decisions taken inside the phase:

- `Harness.offered` and `Harness.call` became module functions in `mcp.py` taking the harness.
  Keeping them methods would have made `codemode.py` import the `ServerTool` table, and the
  dependency has to run one way: transport -> controller. `tests/core/test_code_mode.py` calls
  `call(harness, ...)` accordingly.
- Three names crossed the new boundary and lost their underscore: `director_tools`,
  `authoring_context`, `catalogue`. Nothing else in `Harness` is read from outside.
- `tests/core/test_package_boundary.py` was NOT updated, against the plan's instruction: its
  `FORBIDDEN` table is keyed by package (`app`, `engines`), so all three new files are already
  checked. Only a new *package* would need a row.

## Adversarial review pass (fable), on top of phases 5 and 6

- One real regression, found and fixed: `_keys_present` read `Roles.model_fields_set`, which
  `nested_model_default_partial_update` fills for all four roles as soon as one `ROLES__*` env var
  is set. `ROLES__DIRECTOR__PROVIDER=local` on a keyless openrouter — a local-only install — was
  refused at load, blaming `narrator`. Now a role is checked when it differs from its default;
  `test_configuring_one_role_does_not_key_check_the_others` pins it.
- `authoring_context` moved from `codemode.py` to `authoring_run.py`, beside the toolset it builds
  a context for. `mcp.py` stops reaching into the controller for an authoring helper.
- `offered`'s local `tools_offered` is `tools` again; the director tools it merges are `director`.
- Deleted: the `extra="forbid"` why on `Roles`, already said on the `Role` Literal above it.
- The `Args:` sections on the 24XX director tools look dead — their text never reaches the
  published schema — but `require_parameter_descriptions` refuses to build the schema without
  them. Deleting them fails 59 tests. Left alone.
- Rejected: `getattr(self.roles, name)` in place of `Roles.for_name` (needs a `cast`, breaks the
  `Providers.for_name` idiom, and `_keys_present` is now its second caller); deleting the role loop
  in `_keys_present` and failing at first agent build instead (loses the fail-at-load invariant);
  moving the `ToolArgs` models to `mcp.py` (the `Harness` methods consume them, so it would reverse
  the import direction); re-merging `authoring_run.py` (`authoring.py` now imports no pydantic-ai
  or llm machinery at all, and `runtime.py`/`ui/create.py` each pull only their own side).
- Suite: 260 passed, ruff clean, basedpyright 0 errors.
