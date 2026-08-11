# Plan

The phased plan for what is built next, in order. Written 2026-08-11. Each phase carries enough
detail to implement without prior context; only the next unshipped phase needs full resolution,
and a later phase is rewritten to this resolution when it becomes next.

Part I (phases 1–4) simplifies the architecture; Part II (phases 5–9) builds features on the
simplified core. Simplification comes first so every feature phase is specced once, against the
shape that will carry it.

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
  per-engine — the standing design for Part II (the review's "double down on Fact" point; also
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

# Part II — Features

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

## Phase 6 — Memories + keepers (~4 days)

Durable memory that outlives the 6-exchange history window, then two proposal roles: a
Memorykeeper that keeps durable facts, and a Threadkeeper that judges fuzzy story transitions.
Memory is a core narrative concern on shared world state, never an engine sheet concern (Part I
acceptance criteria). Three steps, each a commit; the state model ships first and works alone.
Wiring language below assumes the post-phase-2 shape: a role is one config entry, one agent
construction beside the others, one explicit call in `run_turn` — this phase is re-resolved
against the landed code when it becomes next.

### 1. Memory state, authored + rendered (deterministic, no model)

- `Memory(Mutable)` in `src/aidm/state/world.py`, beside `Thread`:
  `id: Slug`, `owner: EntityId | None` (None = the shared world), `text: str`
  (`min_length=1, max_length=300`), `tags: tuple[Slug, ...] = ()`, `turn: int = 0` (the turn it
  was recorded; authored ones are 0).
- `GameState.memories: dict[Slug, Memory] = Field(default_factory=dict)`. In
  `_consistent_world`: keys match ids (copy the threads check), and `owner` is None or an
  existing entity id.
- Authoring: `ScenarioWorld.memories: tuple[Memory, ...] = ()` (`src/aidm/content/authored.py`),
  uniqueness checked in `_valid_topology` like threads; carried through `begin_game`
  (`src/aidm/app/session.py`) exactly as `threads` is. whispering-vault authors two: a world
  memory about the abbey's abandonment, and one owned by `mara` about Elena — canon the Scene
  Director should surface when the fiction reaches for it.
- Rendering: `SceneSnapshot` (`src/aidm/turn/prompts.py`) gains
  `memories: tuple[Memory, ...]` — those whose owner is None, the player, or an entity at the
  player's location. Rendered as a `MEMORIES` section in `render_director`'s no-directive branch
  only, beside ACTIVE THREADS. The Scene Director weaves what matters into `focus`; the Narrator
  and Rules Director see nothing new, so a memory can safely hold unrevealed canon —
  `VisibleScene` has no field it could travel through, which is the leak rule this repo already
  enforces by construction.
- Bump `SAVE_VERSION`. Regenerate `save/*`, `state/*`, `turn/*`, `prompts/*` fixtures. One test
  in `tests/core/test_pipeline.py`: an authored memory of a present NPC reaches the scene prompt;
  a memory owned by an absent NPC does not; neither reaches the narrator prompt.

### 2. Memorykeeper

- Output types in `src/aidm/state/turn.py`, beside `WorldkeeperReport`:
  `MemoryProposal(Frozen)` — `owner_id: EntityId | None` (description: exact id of who this
  belongs to, or null for the world), `text: str` (`max_length=300`, description: one concrete
  sentence, past tense) — and `MemorykeeperReport(Frozen)` with
  `memories: tuple[MemoryProposal, ...] = ()`. Deliberately no importance score: code reads none.
- `MEMORYKEEPER` instructions + `render_memorykeeper` in `src/aidm/turn/prompts.py`: sections
  SCENARIO, WHAT HAPPENED (evidence), NARRATION, ALREADY REMEMBERED (existing memories of present
  owners, so duplicates are visible), PLAYER ACTION. Instructions mirror the Worldkeeper's
  admission tone: durable facts about people and places, not play-by-play; **most turns should
  produce no memories** and an empty report is the normal answer.
- Wiring: one agent construction beside the other stage builders, one explicit call in `run_turn`
  after the worldkeeper (its creations can then own memories the same turn). Admission is code,
  mirroring `admitted()`: drop a proposal whose owner id does not exist, drop a
  casefolded-duplicate text against all existing memories, cap at
  `TurnOptions.max_memories: int = 2` (new field, wired from a new `Settings.max_memories`). Each
  admitted proposal: an id from a new slugifier beside `base.slug()` — the existing helper is
  not usable here: it sanitizes with underscores (which fail the `Slug` hyphen pattern) and never
  truncates, while `Slug` caps at 64 chars and memory texts run to 300. Hyphenate, truncate,
  de-collide against existing memory keys. Stored with `turn=draft.turn`, and a
  `Fact(kind="memory_kept", narrator=None)` for the trace.
- Role config key `memorykeeper` (any name works — `Settings.roles` is an open dict). **Probe the
  output mode live** (working rule 2) before cutting fixtures.
- Tests: extend `tests/core/core_test_support.py`'s `played()` with the new role (stubbed to an
  empty report by default); one pipeline test where a stubbed proposal is admitted, a duplicate
  and an unknown owner are dropped, and the cap holds. New goldens: `instructions/memorykeeper`
  family and `schemas/memorykeeper_report.json`.
