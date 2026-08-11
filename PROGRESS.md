# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

## Phase 1 — The engine owns its plan lifecycle — DONE

- `EnginePlugin.actions` → `check` + `resolve` callables; `Engine.check_plan`/`resolve_action` are
  one-line delegations. `ActionSpec`, `_spec`, `_action`, the label machinery: deleted.
  loader.py 380 → 335 lines.
- Shared trial helper `check_plan_with_trial` in `state/plan.py` beside `apply_branch`; takes the
  engine's resolve callable, so `plan.py` never imports `Engine`.
- story: `check`/`resolve` in `rules.py`; `resolve_risk` narrowed to `tuple[list[Fact], Slug]`
  (it always names an outcome), so the None-check disappears.
- dnd5e: `resolve.py` gains `resolve` + `resolve_action` (a `match` over `actions.Action` — the
  union is the registry, spelled once); `rules.py` folds `improvise_labels`/`cast_labels` into `_labels` and
  `check_cast`/`check_feature` into `_paid_by_engine`.
- Deviation from the plan, deliberate: dnd5e's double-spend check now runs *before* the trial
  resolve rather than after. It judges the plan's own effects against untouched state and does not
  depend on the resolve; only a plan with both faults sees a different first message.
- Tests touched: `test_loader.py` (stub plugin takes the two callables), `test_resolve.py`
  (`ACTS` is derived from the `Action` union instead of counting a table that no longer exists,
  so a seventh action with no worked example still fails).
- Verified: `grep -r ActionSpec src tests scripts` empty, no `getattr(plan, "action")` in core,
  no fixture moved, no `SAVE_VERSION` bump.

## Phase 2 — One explicit run_turn — DONE

- `run_turn` is one explicit async function, ~85 lines, reading draft → scene → director →
  resolve → hooks → narrator → worldkeeper → commit. Locals replace the workspace; the nullable
  `plan`/`directive` and their unwrap guards are gone. pipeline.py 354 → 299 lines.
- Deleted: `TurnWorkspace`, `StepFn`, `TurnScript`, the six step factories, `default_workflow`.
- Three plain functions the evals call standalone: `resolve_plan`, `apply_hooks`,
  `apply_creations`. The first two return the revalidated draft alongside their facts, which is
  what the workspace's `ws.draft = ws.draft.committed().draft()` did in place.
- `Stages` (scene/director/narrator/worldkeeper) + `build_stages`, built once by the session;
  the four `*_stage` builders are unchanged. `played()` stubs the bundle per role.
- `session.role_names` → `TURN_STEPS` literal; step names byte-identical, so no `turn/*`
  fixture moved (130 tests pass, no fixture file in the diff). No `SAVE_VERSION` bump.
- `scripts/evals/run.py` calls the same plain functions. `_worldkeeper_turn` now runs the agent
  directly instead of a step closure, so it reports real retries and tokens where it used to
  hardcode `retries=(), tokens=0`.
- Second deviation, deliberate: the empty-narration guard now raises before the worldkeeper call
  rather than after the whole script. The turn is discarded either way; the only difference is one
  model call not made on a narrator that answered nothing.
- Tests: `test_a_script_takes_an_extra_step_without_core_edits` deleted with the abstraction it
  tested (a new role is an explicit call site now, which needs no framework test); `played()`
  lost its `extra` parameter. `test_pipeline.py` ties the observed step order to `TURN_STEPS`,
  which the UI progress panel reads. Net −1 test, 130 passing.

## Phase 3 — Effect vocabulary: 19 ops → 12 — DONE

- Twelve ops. `Move` (actor + item), `CounterChange(mode: adjust|spend)`,
  `TagChange(mode: add|remove)`, `RelationChange(mode: add|remove|untag|reveal)`; `TagRelation`
  deleted with no replacement (authored blocked ways are `Relation.tags` in world.json, and
  `mode: untag` is the only writer that lifts them). `Reveal`, `GainImprovisedItem`,
  `GrantCounter`, `Refill`, `SetNote`, `SetNumber`, `AddRef`, `AdvanceThread` unchanged.
