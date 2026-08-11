# Plan

The phased plan for what is built next, in order. Written 2026-08-11. Each phase carries enough
detail to implement without prior context; only the next unshipped phase needs full resolution,
and a later phase is rewritten to this resolution when it becomes next.

Part I (phases 1–4) removed the first layer of generic infrastructure. Part II (phases 5–10)
finishes the simplification: the shipped prompt pass, small proven deletions, then the
world/mechanics boundary, engine runtime, and role plumbing. Part III (phases 11–14) builds the
features that were previously phases 6–9 against that settled shape.

## Working rules

1. **Golden fixtures are the behavior contract.** `AIDM_GOLDEN_REGEN=1` rewrites them; use it only
   in the same commit as the change that justifies the movement, and read the diff — an unexpected
   fixture moving is a bug, not churn. Any phase that changes persisted bytes bumps `SAVE_VERSION`
   (`src/aidm/state/base.py`) and regenerates the `save/state/turn` fixture families; stale saves
   are refused, never converted.
2. **Probe a new role's output mode live before trusting it.** gpt-oss-120b emitted zero plan
   effects under `NativeOutput` on the Director's large schema, while small schemas (worldkeeper,
   advisor, scene) are fine natively. Every new role starts as `NativeOutput` on a small schema
   and gets one live probe (a few real calls) before its eval or fixture work begins. The same
   rule applies to a schema that a phase reshapes: probe before cutting fixtures.
3. **Evals are manual and noisy.** Live eval gates are suspended by maintainer decision
   (2026-08-11) until the codebase settles — concretely, until Part I lands; golden fixtures and
   offline parity tests are the safety net meanwhile. `uv run python scripts/evals/run.py --only
   <engine|role|tag|id>` when a model-facing surface changed and you want a number. Only same-hour
   runs of the same tree are comparable, and nothing below n=9 per case is attributable to a
   change.
4. **Part I is behavior-preserving except where a phase says otherwise.** A simplification phase
   whose fixture diff shows anything but the movement it predicted has a bug.
5. **Net lines are evidence, not the target.** Record source lines before and after each
   simplification, but accept a phase on fewer concepts, one clear owner per behavior, and the
   same tested capability. Moving generic code into two engines is not a deletion.

Per phase: `uv run pytest && uv run ruff check && uv run ruff format --check && uv run
basedpyright` green after every numbered step, one commit per step.

# Part I — Simplification (~4–5 days)

Acceptance criteria for the whole part, judged without building a third engine (maintainer
decision 2026-08-11: the criteria are adopted, Ironsworn itself is not scheduled):

- Adding a hypothetical engine touches only `engines/<id>/` plus one registry entry; core never
  dispatches an engine action.
- One explicit `run_turn()` orchestration function; a new role is one config entry, one agent
  construction, one explicit invocation.
- A new content collection requires zero core changes — **already true at HEAD**: `Record` is a
  flat fact map (`state/packs.py:88`), a collection is one `spec.json` key plus pack data, and
  `read_pack`/`validate_pack` iterate collections generically. The review's content point needs no
  phase; the only core-owned content vocabulary left is `FactType`, touched only for a fourth
  fact type.
- Memory/quest/location features operate on shared world state and the `Fact` stream, never
  per-engine — the standing design for Part III (the review's "double down on Fact" point; also
  already the shape at HEAD, no phase needed).

## Phase 1 — The engine owns its plan lifecycle (~1 day)

Core still knows engines have actions: `engines/loader.py` (380 lines) holds `ActionSpec`, a
linear-scan dispatcher (`_spec` loader.py:210, `_action` loader.py:265), the static-vs-callable
`labels` split, and generic `check_plan`/`resolve_action` (loader.py:151–175). The dnd5e plan
union (`engines/dnd5e/actions.py:140`) already encodes the dispatch the `ActionSpec` table
repeats; nothing outside loader.py and the two `rules.py` files imports `ActionSpec`.

1. `EnginePlugin` (loader.py:88) drops `actions: tuple[ActionSpec[Any], ...]` for two callables:
   `check: Callable[[Engine, GameState, TurnPlanBase], str | None]` and
   `resolve: Callable[[Engine, GameState, TurnPlanBase, Random], list[Fact]]`.
   `Engine.check_plan`/`resolve_action` become one-line delegations; `ActionSpec`, `_spec`,
   `_action`, and the label machinery are deleted. Contravariance note: an engine function typed
   on its own `TurnPlan` is not assignable to these fields, so each engine accepts `TurnPlanBase`
   and narrows with one `assert isinstance` — the same runtime narrow `_action` performs today
   (loader.py:265). The shared shape both checks need — trial-resolve with `Random(0)`, verify
   every branch label the plan wrote is one the action can produce — moves to one helper in
   `state/plan.py` beside `apply_branch`, called by each engine's own `check`; the helper takes
   the engine's resolve callable as a parameter, since `state/plan.py` cannot import `Engine`
   without a cycle through the loader.
2. Story: `engines/story/rules.py` replaces its one `ActionSpec` with `check`/`resolve` functions
   — `plan.action is None` → return no facts (the pipeline applies `plan.effects` unconditionally
   for every plan, `turn/pipeline.py:114`; an engine that applies them too double-applies), else
   `resolve_risk` + branch application. Labels are the engine's own constant, checked in its
   `check` via the shared helper.
3. dnd5e: `engines/dnd5e/resolve.py` gains one `resolve(engine, draft, plan, rng)` that
   `match plan.action:` over the existing union to the six `resolve_*` functions; `rules.py`'s
   label callbacks (`improvise_labels`, `cast_labels`) and plan checks (`check_cast`,
   `check_feature`, `_double_spend`) fold into one engine `check`. The six-row `ActionSpec` table
   disappears; the union is the registry.