- Eval: extend `scripts/evals/run.py`'s `Role` literal and `_turn` dispatch with `memorykeeper`
  (the worldkeeper turn function is the template — it also runs the standalone phase against an
  authored narration); one case asserting a quiet turn keeps nothing and one that a revelation is
  kept. New probe `memory_kept` in `probes.py`.

### 3. Threadkeeper

- The fuzzy-transition role: hooks fire on exact fact matches, the Director advances what the
  directive names; the Threadkeeper judges what neither can — "has this quietly moved on?" —
  from the committed turn.
- Output `ThreadkeeperReport(Frozen)` in `state/turn.py`:
  `moves: tuple[AdvanceThread, ...] = ()` — reuse the existing effect class, its `why` included;
  no new vocabulary. Output validator (like the scene stage's `known`): every `thread_id` names a
  thread in `state.threads`, `ModelRetry` otherwise.
- Wiring: explicit call in `run_turn` after the memorykeeper. The call **skips the model
  entirely** when no thread is `active` (a trace entry with "(no active threads)" keeps the trace
  honest). Applies each move with `apply_effect` on the draft — thread facts never narrate, so
  running after the Narrator loses nothing.
- Prompt `render_threadkeeper`: SCENARIO, ACTIVE THREADS (the `_threads` renderer), WHAT
  HAPPENED, NARRATION, PLAYER ACTION. Instructions: move a thread only when this turn's committed
  events plainly justify it; moving nothing is the normal answer; never invent a stage for a
  thread whose stages the scenario has not used.
- Same test/eval/golden shape as the Memorykeeper. Probe the output mode first.

Done when: a fact-free narration beat (Mara opening up over several turns) can resolve a thread
without a hook or a Director write, memories persist across a save/load, and a full turn still
completes with both keepers stubbed off in tests. Cost note: the turn is now 6 model calls worst
case; if latency hurts, the keepers are the two steps that can later run fire-and-forget — do not
build that now.

## Phase 7 — Character creation workflow (~1–2 weeks)

In-app character creation producing exactly the files hand-authoring produces
(`characters/<slug>/base.json` + `<engine>.json`), validated by the existing load path — no new
runtime format, no bypass of `Character`'s own validators. Story first (small), 5e second (the
real test), advisor front-end last (optional).

### 1. The workflow shape + story creation

- `src/aidm/state/creation.py`: `CreationOption(Frozen)` — `id: Slug`, `label: str`,
  `detail: str = ""`; `CreationStep(Frozen)` — `id: Slug`, `prompt: str`,
  `options: tuple[CreationOption, ...]` (`min_length=1`), `choose: int = 1` (validator:
  `1 <= choose <= len(options)`). Picks are `Mapping[Slug, tuple[Slug, ...]]` (step id → chosen
  option ids). Nothing more until a real step needs it — no dependencies, no min/max ranges, no
  derived-value language.
- `EnginePlugin` (`src/aidm/engines/loader.py`) gains two required fields:
  `creation_steps: Callable[[Engine, Picks], tuple[CreationStep, ...]]` (takes the picks so far —
  story ignores them, 5e derives follow-up steps from them) and
  `create: Callable[[Engine, str, str, Picks], CreatedCharacter]` (name, brief, picks), where
  `CreatedCharacter(Frozen)` in `creation.py` holds `profile: CharacterProfile` and
  `overlay: CharacterOverlay`. `create` raises `ValueError` with a readable reason on an illegal
  pick set (unknown step, wrong count, unknown option) — the UI shows it verbatim. Required
  fields mean both engines land in the same commit that adds them.
- `engines/story/create.py`: three static steps — an archetype (3–4 authored spreads of the four
  approach numbers, e.g. "Daring" = bold 2 / subtle 1 / clever 1 / empathetic 0), one edge tag,
  one burden tag (options authored in this file with concrete tag texts). Distributing free
  points would need a numeric-allocation step type; authored spreads keep the framework at
  pick-from-options, which is the deliberate ceiling of this phase.
- Validation test per engine: a full legal pick set → `CreatedCharacter` → write to a tmp dir →
  `load_character` → `begin_game` with whispering-vault succeeds. That chain exercises every
  validator the hand-authored path has.

### 2. The UI page

- `/create/<engine>` page in `src/aidm/ui/` (new `create.py` panel, registered in `app.py` like
  the game page; a "New character" button on the home page per engine). Renders: name input,
  brief input, then one `ui.select` (multiple when `choose > 1`) per step from
  `plugin.creation_steps(engine, picks)`, re-rendered on every pick (NiceGUI refreshable) so
  follow-up steps appear. Create button: slugify the name against existing character dirs, call
  `plugin.create`, write both JSON files with `model_dump_json(indent=2)`, navigate home (the
  catalog re-reads the directory). `ValueError` → `ui.notify`, stay on the page.
- No preview pane, no back/forward wizard, no draft persistence — a page of selects is enough at
  3–7 steps. Revisit only if a step count forces it.

### 3. 5e creation

