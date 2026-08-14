# Plan

The phased plan for what is built next, in order. The transaction kernel and Cairn 2e both shipped
2026-08-14 and now live in PROGRESS.md. Phase 1 is the three-part refactor the three shipped
engines have earned, Phase 2 the scenario creator, Phase 3 media. Each phase carries enough detail
to implement without prior context; only the next unshipped phase needs full resolution. Shipped
phases move to PROGRESS.md.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role — and every schema a phase reshapes — starts
   as `NativeOutput` on a small schema and gets one live probe before fixture work begins.
3. **Evals are manual and noisy.** Live eval gates stay suspended; golden fixtures and offline
   parity tests are the safety net. Only same-hour runs of the same tree are comparable, and
   nothing below n=9 per case is attributable to a change.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

## Phase 1 — Live mechanics, declared engines, the Director's loop (~5–6 days)

Three engines ship, so the shapes they share are facts rather than guesses. This phase collapses
what they triplicate and removes the one constraint every engine's deviation list blames: a plan
that resolves at most one action and has to pre-write consequences for outcomes it cannot see.

Parts land in order — **A → B → C** — because each one clears ground for the next: B's action
registry is what C's loop iterates, and A's single live mechanics is what lets one turn resolve
several actions without re-parsing state between them. Steps are numbered continuously; one
commit per step, each green on the four commands.

Measured starting point: 6,809 production lines; 62 `read_mechanics`/`write_mechanics` occurrences
in `src` and 53 more in `tests`; `rules.py` 282 lines across three engines and `advance.py` 319 —
`rules.py` is ~80% shared, `advance.py` shares its `offers`/`violation`/`_offer` third and diverges
in its proposal model and `grant`. Expected finish: ~6,570–6,610 production lines, with the beat
loop added rather than traded away. Part B nets ~140 lines, not more: ~300 deleted against ~165
of new base class.

### Decisions already taken (do not relitigate)

1. **Latency is not a constraint.** gpt-oss-120b is fast and cheap; 3 → 6 model calls on a busy
   turn is acceptable, so Part C buys fidelity with calls rather than with schema size.
2. **No workflow graph.** The turn stays an explicit sequence of calls in `run_turn`, with one
   bounded loop inside it. ROADMAP's "deliberately not doing" still holds.
3. **The plan union stays authored per engine.** A subsystem may ship `Action` classes, but the
   engine names them in its own discriminated union — one line to adopt. Building the union
   dynamically at runtime is not worth what it costs the schema.
4. **Content packs are not touched.** They feed creation only; overhauling them before Phase 2
   exists is guessing. Part B's registry is where they will plug in when there is a requirement.
5. **`Branched` is deleted, not kept alongside.** Two ways to write a turn is worse than either.
6. **`Action` lives under `engines/`, never under `state/`.** `engines/loader.py` already imports
   `state.plan`; an `Action` in `state/` that names `Engine` would close that into the cycle
   CLAUDE.md forbids, and `TYPE_CHECKING` imports are not an escape. `state/plan.py` stays generic
   over the action type and never names one.
7. **Each Director call consumes the notes it was shown.** `pending_notes` are cleared right after
   the prompt that rendered them, per call rather than per turn. A note a beat writes therefore
   reaches the next beat of the same turn — *unless it is written by the last beat that resolves*,
   which no further call renders, so it survives to the next turn exactly as it does today. That
   boundary case is only reached at `max_beats` or on a turn-ending blow. This lands LONER-3E's
   twist in the turn it interrupts rather than the turn after — closer to the SRD, and a deviation
   entry that improves rather than a behaviour regression.

### Part A — one live mechanics per transaction (steps 1–2, ~1 day)

`GameState.mechanics` is `JsonValue` that core cannot read, so every engine round-trips it:
`read_mechanics` re-validates the whole blob into a *fresh copy*, and `write_mechanics` dumps and
re-validates it back. Two reads in one transaction are two independent copies and the last write
wins; a resolver that forgets to write loses its changes silently. `resolve_attack` already reads
and writes, then `apply` reads again in the same plan.

