# Kernel refactor — phased plan

Decided 2026-08-06, revised same day after adversarial review. The current architecture
has extension points, but each is a closed list: engines must ship a plan type plus four
hooks; the workspace, persisted `Turn`, and trace panel hardcode the four roles; every new
world mutation extends the central `Effect` union; per-entity state has exactly one shape
(`Sheet`). Party membership, memories, quests, new roles, and new engines would all keep
editing the same central files.

The refactor collapses this to one rule: **the kernel knows how to store, validate,
change, run, and trace; engines know rules; workflows know roles; content knows the
world.** D&D mechanics stay ordinary Python — attack, spell, rest, and advancement rules
are genuine domain complexity, never to be DSL'd away.

Acceptance criteria for the whole effort:

- No engine ships a `TurnPlanBase` subclass; no resolver contains an `isinstance`
  downcast. Adding an action to an engine touches only that engine's `actions.py` and
  `resolve.py`.
- Adding a role changes no runtime, trace, save, or UI code: the new step brings its own
  module (render function + step function) and is inserted into the workflow assembly.
- Both engines keep the identical file skeleton (layout at the end of this document);
  dnd5e additionally carries `records.py` and `packs/` because it ships content. The
  refactor changes file contents, never the file set.
- Framework LOC drops. Each phase states its budget below; every phase PR reports the
  `src/aidm` line delta, and a phase exceeding its additions budget sheds scope.

Cross-phase rules:

- Golden fixtures are the behavior contract. A phase that changes a persisted or rendered
  shape regenerates exactly the fixture families it names below, and the diff is
  reviewed; any other fixture moving is a bug.
- `SAVE_VERSION` bumps in every phase that changes persisted bytes (1, 3, 5, 6). Stale
  saves are refused, never converted (`content/store.py` already enforces this).
- `scripts/evals/run.py` imports pipeline internals (`default_cast`, `TurnWorkspace`,
  `render_director`, `PlanContext`) and `scripts/evals/probes.py` matches op strings and
  fact kinds on dumped plans. Phases 1, 2, and 5 must update the eval scripts and re-run
  the suite against `baseline.md`.

## Phase 1 — Worldkeeper + generic steps and trace (~2 days, budget −200)

Two changes that both rewrite `Turn` and `trace.py`, shipped as one branch so the save
shape, trace panel, and turn fixtures churn once.

**1a. Merge Maintainer + Creator into one Worldkeeper role step.** Today the Maintainer
proposes growth requests, code screens them, and the Creator runs once per accepted
entity — three concepts and 1 + N model calls for one job.

- New output model in `state/turn.py`: `Creation` (kind, name, brief,
  `detail: EntityDetail`, `location: str | None`) and
  `WorldkeeperReport(creations: tuple[Creation, ...])`. `EntityDetail` is reused as-is.
- One `worldkeeper_step` in `turn/pipeline.py` replaces `maintainer_step` +
  `creator_step`; `render_maintainer` and `render_creator` merge into one
  `render_worldkeeper` in `turn/prompts.py`.