- The three audience unions keep their membership exactly: `TurnEffect` is 7 members,
  `SheetEffect` 6, and no mode is policed at runtime — the unions still carry the whole permission
  story. The Director's plan schema lost ~480 lines.
- Naming deviation from the plan, deliberate: the mode field is `mode` on all three merged ops,
  never `op` — `op` is the union discriminator and cannot double as the mode.
- Two new validators, both stopping a real bug rather than a cosmetic one: a `spend` with a
  negative `amount` would refill the pool it claims to pay from, and `tag` is required exactly
  when `mode: untag`. `TagChange` gets none: `text` on a remove is inert.
- `apply_effect`'s match dispatches on `(op, mode)` patterns; every `Fact` kind and every
  `fact.data` field is preserved, so hook matching and eval probes do not move.
  `_require_carried` folded into `_move_item`, `_tag_relation` deleted.
- Three observable deltas beyond the vocabulary movement, all found by review and all kept:
  `relation_revealed` now carries the effect's `why` in its trace (`RevealRelation` had no `why`;
  `RelationChange` does, and a silently dropped field is worse than a longer trace); a `move`
  that omits `entity_id` now reads as a player move rather than failing a required-field check,
  so a malformed item move gets a movement refusal instead of a validation error; and spend's
  `ge=1` moved from the JSON schema into a validator, since the constraint is per-mode — the
  model now learns it from the field description and the retry message.
- `_effect_vocabulary` (loader.py) now checks per *mode*, not per op: `turn_effect_keys()` expands
  each merged op into one key per mode, `effect_key()` reads one back off an example. The check
  relaxed from "exactly once" to "nothing missing", because `move` legitimately wants two worked
  examples (an actor and an item) and has no mode to tell them apart.
- Rewritten authored surfaces: `engines/examples.json` (13 examples, all 12 keys),
  `engines/{story,dnd5e}/examples.json`, whispering-vault's `warded` hook, both `director.md`,
  both `advancement.md`, and `_IDS`/`_EXITS` in `turn/prompts.py`.
- `SAVE_VERSION` 46 → 47 (hooks in saved state carry effects); `schemas/*`, `instructions/*`,
  `save/*`, `state/*`, `turn/*` regenerated. Diff read: only the vocabulary movement plus the
  version bump. 130 tests pass, ruff and basedpyright clean.

- Live probe (working rule 2) passed: whispering-vault plays under both engines on the merged
  schema, and the Director still writes effects — the shrink did not land on gpt-oss-120b's
  zero-effect failure mode. The `--only director` eval pair is skipped: evals are suspended until
  Part I lands (working rule 3), and phase 5 re-baselines the settled tree anyway.

## Phase 4 — Collapse the authored-world intermediate — DONE

- `begin_game` (`app/session.py`) composes `WorldState` directly from `Scenario` + `Character`:
  build the player entity, merge the two overlays, one loop building each `Record` through
  `engine.sheet`, then `WorldState` + threads + hooks. 15 → 38 lines there, −60 in `authored.py`.
- Deleted: `AuthoredWorld`, `AuthoredEntity`, `authored_world`, `compose_world` (authored.py 210 →
  150 lines) and `Engine.initial_world` + `Engine._entity_rules`. `Engine._sheet` is public
  `sheet(kind, rules)` — the one thing composition needs from the engine.
- The deep copies stay where they were, per entity/relation/thread: loaded content is `Mutable`
  and `restart()` re-runs `begin_game` against the same `Scenario` object, so game state must
  never alias it. Only `hooks` passes through by reference, as before — `Hook` is frozen.
- The duplicate-id check moved into the same loop, message unchanged.
- Tests: `test_an_engine_refuses_an_authored_payload_it_cannot_read` now poisons the scenario
  overlay and calls `begin_game`, so it exercises the real launch path rather than a hand-built
  intermediate; `test_an_authored_ref_backs_the_sheet_and_renders_its_other_facts` calls
  `engine.sheet` directly. No test added — the composition has no new branch.
