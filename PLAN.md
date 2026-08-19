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
- Movement (`state/apply_effects.py`): the player moving through an exit that exists but is
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

### 7. Separate runtime Game from SavedGame — ~1–2 days

- Runtime `Game` (rename of `GameState`): a plain dataclass, not a Pydantic model — its
  `mechanics` holds the engine's validated mechanics instance directly, and `SavedGame` is now
  the validation boundary. Delete `mechanics_as`, `set_mechanics`, `_flush_mechanics`,
  `_live_mechanics`; every `draft.mechanics_as(Mechanics)` becomes a typed read the engine
  narrows once.
- Strict `SavedGame` DTO next to `FileStore` (`content/store.py`): same fields with
  `mechanics: JsonValue`. The engine decodes mechanics once on load and encodes on save;
  `committed()` validates the world copy + `engine.validate` instead of a full dump/re-parse
  round-trip. Draft-per-turn lifecycle is already in place from step 3.

### 8. Deduplicate the engines' shared spine — ~half day

- Lift `completed: Counter` onto `SheetMechanics` (`engines/sheets.py`); delete it from both
  engines' `Mechanics`. `Advancement.earned()` becomes concrete on the base, narrowing with
  `isinstance(state.mechanics, SheetMechanics)` (the base cannot see the engine's own type).
- Merge `end_adventure`/`complete_job` into one shared `complete_chapter` tool whose
  player-facing wording ("the adventure has ended" / "the job is done") the engine supplies.
- Both `new_sheet` newcomer-parity lines now read the lifted counter. Both `director.md`s and
  `director_tools.json` move with it.

### 9. Outcomes onto Exchange — ~1 h

- `Exchange` (`state/history.py`) gains `outcomes: tuple[str, ...]`; `run_turn` fills it with
  the turn's `fact.narrator` strings at commit. Delete `played_turns`, `PlayedTurn`,
  `_outcomes` (`app/views.py`); `ui/panels.chat` reads the one object. Bump + regen.

### 10. Reorganize around the new seams — ~half day

- Move `Game` out of `state/world.py` into its own module; split `content/store.py` into
  authored-content I/O and save/trace persistence; move `app/authoring/` up to
  `src/aidm/authoring/`; move `Runtime` out of `app/session.py` into the composition root
  module. No new layers, no `models/` directory. Update `test_package_boundary.FORBIDDEN`.

## Deferred, with their trigger

- 