4. Verify no fixture moves (working rule 4), `grep -r ActionSpec src tests` is empty, and core
   contains no `getattr(plan, "action", ...)`. No `SAVE_VERSION` bump — no persisted bytes change.

Done when: an engine gets its typed plan and resolves it; core's only knowledge of a plan is
`plan_type` and the two callables.

## Phase 2 — One explicit run_turn (~1 day)

`turn/pipeline.py` (354 lines) wraps one concrete sequence in `TurnWorkspace` (nullable
`plan`/`directive` with runtime unwrap guards), `StepFn`/`TurnScript` aliases, six closure
factories, and `default_workflow()` — abstraction with no second workflow, against this repo's
own port rule. The known consumers that must survive:

- `scripts/evals/run.py:315–385` builds a bare `TurnWorkspace` and invokes step closures
  standalone (and already routes *around* `director_step` for retry visibility).
- `app/session.py:78` derives the UI progress list from the script.
- `tests/core/core_test_support.py:126` re-assembles the script to override stage models;
  `test_pipeline.py`'s extra-step test exercises the abstraction itself.

1. Rewrite `run_turn()` as one explicit async function: draft → scene directive → director plan →
   `engine.resolve` + `fire_hooks` → narrator → worldkeeper apply → history append, turn
   increment, commit, `engine.validate_state`. Locals replace the workspace; the nullable fields
   and their unwrap guards disappear. Keep the four stage builders (`scene_stage` etc.) as plain
   functions, and extract three named plain functions — resolve-application, hook-firing,
   worldkeeper-application — because evals call `resolve_step` and `hook_step` standalone today
   (run.py:328), not just the worldkeeper block. Those plus the stage builders are the per-phase
   entry points evals keep calling.
2. Delete `TurnWorkspace`, `StepFn`, `TurnScript`, the six step factories, `default_workflow`.
   Rewire `scripts/evals/run.py` to call the same plain functions `run_turn` calls (it already
   holds directive/plan/narration as values). `session.role_names` becomes a literal tuple. Keep
   the trace's step names byte-identical so `turn/*` fixtures do not move.
3. Test support: `run_turn` takes one stages bundle (scene/director/narrator/worldkeeper agents)
   built once by the session; `played()` stubs the bundle per role, and the signature survives
   phase 6 adding two more roles. The extra-step extensibility test is deleted with the
   abstraction it tests; a new role is now an explicit call site (see phase 6), which needs no
   framework test.

Done when: `run_turn` reads top to bottom as the sequence it is (~100–150 lines), evals still run
each phase standalone, and no `turn/*` fixture moved.

## Phase 3 — Effect vocabulary: 19 ops → 12 (~2 days)

`state/effects.py` holds 19 effect classes and `state/apply.py` (509 lines) a 19-arm dispatcher.
The merge rule (maintainer decision 2026-08-11): **merge only ops with identical audience
membership and compatible field shape** — a mode never changes which union an op belongs to. The
three unions (`Effect`, `TurnEffect`, `SheetEffect`) do real permission work at the type level;
merging across them would either advertise forbidden modes in the Director's schema or
reintroduce per-audience variant classes. No generic path/value patches. Target:

| Op after | Replaces |
|---|---|
| `Move` | `MoveActor`, `MoveItem` |
| `CounterChange` (mode: adjust/spend) | `AdjustCounter`, `SpendCounter` |
| `TagChange` (op: add/remove) | `AddTag`, `RemoveTag` |
| `RelationChange` (op: add/remove/untag/reveal) | `AddRelation`, `RemoveRelation`, `UntagRelation`, `RevealRelation` |
| *(deleted)* | `TagRelation` — zero runtime writers at HEAD; authored locked ways are `Relation.tags` in world.json, lifted by the untag op |
| unchanged | `Reveal`, `GainImprovisedItem`, `GrantCounter`, `Refill`, `SetNote`, `SetNumber`, `AddRef`, `AdvanceThread` |

`GrantCounter`/`Refill` stay separate from `CounterChange` because the Director may not write
them and engine resolvers legitimately do (Rest writes `Refill`, `dnd5e/resolve.py:37`) —
`apply_effect` cannot tell the two producers apart, so the split must stay in the types. The
sheet trio (`SetNote`/`SetNumber`/`AddRef`) shares an audience but not a payload shape
(str/int/`ContentRef`); merging them costs optional fields plus a validator, which is worse
typing for zero semantic gain.

1. The merge, one union at a time (moves, counters, tags, relations — a commit each). The
   audience unions become unions over the merged ops with membership unchanged; `apply_effect`'s
   match shrinks with the vocabulary; the per-op helper bodies and their `Fact` kinds are
   unchanged, so hook matching and eval probes (which read `fact.kind`/`fact.data`) do not move.
   Effect constructors to rewrite live in engine code after phase 1: `story/resolve.py`
   (`AdjustCounter`, `Reveal`), `dnd5e/resolve.py` (`AdjustCounter`, `SpendCounter`, `Refill`,
   `Reveal`, `SetNote`), and dnd5e's `_double_spend` isinstance checks.
2. Rewrite the authored and validated surfaces that spell effects: hook effects in
   `scenarios/whispering-vault/world.json`; the shared `src/aidm/engines/examples.json` — the
   `_effect_vocabulary` startup check (loader.py:291) requires every `TurnEffect` op exactly
   once, and a merged op needs one worked example per mode, so extend that check to per-mode
   rather than silently under-teaching the modes an example no longer shows; and
   `engines/story/examples.json`, validated against `plan_type` at load. Read the regenerated
   `instructions/*` goldens rather than assuming.
3. **Probe live before fixtures** (working rule 2): the Director's schema shrink lands exactly on
   gpt-oss-120b's weak spot. A few real turns on whispering-vault under both engines; zero-effect
   plans mean the schema shape needs adjusting before anything else proceeds.
