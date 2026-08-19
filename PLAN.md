# Plan

The phased plan for what is built next, in order. Shipped phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted. `tests/core/test_golden_state.py` pins `FIXTURE_SAVE_VERSION` —
   bump both or the suite catches you.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 1 — drastic simplification, same vibe

Folds OPINION-1/2/3 into one ordered sequence. Opinion 2.4 (flatten the effect unions) is
subsumed by step 3, which deletes the unions outright. Roles stay separate (Opinion 2's
constraint); Opinion 1's rejected items stay rejected. Untouched throughout: Entity's three
kinds, `Trait`, `Counter`, `Thread`+clock, the `VisibleScene` leak boundary, draft/commit
transaction discipline, overlay validation, save versioning (refuse, never convert), packs,
advancement, both engines' rule math, the Worldkeeper role.

Every step: one commit, full suite green, and — when persisted bytes move — SAVE_VERSION +
FIXTURE_SAVE_VERSION bumped and `save/state/turn` fixtures regenerated per working rule 1.

### 1. Delete dead pass-throughs and the dynamic registry — ~1 h

- `Fact.source` (`state/facts.py`) is `"core"` everywhere and never read: delete the field, the
  `CORE` constant, and every `source=CORE` argument.
- `Resolution.outcome` (`state/beat.py`) and `Transacted.outcome` (`engines/transact.py`) are read
  by no production code: delete both, drop the `outcome=` pass-through in `Engine._play`, and
  point tests at the roll fact's `data["outcome"]` instead.
- New `src/aidm/app/registry.py`: `ENGINES: tuple[...] = (Loner3eEngine, TwentyfourxxEngine)`
  imported statically, plus `engine_class(engine_id)` and `engine_ids()` doing a linear lookup
  with the same "unknown engine" ValueError. Rewire `app/session.py`, `app/launcher.py`,
  `app/authoring/playability.py`, and tests to it. Delete `engines/registry.py` and the
  `ENGINE = <class>` line at the bottom of both `rules.py`. In
  `tests/core/test_package_boundary.py`, `test_only_the_loader_names_a_concrete_engine` now
  expects exactly `{"app/registry.py"}`.

### 2. Shrink Hook and Memory — ~half day

- `Hook` (`state/world.py`) becomes one concrete shape:
  `Hook(id, on_discover: EntityId, note: str = "", reveals: tuple[EntityId, ...] = (),
  advance_thread: AdvanceThread | None = None)`. Delete `FactMatch`/`DiscoveryMatch`/
  `ThreadMatch`, `HookMatch`, `Hook.effects`, `Hook.once`, and `state/effects.references()`.
- Rewrite `state/hooks.py`: a hook fires when an `entity_discovered` fact's `entity_id` equals
  `on_discover` and the hook is not in `fired_hooks`. Firing = `draft.reveal()` each entity in
  `reveals`, apply `advance_thread` via the existing resolver, append `note` to
  `pending_notes`. Keep the bounded-rounds loop (a reveal may fire the next hook).
- In `content/authored.py` replace `_hooks_wait_on_authored_ids`, `_hook_effects_are_sound`, and
  `_no_hook_domino` with one validator: every id a hook names (on_discover, reveals,
  advance_thread.thread_id) exists in the authored world.
- `Memory` loses its slug: `Memory(owner: EntityId | None, text)`;
  `WorldState.memories: list[Memory]`. In `turn/pipeline.remember()` keep the casefolded-text
  dedupe, drop `text_slug` there (it stays — character creation uses it).