- Verified: `AIDM_GOLDEN_REGEN=1 uv run pytest` rewrote every fixture and `git status` on
  `tests/core/fixtures` stayed empty — byte-identical, no `SAVE_VERSION` bump. 130 tests pass,
  ruff and basedpyright clean.

## Phase 5 — The prompt pass — DONE

- Re-baseline: one `--only director` suite on HEAD (maintainer chose one over the planned two),
  `results/2026-08-11-7e848d4.json` — overall 78%, completion 98%. Per-case comparison against
  PLAN.md's 2026-08-07 list retired two of its four entries outright and re-attributed a third.
- Step 3 was already landed: `dnd5e/examples.json` carries the `poisoned`-lifting worked example
  (a `check` success branch, an effects-only removal, and a `prone`-adding branch) from phase 3's
  rewrite, and `director.md`'s WHAT BELONGS WHERE already mirrors it. No change made.
- Advantage taught in two places — 3 sentences in `dnd5e/director.md` and the trigger list in the
  three `mode` field descriptions (`dnd5e/actions.py`) — and `advantage-attack` stayed 0/9 through
  both. Identical plan every run, zero retries; the schema golden proves the description ships.
  Closed as a gpt-oss-120b limit, not a prompt gap. The teaching stays: it is correct, and a
  stronger model will read it.
- **Both directors now read the whole canon side.** `render_director` substituted the
  `SCENE DIRECTIVE` for `EXISTS BUT THE PLAYER DOES NOT KNOW IT YET` / `ACTIVE THREADS` /
  `SCENARIO NOTES`; it now appends. Neither director writes prose, so the leak rule (which binds
  the narrator) is untouched. Three instruction claims that had gone false were rewritten:
  `SCENE_DIRECTOR`'s "You alone are shown…" and "The Rules Director cannot see these", and
  `_DIRECTIVE_BRIEF`'s "The directive is also your only view…".
- **`_require_exit` distinguishes an absent way from an unfound one** (`state/apply.py`). One
  refusal covered both and read as a flat illegal destination, so the model dropped the move
  instead of revealing the way: 8/9 runs shipped `effects: []`. The unfound case now names the
  reveal-then-move fix in the refusal text. Core, so both engines get it.
- `movement-follows-exits` 0% → 11% (canon fix; retry deaths 6/9 → 1/9) → 67% (refusal fix), all
  at n=9. Re-attributed numbers: `long-rest-recharge` 78% (the 0/67/0 swing was noise),
  `condition-rider` 100%, `condition-lifted` 67–100%, `self-heal-scaling` 56% (a Scene Director
  misread, not an engine fault — left alone).
- Tests: `test_a_scene_directive_replaces_the_directors_own_canon_view` asserted the old
  substitution and became `test_both_directors_read_the_canon_and_only_the_narrator_is_kept_from_it`,
  trimmed to the three assertions that carry it. `test_movement_follows_the_connections_the_world_authors`
  matches the new unfound-way refusal. Net 0 tests, 130 passing.
- Scene-role goal substitution is the standing open problem behind `self-heal-scaling` (56%) and
  `story-check-both-directions`: the Scene Director replaces what the player declared with a goal
  of its own. One clause was tried on the quiet-turn list and reverted — 0→22% against 56→22%,
  both inside the noise floor at n=9. Recorded in PLAN.md so it is not re-tried blind.
- Prompt clarity-and-size pass over every model-facing surface (`prompts.py` instruction
  constants, both `director.md` and `advancement.md`, `effects.py` field descriptions): same
  information, plainer language, `_DIRECTIVE_BRIEF`/`_EXITS`/`WORLDKEEPER` restructured from
  chained prose into bullet lists where each rule stands alone. **Mean tokens/turn 9631 → 8522
  (−11%)** at an unchanged overall rate (80.2% → 80.5%).
- One clause was restored to its pre-pass wording: `_EXITS`'s reveal-then-move rule. Compressed to
  a noun-phrase fragment it read 33% at n=9; back as "Walking an exit the player has not found yet
  is one plan, not two: …" it reads 67% twice. The lesson is worth keeping — a rule the model must
  *act* on survives compression worse than one it must merely know.