4. Regenerate `schemas/*`, `instructions/*`, `save/*`, `state/*`, `turn/*` goldens; bump
   `SAVE_VERSION` (hooks in saved state carry effects). One same-hour eval pair on the director
   cases (`--only director`) to check the merge did not regress plan quality — informational, per
   working rule 3, but this is the one Part I phase that touches the model's language.

Done when: twelve ops, audience still expressed entirely in the unions (no runtime mode
policing), whispering-vault plays a full turn under both engines live, and the fixture diff shows
only the predicted vocabulary movement.

## Phase 4 — Collapse the authored-world intermediate (~½ day)

`content/authored.py` still routes initialization through `AuthoredWorld`/`AuthoredEntity`
(authored.py:155–164) — a near-copy of `ScenarioWorld` that exists to carry `{entity, rules}`
pairs into `compose_world` (authored.py:196), while `relations`/`threads`/`hooks` pass through
unchanged and `begin_game` reads them straight back out (`app/session.py:37`).

1. `begin_game` composes `WorldState` directly from `Scenario` + `Character`: iterate scenario
   entities, merge the engine overlays' rules per entity
   (`{**scenario.overlay.entities, **character.overlay.entities}`, duplicate-id check kept),
   build each `Sheet` via the engine, inject the player entity and `character.profile.items`, and
   carry entities/relations/threads over with `model_copy(deep=True)` — they are `Mutable` and
   `restart()` re-runs `begin_game` against the same loaded `Scenario`, so loaded content must
   outlive the game state (the invariant `authored_world`'s deep copy protects today,
   authored.py:183). Delete `AuthoredWorld`, `AuthoredEntity`, `authored_world`, `compose_world`;
   `Engine.initial_world` shrinks or dissolves into the composition, and `Engine._sheet` goes
   public (or stays behind the smaller `initial_world`), whichever reads cleaner. The on-disk
   authoring structure (scenario canon + engine overlay, character profile + engine overlay) is
   untouched — it earns its place.
2. Verify `save/*` and `state/*` fixtures are byte-identical (same composed state, fewer layers);
   no `SAVE_VERSION` bump unless the diff proves otherwise.

Done when: two model layers between the JSON files and `GameState` (the file models and the
runtime state), and beginning a game produces the same bytes it did before.

# Part II — Finish the simplification

## Phase 5 — The prompt pass: the Director drops the state write — DONE

Shipped 2026-08-11. Evals came back off suspension here (working rule 3). The 2026-08-07 evidence
list this phase set out to act on did not survive contact with the settled tree: two of its four
cases had already fixed themselves, one of its numbers was noise, and the phase's own re-baseline
turned up two failures it had never named. What the measurements now say (gpt-oss-120b, n=9 per
case unless stated):

- `condition-rider` 100%, `condition-lifted` 67–100%. Both recovered on their own: phase 3's
  examples rewrite already carries the `poisoned`-lifting worked example this phase planned to
  add, so its step 3 was a no-op. `condition-lifted`'s residual failures are two shapes worth
  knowing apart — a correct plan whose roll simply misses (the case asserts an unconditional
  outcome, so a dice-gated plan can never pass it), and a `check` written with no branches at
  all, which settles nothing. The first is a case-design flaw, not a model fault.
- `long-rest-recharge` 78%. The 0% → 67% → 0% swing was small-n noise; nothing was ever wrong.
- `advantage-attack` 0/9, and closed as a model limit rather than a prompt gap. The rule is now
  taught twice — prose in `dnd5e/director.md` and the trigger list in the `mode` field
  descriptions (`dnd5e/actions.py`), which the schema golden confirms ships in the tool schema.
  Every run still writes `mode: "normal"` with an identical plan and zero retries. Two
  independent surfaces moved nothing, so further tuning would be guessing.
- `movement-follows-exits` 0% → 67%, having regressed from the 100% this list once credited to
  the `_EXITS` clause. Two independent faults, both fixed, neither a prompt-wording problem —
  see below.
- `self-heal-scaling` 56% and `story-check-both-directions` 0–22%, neither named by this list.
  One fault, upstream of the Rules Director: the Scene Director silently replaces what the player
  declared with a goal of its own — "dig into my last reserve of stamina" becomes *searching the
  cloister*, and a deliberate, unopposed act becomes a risk roll for hidden clues. The Rules
  Director then faithfully realizes the directive it was given. Pre-existing, not caused by the
  fixes below: `story-check-both-directions` failed 2/3 on the baseline with the identical plan,
  and its 33% there was the noise, not the 0% after.

  One clause was tried on the Scene Director's quiet-turn list (deliberate unopposed acts, plus a
  line against replacing the player's goal) and **reverted**: `story-check-both-directions` 0→22%
  against `self-heal-scaling` 56→22%, both inside the noise floor at n=9. Scene-role goal
  substitution is the standing open problem here and wants its own measured phase, not a clause.

The two fixes the re-baseline actually earned, both in core rather than in wording:

1. **Both directors read the whole canon side.** `render_director` gave the Rules Director only
   the `SCENE DIRECTIVE`, substituting it for `EXISTS BUT THE PLAYER DOES NOT KNOW IT YET`,
   `ACTIVE THREADS`, and `SCENARIO NOTES`. The directive is now appended to that view instead of
   replacing it. The leak rule binds the *narrating* role, and neither director writes prose, so
   the canon reaches both safely. This alone cut `movement-follows-exits`'s retry deaths from 6/9
   to 1/9.
2. **`_require_exit` tells the truth about an unfound way** (`state/apply.py`). It collapsed *no
   such connection* and *the connection exists but the player has not found it* into one refusal
   reading as a flat illegal-destination. The model believed it and dropped the move: 8/9 runs
   shipped `effects: []` rather than the reveal-then-move pair `_EXITS` prescribes. The second
   case now names the fix in the refusal itself. One message in core, so both engines get it.