- Update both `scenarios/*/world.json`, the Expander prompt/`ExpansionPatch.hooks` docs, tests.
  Expected behavior change: drowned-road's `key-discovered` hook loses its two `relation-change`
  effects (unlock + reveal of the chapel→crypt way) — fold them into its `note` ("…the way to
  the crypt can now be revealed and unlocked"); unlocking becomes Director-steered, which is
  Opinion 3's design, not a bug. Persisted bytes move: bump + regen.

### 3. Tool-calling Director — ~2–3 days, the core of the phase

The Director runs once per turn with tools instead of one structured beat per call. The pattern
already exists: `expansion_toolset` in `turn/agents.py` — `Tool(fn, sequential=True)`, trial-copy
validation, apply to the turn's draft through resolver code, `ModelRetry` on refusal.

1. **Probe first** (working rule 2): raise the director's `ROLE_DEFAULTS` in `config.py`
   (max_tokens 8192, reasoning_effort medium), build the current Director with
   `output_type=str` and a FunctionToolset carrying two draft tools (`roll_question`, `move`),
   run one live turn, and confirm gpt-oss-120b calls tools and reacts to the returned dice.
   Only then start fixture work.
2. **Shared plumbing** in a new `turn/tools.py`: generalize `Expansions` into a `TurnLog`
   (facts + steps, same cap for expansions). Extract from `engines/transact.transact()` an
   `apply_to_draft(engine, draft, resolve)` helper: resolve → `fire_hooks` → `_seed_created` →
   `engine.validate`, no commit. Every tool body: refuse via `check_draft` on a throwaway copy,
   then run `apply_to_draft` against `ctx.deps.state`, extend `TurnLog.facts`, and return the
   facts' `trace` lines plus any new `pending_notes` — that return is how the model reacts
   in-run without being re-prompted.
3. **Core tools**, one function per op in `state/effects.py` — `move`, `reveal`,
   `gain_improvised_item`, `add_trait`, `remove_trait`, `advance_thread` — plus the final
   relation vocabulary directly: `unlock_exit`, `join_party`, `leave_party`, and a thin
   `reveal_way` (bodies over the existing `_relation_change` modes; step 5 rewires three of
   them to exits and deletes only `reveal_way`). No 4-mode `change_relation` tool is ever
   built. The typed signature is the schema: copy each op's fields and Field descriptions
   onto the function parameters; the body calls the existing resolver in
   `state/apply_effects.py`. Rewire `expand_world` from `transact` to `apply_to_draft` and
   delete its mid-turn commit (`landed.state`).
4. **Engine tools**: repurpose the existing `Engine.director_toolsets` attribute
   (`engines/engine.py`, already consumed by `director_agent` and rendered into
   `director_tools.json`) — widen its deps typing to `PlanContext`; do not add a second
   mechanism. loner3e: `roll_question(actor_id, question, position, edge, opponent_id)`,
   `restore_luck`, `end_adventure`. 24xx: `roll_attempt(...)`, `roll_luck_test`,
   `change_credits`, `complete_job`. Bodies call the existing `resolve_*`/`apply_*` functions
   unchanged; a roll tool's return includes outcome, dice, and any twist/defeat note.
5. **Switch the pipeline**: `director_agent` gets `output_type=str` (the closing text goes in
   the step trace, nothing reads it), toolsets = core + engine + expand, no output validator.
   `run_turn` makes one `director.run` on the turn draft with
   `UsageLimits(request_limit=<one constant>)`; evidence for Narrator/Worldkeeper comes from
   `TurnLog.facts`. The Worldkeeper's `remember()` applies via `apply_to_draft` on the same
   turn draft — no more `transact` → `reported.state.draft()` cycle; the turn's single
   `committed()` stays at the end. Shrink `TURN_STEPS` to
   `("director", "hooks", "narrator", "worldkeeper")` (it feeds `GameSession.role_names` and
   the UI progress ring); update `test_pipeline`'s QUIET_STEPS assertion and
   `test_golden_turn`'s pinned step-name sequence.
6. **Prompts**: rewrite `turn/prompts/director.md` and both engines' `director.md` for a tool
   loop (call tools for everything that happens; end with a short wrap-up; empty turns are
   fine). Regenerate prompt/schema/turn goldens — `director_tools.json` now carries the whole
   vocabulary.

### 4. Delete the beat machinery — ~half day

Dead after step 3; this commit removes it and moves the docs.

- `turn/pipeline.py`: `_run_beats`, `_ask_director`, `BeatRun`, the `happened`/`preface`/
  `settle` plumbing. `state/beat.py`: `Followup`, `Resolution.followup`, `BEAT_DOC`,
  `BEAT_ROLL_DESCRIPTION`, `BEAT_EFFECTS_DESCRIPTION` (keep `Resolution` and `check_draft`).
  Also `Transacted.followup` (`engines/transact.py`) and `PlanContext.settle`
  (`turn/agents.py`).
- `engines/engine.py`: `beat_type`, `unpack_beat`, `check_beat`, `resolve_beat`, `_play`,
  `resolve_roll`, `apply`, `_worked_plans`, `WORKED_PLANS`, `SETTLE_REFUSAL`. `Engine` shrinks
  to id/badge/dirs, sheet + mechanics types, `begin/validate/seed/new_sheet`,
  `describe`/`sheet_view`/`renderer`, `toolsets`, advancement, creation.
- Per engine: the `*Beat` model, the effect unions (`Loner3eEffect`, `TwentyfourxxEffect`,
  `TwentyfourxxRoll`), `examples.json`. Core: the op classes in `state/effects.py`, `WorldOp`,
  `WorldEffect`, `is_world_op`, the `apply_effect` match dispatch (tools call the `_`
  functions directly — unprefix them). `prompts/beat.md`, `prompts/settle.md`, `BEAT`/`SETTLE`
  constants, `Settings.max_beats`, `schemas/*/beat.json` fixtures.
- CLAUDE.md + AGENTS.md: "in the turn loop tools are read-only lookups, with one exception"
  becomes "turn-loop tools mutate only the turn's draft through resolver code".

### 5. Delete Relation — ~1 day

- `Exit(to: EntityId, known: bool = False, locked: bool = False)` in `state/world.py`;
  locations get `Entity.exits: list[Exit] = []` (validator: only locations have exits).
  Exits are directional; authors write both directions. `WorldState.party: list[EntityId]`.
- Delete `Relation`, `RelationId`, `WorldState.relations`, `CONNECTED`, `PARTY_MEMBER`,
  `joins`/`touches`/`far_end`, `connections()`, `relation()`, `party()`, `_check_relation`,
  and the `reveal_way` tool. Rewire the bodies of `unlock_exit`/`join_party`/`leave_party`
  (built final in step 3) from relations to exits/party — their schemas do not move.
- Movement (`state/actions.py`): the player moving through an exit that exists but is
  unknown auto-reveals it — the Director moving them IS the fiction revealing the way; a
  locked exit still refuses.
- Rewrite `_walk` in `content/authored.py` over exits; `turn/scene.py` deletes its own `Exit`
  model and projects the state one (the name joins at render time);
  `begin_game` writes `starting_party` into `world.party`;
  `ExpansionPatch.relations` becomes exit additions (new locations carry their own exits, plus
  `(location_id, Exit)` pairs to link back). Update both `world.json`, prompts, goldens.

### 6. One collection shape for worlds — ~half day

- `WorldState.entities/threads/hooks` become ordered lists (memories already are); validate
  unique ids in `_consistent_fiction`; `find`/`require`/`require_kind` go linear (worlds hold
  under ten entities). Update every `.values()` / `[id]` site.
- `ScenarioWorld` loses the `world` cached_property and its dict reconstruction: it validates
  ids unique and hands the lists straight to `WorldState`. `WorldDraft`
  (`app/authoring/draft.py`) uses the same lists. Persisted bytes move: bump + regen.

### 7. Shrink the Director's tool surface — ~1 day

The Director sees 13 tools (24xx) plus `expand_world`, every one of them present on every turn,
and their docstrings re-teach what `director.md` already taught. Four moves, each its own commit:
the schema stops duplicating the models, the vocabulary stops duplicating the prompt, a tool the
state makes impossible is absent rather than discouraged, and a closed value set is a closed value
set. Nothing here changes what a tool *does* — every resolver, refusal, and fact stays put.

1. **The action model is the parameter.** Pydantic AI flattens a tool's single model-like
   parameter: the model's own JSON schema becomes the tool's, with no `{"attempt": {...}}`
   nesting, and the model's class docstring becomes the tool description when the function has
   none (probed against 2.16.0 — `_function_schema._build_schema`). So `roll_attempt(ctx,
   attempt: Attempt)`, `roll_luck_test(ctx, test: LuckTest)`, `roll_question(ctx, question:
   Question)`, `advance_thread(ctx, advance: AdvanceThread)`: the eight-field reconstruction in
   each tool body goes, and the field descriptions move from the docstring `Args:` onto
   `Field(description=...)` on the model, where they are written once.
   `require_parameter_descriptions=True` still wants one `Args:` line for the model parameter
   itself; it never reaches the model.
   - Cross-field refusals (`Attempt._one_help_die`, `AdvanceThread._moves_something`) now surface
     as tool-argument validation, which Pydantic AI already retries — the step 3 note about
     building ops inside the play closure stops applying to these three, and the closures
     collapse to `act(ctx, lambda draft, rng: resolve_attempt(draft, attempt, rng))`.
   - `AdvanceThread.op` goes: it discriminates nothing since step 4, and as a tool parameter it
     would be a required literal the model has to type. It survives only in the `save`/`state`
     fixtures, so this is a bump + regen and no `world.json` edit.
   - Drop `unlock_exit.location_id`: a way is unlocked from where the player stands, so the
     resolver derives it. `actions.unlock_exit(draft, to_id)` reads `draft.player_location`.
2. **One owner per instruction.** Tool text is prompt tokens on every turn, and roughly 4.7k
   characters of it restates `director.md` and the engines' `director.md`. Establish the split
   and cut to it: director instructions own decision and sequence policy, engine instructions own
   system semantics, a tool description owns *when to call it and what it does* in a sentence or
   two, a field description owns the legal value alone, and the resolver owns the rule. Anything
   deleted from a docstring that is not already in a prompt moves into one — the step 3 lesson
   that `examples.json` was carrying instruction, not illustration, is the standing warning here.
   Regenerate `schemas/*/director_tools.json` and the `instructions/*` fixtures.
3. **A tool the state makes impossible is absent.** `AbstractToolset.filtered()` re-runs its
   predicate before every step, and `RunContext.deps.state` is the turn's live draft, so a tool
   that becomes possible mid-run appears mid-run. `core_toolset()` keeps returning the plain
   `FunctionToolset` (the golden schema pins the whole vocabulary); `director_agent` wraps it,
   with one name → `Callable[[GameState], bool]` mapping in `turn/tools.py`: `unlock_exit` needs a
   locked way out of here, `join_party` an actor here who is neither the player nor already in the
   party, `leave_party` a non-empty party, `advance_thread` an active thread, `remove_trait` a
   trait on the player, on someone here, or on what they carry. `expand_world` is filtered on
   `capped(log)`; its `ModelRetry` guard stays, because the cap is a cost boundary and a tool
   definition already in flight would otherwise walk through it. The engine toolsets are not
   filtered: `restore_luck` is the only engine tool a state ever forbids, and one predicate does
   not earn a per-engine mechanism.
4. **A closed set is an enum.** 24xx's `skill` and `helper_skill` are free strings the resolver
   refuses unless copied exactly off a sheet — the model is allowed to invent an invalid value and
   the turn pays a retry for it. The engine owns its own mechanics, so `twentyfourxx/tools.py`
   wraps its own toolset in `.prepared(...)` and writes `enum` onto those two properties of
   `roll_attempt`: `""` plus the skills on the sheets of the player and of every actor here.
   `test_golden_schemas._definitions` unwraps a `WrapperToolset` so the golden still pins the
   static vocabulary; one focused test covers the narrowing, and one covers the filtering in 3.

### 8. Separate runtime Game from SavedGame — ~1–2 days

- Runtime `Game` (rename of `GameState`): a plain dataclass, not a Pydantic model — its
  `mechanics` holds the engine's validated mechanics instance directly, and `SavedGame` is now
  the validation boundary. Delete `mechanics_as`, `set_mechanics`, `_flush_mechanics`,
  `_live_mechanics`; every `draft.mechanics_as(Mechanics)` becomes a typed read the engine
  narrows once.
- Strict `SavedGame` DTO next to `FileStore` (`content/store.py`): same fields with
  `mechanics: JsonValue`. The engine decodes mechanics once on load and encodes on save;
  `committed()` validates the world copy + `engine.validate` instead of a full dump/re-parse
  round-trip. Draft-per-turn lifecycle is already in place from step 3.

### 9. Split interpretation from execution — ~1 day

Folded in from PHASE-1-EVAL-IMPROV-PROPOSITION.md. The Director currently reads free-form player
intent, decides whether mechanics apply at all, decides whether the fiction is worth dice, picks
tools, sequences them, reacts to what they answer, and remembers the clauses it has not covered
yet — in one loop. `three-things` fails on exactly that load: the move and the handover land and
the third clause never becomes `add_trait`. One cheap structured call ahead of it takes the first
half of that job.

The new role writes no state and calls no tool; it compiles the player's words into this build's
mechanical vocabulary and hands the Director an ordered plan. Both roles read the same rendered
scene, so nothing new has to be assembled for it.

1. **The role.** `Role` (`config.py`) gains `"interpreter"`, with `ROLE_DEFAULTS` at
   `max_tokens=4096, reasoning_effort="medium"` — it judges the engine's roll rule, which is the
   part that has to be reasoned. In `turn/reports.py`:
   `MechanicStep(tool: str, instruction: str, when: str = "")` and
   `TurnInterpretation(mechanics: tuple[MechanicStep, ...] = (), explanation: str)`, both
   `Frozen`, both with `Field(description=...)`. `explanation` carries no default on purpose: an
   empty answer would otherwise pass for a considered "no mechanics" decision, which is the one
   reading of an empty plan that has to be earned. `interpreter_agent` in `turn/agents.py` is
   `NativeOutput(TurnInterpretation)`, `deps_type=None`, no tools — a small schema natively,
   which working rule 2 already says is safe.
2. **What it is shown.** `prompts.render_interpreter` is `render_director` without the plan
   section: the two share one `_direction_sections` helper. Instructions are
   `interpreter_instructions(engine.director_instructions, vocabulary(engine))`: the engine's
   `director.md` verbatim, as the Director gets it, plus the tool list `vocabulary()`
   (`turn/tools.py`) renders from the toolsets themselves — name and description, core then
   engine, unwrapping a `WrapperToolset` the way the golden schema test does. No mechanic is
   named by hand in a prompt file, so a renamed or added tool cannot drift out of the role that
   plans it, and each engine's own tools are in the list for free.
   `turn/prompts/interpreter.md` is the static half and owns one rule of its own: a roll is where
   the plan branches. `expand_world` is deliberately outside the vocabulary — reaching for absent
   canon stays the Director's call, behind its own cost cap. An output validator refuses a step
   naming a tool no toolset declares; it deliberately does *not* narrow to `possible()`, because
   a step may be what makes the next one legal.
3. **The turn.** `TURN_STEPS` becomes `("interpreter", "director", "hooks", "narrator",
   "worldkeeper")`; `run_turn` runs the interpreter first on the same `message_history` and
   traces it like any other role. `render_director` gains a `plan: TurnInterpretation | None`
   parameter and renders it as the last section, `MECHANICS PLAN — EXECUTE THIS`, after
   `PLAYER ACTION`: numbered `[if <outcome>: ]tool — instruction` lines, or one line saying no
   mechanic is needed, plus the explanation. The role is advisory, so an
   `UnexpectedModelBehavior` is logged and the section says no plan was read rather than killing
   a turn the Director could have judged alone. Nothing else in the pipeline moves; the
   Director's toolsets are untouched.

   A step carries `when`: empty for what the player's words already settled, otherwise the
   outcome it waits on in the engine's own words. Free text, not an enum — loner3e answers
   `yes-and…no-and` and 24xx answers `disaster/setback/success`, so an enum would force a
   per-engine output schema and break `SHARED_OUTPUTS` being engine-independent.
4. **The Director becomes an executor.** `turn/prompts/director.md` opens on the plan — execute
   every step in order, never drop one or swap a different mechanic in because you would have
   planned it differently, and when a tool result contradicts a later step, skip or adapt it and
   say so in the closing line. The plan stops at a roll, so what the dice leave behind is still
   the Director's to write. Everything else in that prompt stays: step 3's lesson is that prose
   cut from this surface costs turns, and this step's variable is the plan, not the trim.
5. **Fixtures and version.** New `instructions/*/interpreter.txt`, `prompts/*/interpreter.txt`,
   and `schemas/turn_interpretation.json`; `prompts/*/director.txt` and both `turn/*.json` move.
   `played()` (`tests/core/core_test_support.py`) takes an `interpreter` model defaulting to an
   empty plan, so no existing test has to script one; `test_golden_turn` scripts a real one.
   Persisted trace bytes move: SAVE_VERSION 79 → 80, `FIXTURE_SAVE_VERSION` with it, `save`/
   `state`/`turn` regenerated. One new test, that the plan reaches the Director's prompt and no
   other role's; the generated vocabulary needs none of its own, since the instructions golden
   pins every line of it.
6. **Eval.** Three cases were scoring a legitimate reading as failure and were rewritten with the
   step: `open-the-way-and-climb` asked the player to *search* for a hidden person, which both
   engines' own rules make a fair roll whose `no` correctly reveals nobody; `three-things` asked
   for "winded and shaking", which both engines' definition of `add_trait` ("a *lasting* change")
   tells the model not to write; and `risky-lock`'s `narrated-fact` scored flavour, since
   `dice_rolled` carries no narrator line and an honest "the door holds" writes nothing. The
   third is now `outcome-written` — the roll reached state as an unlock or as a trait — which is
   what a branching plan is for. `Run.planned` records the plan beside the facts, so a failure
   says whether a mechanic was never named or named and not executed.

### 10. Deduplicate the engines' shared spine — ~half day

- Lift `completed: Counter` onto `SheetMechanics` (`engines/sheets.py`); delete it from both
  engines' `Mechanics`. `Advancement.earned()` becomes concrete on the base, narrowing with
  `isinstance(state.mechanics, SheetMechanics)` (the base cannot see the engine's own type).
- Merge `end_adventure`/`complete_job` into one shared `complete_chapter` tool whose
  player-facing wording ("the adventure has ended" / "the job is done") the engine supplies: the
  fact narrates it, so the boundary reaches the chat and not only the trace.
- Both `new_sheet` newcomer-parity lines now read the lifted counter. Both `director.md`s and
  `director_tools.json` move with it.

### 11. Outcomes onto Exchange — ~1 h

- `Exchange` (`state/history.py`) gains `outcomes: tuple[str, ...]`; `run_turn` fills it with
  the turn's `fact.narrator` strings at commit. Delete `played_turns`, `PlayedTurn`,
  `_outcomes` (`app/views.py`); `ui/panels.chat` reads the one object. Bump + regen.

### 12. Reorganize around the new seams — ~half day

- Move `Game` out of `state/world.py` into its own module; split `content/store.py` into
  authored-content I/O and save/trace persistence; move `app/authoring/` up to
  `src/aidm/authoring/`; move `Runtime` out of `app/session.py` into the composition root
  module. No new layers, no `models/` directory. Update `test_package_boundary.FORBIDDEN`.

## Deferred, with their trigger

- Shrinking the Director's toolset to the tools step 9's plan named. The plan stops at a roll and
  the Director still needs whatever the outcome demands, so the filtered set would be "the planned
  tools plus everything consequence-handling reaches" — nearly the whole vocabulary. Trigger: an
  eval run where the Director calls a mechanic nobody planned and the turn is worse for it.
- Enums for entity ids, thread ids, and exit destinations on the Director's tools (the rest of
  PHASE-1-ADDITIONAL-APPROACH.md's item 3). Every id is already bracketed beside its entity in the
  prompt, the legal set differs per tool and per argument, and step 7.4's mechanism is per-engine
  by design. Trigger: an eval run that loses turns to an invented id — and when it fires, note
  that `unlock_exit.to_id` and `advance_thread.thread_id` are the two whose legal set step 7.3
  already computes, so enumerating those two replaces their predicate rather than joining it.