- Goldens: `instructions/*` (all 10), `prompts/{dnd5e,story}/director`,
  `schemas/dnd5e/turn_plan.json`. No `SAVE_VERSION` bump — no persisted bytes change.

## Phase 6 — Small proven deletions — DONE

- **One content lookup surface.** `Content` exposes `record`/`require`/`provides` only. Deleted:
  the generic type parameter, the `kind` argument, the `wrong_type` miss reason, `get()`,
  `resolves()`, and `SerializeAsAny` on `Pack.records`. Every caller already passed `Record`
  (loader ×4, `dnd5e/advance.py`, `evals/probes.py`, `tests/dnd5e/test_content.py`), and the SRD
  importer already flattens `Interpreted` through `.generic()` before a pack is written — so no
  `Record` subclass ever entered a runtime `Pack`. `validate_state` now probes the same
  `record()` it uses everywhere else. packs.py 285 → 256 lines; pack round-trip bytes unchanged.
- **One frozen value base.** `state.packs.Value` and the `Frozen.__hash__` override are gone;
  `ContentRef`, `Record`, `Manifest`, `Pack`, `ContentMiss`, `EngineSpec`, the sheet templates,
  and the SRD importer's authoring values all subclass `state.base.Frozen`. `Value` existed only
  to keep Pydantic's generated hash that `Frozen` threw away, so `ContentRef` could key
  `Content.records`; deleting the override made the second base pointless. `FrozenMap` stays —
  `frozen=True` does not freeze a contained dict.
- **One UI panel module.** `chat`, `role_badges`, `trace_panel`, `advancement_panel`,
  `state_panel`, and `show_engine_badge` moved verbatim into `src/aidm/ui/panels.py` (170 lines);
  the `panels/` and `components/` packages are deleted. Import consolidation only — no callback
  ownership or rendered output changed, and `test_package_boundary` still walks the package.
- `read_trace` inlined into its sole caller `FileTraces.load`. `FileSaves`/`FileTraces` stay
  split, per PLAN.
- Net Python delta: **−43 lines** (166 added, 209 deleted). 130 tests pass, ruff and basedpyright
  clean, no fixture regenerated, no `SAVE_VERSION` bump.

## Phase 7 — Test-only Ironsworn-shaped boundary probe — DONE

- `tests/probe/probe_engine.py` (137 lines): a `Fighter` with bounded momentum under a per-fighter
  `ceiling` (10 minus its debilities) and `Track`s that refuse to be `resolved` below 40 ticks —
  two cross-field invariants no shared `Sheet` can express. One typed action (`Strike`) resolved
  by an action die against two challenge dice into strong/weak/miss, mutating mechanics directly
  and emitting `Fact`s. Five functions are the whole contract: `create`, `commit`, `initialize`,
  `render`, `resolve`. Not in `ENGINE_MODULES`, not in the launcher.
- Its entire import list is `aidm.state.base`, `aidm.state.dice`, `aidm.state.facts` — no `Sheet`,
  no sheet effect, no `EngineSpec`, no packs, no advancement, no shipped engine.
- `tests/probe/test_probe_boundary.py` (5 tests): authored JSON → mechanics → byte round trip;
  three corruptions only the engine can judge are refused (momentum over its ceiling, ticks past
  40, a resolved-but-unfilled track); the strike is deterministic per seed and reaches all three
  outcomes across 20 seeds; an actor created during play gains mechanics before the commit while
  an item gains none, and both render; and an **AST assertion** that the fixture imports nothing
  core must not own, plus that it exposes no advancement or content capability. The last one is
  the durable pressure — pushing engine concepts back into core now fails a test, not a review.
- `docs/adr/0001-world-mechanics-boundary.md` records what the fixture proves and gives phase 8
  the method-by-method contract: core owns fiction (entities, placement, discovery, relations,
  threads, hooks, facts, uninterpreted traits), an engine owns every number and its whole plan
  lifecycle, persisted mechanics is opaque JSON to core and a strict model inside the engine, one
  engine-owned commit validates both halves, and core hooks write world operations only.