Standing lesson: a prompt-wording phase found no prompt-wording bugs. Both real faults were core
code lying to the model — one by withholding context, one by misdescribing a refusal. Measure the
model's *input* before rewriting its instructions.

## Phase 6 — Small proven deletions (~½ day)

Remove local YAGNI before changing the engine boundary, but only where every current caller proves
the smaller shape. This phase is behavior-preserving, makes no persisted or model-facing change,
and records the net source-line movement without treating it as an acceptance target.

1. **One content lookup surface.** No `Record` subclass enters a runtime `Pack`; the SRD importer
   flattens its authoring-time `Interpreted` values first, and every `Content.get`/`require` caller
   asks for `Record`. Delete the generic type parameter, `kind` argument, `wrong_type` miss,
   `SerializeAsAny`, `get()`, and `resolves()`. Keep
   `record(ref) -> Record | ContentMiss` and `require(ref) -> Record`, with the existing
   `unknown_pack`/`unknown_index` distinction. Update all engine, script, and test callers; pack
   round-trip bytes must remain identical.
2. **One frozen value base.** Remove `state.packs.Value` and the `Frozen.__hash__` override; use
   `state.base.Frozen` for refs, records, manifests, and specs. `ContentRef` must remain hashable
   because it keys `Content.records`. Keep `FrozenMap`: `frozen=True` blocks field assignment but
   does not freeze a contained dict, and authored values must remain immutable.
3. **One UI panel module.** Fold the small chat, roles, state, trace, advancement, and engine-badge
   modules into `src/aidm/ui/panels.py`; delete the now-empty `panels/` and `components/` packages.
   This is file/import consolidation only: screenshot-visible behavior and callback ownership stay
   unchanged.
4. Inline `read_trace` into its sole caller, `FileTraces.load`. Keep `FileSaves` and `FileTraces`
   separate: their codecs and operations differ, and the mechanics boundary will change save
   loading in phase 8.

Done when: all 130 tests and checks pass without regenerated fixtures; `Content` exposes only
`record`/`require`/`provides`; there is one frozen value base and one UI panel module. Record the
actual net Python delta in `PROGRESS.md`.

## Phase 7 — Test-only Ironsworn-shaped boundary probe (~1 day)

Build no third shipped engine. Keep a tiny engine permanently behind tests: temporary as product
code, durable as the executable counterexample that prevents Story and 5e from defining the core
by accident. It is Ironsworn-shaped, not an Ironsworn implementation.

1. Add a test fixture with strict engine-owned mechanics: characters with momentum-like bounded
   state and progress tracks with their own validation. Add one typed action with three outcomes
   that mutates those mechanics deterministically from a seeded RNG and emits `Fact`s. The fixture
   imports world entities, ids, dice/facts where useful, but never `Sheet`, sheet effects,
   `EngineSpec`, packs, advancement, or a shipped engine.
2. Exercise the boundary the production contract must support: create mechanics from authored
   JSON, validate a round trip and reject corrupt JSON, render an entity, resolve the action,
   initialize mechanics for an actor created during play, and explicitly expose no advancement or
   content capability. Do not register it in the launcher or `ENGINE_MODULES`.
3. Capture the decisions the fixture proves in an ADR before production moves: core owns entities,
   placement, discovery, relations, threads, hooks, and uninterpreted fictional traits; an engine
   owns all numeric/mechanical state and its whole plan lifecycle; persisted mechanics is JSON to
   core and a strict Pydantic model inside the engine; one engine-owned commit path validates both
   halves; core hooks write world operations only. Keep the fixture and its contract tests after
   the spike.

Done when: the test-only engine demonstrates the target boundary without a production registration
or universal mechanic, and phase 8 has an explicit method-by-method contract written down in an
ADR rather than an illustrative sketch.

## Phase 8 — Separate fictional world from engine mechanics (~3–5 days)

Replace `WorldState.Record(entity, rules: Sheet)` with fictional entities only and add one opaque
mechanics payload to the persisted game envelope. Story and 5e each validate that payload into
their own strict mutable Pydantic model whenever they create, load, resolve, render, or commit it.
Core never branches on a mechanical field.

- Migrate sheet tags that describe lasting fiction into a core `Trait`/`TraitChange` world
  facility, so shared hooks can still author `warded` and both engines can read conditions without
  core interpreting them. Counters, numbers, notes, content refs, recharge, and advancement
  mutations move into engine mechanics. Keep small primitives such as `Counter`, dice, ids, and
  facts where two implementations genuinely reuse them; remove the universal `Sheet` aggregate.
- Engine plans own their complete validated output and resolution. Core exposes typed world
  operations, but it no longer fixes a mechanical effect union into `TurnPlanBase`. Direct engine
  mutations replace `apply_effect` calls for damage, healing, costs, refills, and bookkeeping.
- Route every transaction through the engine-owned commit operation established by phase 7. The
  core `GameState` validation checks the envelope and world; engine validation checks mechanics.
  Beginning a game and adding a Worldkeeper-created entity both ask the engine to initialize that
  entity's mechanics.
- Migrate Story first, then 5e, reading state/turn fixture diffs at each step. Bump `SAVE_VERSION`;
  stale saves are refused as usual. Finish by running the retained test-only engine through the
  real initialization, resolution, rendering, creation, and commit paths.

Done when: core has no `Sheet`, counter/number/note/ref effect, or mechanical-field lookup; all
three contract suites pass; a corrupt mechanics payload fails at load/commit; shared world hooks
and the Narrator leak boundary still behave exactly as specified.

## Phase 9 — One engine object with optional capabilities (~2–3 days)

Collapse `EnginePlugin` plus the loaded wrapper into one concrete engine object built by a module
factory. Registration remains one module-name entry; core still never imports or dispatches a
concrete action.

- The object owns metadata, plan type and resolution, mechanics creation/validation/rendering,
  instructions/tools, and whatever content interpretation it needs. Delete delegation rather than
  first making callers reach through `engine.plugin`; the six current re-exports disappear with
  the split itself.