1. **Cache the parsed mechanics on the state.** In `state/world.py`, `GameState` gains
   `_live_mechanics: Mutable | None = PrivateAttr(default=None)` and four members:
   - `mechanics_as[M: Mutable](self, model: type[M]) -> M` — returns the cached instance when
     `isinstance(held, model)`, otherwise validates `self.mechanics` into one and caches it.
   - `set_mechanics(self, mechanics: Mutable) -> None` — installs a freshly built instance as the
     live one. `begin` needs this: at that point `self.mechanics` is `None`, so there is nothing
     for `mechanics_as` to parse. This is the only writer, and after Part B it has one caller in
     `SheetEngine.begin` plus Cairn's override.
   - `_flush(self) -> None` — when a live instance exists: dump it `mode="json"`, validate the
     payload back through `type(live)` (this is the gate `write_mechanics` used to be, now run
     once per transaction instead of ~10 times per turn), assign it to `self.mechanics`.
   - `committed()` calls `_flush()` first. **`draft()` does not flush** — it deep-copies and then
     clears the copy's cache, so a draft always re-parses from the last committed JSON. Flushing
     inside `draft()` would write to the committed parent, which CLAUDE.md forbids, and clearing
     is what keeps a stray mutation made against a committed state as harmless as it is today.
     This rests on one invariant that holds everywhere today and nothing enforces: **a draft is
     taken from a committed state, never from a dirty one.** Say so in a comment on `draft()`;
     the deep copy of a cache that is then cleared is deliberate slack, not an oversight.

   Private attributes are ignored by `model_dump`/`model_validate`, so no persisted byte moves and
   `SAVE_VERSION` does not change in this part. `model_copy(deep=True)` does deep-copy
   `__pydantic_private__` on the pinned Pydantic; the copy is cleared rather than relied on.
2. **Delete `read_mechanics` and `write_mechanics`** from `engines/counters.py`. Rewrite the src
   call sites as `state.mechanics_as(Mechanics)` and drop every `write_mechanics(...)` line
   outright, except the three that build fresh mechanics (`loner3e/rules.py`,
   `twentyfourxx/rules.py`, `cairn2e/rules.py` in `begin`), which become `set_mechanics`. Then the
   53 occurrences across `tests/` — `tests/loner3e/test_loner3e_engine.py` (16),
   `tests/core` (16), `tests/cairn2e/test_cairn2e_engine.py` (11), `tests/twentyfourxx` (6), and
   the per-engine support modules. Three tests in `tests/core/test_integrity_boundaries.py`, where
   the other state invariants live: two reads inside one draft return the same object; a mutation
   with no write survives that draft's commit; a mutation made against a *committed* state never
   reaches a save or a draft taken from it.

Done when: no golden fixture moves, `SAVE_VERSION` is unchanged, and `write_mechanics` appears
nowhere in the tree.

### Part B — engines declare, they do not re-implement (steps 3–6, ~2 days)

The three `rules.py` files are one file written three times: pack loading, subsystem and creation
wiring, `begin`, `validate`, `seed`, `parse_effect`, `apply_effect`, `renderer`, a `match` over
the action, a labels lookup, and two `assert isinstance(plan, TurnPlan)` narrowings. The three
`advance.py` files repeat the same offer-per-resolved-thread rule and the same
`check_draft`-shaped `violation`.

