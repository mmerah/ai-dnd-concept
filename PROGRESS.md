# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 Part A — one live mechanics per transaction (2026-08-14)

- `GameState` caches the parsed mechanics in `_live_mechanics` (a `PrivateAttr`, so no persisted
  byte moved and `SAVE_VERSION` stayed at 61): `mechanics_as(Model)` parses once and returns the
  same instance for the rest of the transaction, `set_mechanics` installs a freshly built one.
- `committed()` flushes (dump + revalidate, the gate `write_mechanics` used to be, now once per
  transaction rather than ~10 times per turn); `draft()` clears the copy's cache so a draft always
  re-parses from the last committed JSON.
- `read_mechanics`/`write_mechanics` deleted from `engines/counters.py`; all 62 src and 53 test
  call sites rewritten. Every write-back line vanished; the three `begin` builders use
  `set_mechanics`.
- **Trap for later phases:** Pydantic's `__eq__` compares private attributes, so a state whose
  cache has been primed never equals a freshly parsed one. Two tests comparing a save to a live
  state now compare dumps instead. Overriding `__eq__` was tried and reverted: ignoring the cache
  would make a dirty draft compare *equal* to its pristine origin.
- Three cases in `tests/core/test_integrity_boundaries.py`: two reads in one draft share one
  object; a mutation with no write-back survives the commit; a mutation against a *committed* state
  reaches no save and no draft.
- No golden fixture moved. 158 tests green on all four commands.

### Phase 1 Part B — engines declare, they do not re-implement (2026-08-14)

- `SheetEngine[S: SheetBase, A: Action]` (`engines/sheet_engine.py`) owns `check_overlay`, `begin`,
  `validate`, `seed`, `parse_effect`, `apply_effect`, `apply`, `renderer`, `check_plan` and
  `resolve_action`. An engine declares `sheet_type`, `mechanics_type`, `effects`, `plan_type` and
  writes `new_sheet` + `describe`. `rules.py` is now 44–75 lines; `Engine.rules_type` is gone
  (`sheet_type` is the overlay shape) and `check_overlay` is abstract on `Engine`.
- Mechanics shapes are shared: `SheetBase` (abstract `counters`) and `SheetMechanics[S]` in
  `engines/sheets.py`; each engine's `Mechanics` subclasses it and adds only what it also tracks.
- `Action` (`engines/actions.py`) carries `resolve(engine, draft, rng)` — it also declared an
  `outcomes` label set, which Part C deleted along with the branches that read it; the plan is
  `Branched[E, A]` and `plan.action.resolve` replaced every `_resolver`/`_labels` match and six of
  the seven `assert isinstance` narrowings. The seventh is loner3e's `twist_table_of`, which
  refuses an engine that cannot hand it a twist table.
- `Resolution(facts, outcome, flow)` replaced the resolvers' `(facts, outcome)` tuple and is what
  `transact` takes; `Transacted.flow` is plumbed and unread until Part C's loop. Cairn yields on
  the player's own scar/critical damage/death, 24XX on a player disaster or landed bad luck,
  loner3e never.
- `ThreadAdvancement` (`engines/advancement.py`) owns `offers`, `resolve` and `violation`; an
  engine writes `ledger` and `grant` plus four class vars.
- **Each action now lives with its own resolver**: `resolve.py` merged into `actions.py` per
  engine, because an action that resolves itself and a resolver that reads the action would
  otherwise import each other.
- **Deviations from the plan, deliberate:** `pack_type`/`creation_type`/`subsystem_types` were not
  hoisted — each engine keeps its five-line `__init__`, since abstracting it costs a fourth type
  parameter and a creation-factory protocol to save fifteen lines. `check_mechanics(state)` takes
  no mechanics argument (an override cannot narrow a parameter), and Cairn's `apply` override does
  not call `super()` — its deprivation refusal, item pools and load check leave nothing to reuse.
- **Typing:** two type parameters, no `Any`. `isinstance` against `self.plan_type` drops the type
  arguments, so `SheetEngine._typed` is the one cast in the tree; `plan_type` narrows `Engine`'s
  declaration under a scoped `reportIncompatibleVariableOverride` ignore. `SheetEngine.__init__`
  reads its three declarations once, so a missing one fails the build rather than the turn.
- **Known limit for Part C:** `flow` is decided from the action's own facts, so a death caused by
  a *branch effect* rather than by the action does not yield.
- No golden fixture moved (`turn_plan.json` byte-identical for all three engines), `SAVE_VERSION`
  unchanged at 61. 160 tests green on all four commands. Production lines 6,803 → 6,856: the
  duplication went, but Part B also added the `Resolution`/`flow` machinery Part C consumes and an
  `outcomes`/`resolve` pair on six action classes. A shared effect alias would have saved ~10 more
  and was refused: it renames the `$defs` key the Director's schema shows.

### Director fidelity: two fixes the probes forced (2026-08-14)

On "I search the study." every engine named the vault map in `focus` and revealed it in no plan.
Both causes are in how the plan is asked for, not in the prose that asks:

- **`Branched.effects` is required, not defaulted.** An optional array a small model may omit is
  an array it omits: forcing the key moved the reveal from 3/12 to 12/12 per engine. Required
  alone over-fires on a quiet turn (talk revealed 6/12), so `director.md` pairs it with the
  sentence naming the empty list as the right answer — talk back to 1/12, search still 12/12.
  Prose alone moved nothing (3/12 → 3/12): the schema is what this model obeys.
- **The Director takes one `ToolOutput`, no `TextOutput` fallback.** Two output types make
  pydantic-ai send `tool_choice: auto`, under which gpt-oss-120b truncated its own tool call
  arguments 17 times in 50 and skipped the call 8 more; under `required`, 0 and 0. The truncation
  returns `finish_reason: tool_calls` on unterminated JSON, so nothing upstream reports an error,
  and it is **not** a token limit — those answers ran ~150 output tokens against a 2048 budget.
- Shipped, across the three engines: the searched-for map revealed 36/36, a pure-talk turn
  revealed 1/36, no truncation and no retry. Forcing `action` required as well was measured and
  refused: it buys nothing and reveals on talk turns 6/12.
  `turn_plan.json` and the director instructions moved; no persisted byte did.

### Phase 1 Part C — the Director's beat loop (2026-08-14)

- `Branched`, `OutcomeBranch`, `apply_branch`, `check_branched`, `resolve_branched` and the branch
  half of `check_effects` are gone. `state/plan.py` is now `TurnPlanBase` (framing: `focus`,
  `speaker_id` — `pressure` and `stakes` deleted, written by the model and read by nothing),
  `Beat[E, A]` (`effects` required, `action` optional), `check_beat` and `resolve_beat`.
- An engine declares `class TurnBeat(Beat[...])` and `class TurnPlan(TurnBeat, TurnPlanBase)`, so
  **a plan is a beat with framing on it** — one `check_beat`/`resolve_beat` pair on `Engine` serves
  both, and `check_plan`/`resolve_action` are gone. `SheetEngine` narrows `beat_type`, not
  `plan_type`, which is why `Engine.plan_type` needs no ignore any more.
- `check_beat` is one trial in the order the beat runs: trial roll, then effects. **Ordering
  change:** a beat's effects now apply *after* its action resolves, so fact order moved.
- `run_turn`: plan → transact → while the last beat rolled an outcome, `Transacted.flow` is
  `"continue"` and fewer than `settings.max_beats` (new, default 3) have resolved: render the
  continuation, run `stages.beat`, transact. One `transact` per beat, so hooks fire between them
  and the next beat plans against a validated state. `Transacted` carries `outcome` for that test.
- Notes are cleared after *each* Director call rather than once per turn, so a scar or twist a beat
  writes steers the next beat — visible in the golden `beat-1.txt` prompts.
- `beat_stage` reuses the `"director"` role config and `ToolOutput`, prefixed with
  `turn/prompts/beat.md` — named for the stage, like every other file in that directory, and kept
  to what `director.md` cannot say: that this call is mid-turn. `render_director` grew one optional
  "WHAT JUST HAPPENED" section, so there is still one Director renderer. Traces: `director`, `beat-1`…, then one
  aggregate `resolve` and `hooks`; `TURN_STEPS` gained `"beat"` and per-beat names stay trace-only.
- `SAVE_VERSION` 61 → 62; `save`/`state`/`turn`/`prompts`/`schemas`/`instructions` regenerated and
  read. New fixture families: `schemas/*/turn_beat.json`, `instructions/*/beat.txt`,
  `prompts/*/beat-1.txt`.
- Tests: the loop's semantic case (beat 2 walks the way beat 1 revealed, and the same beat against
  the pre-turn state is refused), the stop at `max_beats`, a beat with no action ending the turn,
  and a failing beat discarding what the earlier one did. 167 green on all four commands.
- 24XX deviation 4 (bad luck only rode an attempt) closed in the same tree: a standalone
  `luck-test` action joins the attempt in a discriminated union, resolved by the same
  `_bad_luck` roll; `docs/24XX.md` renumbered.
- `Action.outcomes` went with the branches: the label sets existed only to validate a branch key
  against the action that allowed it, and nothing else ever read them. The two tests that did now
  name their own literals.
- Production lines 6,856 → 6,855. The branch machinery deleted ~85 lines and the loop, the beat
  stage, `beat.md`, the four new test cases and the 24XX `luck-test` put them back: Part C buys
  fidelity, not size. Phase 1 as a whole landed at 6,855 against the ~6,570–6,610 the plan guessed.
- **Live probe (step 7), gpt-oss-120b, 4 runs × 3 engines on "I lever up the loose flagstone and
  listen at the vault door":** 12/12 plans came back with an action, 12/12 continuations came back
  as a valid beat under `ToolOutput` — no truncation, no retry, no failure. The trimmed plan
  (no `pressure`/`stakes`) cost nothing. **12/12 beats left `action` null**, so a busy turn costs
  2 Director calls rather than 3 and the loop does not run away with the turn; the multi-action
  path is therefore exercised offline only. Probe deleted.

## Next

- PLAN.md Phase 2: the scenario creator.
- Close the Cairn 2e, Loner 3e, 24XX fidelity deviations, per their docs' "Deviations in this repo" sections — Phase 1 Part C unblocks the ones that blame the one-action turn.