- Advancement becomes an optional engine-owned capability with its own proposal type, offer,
  validation, preview, and application. Remove generic `SheetDelta` after both shipped engines use
  their typed capability. The app and UI depend only on the optional capability.
- Pack manifests, refs, generic records, and byte-stable loading remain reusable dumb storage.
  `spec.json`, projection, examples, packs, and advancement instructions are no longer mandatory
  engine ceremony: D&D may keep files its real content needs; Story should not carry empty ones.
- Preserve the acceptance test that adding an engine changes only its package plus one registry
  entry. The test-only probe remains unregistered and capability-free.

Done when: `EnginePlugin`, the wrapper split, universal sheet advancement, and mandatory empty
engine files are gone; Story and 5e still build once at the composition root and expose the same
catalog, plans, tools, turns, and advancement behavior.

## Phase 10 — Simplify role construction and prompt rendering (~2–3 days)

Keep `run_turn()` explicit. Share only model invocation plumbing and safe context serialization.

- Consolidate agent construction/caching without hiding role-specific output validators, tools,
  fallback modes, or dependencies. Adding a role remains one config entry, one construction, and
  one explicit `run_turn` call.
- Keep distinct typed Director and Narrator input models; the Narrator type must have no hidden
  canon field. Prototype one compact, deterministic renderer for their repeated sections. Adopt
  it only if golden diffs are intentional, prompt tokens do not grow, and same-hour evals do not
  regress. Direct `model_dump_json()` is not assumed safe or compact.
- Retain the Director's `ToolOutput` plus plain-text JSON fallback and the other documented
  gpt-oss transport repairs. Each has a production rationale or a test; removing them is not
  YAGNI. Preserve phase 5's measured reveal/movement wording.

Done when: role construction has one obvious path, prompt safety remains structural, and a new
keeper role needs no copied infrastructure. No generic workflow graph, configurable turn order,
or role middleware is introduced.

## Phase 10A — Consolidate engine ownership and world state (~3–5 days)

Finish the simplification the landed engine boundary exposed before adding more state and
capabilities. Preserve the public engine operations and the explicit turn pipeline; remove the
universal construction and duplicated world shapes around them.

- `engines/loader.py` owns only the engine contract, the explicit module registry, and construction
  dispatch. Each engine owns the resources it actually uses: instructions, examples, content,
  tools, configuration, and optional capabilities. D&D keeps its packs and `read_content` tool;
  Story carries no empty spec, empty content index, or irrelevant lookup tool. Adding an engine
  remains its package plus one registry entry — no entry-point discovery or plugin framework.
- The shared half of the Director brief keeps one owner above both engines: the world-effect
  vocabulary read from `engines/examples.json` and asserted complete against the `WorldEffect`
  union (`loader.py:171–188`). Pushing it down would grow the same append in every engine, which
  is the duplication this phase removes, not an ownership win.
- Dropping Story's `read_content` is model-facing, not internal: the tool list is advertised to the
  model and `tests/core/fixtures/schemas/story/director_tools.json` moves with it. Story's
  `director.md` never teaches the tool and Story ships no content for it to find, so it can only
  miss — but per working rule 2, probe Story's Director live before cutting that fixture.
- Preserve the engine surface callers already use (`id`, `badge`, `plan_type`, `begin`, `commit`,
  `renderer`, `check_plan`, `resolve_action`, and optional capabilities). This is an ownership
  refactor, not a new adapter layer or a rewrite of either engine's mechanics and resolvers.
- `WorldState` becomes the complete persistent fictional aggregate: entities, relations, threads,
  hooks, fired-hook ids, and pending notes. `GameState` keeps identity, scenario metadata, engine,
  opaque mechanics, history, and turn number. Memory joins `WorldState` in phase 11.
- `ScenarioWorld` contains that same validated `WorldState` beside its metadata and starting
  location. `world.json` keeps its authored arrays: one `mode="before"` validator raises on a
  duplicate entity or relation id and then keys them, because an id-keyed JSON object collapses a
  duplicate silently and would lose the check `authored.py:32–35,47–49` makes today. Scenario-only
  validation still rejects the reserved player id, checks the starting location and hook
  references, and requires runtime-only fired-hook ids and pending notes to be empty.
- A scenario's world holds no player, and `WorldState._check_relation` requires both ends to exist
  and pins `party-member` at `PLAYER_ID` (`world.py:127–139`). An authored relation naming the
  player is therefore refused. Keep the relation check whole and give the scenario the same shape
  it already uses for the player's own start: `starting_party: tuple[EntityId, ...]` beside
  `starting_location_id`, validated as authored actors, which `begin_game` turns into
  `party-member` relations in the same step that composes the player. No shipped scenario starts
  a companion, but phase 13 generates `ScenarioWorld` and would otherwise have no way to.
- `begin_game` deep-copies that world and then adds what only runtime holds — the player entity
  built from the character, and the character's own items. It stops rebuilding parallel tuple
  collections into runtime dictionaries; it does not stop composing the player.
- Bump `SAVE_VERSION`; update authored scenarios and the affected state/save fixtures to the new
  nesting. Refuse stale saves as usual — no converter. Model-facing text stays byte-identical apart
  from Story's tool list.

Done when: Story initializes without pack/spec/tool ceremony; D&D owns and validates its content
unchanged; all persistent fiction is reached through `state.world`; authored and runtime topology
have one validated representation; engine behavior, turn order, narration safety, and advancement
are unchanged. Expected current production reduction: roughly 20–55 lines — most engine code moves
to its owner rather than disappearing, so fewer engine prerequisites and one world shape are the
acceptance criteria, not a larger LOC gate.

## Phase 10B — One owner for the scene rule, the counter effect, and growth (~2–3 days)