- Screening becomes code applied to the report, preserving today's exact behavior
  (`screen_growth` + the creator loop):
  1. Dedupe names casefolded against existing world entities AND earlier entries in the
     same report; drop duplicates.
  2. Cap at `max_growth`; drop the excess. Dropped entries are not persisted — no
     rejection bookkeeping.
  3. Apply locations first (today's `kind != "location"` sort), so an NPC placed "at" a
     location created this same report resolves. Resolve `location` by casefolded name
     against world locations plus locations created earlier in this batch; fall back to
     the player's location.
- Delete: `Growth`, `GrowthRequest`, `GrowthRejectionReason`, `RejectedGrowth`,
  `ScreenedGrowth`, `screen_growth` (`state/turn.py`), `maintainer_step`, `creator_step`,
  `_created_entity`'s request plumbing (`turn/pipeline.py`), `render_maintainer`,
  `render_creator`, the `MAINTAINER`/`CREATOR` instruction constants (merged into one
  `WORLDKEEPER`), and the maintainer/creator sections of `ui/panels/trace.py`.
- Config: role settings key is `worldkeeper`; `ROLES__MAINTAINER__*` /
  `ROLES__CREATOR__*` env entries silently stop applying (`Settings.roles` is an open
  dict — by design). Note it in the commit message.
- Risk note: the merged schema is Growth plus `EntityDetail` per entry — bigger than the
  maintainer schema the 3/3 gpt-oss NativeOutput probe covered. Live-probe it once before
  trusting `NativeOutput`; fall back to `ToolOutput` if it writes empty output (same
  failure mode as the director finding).

**1b. Generic step traces.** The script loop already exists (`TurnScript` is a
`(name, StepFn)` tuple `run_turn` iterates); what's closed is the persisted `Turn` and the
trace panel, which name each role.

- New in `state/turn.py`: `StepTrace(name: str, kind: Literal["role", "code"],
  prompt: str | None, output: dict[str, JsonValue] | str | None)`.
- `Turn` becomes: `prompt`, `narration`, `facts`, `steps: tuple[StepTrace, ...]`. The
  director's plan persists as the director step's `output` (dumped `mode="json"`, as
  `Turn.plan` is today); `narrator_evidence` persists as the resolve step's `output`.
- `TurnWorkspace` keeps `plan`, `evidence`, and `narration` as first-class fields —
  `resolve_step` and `narrator_step` genuinely depend on them, and `run_turn`'s two
  closing checks (plan settled, narration non-empty) stay. The
  `growth`/`accepted`/`rejected`/`created` fields are deleted (1a). Steps append their
  own `StepTrace` to `ws.steps`; the `ws.prompts` dict dies with it.
- `trace_panel` loops over `entry.steps` — one generic section per step, prompt behind
  the existing expansion. It is never edited for a new role again.
- Dissolve `Cast`: `default_workflow(engine, settings, options) -> TurnScript` in
  `turn/pipeline.py`, called from `app/session.py`. A challenger, second director, or
  image step is an inserted `(name, StepFn)` pair whose module owns its render function;
  `turn/prompts.py` remains the home of the shared scene machinery (`SceneSnapshot`,
  `VisibleScene`, section helpers) new roles import.

Fixtures regenerated: `fixtures/turn/*`, `fixtures/prompts/*` (maintainer+creator →
worldkeeper), `fixtures/schemas/growth.json` → worldkeeper schema. Tests touched:
`test_growth.py`, `test_golden_turn.py` (`TURN_PROMPTS`), `test_context_boundary.py`.
`scripts/evals/run.py` rebuilt around `default_workflow`. One `SAVE_VERSION` bump.

Acceptance: pipeline runs director → resolve → narrator → worldkeeper; no growth types
remain; `trace.py` contains no role names.

## Phase 2 — Action registry, one TurnPlan (~2 days, budget −50)

Engines register actions; the loader builds the Director's action union; the four-hook
plugin dies. The resolver signatures below are wider than a naive registry because the 5e
resolvers genuinely need the engine (content, recharge spec) and the plan (branch
inspection) — do not narrow them.

- In `engines/loader.py`, next to `EnginePlugin`:

  ```python
  @dataclass(frozen=True, slots=True)
  class ActionSpec[A]:
      model: type[A]                # Frozen model with an `act` Literal discriminator
      labels: Callable[[Engine, A], frozenset[Slug]]   # outcome labels; constant via lambda
      resolve: Callable[[Engine, GameState, TurnPlanBase, A, Random], tuple[list[Fact], Slug | None]]
      check: Callable[[Engine, GameState, TurnPlanBase, A], str | None] | None = None
  ```

  `resolve` mutates the draft and returns the outcome; the **kernel** applies the matching
  branch (`apply_branch`) and then the plan's unconditional effects — resolvers never
  call `apply_branch` themselves. `check` receives the whole plan so 5e's `_double_spend`
  (which inspects `plan.effects` and every branch) moves into the `CastSpell`/`UseFeature`
  checks unchanged.
- `EnginePlugin` drops `plan_type`, `check_plan`, `resolve_action`, `offered`,
  `check_delta`; gains `actions: tuple[ActionSpec[...], ...]`,
  `action_doc: str` (the engine-specific `action` field description — LLM-consumed,
  runtime behavior, kept per engine), and `advancement: Advancement | None`.
- `Advancement` (not "Progression" — the codebase already says advancement everywhere) is
  a dataclass in `engines/loader.py`: `offered` + `check_delta`, implemented in each
  engine's `advance.py` as today.
- The loader builds the plan model once per engine with
  `create_model("TurnPlan", __base__=TurnPlanBase, action=(...))` where the annotation is
  `Annotated[Union[*models], Field(discriminator="act")] | None` — **trap**: a
  single-action engine (story) collapses `Union[Risk]` to `Risk`, and a discriminator on
  a non-union raises `PydanticUserError`; special-case one spec to plain `Risk | None`.
  Pin the generated model's title/config so the emitted JSON schema is stable, then
  regenerate `fixtures/schemas/{story,dnd5e}` and review the diff.
- The kernel plan check (was `check_plan` per engine): speaker guard + branch-label check
  (`check_plan_base`) + the spec's `check` + a trial resolve on a throwaway draft with
  `Random(0)`, wrapped in `try/except ValueError` → refusal string. The wrap is mandatory:
  an output validator that raises kills the turn instead of retrying (`loader.py` says
  so today).
- Delete: `StoryPlan`, `Dnd5ePlan`, `_story_plan`, `_dnd5e_plan`, the
  `PlanCheck`/`ActionResolver`/`Offered`/`DeltaCheck` type aliases, and both engines'
  `check_plan`/`resolve_action` wrappers. Each 5e `_resolved` match arm becomes that
  action's `resolve` function; the `_labels` match becomes per-spec `labels`.
- Delete `Dnd5ePlan.milestone_earned` and the `MILESTONE_TAG` path in
  `dnd5e/resolve.py` outright: IDEAS.md records it as unmeasured, and scenario-marked
  milestones (`milestone-level` on a location, already implemented in
  `dnd5e/advance.py`) are the reliable path. This is the phase's main LOC win beyond the
  downcasts.
- Re-run evals live against `baseline.md` — the director schema shape changes, and
  gpt-oss quality is sensitive to exactly this (eval-conditions history).

Acceptance: no engine ships a plan subclass or an isinstance downcast; both engines'
`rules.py` declare `PLUGIN` with `actions=`, `action_doc=`, `advancement=`; `story/` and
`dnd5e/` have the identical file set.

## Phase 3 — Components (~2 days, budget +80, accepted)

`Record.rules: Sheet` becomes `Record.components`, with `Sheet` surviving as the `sheet`
component. Speculative until `memory`/`location-state` land — accepted deliberately; the
budget is honest about it being LOC-positive.

The validation mechanism (this is the part that must not be improvised — the transaction
model validates with no engine in scope today):

- `Record.components: dict[Slug, SerializeAsAny[BaseModel]]` holds **live typed models**,
  so resolvers keep mutating in place (`sheet_of` returns the same object all turn) and
  `model_dump(round_trip=True)` keeps working per entry.
- A registry `ComponentRegistry = Mapping[Slug, type[BaseModel]]`; core registers
  `{"sheet": Sheet}` in `state/world.py`; `EngineSpec`-level additions come later, with
  real features.
- Validation reaches the registry through Pydantic validation context: a wrap validator
  on `Record.components` reads `info.context["components"]` and validates each entry
  against its registered type (unknown component name → fail fast). Consequently
  `GameState.committed()` gains the registry:
  `committed(registry: ComponentRegistry)`. Every call site already has the engine in
  scope: `resolve_step`, `run_turn`'s final commit, `_trial` in `state/plan.py`,
  `GameSession.apply_proposal`/`_begun`. `Engine` exposes `engine.components`.
- Typed access: `component(state, entity_id, Sheet)` in `state/world.py` — looks up by
  the registered name for that type, asserts the instance type, returns it. `sheet_of`
  and `player_sheet` keep their exact signatures, implemented on top of it.
- `content/authored.py` is untouched in meaning: an overlay's `Rules` dict is still the
  sheet definition; `compose_world` builds `components={"sheet": ...}`.
- `engine.validate_state` keeps its current job (canonical keys, ref resolution) — it is
  not the component validator; the transaction boundary is.

Fixtures regenerated: `fixtures/save/*`, `fixtures/state/*`. One `SAVE_VERSION` bump.

Acceptance: a new component type is one model + one registry entry; `sheet` behavior is
byte-identical in saves apart from the `rules` → `components.sheet` key move.

## Phase 4 — Ironsworn proof (~2 days, LOC excluded — new engine content)

Two engines can share an accident; a third is the test. Copies the canonical layout
file-for-file: actions (face-danger-style moves), resolvers, `spec.json` (momentum via
`Counter.minimum < 0`, already supported), `director.md`, `advancement.md`,
`examples.json`. No `records.py`/`packs/` until it ships content.

- A playable proof also needs content the plan for once must not forget:
  `scenarios/whispering-vault/ironsworn.json` overlay and an ironsworn character overlay
  (`load_scenario`/`load_character` are engine-keyed).
- Ironsworn ships permanently and gets one eval scenario, or phase 5's vocabulary change
  has an engine no eval covers.

Acceptance: zero core-file changes except one line in `ENGINE_MODULES`. If any
phase-1/2/3 seam forces more, fix the seam before merging.

## Phase 5 — One change language (~3 days, eval-gated, budget −100)

Unify `Effect` and `DeltaChange` into one union applied by one function. Highest
model-quality risk in the plan — the Director's effect vocabulary is rewritten and the
advisor's schema grows. Prerequisites before any code:

1. Write advisor evals (none exist — today's suite gates only the Director half).
2. Live-probe the advisor's `NativeOutput` on gpt-oss (IDEAS.md item, never done).

The design decisions, so nobody re-derives them mid-flight:

- The unified union keeps the name `Effect`, lives in `state/effects.py`; `DeltaChange`
  and its ops in `state/sheet.py` are deleted. Saves and prompts already speak "effects".
- Every op carries `entity_id` (the advisor writes `player`) and `why: str = ""` —
  optional so the Director's schema doesn't force it; the advisor's output validator
  requires it non-empty, keeping the `CORE_ADVISOR` promise and the confirmation panel's
  per-change reasons.
- Context split is a flag, not a vocabulary: `apply_effect(..., advancing: bool = False)`.
  At turn time `set-number` refuses unknown keys and `grant-counter`/`add-ref` are
  refused outright; advancing, they grow the sheet (today's semantics, ported exactly).
- Creation stays out of the union: `GameState.add` called from the worldkeeper step and
  `GainImprovisedItem` are already the creation bookkeeping; nothing new.
- `scripts/evals/probes.py` matches op strings on dumped plans — update alongside, then
  run the full suite against `baseline.md` before merging.
- Bail-out, explicitly allowed: if evals regress and prompt tuning doesn't recover them,
  keep two vocabularies and extract only the shared mutation helpers (counter lookup and
  clamp, tag add/remove, note set) — that captures most of the ~150-line duplication at
  zero model risk.

Fixtures regenerated: schemas, `fixtures/turn/*` fact traces. `SAVE_VERSION` bump.

## Phase 6 — Scenario hooks, a proto-quest system (~2 days, budget +100 — a feature)

Scenario-authored triggers over the `Fact` stream: the simplest system that lets a story
progress from player actions. After phase 5 so hook consequences are written in the same
`Effect` language, not invented twice.

- A hook is data in `world.json` (`hooks: tuple[Hook, ...]` on `ScenarioWorld`): an id, a
  match (`kind` plus exact-equality `data` fields, e.g.
  `{"kind": "entity_discovered", "entity_id": "vault"}`), `effects: tuple[Effect, ...]`,
  and an optional `note: str`. Shape-validated at load; no trial application (a hook may
  reference state that only exists mid-game).
- A code step runs **after the worldkeeper** (so it sees every fact the turn produced,
  including creations), one single pass per turn: for each unfired hook whose match hits
  any fact, apply its effects, emit a `hook_fired` Fact, and add its id to
  `GameState.fired_hooks: set[str]`. Chaining happens across turns, never within one
  pass — no fixpoint loop.
- A refusing effect (`ValueError`) must not kill the player's turn on an authored-content
  bug: catch it, record a `hook_failed` Fact with the reason, and mark the hook fired
  anyway (no retry loops).
- The note transports to the **Director only, next turn** — the Director already ran when
  hooks evaluate, and a scenario-authored free-text note shown to the Narrator is a
  canon-leak channel by construction (the Narrator's input type must have no field a leak
  can travel through). Mechanism: notes append to `GameState.pending_notes:
  tuple[str, ...]`; `render_director` gains a `SCENARIO NOTES` section; the director step
  clears them on the draft after rendering. The Narrator needs nothing: a hook's effects
  produce Facts, and Facts already reach it through `narrator_evidence` with the leak
  filter built in.
- This is the seed of quests/events: a quest stage is a hook whose effects set state and
  whose note steers the Director. Grow it only when a real scenario outruns it.

Fixtures: `fixtures/save/*` (fired set, pending notes), director prompt fixtures.
`SAVE_VERSION` bump.

Acceptance: whispering-vault ships at least one authored hook; firing it requires no core
edits beyond the hook runner itself.

## Feature-time (not this refactor)

- Relations (`at`, `connected`, `party-member`, `holds`) replace `parent_id` when
  connected locations or party membership is built.
- Additional components (`memory`, `location-state`, `quest`) land with their features,
  on the phase-3 registry.
- Entry-point engine discovery: rejected — `ENGINE_MODULES` stays a two-line tuple.

## Canonical engine layout

Both engines keep this identical skeleton; a new engine copies it file-for-file. dnd5e
alone adds the two content-bearing entries. The refactor changes file contents, never the
file set.

```
src/aidm/engines/<engine>/
  rules.py         # the PLUGIN: id, badge, engine_dir, actions, action_doc, advancement, (record_types)
  actions.py       # action models + outcome-label constants
  resolve.py       # per-action resolve + check functions (ordinary Python)
  advance.py       # offered / check_delta — the Advancement bundle's implementation
  director.md      # role instructions
  advancement.md
  examples.json    # worked plans, validated at load against the built TurnPlan
  spec.json        # templates, recharge, collections
  records.py       # dnd5e only — typed pack records
  packs/           # dnd5e only — shipped content
```