- `tests/probe` added to pytest `pythonpath` and basedpyright `extraPaths`. 137 tests pass (+7),
  ruff and basedpyright clean, no fixture moved, no production file touched.

## Phase 8 — Separate fictional world from engine mechanics — DONE

- **Core owns fiction only.** `WorldState.records: dict[EntityId, Record]` (entity + `Sheet`)
  became `WorldState.entities: dict[EntityId, Entity]`; `Record`, `sheet_of`, `player_sheet`, and
  the whole of `state/sheet.py` are deleted. The dict owns the name `entities`, so iterating is
  `world.entities.values()` or `world.of_kind(kind)`.
- **`Trait` on the entity.** `Trait(id, name, text)` and `Entity.traits` carry the lasting fiction
  the sheet's tags used to: conditions, edges, burdens, gear benefits, and the `warded` a shared
  hook authors. `TagChange` became `TraitChange` (`trait_id`, facts `trait_added`/`trait_removed`).
  Core renders them: `prompts.entity_state` appends one `traits:` line under whatever the engine's
  own renderer wrote, so an engine never sees or re-renders core's fiction.
- **`GameState.mechanics: JsonValue`.** One opaque payload in the envelope. Each engine validates
  it into its own strict mutable model on every read and validates the dump back on every write —
  dumping runs no validator, so the round trip *is* the commit gate. `Engine.validate_state` became
  `Engine.commit(state)`: the one path that gives a new entity its mechanics and revalidates the
  half core cannot read. It runs at load, at the end of every turn, after an advancement, and after
  a new game is composed.
- **Effects split by owner.** `state/effects.py` keeps six world ops (`Reveal`, `Move`,
  `GainImprovisedItem`, `TraitChange`, `RelationChange`, `AdvanceThread`) as `WorldOp`/`WorldEffect`;
  `apply_effect(draft, effect)` lost its `default_rules` parameter and its `advancing` flag.
  `CounterChange` moved to `engines/counters.py` as an *engine* effect (and lost `maximum`, which
  only advancement ever set). `GrantCounter`, `Refill`, `SetNote`, `SetNumber`, `AddRef`,
  `SheetEffect`, `SheetDelta`, and `Effect` are gone from core entirely.
- **Plans are generic over their engine's vocabulary.** `TurnPlanBase` is now only the marker plus
  the stringified-JSON transport repair; `Branched[E]` carries `effects`/`branches` over the
  engine's own union, and `apply_branch`/`apply_all`/`check_effects`/`check_action` take that
  engine's applier as a parameter. Core no longer fixes a mechanical effect union into the plan,
  and the pipeline no longer applies `plan.effects` — `engine.resolve_action` owns the whole plan.
- **Story's mechanics are typed, not a map.** `Adventurer` spells out four approach ints and two
  `Counter` pools; a typo in an authored file now fails at load rather than sitting unread. The
  authored story overlay flattened to match (`{"bold": 2, ..., "stress": {...}}`), and its tags
  moved into the core-authored files.
- **5e keeps an open map, and says so in its own package.** `dnd5e/mechanics.py` owns `Sheet`
  (numbers/counters/notes/refs), the actor template that used to live in `spec.json`, content-ref
  projection, and rendering. `spec.json` is down to `collections` + `projecting`, which are content
  concerns; story's is `{"collections": {}}`.
- **Advancement speaks each engine's own language.** `ProposalBase` in `state/advancement.py`
  replaces `SheetDelta` the way `TurnPlanBase` replaces a shared plan: story proposes `Growth`
  (one change of four, the engine spending the three marks itself), 5e proposes `LevelUp` (picks,
  hit points, proficiency, slots, granted pools, ability improvements — the engine setting `level`
  and lifting `advancement-ready` itself). Both moved bookkeeping the model used to write into
  code, which is the same rule the turn already follows.
- `SAVE_VERSION` 47 → 48. Saves and traces from 47 are refused, never converted. Goldens
  regenerated in one pass; the diff is only the predicted movement — `records` → `entities` (a
  location no longer carries an empty sheet at all), `traits` on the entity, the engine half split
  out into `mechanics`, `sheet_delta.json` replaced by a per-engine `proposal.json`.