Three consolidations 10A does not reach, in the order of what they cost today. One commit per step.
Behavior-preserving except step 1, which fixes a turn that currently dies. Runs after 10A, because
10A moves `threads`/`hooks`/`pending_notes` under `WorldState` and reshapes `Engine`'s construction,
and all three steps read those.

### 1. One scene answers who may be voiced (~½ day)

The rule for who the Narrator may speak as is implemented twice. `check_speaker`
(`state/plan.py:13`) judges the Scene Director's `speaker_id` against `GameState` before the turn
resolves and returns a refusal the role retries on. `_speaker` (`turn/prompts.py:373`) judges it
again against `VisibleScene` after resolve and hooks, and raises. Between the two, the plan may
move the player or the speaker, so a directive that was legal when written is fatal by the time it
is rendered:

```
scene picks speaker_id="mara" (an actor in the study, with the player)
player prompt: "I leave for the cloister."
director plans {"op": "move", "entity_id": null, "to_id": "cloister"}
→ ValueError: speaker 'mara' is not a visible actor here   (turn/prompts.py:378)
```

`run_turn` raises before `engine.commit`, so the whole turn is discarded — three model calls
spent, nothing written — and `ui/busy.py:22` shows the player a notification with no state behind
it.

- Presence becomes one question the scene answers: `voice(speaker_id) -> Entity | None` on the
  shared scene base, returning the actor only when that scene holds them as a voiceable actor.
- `check_speaker` keeps its four refusal strings unchanged — they are model-facing and tested
  (`test_story_engine.py:114`) — and derives presence from the pre-turn scene instead of
  `is_here`/`known` directly.
- `_speaker` asks the post-turn scene and falls back to the existing
  `"(none — narrate the scene)"` when the speaker has left. A speaker who walks out of the scene
  is fiction, not a fault.
- Test: the repro above, asserting the turn commits and the narration renders. No golden moves; no
  shipped golden has an absent speaker.

### 2. The counter effect has one owner (~½ day)

`apply()` is char-for-char identical in both engines but for the union alias and the helper name
(`dnd5e/mechanics.py:175-182`, `story/mechanics.py:106-113`): not a `CounterChange`, fall through to
the world; else read mechanics, reveal the target, move the counter, write back. The probe engine
would copy it a third time.

- `engines/counters.py` owns the protocol; an engine supplies the counter lookup and its own
  read/write. It already owns `CounterChange`, `adjust`, `spend`, and `write_mechanics`, so nothing
  new crosses into core and ADR-0001 is untouched — this is engine-layer sharing, not core.
- Accept this step only if the shared signature stays narrower than the 16 lines it replaces. Three
  injected callables would not be a win; stop and leave the duplication if that is where it lands.
- `move_counter` and `_move_pool` stay per-engine: their counter lookup and refusal wording are
  genuinely different.

### 3. Growth has one consumer-side owner (~1 day)

10A leaves the capability owned by its engine and asks nothing of its consumers, where the cost is:
`GameSession` re-derives "is there an advancement" three times — `offer()` (`session.py:129`),
`_capability()` (`:158`), `_open()` (`:232`) — plus a fourth on `advisor is None` (`:136`), whose
own comment says it is the same fact stated twice.

- One module owns offer → propose → preview → confirm, holding the capability and its advisor
  together so the pair cannot be half-present. `GameSession` keeps one nullable accessor.
- `state/advancement.py` folds into it: 25 lines, two declarations, no function, no core caller.
  `AdvancementOffer._choice_is_whole` is a weaker copy of `packs.Record._choice_is_whole` — keep
  the stricter rule.
- Leave `assert isinstance(proposal, LevelUp)` alone. Erasing to `ProposalBase` is the price of
  removing the engine type parameter (`1c58662`), and phase 1 records the contravariance reasoning.
- The `render_proposal` call and the panel keep their current shapes; this is a consolidation of
  where the capability is asked about, not a change to what it offers.

Done when: one module answers who may be voiced and a departed speaker narrates instead of raising;
one module applies a counter effect; one module answers whether growth is available. No new adapter,
no capability registry, no generic role plumbing. Target production reduction: roughly 60–100
lines, almost all of it in step 3.

Note: the review's fourth candidate — the prompt compiler and content toolset in
`engines/loader.py` — is 10A's first bullet already, and is not repeated here.

# Part III — Features on the settled boundary

The original feature specifications are preserved below. Per the plan rule at the top, each phase
is re-resolved against the landed Part II types when it becomes next; only references to concepts
Part II explicitly removes (`Sheet`, `EnginePlugin`, fixed `Stage` plumbing, mandatory `spec.json`,
and fictional collections outside `WorldState`) are adjusted here.

## Phase 11 — Memories + Worldkeeper judgments (~4 days)

Durable memory that outlives the 6-exchange history window, then extend the existing Worldkeeper
to keep durable facts and judge fuzzy story transitions. Memory is a core narrative concern on
shared world state, never an engine-mechanics concern. The state model ships first and works alone;
the model-facing work remains the one existing post-narration Worldkeeper call.

### 1. Memory state, authored + rendered (deterministic, no model)

- `Memory(Mutable)` in `src/aidm/state/world.py`, beside `Thread`:
  `id: Slug`, `owner: EntityId | None` (None = the shared world), `text: str`
  (`min_length=1, max_length=300`), `tags: tuple[Slug, ...] = ()`, `turn: int = 0` (the turn it
  was recorded; authored ones are 0).
- `WorldState.memories: dict[Slug, Memory] = Field(default_factory=dict)`. Its whole-world
  validation checks that keys match ids and every `owner` is None or an existing entity id.
- Authoring: memories live in the `WorldState` already carried by `ScenarioWorld`; `begin_game`
  needs no memory-specific copy path. whispering-vault authors two: a world memory about the
  abbey's abandonment, and one owned by `mara` about Elena — canon the Scene Director should
  surface when the fiction reaches for it.