3. **`src/aidm/engines/sheet_engine.py`: `SheetEngine(Engine)`.** Class-level declarations —
   `mechanics_type`, `sheet_type`, `pack_type`, `effects: TypeAdapter[...]`, `creation_type`, and
   `subsystem_types: tuple[type[Subsystem], ...]` (**plural from the start**: a fourth engine
   shipping advancement *and* combat is the stated point of Part B, and singular would cost a
   second refactor to undo) — drive a concrete `__init__` (loads packs from `engine_dir / "packs"`
   merged with `extra_packs`, builds each subsystem, builds creation) plus concrete `begin`
   (`actor_sheets` → `mechanics_type(sheets=...)` → `set_mechanics`), `validate` (`check_sheets`,
   then `check_mechanics(state, mechanics)` — a no-op by default), `seed` (skip non-actors and
   known ids, then the abstract `new_sheet(state, rng) -> Sheet`), `parse_effect`, `renderer`
   (abstract `describe(state, mechanics, entity) -> str`), and `apply_effect` (the body all three
   share today: a `CounterChange` goes through `reveal_target` + `move_pool`, anything else
   through core's `apply_effect`).
   Cairn keeps **four** overrides and no more: `check_overlay` (its `Sheet | ItemRules` union),
   `begin` (it authors item rules as well as sheets), `check_mechanics` (`check_items` and
   `check_load_limits`), and `apply_effect` — which calls `super().apply_effect(...)` around its
   deprivation refusal and load check. Prefer a plain shared function over a template-method hook
   wherever one override would otherwise become two.
4. **The action registry.** In `engines/` — beside `Engine`, never in `state/`, per decision 6 —
   `Action(Frozen, ABC)` with `outcomes: ClassVar[frozenset[Slug]]` and
   `resolve(self, engine: Engine, draft: GameState, rng: Random) -> Resolution`.
   `Resolution(Frozen)` lives in `state/plan.py` — it names `Fact`, `Slug` and a literal, and
   nothing from `engines/`, so decision 6 holds — and carries `facts`, `outcome`, and
   `flow: Literal["continue", "yield-to-player"] = "continue"`. `Resolver` returns it;
   `Engine.resolve_action` returns it; `transact` carries `flow` onto `Transacted`, where a
   subsystem resolution leaves it at the default. The flow is typed rather than smuggled as a
   fact kind: the loop in step 8b reads a field, not a string match.
   **What each engine does with it.** The resolvers already know the grave moments and today can
   only say so in prose the loop cannot read — `cairn2e/resolve.py` writes `pending_notes` in
   `_fell`, `_take_scar` and the attribute-emptied branch. Cairn yields when the **player** takes
   a scar, takes critical damage, or goes down; an NPC going down continues, which is why the flag
   belongs on the resolution and not on a static per-action outcome set. 24XX yields on a player
   `disaster` and when `_bad_luck` lands `trouble`. Loner3e yields nowhere — its twist is meant to
   feed the next beat, per decision 7 — and stays on the default throughout.
   Every engine action subclasses it: `Save.outcomes = {"pass", "fail"}` and its `resolve`
   delegates to `resolve_save`; `Attack`, `Attempt` and `Question` likewise. `state/plan.py` stays
   generic over the action type and never imports `Action`, so the import graph keeps its one
   direction.
   `Question` is why `resolve` is handed the engine: its twist table is read off the engine's
   packs, not off the state. That leaves **one** residual narrowing in the tree — a module-level
   `twist_table_of(engine)` in `loner3e` that refuses an engine of another type — and the step's
   claim is that the other six narrowings go, not all seven.
   `SheetEngine.check_plan` and `resolve_action` become concrete: narrow the plan once against
   `self.plan_type` — `check_plan` returns the mismatch as its refusal string rather than raising,
   because `Engine.check_plan`'s contract is that an output validator must never raise — then read
   `plan.action.outcomes` and `plan.action.resolve` instead of matching. Every `_resolver`,
   `_labels`, `LABELS`, `SAVE_LABELS`, `ATTACK_LABELS` and per-engine `assert isinstance` goes.
   **Name the typing path before writing it**, because `plan_type` is
   `ClassVar[type[TurnPlanBase]]` and narrowing against it yields a `TurnPlanBase`, which has no
   `action`. In preference order: make `SheetEngine` generic in its plan type (`Engine.plan_type`
   drops `ClassVar` — it is only ever read off an instance, in `roles.director_stage`); failing
   that, one `cast` at the single narrowing site in the base, with the rationale in a comment.
   Re-annotating `action` to a narrower union on each engine's plan is *not* a path — pyright
   reads it as an invariant attribute override, since Pydantic's `frozen=True` is runtime config
   it cannot see. If neither of the two paths is clean inside half an hour, keep the three
   per-engine narrowings and strike that clause from this step rather than reaching for `Any` or
   a file-level suppression.
5. **`ThreadAdvancement(Subsystem)`** beside `SheetEngine`: concrete `offers` (one per resolved
   thread per party member, over `PLAYER_ID` and `world.party()`), concrete `violation` (the
   `check_draft` call all three make verbatim), and two abstract members — `ledger(sheet) ->
   Counter` (the deliberately Director-invisible `growths` / `milestones` / `jobs`) and
   `grant(draft, sheet, subject, proposal) -> Fact`. The three `advance.py` keep their proposal
   model, their prompt text, and `grant`.
6. **Prove nothing moved.** `tests/core/test_golden_schemas.py` must pass untouched: methods on a
   pydantic model do not reach its JSON schema, so a byte-identical `turn_plan.json` for all three
   engines is the check that Part B changed no model-facing shape. `tests/core/test_engine_contract.py`
   gains one case: a `SheetEngine` subclass that declares nothing raises at class definition or at
   first build, rather than failing at turn time.

Done when: ~140 fewer production lines (~300 deleted against ~165 of new base class), no golden
fixture moved, and the answer to "what does a fourth engine have to write" is a sheet model, its
actions and resolvers, `director.md`, and a pack — roughly 250 lines rather than 700.

### Part C — the Director's loop replaces outcome branches (steps 7–9, ~2–3 days)

Today the Director writes the whole turn blind: an action plus `branches` keyed by outcomes it
cannot see. `state/plan.py` spends ~100 of its 180 lines on that — `Branched`, `OutcomeBranch`,
`apply_branch`, `check_effects`'s per-branch alternative trials, `check_branched`,
`resolve_branched` — every `director.md` spends a paragraph teaching it, and the field
descriptions carry defensive prose ("with no branch, even success changes nothing") because the
shape is hard to get right unseen. Every engine's deviation list blames the same constraint:
LONER-3E 6 (one Oracle question per turn), 24XX 4 and 5, CAIRN-2E 1, 2 and 3.

The turn becomes: frame and act, see what the dice said, say what changed, optionally act again.

**Part C is three commits, not five, and the middle one is large by necessity.** `loader._examples`
validates every `examples.json` entry against `plan_type` at engine build, and `Frozen` forbids
extra keys — so the moment `branches` leaves the model, every engine fails to construct until the
examples, the prompts and the tests have all moved. Working rule 1 puts the fixture regeneration
in that same commit. Do the work in the order written inside step 8; commit it once.

7. **Probe first (working rule 2).** Before any other Part C work: one live run of the continuation
   schema against gpt-oss-120b. It carries the same large effect union that made the Director's
   plan emit zero effects under `NativeOutput`, so it starts on `ToolOutput` with the existing
   `TextOutput` fallback, and the probe is what decides whether that stays. Probe the **trimmed**
   framing plan too — without `pressure` and `stakes`, per 8a — so working rule 2 covers that
   reshape with the probe already planned rather than a second one later. Record the result in
   PROGRESS.md; delete the probe.
8. **The cutover.** One commit, in this order:

   **a. Core.** In `state/plan.py`, `Beat[E, A](Frozen)` — two parameters, because `action` must
   carry the engine's own discriminated union (`Cairn2eAction`), not the abstract base, or pydantic
   can neither schema nor discriminate it. `effects: tuple[E, ...]`, `action: A | None`.
   `TurnPlanBase` keeps `focus` and `speaker_id` and **loses `pressure` and `stakes`** — both are
   written by the model and read by nothing in `src` (one test fixture writes them; the Narrator
   consumes `focus` and `speaker_id` alone). Carrying two verified-dead fields through the one
   commit that rewrites this model line by line would be a waste, and schema size has a
   demonstrated cost here where the chain-of-thought argument for keeping them is weak: this model
   runs with `openai_reasoning_effort`, so its thinking does not live in two serialized prose
   fields, and `focus` still forces one summary sentence. The pressure/stakes *judgment* stays as
   prose in `director.md`, which is where it already is. The engine's `TurnPlan` becomes framing +
   beat, and each engine also names its `beat_type` (the continuation's output model) beside
   `plan_type`. Delete `Branched`, `OutcomeBranch`, `apply_branch`, `check_branched`,
   `resolve_branched`, and the branch half of `check_effects`; what is left is `check_beat` (the
   effects trial, plus `check_action` when a beat carries one) and `resolve_beat`.
   Both **keep today's `Resolver`-callable parameter** rather than reaching into `beat.action`
   themselves: a typevar bound naming `Action` would drag `engines/` back into `state/plan.py` and
   undo decision 6. Only `SheetEngine` touches `.action`, passing
   `lambda draft, rng: beat.action.resolve(self, draft, rng)` down. `SheetEngine.check_plan` and
   `resolve_action`, written in step 4 against `check_branched`/`resolve_branched`, are rewritten
   here to the two survivors.
   **Ordering change, intentional:** a beat's effects now apply *after* its action resolves, and
   the first beat's effects are no longer deferred behind the roll. Fact order moves with it.

   **b. Pipeline.** Inside `run_turn`: plan → `transact` the first beat → while the beat just
   resolved carried an action, its `Transacted.flow` is `"continue"`, and fewer than
   `settings.max_beats` (new field, default 3) have resolved: render the continuation prompt, run
   the beat stage, `transact` it. The engine-side `yield-to-player` is the stronger half of the
   24XX-5 mitigation — a deterministic stop the model cannot talk itself past — and the
   `director_beat.md` clause in 8c is the softer half covering what no resolver can see. One `transact` per
   beat, not one for the loop, so hooks fire and the next beat plans against a validated state.
   Per decision 7, notes are cleared immediately after each Director prompt renders them, in place
   of today's single clear after the first call — so a scar or twist written in beat 1 steers
   beat 2 and does not also steer next turn. A mid-turn failure still discards the whole turn,
   because nothing is persisted until `GameSession._commit`. `TURN_STEPS` gains one entry,
   `"beat"`, and `announce("beat")` uses exactly that spelling — `ui/panels.role_badges` matches
   `session.step` against the `TURN_STEPS` entry, so the per-beat `StepTrace` names (`beat-1`,
   `beat-2`) must stay trace-only and never reach `announce`.

   **c. Roles and prompts.** `turn/roles.py` gains `beat_stage(engine, settings)` — the same
   `"director"` role config and `engine.director_instructions`, prefixed with a new short
   `turn/prompts/director_beat.md`, output type `engine.beat_type`, validator judging the beat
   against the **current draft**: `PlanContext.state` is replaced by the draft the loop is holding,
   which is the only baseline under which "reveal in beat 1, walk through in beat 2" is legal.
   `prompts.render_director` grows one optional "WHAT JUST HAPPENED" section so the continuation
   reuses the renderer instead of growing a second one.
   Then the four `director.md` and four `examples.json` files: out go the branch paragraphs, every
   `branches` key, and the two lines of `turn/prompts/director.md` that describe `pressure` and
   `stakes` as fields — the paragraph that teaches the judgment itself stays, since the Director
   still has to weigh whether a turn should push back; in goes one paragraph — you will be asked again after each roll, write
   what the outcome actually caused, and **stop the turn when the next action would need the
   player's own intent rather than yours**. That last clause is the guard against the loop
   swallowing what the player should have been asked (see the 24XX 5 note below).

   **d. Tests and fixtures.** `tests/core/test_pipeline.py` stubs answer the Director twice; new
   cases for the loop stopping at `max_beats`, a beat with no action ending the turn, a failure in
   beat 2 discarding beat 1's facts and state, and a beat-2 effect that is legal only because
   beat 1 revealed the way (the semantic heart of Part C). `tests/loner3e/test_loner3e_engine.py`
   imports `OutcomeBranch` and builds branch plans, and all three per-engine suites drive
   `check_plan`/`resolve_action` on `Branched` plans — all of them move here.
   `test_golden_turn.SCRIPTS` gains a multi-beat script per engine. Bump `SAVE_VERSION` (the
   trace's step shape and the plan shape both move) and regenerate the
   `save`/`state`/`turn`/`prompts`/`schemas` families with `AIDM_GOLDEN_REGEN=1`, then read the
   diff.
9. **Deviations.** Update each engine's "Deviations in this repo" section — accurately, because
   the loop's reach is narrower than it first looks:
   - **LONER-3E 6** (one Oracle question per turn) — genuinely unblocked by the loop.
   - **LONER-3E's twist timing** — improved by decision 7: the twist interrupts the scene in the
     turn it fires, as the SRD has it, except when it fires in the last beat a turn resolves —
     no further call renders it, so that one still lands the turn after.
   - **CAIRN-2E 1–3** — partly unblocked: action sequences, a morale save that follows the blow
     that triggered it, and a blast written as several attacks all become possible. The unrolled
     tables, detachments and `d8+d8` do not move.
   - **24XX 4** (the bad-luck test only rides an attempt) — closed by **Part B**, not the loop: it
     wants a standalone luck-test `Action`, which the registry makes a one-line addition.
   - **24XX 5** (advise-and-revise) — *not* unblocked, and the loop would make it worse unguarded:
     `max_beats` commits up to three actions' consequences before the player can revise anything.
     Two guards, recorded as the mitigation, and the deviation stays: the engine-side
     `yield-to-player` from step 4, which stops the loop deterministically on a player disaster or
     bad-luck trouble, and the `director_beat.md` clause from 8c for what no resolver can see.
   Closing the rest is per-engine work that follows this phase, not part of it.

Done when: `branches` appears nowhere in the tree, a turn where the player attacks resolves the
blow and its consequence in two Director calls without pre-written outcomes, and a quiet turn
still costs exactly one.

### What this phase deliberately leaves alone

Content packs, media, the narration-against-facts check, undo, history summarisation, and any
change to the Narrator or Worldkeeper. Combat as a subsystem is *enabled* by Part B's registry and
Part C's loop, and specced only once an engine actually needs it.

## Phase 2 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at
authoring time. This is a script, not the app: agentic workflows are fine outside the turn
loop, where speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the shared format already exists and
   is the validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`). Give it one read-only tool returning whispering-vault's
   `world.json` as the worked example, and put the authoring bar in the instructions: 4+
   locations connected by relations with at least one hidden and one `locked` way, 2+ NPCs with
   at least one unrevealed, one secret item, at least one thread with hooks that advance it on
   `entity_discovered` facts, hook `note`s that steer the Director, and `detail.hook` on every
   entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then validate the world alone — a `Scenario` per
   shipped engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the
   engine's normal mechanics validation. Any `ValueError` goes back to the agent as a retry
   message, max 3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per shipped engine, output that engine's strict
   authored-overlay model, prompted with the generated world and engine-provided authoring
   guidance/defaults. Re-run step 2's loop with each generated overlay in place — the overlay
   is what `begin_game` exercises beyond shared structure.
4. Files land in `scenarios/<slug>/` only after every shipped engine validates. The script
   prints a summary (entities, relations, threads, hooks per engine) and the author reviews the
   diff before committing — generated content merges by the same review as hand-written
   content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under every shipped engine. Quality beyond
validity is judged by playing it, not asserted by the script. PDF/notes ingestion is a later
input mode for the same script, not a separate system.

## Phase 3 — Media: scene illustrations (~2–3 days)

Presentation only, outside mechanical truth: the game must be indistinguishable with media
disabled, and a failed generation must cost nothing but a log line.

1. `MediaConfig` on `Settings`: `enabled: bool = False`, `provider: ProviderName = "openrouter"`,
   `model: str` (an image-capable model id). `src/aidm/app/media.py`:
   `illustration_request(state: GameState, narration: str) -> str` builds the image prompt
   deterministically — location name and brief, the `here` entities' briefs, the narration — **no
   model call decides whether to illustrate**; a Producer role is not built until a deterministic
   builder proves insufficient. `async generate(prompt, config) -> bytes | None` calls the image
   API and returns None on any failure (logged, never notified).
2. Wiring, at the boundary: after the commit in `GameSession.submit`, when media is enabled,
   schedule generation as a background asyncio task writing
   `saves/<slug>.media/turn-<n>.png`. The turn returns without waiting. `restart()` discards the
   media directory alongside the save.
3. UI: the chat panel shows the image above its exchange when the file exists; refresh on next
   submit (simplest) picks up late arrivals, a `ui.timer` only if that feels bad in practice. No
   gallery, no regeneration button.
4. Tests: the request builder is pure — one test on its output for a known state; the generate
   path is not tested live (network rule). Voice, portraits, and ambient audio are later phases
   of the same shape, none specced until wanted.

Done when: with media enabled a turn grows an illustration within seconds after the narration,
and with it disabled (the default) nothing in state, saves, prompts, or tests differs.