- Tests: `test_sheet.py` went with its subject, its counter-bounds half surviving as
  `test_counters.py`; `test_proposals.py` now exercises story's `Growth` and the 5e pick legality
  moved to the engine suite that owns it. Two eval probes got *stricter*, not looser —
  `NoStateChange` compares `state.mechanics` as well as the world (mechanics left `world`, so the
  old check had a hole a silent HP change would slip through), and `BranchAddsTag` follows the
  `trait-change` rename or `condition-rider` would never match a real plan again. The probe engine
  now round-trips its payload through a real `GameState.mechanics` and refuses a corrupted one,
  which is phase 7's fixture driving the paths phase 8 actually shipped. 133 tests pass, ruff and
  basedpyright clean.

### What the review changed

An adversarial review ran over the staged diff. Three findings were worth acting on:

- **The advisor had stopped seeing the character's traits.** `render_proposal` rendered only
  `engine.renderer(...)`, which is now mechanics alone — while story's `Growth.lose_trait_id` asks
  the model for "the exact id of a burden the character carries". Every shed-a-burden intent would
  have burned a guaranteed retry. `prompts.entity_state` (the engine's render plus the core
  `traits:` line) is now what both the turn and the advisor render, so there is one answer to
  "what does a role see about an entity".
- **A corrupt payload was being repaired instead of refused.** `commit` fills in mechanics for an
  entity created mid-turn, which cannot be told apart from an entry corruption dropped — so a save
  whose mechanics had lost the player was silently rebuilt, and 5e then died on a raw `KeyError`
  reading `level`. Both engines' `commit` now refuse a payload that names no player, before any
  gap is filled. ADR-0001's "fails at load and at commit, never silently" holds again.
- **`_double_spend` refused by counter name alone**, so a branch spending *another* entity's
  `slot-1` was rejected with a message that then lied about why. It compares the payer now.

Cuts taken with it: the six `del engine` adapter functions in both `rules.py` (each engine's
`mechanics` module now exposes `begin`/`commit`/`render` under the plugin's own names, passed
straight through), dnd5e's single-caller `resolve()` inlined into `resolve_plan` so both engines
read the same way, `apply_hooks`'s dead `engine` parameter, and `Adventurer.counter()`.
Renames the review earned: `check_plan_base`/`check_plan_with_trial` → `check_effects`/
`check_action` (the second adds a trial *resolve*, which the old names hid), `target` →
`reveal_target`, `counters.changed` → `counter_fact`, and `world.of_kind()` now requires its kind
— seven of ten callers wanted every entity and can say `world.entities.values()`.

### Honest line count

`src` is **net +183** (+1305/−1122): `state/` −451, `engines/` +631. That is the shape the phase
asks for and not a simplification by line count — concepts that existed once generically now exist
twice by design (two mechanics models replacing one `sheet.py` plus its spec templates, two typed
proposals replacing one `SheetDelta`). What core bought is that it no longer names a mechanical
field anywhere, which the probe engine proves by importing only ids, dice, and facts. Tests and
scripts came down 114 lines. The remaining recoverable ceremony — the `Engine` wrapper's fifteen
delegations, story's mandatory empty `spec.json`, and the ~25 lines of `read`/`write`/`apply`
plumbing duplicated between the two mechanics modules — is phase 9's deletion list, so it was left
alone rather than churned twice.

## Phase 9 — One engine object with optional capabilities — DONE

- **One object, no split.** `EnginePlugin` (12 callable fields, each taking the loaded `Engine`
  first), the `Engine` dataclass wrapper with its fifteen delegations, and `load_engine` are gone.
  `Engine` is an ABC: ClassVars `id`/`badge`/`plan_type`/`engine_dir`, an `__init__` that loads
  content, director instructions and toolset, and five abstract methods —
  `begin`/`commit`/`renderer`/`check_plan`/`resolve_action`. `StoryEngine` and `Dnd5eEngine`
  subclass it in their own `rules.py`; the plan checks and resolution that used to be free
  functions taking `engine` are the methods themselves, so the `del engine` lines went with them.
  loader.py 268 → 233 lines.