- Rendering: phase 10's typed Director input gains `memories: tuple[Memory, ...]` — those whose
  owner is None, the player, or an entity at the player's location. Rendered as a `MEMORIES`
  section for the Scene Director only, beside ACTIVE THREADS. The Scene Director weaves what
  matters into `focus`; the Narrator and Rules Director see nothing new, so a memory can safely
  hold unrevealed canon. The Narrator input has no field it could travel through, preserving the
  existing leak rule by construction.
- Bump `SAVE_VERSION`. Regenerate `save/*`, `state/*`, `turn/*`, `prompts/*` fixtures. One test
  in `tests/core/test_pipeline.py`: an authored memory of a present NPC reaches the scene prompt;
  a memory owned by an absent NPC does not; neither reaches the narrator prompt.

### 2. Extend the Worldkeeper report

- Output types in `src/aidm/state/turn.py`, beside `WorldkeeperReport`:
  `MemoryProposal(Frozen)` — `owner_id: EntityId | None` (description: exact id of who this
  belongs to, or null for the world), `text: str` (`max_length=300`, description: one concrete
  sentence, past tense). Extend `WorldkeeperReport` with
  `memories: tuple[MemoryProposal, ...] = ()` and
  `thread_moves: tuple[AdvanceThread, ...] = ()`. Deliberately add no importance score or second
  transition vocabulary: code reads neither.
- Extend the existing `WORLDKEEPER` instructions and renderer with ALREADY REMEMBERED (memories of
  present owners, so duplicates are visible) and ACTIVE THREADS. Durable memories record concrete
  facts about people and places, not play-by-play; **most turns should produce no memories or
  thread moves**, and empty tuples are the normal answer. A thread moves only when the committed
  turn plainly justifies it; never invent a stage the scenario has not used.
- The existing Worldkeeper stage receives the current draft as validation context. Every memory
  owner must name an entity that existed before this report, and every `thread_id` must name a
  thread in `state.world.threads`; request a `ModelRetry` otherwise. A creation and a memory about
  it need not land in the same turn — avoiding model-authored ids and name-resolution machinery is
  the deliberate simpler rule.
- Keep the one existing Worldkeeper call in `run_turn`. Apply admitted creations, memories, and
  thread moves deterministically after its report; all remain inside the turn's single final
  commit. Thread moves reuse `AdvanceThread` through the core world-operation path and never reach
  the Narrator.
- Memory admission mirrors `admitted()`: drop casefolded-duplicate text against all existing
  memories and cap accepted proposals at `Settings.max_memories: int = 2`. Each admitted proposal
  gets an id from a new slugifier beside `base.slug()` — the existing helper sanitizes with
  underscores (which fail the `Slug` hyphen pattern) and never truncates, while `Slug` caps at 64
  chars and memory texts run to 300. Hyphenate, truncate, de-collide against existing memory keys.
  Store with `turn=draft.turn`, and emit a non-narrating `Fact(kind="memory_kept")` for the trace.

### 3. Verification

- One pipeline test admits a memory, drops a duplicate, retries an unknown owner or thread, applies
  a justified thread move, and respects the cap. Existing Worldkeeper stubs default both new fields
  to empty, so unrelated turn tests need no new role plumbing.
- Update the existing Worldkeeper instruction and schema goldens; add no Memorykeeper or
  Threadkeeper fixture families or role config keys.
- Extend the existing Worldkeeper eval with a quiet case that keeps and moves nothing, a revelation
  worth remembering, and a fact-free narration beat that resolves a thread. Probe the changed
  output schema live before accepting it.

Done when: a fact-free narration beat (Mara opening up over several turns) can resolve a thread
without a hook or a Director write, memories persist across a save/load, and a full turn still
completes with the Worldkeeper's new fields empty in tests. A turn remains four model calls in the
worst case; no keeper pipeline or concurrency mechanism is introduced. Compared with the original
two-role design, this avoids roughly 70–120 lines of future production growth rather than removing
those lines from the current codebase.

## Phase 12 — Character creation workflow (~1–2 weeks)

In-app character creation producing exactly the files hand-authoring produces
(`characters/<slug>/base.json` + `<engine>.json`), validated by the existing load path — no new
runtime format, no bypass of `Character`'s own validators or the engine's authored-mechanics
validator. Story first (small), 5e second (the real test), advisor front-end last (optional).

### 1. The workflow shape + story creation

- `src/aidm/state/creation.py`: `CreationOption(Frozen)` — `id: Slug`, `label: str`,
  `detail: str = ""`; `CreationStep(Frozen)` — `id: Slug`, `prompt: str`,
  `options: tuple[CreationOption, ...]` (`min_length=1`), `choose: int = 1` (validator:
  `1 <= choose <= len(options)`). Picks are `Mapping[Slug, tuple[Slug, ...]]` (step id → chosen
  option ids). Nothing more until a real step needs it — no dependencies, no min/max ranges, no
  derived-value language.
- Phase 10A's engine-owned construction exposes an optional creation capability:
  `steps(picks) -> tuple[CreationStep, ...]` (takes the picks so far — Story ignores them, 5e
  derives follow-up steps from them) and `create(name, brief, picks) -> CreatedCharacter`, where
  `CreatedCharacter(Frozen)` holds `profile: CharacterProfile` plus the engine overlay written to
  `<engine>.json`. `create` raises `ValueError` with a readable reason on an illegal pick set
  (unknown step, wrong count, unknown option) — the UI shows it verbatim. Engines without the
  capability expose no creation page.
- `engines/story/create.py`: three static steps — an archetype (3–4 authored spreads of the four
  approach numbers, e.g. "Daring" = bold 2 / subtle 1 / clever 1 / empathetic 0), one edge trait,
  one burden trait (options authored in this file with concrete texts). Distributing free points
  would need a numeric-allocation step type; authored spreads keep the framework at
  pick-from-options, which is the deliberate ceiling of this phase.