- `engines/dnd5e/create.py`. Static steps from content: race (the `races` collection), class
  (`classes`), background (`backgrounds`) — options built by iterating `engine.content.records`
  for the collection (label = record name, id = record index). One more static step:
  ability-priority, 2–3 authored assignments of the standard array (15/14/13/12/10/8) by casting
  or martial emphasis.
- Dynamic steps, data-driven: any chosen record whose `Record.options` and `choose` are set
  becomes one more `CreationStep` — this is exactly the shape advancement offers already read, so
  a class record's skill choices arrive for free through `creation_steps(engine, picks)`.
- `create` builds the overlay: refs for race/class/background (+ chosen options), `numbers` from
  the ability assignment. Level-1 numbers the projecting collections already provide (hp, class
  facts) land at compose time — do not duplicate them in the overlay. Starting gear and spell
  choice are deliberately skipped this phase: characters start with `items: ()` and pick things
  up in play, and a caster's castable list arrives with the class ref in the current model. Both
  are future work, noted below, not half-built now.
- Same round-trip test as story, with a caster and a martial pick set.

### 4. Optional: advisor front-end

- One text box above the selects ("describe your character"), a `creation-advisor` stage reusing
  the advancement advisor pattern: `NativeOutput` of a picks-shaped model built from the steps,
  output validator = the same legality `create` enforces (run `create` in a try, `ModelRetry` the
  message). The picks land in the form for the player to review and edit — the advisor fills
  selects, it never writes files. Build only if hand-picking feels slow in practice.

Done when: a new story and a new 5e character can be created in the app, both playable in
whispering-vault immediately, and `characters/kael` is untouched — hand-authoring stays a
first-class path. Deferred, on purpose: starting gear, spell choice, and migrating advancement
onto this machinery (wait until the workflow has proven itself in play).

## Phase 8 — Scenario creator (~3–4 days)

Premise → a complete scenario in the exact on-disk format, authored by a strong model at authoring
time. This is a script, not the app: agentic workflows are fine outside the turn loop, where
speed and small-model reliability do not constrain the design.

1. `scripts/create_scenario.py <slug> "<premise>"`. A pydantic-ai agent whose output type **is**
   `ScenarioWorld` (`NativeOutput`) — the strictest spec of the format already exists and is the
   validator. Role config key `creator` (set a strong model in `.env`:
   `ROLES__CREATOR__MODEL=...`; `Settings.role()` resolves any name). Give it one read-only tool
   returning whispering-vault's `world.json` as the worked example, and put the authoring bar in
   the instructions: 4+ locations connected by relations with at least one hidden and one
   `locked` way, 2+ NPCs with at least one unrevealed, one secret item, at least one thread with
   hooks that advance it on `entity_discovered` facts, hook `note`s that steer the Director, and
   `detail.hook` on every entity worth one.
2. Validation loop, in the script: `ScenarioWorld` validates structurally on output (the agent
   retries on `ValidationError` for free). Then the script validates the world alone — a
   `Scenario` per engine with an empty overlay (default template sheets satisfy
   `validate_state`), `begin_game` with the shipped `kael`; any `ValueError` goes back to the
   agent as a retry message, max 3 rounds, then fail loudly with the reason.
3. Overlays: a second agent call per engine, output `ScenarioOverlay`, prompted with the
   generated world, the engine's `spec.json` templates, and (for 5e) a compact list of legal
   monster refs from the pack. Re-run step 2's loop with each generated overlay in place — the
   overlay is what `begin_game` exercises beyond structure.
4. Files land in `scenarios/<slug>/` only after every engine validates. The script prints a
   summary (entities, relations, threads, hooks per engine) and the author reviews the diff
   before committing — generated content merges by the same review as hand-written content.

Done when: `uv run python scripts/create_scenario.py rats-of-thornhill "..."` yields a scenario
that appears on the home page and plays a first turn under both engines. Quality beyond validity
is judged by playing it, not asserted by the script. PDF/notes ingestion is a later input mode for
the same script, not a separate system.

## Phase 9 — Media: scene illustrations (~2–3 days)

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

# Considered and decided without a phase (2026-08-11)

- **File reorg to a flat layout** (`state.py`, `turn.py`, `events.py`, ... at package root):
  rejected. Packages stay; files shrink in place, and code moves only when a deletion leaves a
  file trivially small.
- **Generic path/value effect patches** as the endpoint of phase 3: rejected. They save lines by
  discarding the domain boundary, validation quality, and model guidance the typed vocabulary
  provides.
- **The full 19 → 8 effect merge** (grant/refill and the sheet ops folded in as modes): rejected
  after review. Cross-audience modes either advertise forbidden writes in the Director's schema
  or need per-audience variant classes — both cost more than the four classes they save.
- **Content simplification**: shipped before this plan (`Record` as one fact map, data-only
  collections); the residual `EngineSpec`/projection interpreter in core is ~30 generic lines and
  earns its place.
- **Fact as the domain event stream**: already the architecture; Part II builds memories, thread
  judgment, and hooks on it rather than adding parallel systems.
- **Ironsworn**: not scheduled; its acceptance criteria are Part I's done-conditions.