- **Registration is the class, not an instance.** A module declares `ENGINE = <its class>` and
  `ENGINE_MODULES` keeps its one line per engine. `plugins()`/`plugin_for()` became
  `engines()`/`engine_class()`, which hand back the class: the launcher reads `id` and `badge`
  off it without building the 5e content pack, and `build_engine` is now
  `engine_class(engine_id)(pack_paths)` — construction *is* the load.
- **Advancement is an optional capability.** `Advancement` (ABC: `proposal_type`, `instructions`
  read from the engine's own `advancement.md`, `offered`/`advance`/`violation`) replaces the four
  plugin fields every engine had to fill. `Engine.advancement` is `Advancement | None`, set by the
  engine that has one. The advisor stage is built from the capability, not the engine
  (`AdvisorContext.advancement`), `GameSession.advisor` is optional, and `session.offer()` returns
  None for an engine without the capability — which is already the "No advancement is on offer"
  the UI panel renders, so the UI needed no change.
- **Projection is 5e's, the spec stays shared.** `EngineSpec` lost `projecting` — the only reader
  was dnd5e's sheet building and ref rendering, so it is now `PROJECTING` in the new
  `engines/dnd5e/content.py`, checked against the spec's collections in `Dnd5eEngine.__init__` —
  the same guarantee the deleted `EngineSpec` validator gave.
  Deviation from the plan, by maintainer decision mid-phase: every engine keeps a `spec.json` even
  when it is `{"collections": {}}`, because parallel organization between engine packages is worth
  more than deleting one empty file; core reads it in `Engine.__init__` and exposes
  `engine_spec()` for the SRD builder and the 5e tests. `examples.json` and `advancement.md` did
  become optional — `tests/core/test_loader.py`'s stub engine ships neither and still loads.
- **Shared mechanics plumbing, half of it.** `write_mechanics` in `engines/counters.py` writes the
  "the dump is validated back: that is the commit gate" rule once. A matching `read_mechanics` was
  tried and reverted: `read_mechanics(Mechanics, state)` is the same length as the
  `Mechanics.model_validate(state.mechanics)` it hid, so it shared a rename, not an invariant.
  `apply` stayed per-engine too: the two differ in how they find a counter, and sharing that needs
  a callback worth more than the eight lines it saves.
- `begin_game` now calls `engine.begin(state, rules)` then `engine.commit(state)`: the old wrapper
  hid the commit inside `begin`, and the phase's rule is that a caller sees the commit that
  validates the half core cannot read.
- No fixture moved, no `SAVE_VERSION` bump, no persisted or model-facing byte changed: 133 tests
  pass, ruff and basedpyright clean. Net Python: **src +10** (383/−373), tests and scripts +18.
  The line count is flat because the class form spells out signatures the plugin's shared callable
  types used to imply; what went is the double indirection (`engine.plugin.check(engine, ...)`),
  four mandatory advancement fields, and core's knowledge that content can project.
- An adversarial review found no behaviour change and three cuts, all taken: `read_mechanics`
  above, `Dnd5eAdvancement(engine)` (its two arguments could only ever agree), and dnd5e's
  action dispatcher renamed `resolve_action` → `dispatch_action`, since a method and a free
  function of the same name in one file resolve correctly and read as a recursion that isn't.
  Left standing after weighing it: each engine's three one-line `begin`/`commit`/`renderer`
  methods delegating to its `mechanics` module. Inlining them saves ~9 lines per engine and moves
  mechanics writing into `rules.py`; the split between "how this engine assembles and plans" and
  "this engine's numbers" is worth more than the lines.

## Next

Phase 10 — simplify role construction and prompt rendering. `run_turn` stays explicit; the work is
one obvious path for building agents (the advisor now builds from a capability, the four turn
stages from `build_stages`) without hiding role-specific validators, tools, or fallback modes, and
a prototype compact renderer for the Director's and Narrator's repeated prompt sections — adopted
only if the golden diffs are intentional and prompt tokens do not grow.