- Validation test per engine: a full legal pick set → `CreatedCharacter` → write to a tmp dir →
  `load_character` → `begin_game` with whispering-vault succeeds. That chain exercises every
  validator the hand-authored path has.

### 2. The UI page

- `/create/<engine>` page in `src/aidm/ui/` (new `create.py` panel, registered in `app.py` like
  the game page; a "New character" button on the home page per engine). Renders: name input,
  brief input, then one `ui.select` (multiple when `choose > 1`) per step from the engine's
  creation capability, re-rendered on every pick (NiceGUI refreshable) so follow-up steps appear.
  Create button: slugify the name against existing character dirs, call `create`, write both JSON
  files with `model_dump_json(indent=2)`, navigate home (the catalog re-reads the directory).
  `ValueError` → `ui.notify`, stay on the page.
- No preview pane, no back/forward wizard, no draft persistence — a page of selects is enough at
  3–7 steps. Revisit only if a step count forces it.

### 3. 5e creation

- `engines/dnd5e/create.py`. Static steps from content: race (the `races` collection), class
  (`classes`), background (`backgrounds`) — options built by iterating the engine's content
  records for the collection (label = record name, id = record index). One more static step:
  ability-priority, 2–3 authored assignments of the standard array (15/14/13/12/10/8) by casting
  or martial emphasis.
- Dynamic steps, data-driven: any chosen record whose `Record.options` and `choose` are set
  becomes one more `CreationStep` — this is exactly the shape advancement offers already read, so
  a class record's skill choices arrive for free through `steps(picks)`.
- `create` builds the engine overlay: refs for race/class/background (+ chosen options), numbers
  from the ability assignment, and no duplicate of level-1 defaults the engine derives from its
  content. Starting gear and spell choice are deliberately skipped this phase: characters start
  with `items: ()` and pick things up in play, and a caster's castable list arrives with the class
  ref in the current content model. Both are future work, noted below, not half-built now.
- Same round-trip test as Story, with a caster and a martial pick set.

### 4. Optional: advisor front-end

- One text box above the selects ("describe your character"), a `creation-advisor` role reusing
  the advancement-advisor pattern through phase 10's role path: `NativeOutput` of a picks-shaped
  model built from the steps, output validator = the same legality `create` enforces (run
  `create` in a try, `ModelRetry` the message). The picks land in the form for the player to
  review and edit — the advisor fills selects, it never writes files. Build only if hand-picking
  feels slow in practice.

Done when: a new Story and a new 5e character can be created in the app, both playable in
whispering-vault immediately, and `characters/kael` is untouched — hand-authoring stays a
first-class path. Deferred, on purpose: starting gear, spell choice, and migrating advancement
onto this machinery (wait until the workflow has proven itself in play).

## Phase 13 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at authoring
time. This is a script, not the app: agentic workflows are fine outside the turn loop, where
speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the shared format already exists and
   is the validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`; `Settings.role()` resolves any name). Give it one read-only tool
   returning whispering-vault's `world.json` as the worked example, and put the authoring bar in
   the instructions: 4+ locations connected by relations with at least one hidden and one
   `locked` way, 2+ NPCs with at least one unrevealed, one secret item, at least one thread with
   hooks that advance it on `entity_discovered` facts, hook `note`s that steer the Director, and
   `detail.hook` on every entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then validate the world alone — a `Scenario` per
   engine with an empty/default overlay, `begin_game` with the shipped `kael`, and the engine's
   normal mechanics validation. Any `ValueError` goes back to the agent as a retry message, max
   3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per engine, output that engine's strict authored-overlay model,
   prompted with the generated world, engine-provided authoring guidance/defaults, and (for 5e)
   a compact list of legal monster refs from its pack. Re-run step 2's loop with each generated
   overlay in place — the overlay is what `begin_game` exercises beyond shared structure. The
   creator never assumes a `Sheet`, projection rules, or mandatory `spec.json`.
4. Files land in `scenarios/<slug>/` only after every engine validates. The script prints a
   summary (entities, relations, threads, hooks per engine) and the author reviews the diff
   before committing — generated content merges by the same review as hand-written content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under both engines. Quality beyond validity
is judged by playing it, not asserted by the script. PDF/notes ingestion is a later input mode for
the same script, not a separate system.

## Phase 14 — Media: scene illustrations (~2–3 days)

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

# Considered and decided without a phase (updated 2026-08-11)

- **File reorg to a flat package layout**: rejected. Phase 6 consolidates only the tiny UI files;
  domain packages stay and files move only when a deletion makes the old boundary empty.
- **Generic path/value mechanical patches**: rejected. Core keeps typed world operations; each
  engine owns strict mechanical state and procedures.
- **`FrozenMap` removal**: rejected. Frozen Pydantic models do not deep-freeze contained dicts;
  the wrapper enforces the repository's frozen-value invariant.
- **One generic save/trace storage class**: deferred to phase 8 and expected to remain split unless
  opaque mechanics makes their codecs converge. A shared suffix does not make their APIs equal.
- **Shared path I/O helpers**: rejected. Pack, engine-resource, save, and trace reads/writes have
  different missing-file, parent-directory, newline, and append semantics; `utf-8` duplication is
  cheaper than erasing those contracts.
- **Provider config as `dict[str, ProviderConfig]`**: rejected. The present literal and model make
  provider names exhaustive and env configuration strictly validated.
- **Plain-text Director fallback removal**: rejected. It is a tested provider workaround, not an
  unused second design; phase 5 documents why the Director cannot rely on one native path.
- **Fact as the domain event stream**: already the architecture; Part III builds memories and
  thread judgment on it without adding an event bus or renaming it.
- **Ironsworn**: no shipped engine is scheduled. Phase 7 keeps only an Ironsworn-shaped test engine
  as permanent architectural pressure.
