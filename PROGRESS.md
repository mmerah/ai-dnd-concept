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

## Phase 10 — Simplify role construction and prompt rendering — DONE

- **One module builds every role.** `turn/roles.py` now holds `Stage`/`stage`, the five role
  constructions (`scene_stage`, `director_stage`, `narrator_stage`, `worldkeeper_stage`,
  `advisor`), their deps types (`PlanContext`, `AdvisorContext`), `Stages`/`build_stages`, and the
  two transport repairs. `turn/advancement.py` is deleted: its instructions constant and
  `render_proposal` went to `prompts.py` beside every other role's instructions and renderer, and
  the advisor construction to `roles.py` beside every other role's. `turn/` is three modules with
  one job each — `prompts.py` renders and instructs, `roles.py` builds, `pipeline.py` runs the
  turn (291 → 174 lines).
- **`stage(validator=...)` ends the three-step dance.** Scene, Director, and Advisor each did
  `built = stage(...)` / `_ = built.agent.output_validator(f)` / `return built`; the validator is
  now an argument, typed `Callable[[RunContext[Deps], Out], Out]`, and every role is one `stage()`
  call. Nothing is hidden by it: each validator stays a named local function in its own builder,
  and the Director's `ToolOutput` + `TextOutput` pair, its toolset, and `ChannelSafeModel` are
  passed exactly as before. Adding a keeper role in phase 11 is one `stage()` call, one `Stages`
  field, one `run_turn` line.
- **Both transport repairs kept, both already tested**: `test_a_plan_answered_as_plain_text_json_settles_the_turn`
  covers `plan_from_text`, `test_a_tool_call_with_a_channel_marker_in_its_name_still_lands` covers
  `ChannelSafeModel`. Neither is YAGNI and neither was touched; `plan_from_text` gained the
  one-line why it was missing.
- **The compact-renderer prototype found one real divergence, and only that was adopted.** The
  Director's and Narrator's repeated sections were *already* one renderer (`_scene_sections`), so
  there was no second implementation to collapse. What the prototype turned up instead: the
  Narrator's view was rendered with ids everywhere except the player line. `label=_named` proved
  the intent existed; it only ever reached `_character`, so entity lines, exits, the speaker, and
  every trait still handed the Narrator `[id=...]` — while the NARRATOR instructions say never to
  recite one. The `label: Label` callable is replaced by one `ids: bool` threaded from the two
  render entry points (`_labelled`/`_named` collapse into `_label(entity, *, ids)`), and
  `render_narrator` passes `ids=False`.
- Adoption gates, all met: the golden diff is exactly the 9 ids leaving each narrator prompt and
  nothing else; the prompt **shrinks** 2109 → 1983 chars (story) and 3217 → 3089 (dnd5e), roughly
  −45 tokens a turn at identical word count; and no eval can regress because no eval case runs the
  narrator (`director`/`advisor`/`worldkeeper` only) and nothing downstream parses its output for
  ids. Every other role's prompt is byte-identical — the Director, Worldkeeper, and Advisor still
  get ids, which `test_the_roles_shown_everything_get_ids_...` still asserts.
- **Prompt reduction: dedup only, never compression.** Measured first — 72% of the Director's
  13.9k chars is the engine's own `director.md` plus the worked examples, not the core constants
  phase 5 already trimmed. Reading both `director.md` files turned up five places where a sentence
  restates another section *of the same assembled prompt*, and only those were cut: the "engine
  owns the arithmetic" rule was stated four times (`_DIRECTOR_OPENING`, `_PLAN_FIELDS`, and twice
  more per engine), and the "plan whoever the fiction has act, not a player reaction" rule twice,
  core and 5e, with the same monster example. Each cut keeps every engine-specific noun and every
  surviving sentence whole. One rewording the cuts forced: story's "Its three outcomes" lost its
  antecedent, so it reads "The roll's three outcomes".
- Compression itself was refused. Phase 5 measured what re-encoding a model-facing surface costs
  (`_EXITS` as a fragment: 67% → 33%), and the only gate that could catch that regression — live
  evals — is the one the working rules call noisy at n=9. `director.md` is dense, not fat: every
  paragraph teaches a rule the model must act on. Cutting proven duplication is free; cutting
  prose that teaches is a bet with no way to settle it.
- **Renderer collapse.** `_catalogue` was `_entities` plus a detail suffix, spelled out a second
  time; it is deleted and `_entities` takes `detail: bool = False`, which the Worldkeeper's
  "EVERYTHING THAT EXISTS" passes. The worldkeeper goldens not moving is the proof it is faithful.
  Left standing: `render_proposal` still spells its own section join, because `_sections` writes
  `TITLE:` and the advisor prompt writes `TITLE` — reusing it would move an advisor golden for a
  role that *does* have eval cases, which is a model-facing change to save two lines.
- The review pass took the deletions the consolidation had left: `TurnOptions` (two ints that
  duplicated `Settings` fields and their `ge=0` validation — `run_turn` and `GameSession` take
  `history_window`/`max_growth` directly), the `Validator` and `Placement` aliases, and the
  single-caller wrappers `_exits`, `_notes`, `_kind_label` (inlined; rendered output
  byte-identical, no golden moved). One prompt cut: `_PLAN_FIELDS`'s closing clause "the
  directive said what the turn is about" restated `_DIRECTIVE_BRIEF`'s first sentence verbatim
  in meaning and is gone — "Write no prose: the Narrator writes what the player reads." survives
  whole. Goldens: `instructions/{story,dnd5e}/director.txt` −47 chars each, exactly that clause.
  Kept deliberately: `TurnResult` (a dozen call sites read `.state`/`.turn`; a tuple reads worse
  at that fan-out), `Stages`/`build_stages` (the bundle is one field per role at every seam),
  `exchanges_to_messages` (keeps the pydantic-ai message types out of `pipeline.py`).
- Tests: one assertion added (`"[id=" not in prompt` in the narrator boundary test). No test
  deleted. Goldens: `prompts/{story,dnd5e}/narrator.txt` and the director instruction pair; the
  `turn/*` fixtures carry step outputs, not prompts, so they did not move. No `SAVE_VERSION` bump.
- 133 tests pass, ruff and basedpyright clean. Net Python: **src −24** (244/−268), tests and
  scripts −1. Model-facing text: **−912 chars** across the four goldens that moved (director
  instructions −374 dnd5e / −284 story, narrator prompts −128 / −126). One module fewer, one
  answer to "where does a role get built".
- Process note, worth more than the numbers: a subagent given a code-collapse spec read a stale
  copy of `prompts.py`, edited against it, and recovered by stashing the working tree and running
  `git stash drop` — deleting the whole phase from the tree. It was recovered from the dangling
  stash commit in the object database (`git fsck --unreachable`, then `git stash store`) and the
  final state was verified against markers, not against the agent's report, which described the
  destroyed work as "bad edits". A subagent must never be left to resolve a conflict with
  `git stash`/`reset`/`checkout`; the recovery instruction is to stop and report.

## Pre-Part III architecture review — DONE

- Read all 5,855 lines of production Python against the planned Part III features. The accepted
  simplification keeps the engine API and explicit pipeline, moves engine-specific construction
  out of the universal loader, and makes `WorldState` the complete fictional aggregate. Expected
  current production reduction: 20–55 lines; most of the engine code moves to its owner.
- `PLAN.md` now adds Phase 10A for that work. Phase 11 extends the existing Worldkeeper report with
  memories and thread moves instead of adding Memorykeeper and Threadkeeper roles, keeping a turn
  at four model calls and avoiding an estimated 70–120 lines of future growth. Later phases needed
  only the creation-capability ownership wording updated.

## Phase 10A — Consolidate engine ownership and world state — DONE

### 1. Each engine owns the resources it uses

- `engines/loader.py` 233 → 160 lines: the `Engine`/`Advancement` contract, the module registry,
  `engine_text`, and the two shared halves of the Director brief (`_effect_vocabulary` asserted
  complete against `WorldEffect`, `_examples` validated against the engine's own `plan_type`).
  Gone from core: `EngineSpec`, `engine_spec`, pack directory discovery, the `read_content` toolset
  with its `_record_text` renderer, and `Engine.record`/`.content`/`.collections`.
- `Engine.__init__` now assembles only the director brief. `pack_paths` stays in its signature —
  the composition root passes it to whatever it builds — and the base ignores it in one documented
  line, so an engine without content needs no override to drop it.
- `engines/dnd5e/content.py` 7 → 95 lines owns all of it: `Spec` + `collections()` reading its own
  `spec.json`, `load_content()` (which makes the `PROJECTING`-vs-collections check its own),
  `lookup()`, `director_toolset()`, `_record_text`, `_packs()`. `Dnd5eEngine.__init__` is four
  lines: super, content, toolset, advancement.
- Every `engine: Engine` parameter inside the dnd5e package became `content: Content`: all thirteen
  of them only ever looked a record up, and `Dnd5eAdvancement(content)` now reads `ENGINE_DIR`
  straight from the module that owns the directory. Nothing in the package types on the core
  contract any more.
- `director_toolset` → `director_toolsets: tuple[AbstractToolset[object], ...] = ()`. Story
  overrides nothing: no `spec.json` (deleted), no `Content`, no tool. `tests/core/test_loader.py`'s
  stub engine ships only a `director.md` and asserts exactly that — the phase's acceptance criterion
  as a test, not a review note.
- Callers outside `src` follow the ownership: `scripts/srd/build.py` and the three 5e content tests
  read `dnd5e.content.pack_format()`, and `probes._level_up_to` asserts
  `isinstance(engine, Dnd5eEngine)` before reading the levels pack — it was already 5e-only code.
- The `read_content` test moved to `tests/dnd5e/test_content.py` and now runs against the shipped
  SRD pack (`srd-2014/monsters/giant-rat`) instead of a synthetic tmp pack, so the tool is exercised
  on the content it actually ships with. `test_loader.py` keeps the generic pack round-trip and
  `validate_pack` tests, which never needed an engine.

### 2. One model-facing change beyond the planned tool list

- `schemas/story/director_tools.json` is `[]`, as the plan predicted.
- Unplanned, and a real leak: core's shared `_RETRY` told **both** directors to "Call
  `read_content` first when planning from a spell, feature, or stat block whose wording you cannot
  quote." Story has no such tool, and 5e teaches the same rule in its own `director.md` ("Your only
  tool, `read_content`, reads a record's full text when a line does not answer what you need"). The
  clause is deleted, not moved: `instructions/{story,dnd5e}/director.txt` each lost exactly that
  sentence and nothing else. Same fault class as phase 5's two findings — core text, not engine
  text, was lying to the model.
- **Probed live and passed**: the maintainer played Story with the empty tool list and its Director
  still plans, so the cut fixture stands. The ordering was still a deviation worth naming — working
  rule 2 asks for the probe *before* the fixture is cut, and here it came after, so for a while the
  tree carried a model-facing change nothing offline could judge.

### 3. `WorldState` is the whole persistent fiction

- `threads`, `hooks`, `fired_hooks`, and `pending_notes` moved from `GameState` to `WorldState`;
  `GameState` keeps identity, scenario meta, engine, opaque `mechanics`, history, and turn.
- One validator owns the fiction's integrity (`_consistent_fiction`): key/id agreement for all
  three keyed collections in one message, placement for every entity, the two relation kinds core
  interprets, and the hook rules (unique ids, fired ids authored, no hook fired twice).
  `GameState` is left with `_the_player_is_playable` — the player is the one thing only a played
  game holds.
- `check_placement` now has a single caller, so the authored world gets it by holding a
  `WorldState` rather than by re-running the same loop.

### 4. One validated representation of topology, authored and played

- `ScenarioWorld` keeps `world.json`'s flat arrays as its fields and derives the one validated shape:
  `@cached_property world -> WorldState`, keyed by id there because the file cannot key them itself
  without collapsing a duplicate silently. `_unique` refuses a repeated entity, relation, or thread
  id before the keying; `WorldState` refuses everything else. `world.json` bytes are unchanged.
  **Deviation from the plan, deliberate**: PLAN.md specifies `world: WorldState` as a field fed by a
  `mode="before"` validator. That shape was built first and cost 32 lines of reshaping machinery
  (`_AuthoredFiction`, a raw-dict `TypeAdapter`, an "already keyed" passthrough branch for dumped
  scenarios); the derived property reaches every acceptance criterion in 13 and makes `updated()`
  round-trips simpler, since a dump stays flat. Frozen models take `cached_property` (pydantic
  stores it outside the fields, so `model_dump` and the frozen hash both ignore it — checked, not
  assumed).
- Scenario-only validation is what only a scenario answers: the reserved player id, the starting
  location, the starting party, and the hooks' thread references. The planned "runtime-only fields
  are empty" check is gone with the nesting: a derived world never carries `fired_hooks` or
  `pending_notes`, so the check could not fail.
- `starting_party: tuple[EntityId, ...]` exists because `WorldState` refuses a `party-member`
  relation whose target is not `PLAYER_ID`, and a scenario holds no player. `begin_game` turns each
  id into that relation in the step that composes the player. A companion must be `known` and must
  start at `starting_location_id`: the relation is written `known=True` (which `WorldState` refuses
  against an unmet entity), and a companion authored in another room would render as "travelling
  with the player" while standing elsewhere. Kept by maintainer decision after the review called it
  speculative: no shipped scenario starts one, phase 13 needs it, and the cost is 8 lines.
- `begin_game` deep-copies the authored world once, adds the player and the character's items to it,
  ties the party, and returns `state.committed()`. That last call is load-bearing: a `WorldState`
  handed to `GameState` as an instance is not revalidated (`revalidate_instances` is pydantic's
  default), so the composition has to ask for the validation it used to get from building the
  collections field by field.

### 5. Fixtures and numbers

- `SAVE_VERSION` 48 → 49. `state/*` and `save/*` carry the nesting, `turn/*` the version,
  `schemas/story/director_tools.json` the empty tool list, `instructions/*/director.txt` the deleted
  clause. No `prompts/*` golden moved — the two `instructions/*` ones did, for the clause above.
- The state/save diff was checked structurally, not by eye: lifting the four fields back out of
  `world` and restoring the version reproduces the previous file exactly, for both engines and both
  families. The one movement the first regeneration showed beyond that — the player entity landing
  before the character's items — was not asked for, so `begin_game` keeps the old order.
- Tests 133 → 135: the bare engine that loads with no content ceremony, and the scenario that starts
  the party it authors (with the duplicate-id refusal `_unique` exists for).
- Net Python: **src 0** (286/−286), tests and scripts +13. The first pass of this phase was **+41**,
  against the review's estimate of a 20–55 line reduction; what closed the 41-line gap was not the
  moved code but four pieces of ceremony that had no business existing (see the review below). The
  review's own floor was −4, and the 4 lines between that and zero are the second `starting_party`
  guard, which the maintainer chose over deleting the field. The irreducible cost of the move itself
  is the ~70 lines of toolset and loader code that changed owner plus the ~20-line import block a
  module needs to own what it was handed.

### What the adversarial review changed

A review pass over the staged diff found **no correctness defect**: it walked the fourteen checks the
two old validators made and confirmed every one survives (scenario relation endpoints are now checked
*earlier*, at load rather than at `begin_game`), confirmed every state path still ends in validation,
and reproduced the structural fixture claim above with its own script. The three message changes are
load-time only and no model-facing retry string moved. What it took apart was the size:

- **The before-validator machinery, −23 lines.** Replaced by the derived `world` property described
  above. This was the whole miss: the plan's mechanism was implemented faithfully and the faithful
  version was the expensive one.
- **`Spec` and `spec.json`'s wrapper key, −4.** A one-field frozen model existed to unwrap
  `{"collections": {...}}`. `spec.json` is now the bare collection mapping, read by one `TypeAdapter`,
  and `collections()` became `pack_format()` — a name that says what it returns and does not shadow a
  stdlib module. `fivee_test_support`'s wrapper of it went too; the three 5e tests import from the
  module that owns it.
- **`_packs()` inlined, −5, and its `is_dir` guard on the packs directory dropped.** A missing packs
  directory used to load *empty* content and die later with "refs missing content"; it now raises
  where the mistake is. This engine vendors its packs.
- **A dead check and four docstrings.** The scenario emptiness check above, plus docstrings that
  restated a name or a one-line body (`lookup`, Story's `__init__`, `_the_player_is_playable`,
  `check_placement`). `read_content`'s docstring is untouched: it is the tool description the model
  reads, locked by a golden.
- Two nits it found and this phase closed: a duplicate id in `starting_party` silently collapsed two
  relations into one, and a companion could be authored in a different room from the player.
- Recommendations **not** taken, with reasons: moving the `PROJECTING ⊆ collections` check out of
  startup into a test (it is an invariant, and CLAUDE.md says fail fast on a broken one — 3 lines is
  a fair price), and inlining `check_placement` into its now-single caller (three distinct refusals
  under one name, pointed at by `base.py`'s comment on `parent_id`; `_consistent_fiction` would grow
  to four jobs to save 5 lines).
- Process note: a subagent's edit silently dropped `read_content`'s docstring (the tool description
  the model reads) and one invariant comment. The tool-schema golden caught the docstring within the
  same run. Model-facing docstrings need naming as such in a subagent's brief, the way CLAUDE.md
  names them: they are runtime behaviour, not prose.

## Phase 10B — One owner for the scene rule, the counter effect, and growth — DONE

### 1. One scene answers who may be voiced

- `BaseScene.voice(speaker_id) -> Entity | None` is the single answer: an actor the scene holds as
  here. Both judges now ask it, so a rule that was written twice cannot disagree twice.
- `check_speaker` moved from `state/plan.py` to `turn/prompts.py` and takes the pre-turn
  `SceneSnapshot` instead of `GameState`. Its four refusal strings are byte-identical — they are
  model-facing and tested. The unknown-id case reads `scene.canon`, which holds every entity, so the
  *unknown id* and *not voiceable* refusals stay distinct.
- `_speaker` no longer raises. A speaker the turn walked away from falls back to the existing
  `"(none — narrate the scene)"`. **This is the phase's one behaviour change**, and it fixes a turn
  that died: scene picks `mara` in the study → player walks to the cloister → `ValueError` at
  `prompts.py:378`, before `engine.commit`, discarding three model calls and the whole turn.
- Deviation from the plan, deliberate: the plan has `check_speaker` "derive presence from the
  pre-turn scene". It could not stay in `state/plan.py` to do that — `plan.py` → `turn/prompts.py` →
  `engines/loader.py` → `plan.py` is a cycle — so the function moved to the module that owns the
  scene. `roles.py` builds the snapshot at the call site (`prompts.SceneSnapshot.of(state)`);
  rebuilding it per validation is pure dict work and keeps the scene stage's deps as `GameState`,
  which the thread and reveal checks beside it still need.
- Tests: the repro plays a full turn and asserts it commits with the fallback in the narrator
  prompt (`test_pipeline.py`); `test_context_boundary.py`'s speaker case swapped `pytest.raises` for
  the fallback assertion — the old test asserted exactly the fatal behaviour this step removes.
  No golden moved: no shipped golden has an absent speaker.

### 2. The counter effect has one owner — NOT TAKEN, per the plan's own gate

The step was built, measured, and reverted. `engines/counters.py` gained an `apply_counter` taking
each engine's mechanics and its own move function — reveal the target, move the counter, write the
mechanics back — leaving `move_counter` and `_move_pool` per-engine, one injected callable rather
than three. It landed at **+9 lines**: the shared function (13) is narrower than the 16 it replaces,
but two 4-line call sites and two import lines more than eat the difference.

PLAN.md gates this step exactly there — "accept only if the shared signature stays narrower than the
16 lines it replaces … stop and leave the duplication if that is where it lands" — so it was
reverted rather than argued for. The invariant it protected is real (dropping `write_mechanics` is a
silent no-op-on-commit) but speculative at HEAD: there is no third engine, and CLAUDE.md forbids
paying for one. The duplication that stays is eight readable lines in each engine, and the day a
third engine wants them the step is 15 minutes' work with its measurement already recorded here.

### 3. Growth has one consumer-side owner

- `Advancer` is a frozen pair in `app/session.py` — the `Advancement` capability and the advisor
  built against it — so the pair cannot be half-present: the fourth re-derivation in `GameSession`
  was a comment admitting `advisor is None` and `advancement is None` were the same fact stated
  twice. `GameSession` keeps `advancer: Advancer | None` and one accessor (`_advancer`), and owns
  offer → propose → preview → apply itself, ending in its own `_commit`. No growth module sits
  between the panel and the session: the review collapsed an earlier draft whose `app/growth.py`
  held the four operations behind four one-line `GameSession` delegates — a layer that existed
  only to be a layer. It is `Advancer`, not `Growth`, because story's proposal type is already
  `Growth` and `test_proposals.py` would have imported both names.
- Deviation from the plan, forced: `state/advancement.py` folds into **`engines/loader.py`**, not
  into the consumer. `loader.py` declares the `Advancement` contract these two types spell, and
  folding them into `app` would make `engines` import `app`. `AdvancementOffer` took the stricter
  `packs.Record` rule — options and a count are set together, or neither is — which both shipped
  offers already satisfy.
- `ui/panels.py` reads the two types from `aidm.app.session`: the package boundary test forbids
  `ui` importing `aidm.engines`.

### Numbers

- Net Python: **src 0** (88/−88), tests +20. Tests 135 → 136. Per step: step 1 **+2** (the fatal
  bug, `voice`, and `check_speaker` changing module), step 2 **0** (reverted), step 3 **−2**.
- Against the plan's predicted 60–100 line reduction, "almost all of it in step 3". That estimate
  was wrong in kind, and zero is this phase's floor, not a shortfall to keep shaving at. The four
  re-derivations it counted are ~15 lines; the one file it deletes (`state/advancement.py`, 25
  lines) re-declares the same two types in `engines/loader.py`, because a type both an engine and
  the app need cannot be deleted by moving it. Consolidating *where a question is asked* does not
  remove the answer.
- What the phase bought instead: a turn that used to die now commits, and three behaviours that
  had two owners have one. Two rounds of review drove +37 → +9 → 0, and the two things that closed
  the gap were both **deletions of the phase's own work** — a `growth` module that was four
  one-line delegates in front of four methods, and a shared counter helper that cost more than the
  duplication it removed. Working rule 5 applies to the residue: net lines are evidence, not the
  target.
- No `SAVE_VERSION` bump: no persisted bytes and no model-facing string changed, and no golden
  fixture moved.

## Phase 11 — Memories + Worldkeeper judgments — CODE DONE, LIVE PROBE OWED

### 1. Memory state, authored + rendered

- `Memory(Mutable)` in `state/world.py` beside `Thread` (`id`, `owner: EntityId | None`, `text`
  1–300, `tags`, `turn`), and `WorldState.memories: dict[Slug, Memory]`. Whole-world validation
  keys memories by id in the same `keyed` tuple entities/relations/threads use, and refuses an
  owner who is not an entity.
- `ScenarioWorld` carries `memories` like its other authored arrays, with the same duplicate-id
  check; `begin_game` needs no memory-specific path — the deep copy it already makes carries them.
- whispering-vault authors two: the abbey emptying in one night (the world's own), and Mara's
  memory of cataloguing beside Elena. The second is canon about an entity the player has not met,
  which is exactly the case the leak rule has to survive.
- `SceneSnapshot.memories` filters to owner None, the player, or an entity at the player's
  location, computed from the `locations` map the snapshot already builds. `render_director`
  renders `MEMORIES` **only when it is rendering the Scene Director** (`directive is None`) —
  the same switch that already distinguishes the two director calls. The Rules Director and the
  Narrator gain no field a memory could travel through, and the golden diff proves it: the two
  `scene.txt` fixtures moved, the `director.txt` and `narrator.txt` ones did not.
- `SAVE_VERSION` 49 → 50, `FIXTURE_SAVE_VERSION` with it.

### 2. The extended Worldkeeper report

- `MemoryProposal(Frozen)` (`owner_id`, `text` ≤300) in `state/turn.py`; `WorldkeeperReport` gains
  `memories` and `thread_moves: tuple[AdvanceThread, ...]`. No importance score, no second
  transition vocabulary — code would read neither.
- The Worldkeeper stage becomes `Stage[GameState, WorldkeeperReport]` and validates against the
  draft: a memory owner that names no entity, or a thread move that names no thread, comes back as
  a `ModelRetry`. The thread rule is one helper (`_unknown_threads`) shared with the Scene
  Director's validator, which stated it identically.
- `apply_creations` becomes `apply_report`: creations, then memories, then thread moves through
  `apply_effect` — one function, one entry point, still inside the turn's single final commit.
  `_remembered` mirrors `admitted`: casefolded-duplicate drop against every existing memory, cap
  at `Settings.max_memories = 2`, id from a new `base.text_slug` (hyphenated, capped at `SLUG_MAX`,
  de-collided — `slug()` underscores and never truncates, and both would fail `Slug`).
- Memories are recorded with `turn=draft.turn` and a non-narrating `Fact(kind="memory_kept")`, so
  the trace shows them and the player's prose never does.
- `render_worldkeeper` gains `ALREADY REMEMBERED` (the same present-owner filter) and
  `ACTIVE THREADS`; the `WORLDKEEPER` instructions are restructured into CREATIONS / MEMORIES /
  THREAD MOVES with "most turns record nothing at all" lifted into the opening.

### 3. Verification

- Two tests, both through the real pipeline: memory reaches the Scene Director and neither the
  Rules Director nor the Narrator (and a memory owned by an actor in another room reaches nobody);
  a report that keeps two, drops a repeat of an authored memory, hits the cap of two, moves a
  thread, and retries an owner naming nobody. 136 → 138 tests.
- Golden movement, exactly as predicted and nothing else: `instructions/*/worldkeeper.txt`,
  `prompts/*/{scene,worldkeeper}.txt`, `schemas/worldkeeper_report.json`, and the
  `save/state/turn` families for the version bump and the two authored memories.
- Evals: `remembered` probe added, `thread_at` extended to read a `status` as well as a `stage`
  (a resolving beat moves the status, and no shipped stage vocabulary exists to name), the quiet
  `worldkeeper-creates-nothing` case now also asserts nothing was kept or moved, and two new cases
  cover a revelation worth remembering and a fact-free beat that resolves a thread.

### Review

- **A location could hold a memory nothing would ever render.** `present` was built from
  `location_of`, which returns None for a location, and from `placed`, which excludes the scene's
  own location — so `owner_id: "study"` passed validation, was stored, and appeared in no prompt,
  where the exact-text duplicate rule would let the model re-propose it in other words forever.
  The place is now present in its own scene. No golden moved: no shipped scenario authors one.
- The MEMORIES block listed three reasons to keep one and no reason not to, with the restraint
  sentence only in the opening, where gpt-oss-120b at low effort weights it least. One bullet
  closes the block, and it is the **only** model-facing change beyond the phase itself, so the
  owed probe measures one surface rather than two (phase 5's lesson).
- The retry test folded into the admission test: the plan asked for one test over
  admit/dedupe/cap/move/retry, and a bad first answer makes the retry the only path to the second.
- Left open on purpose, both out of this phase's scope: memories have no eviction, so the two
  rendered sections grow for the life of a campaign at up to 2 a turn; and the duplicate rule reads
  every memory while ALREADY REMEMBERED shows only present owners, so an absent owner's memory can
  be restated in other words. Decide both after the probe says how often the Worldkeeper actually
  keeps one — pruning a stream nobody has measured is guessing.

### Numbers

- Net Python: src **+151** (181/−30), test code **+88**. This is a feature phase; growth is the
  point. Against the plan's own accounting, the single-role design avoids the 70–120 lines a
  Memorykeeper/Threadkeeper pair would have added: no new role config key, no new fixture family,
  and the turn is still four model calls in the worst case.

### Owed — settled 2026-08-12

- The live probe ran: the maintainer ran `scripts/evals/run.py --only worldkeeper` multiple
  times and judged performance OK. The reshaped `WorldkeeperReport` schema did not hit phase 3's
  zero-output failure mode, so the fixtures stand. (Per working rule 3, the numbers are
  informational — same-hour n=9 pairs only ever compare a specific change.)

## Phase 12 — Character creation workflow — DONE (advisor front-end not built)

### 1. The workflow shape

- `state/creation.py` (43 lines): `CreationOption` (`id`/`label`/`detail`), `CreationStep`
  (`id`/`prompt`/`options` min 1/`choose` validated `1 <= choose <= len(options)`),
  `Picks = Mapping[Slug, tuple[Slug, ...]]`, and `check_picks` — one legality rule (unknown step,
  repeated pick, wrong count, unknown option) shared by the page and by every engine's `create`,
  so neither can drift. Nothing more: no dependencies, no ranges, no derived-value language.
- `Creation` ABC in `engines/loader.py` beside `Advancement`, same optional-capability shape:
  `steps(picks)` (tolerates partial/stale picks so follow-up steps appear as parents are picked)
  and `create(name, brief, picks) -> CreatedCharacter`, raising `ValueError` with the reason the
  page shows verbatim. `Engine.creation: Creation | None`, default None; the loader-stub engine
  gets no creation page for free.
- Placement deviation from the plan, forced by the import graph: `CreatedCharacter` is
  `profile: CharacterProfile` + `overlay: CharacterOverlay` and lives in `content/authored.py`,
  not beside the ABC — `content.store` writes the files and cannot import `engines`. For the same
  reason it holds a `CharacterOverlay`, not a loose engine payload: the type *is* the file format.
- `store.write_character(directory, name, engine, created)` writes `base.json` + `<engine>.json`
  with `model_dump_json(indent=2)` and refuses an existing directory. The output is read back by
  the untouched `load_character` — no new runtime format, no validator bypass.

### 2. Story creation

- `engines/story/create.py`: three static steps — four authored archetype spreads (4 points over
  the approaches: daring/sly/keen/warm), four edges, four burdens, the traits carrying the same
  `(edge)`/`(burden)` text convention kael uses. `create` writes the spread as the character
  overlay and the two traits into the profile. Free point allocation stays out, per the plan's
  own ceiling: authored spreads keep the framework at pick-from-options.

### 3. 5e creation

- `engines/dnd5e/create.py`: static steps for race/class/background built by iterating the
  engine's content per collection (label = record name, id = index), plus the authored
  ability-priority step — `might`/`grace`/`focus` orderings of the standard array, `focus`
  resolving its lead from the class record's `spellcasting` fact (wisdom fallback). CON sits
  second in every spread, so level-1 hp never goes negative.
- **Plan re-resolution, verified against the pack**: the plan expected skill choices on class
  records; in the actual SRD pack a class record carries no options — the *level-1* `levels`
  record does (fighter-1: choose 2 of 7 features). A picked class therefore also answers with its
  `<class>-1` sibling (the same `sibling("levels", ...)` shape advancement's `level_ref` uses),
  and the generic rule — any chosen record whose `options`/`choose` are set becomes one more
  step — then delivers the race's language choice and the class's level-1 features for free.
  Skill proficiencies are not encoded as options anywhere in the pack, so created characters
  carry none; that joins gear and spells in the deferred list rather than being half-modelled.
- `create` derives what content answers: refs for race/class/background + picked options; the
  six abilities from the priority, then racial bonuses (below); `armor-class` 10 + DEX mod;
  hp = `hit-die` fact + CON mod; every int fact of the level-1 record (`level`,
  `proficiency-bonus`, `cantrips-known`, ...) as numbers except `slot-N`, which become full
  counters — long-rest, except the warlock's pact slots, which the SRD returns on a short rest.
  The overlay is built through the engine's own `Sheet` and dumped, so it validates before it is
  ever written.
- Where the pack keeps a rule as prose, `create.py` transcribes it into an authored table rather
  than leaving a state gap (maintainer decision mid-phase, reversing the first cut's deferrals —
  see the review): `_CLASS_SKILLS` (choose-N per class, bard = all 18) spawns a `<class>-skills`
  step whose picks land as `proficiencies` refs exactly like kael's, with `_BACKGROUND_SKILLS`
  granting acolyte's fixed Insight+Religion and removing them from the class list; and
  `_feature_pool` grants the counter behind each pool-bearing level-1 feature (second-wind 1/short,
  rage, bardic-inspiration-d6, divine-sense, lay-on-hands, arcane-recovery — audited against all
  twelve `-1` rows; ki is level 2, so the table is complete at level 1). `__init__` verifies every
  table row against the pack, so a transcription typo refuses at engine build, not at play.
- Racial ability bonuses land on the array before AC and hp are derived: flat entries from each
  race's `ability-bonuses` fact (validated by a strict `_AbilityBonus` model, refused at engine
  build if unreadable), and half-elf's "choose 2 others +1" as one more dynamic step
  (`<race>-bonus`, offering the six abilities minus the flat-bonus ones).

### 4. The UI page

- `ui/create.py`: `/create/{engine}` — name, brief, one `ui.select` per step (`multiple` when
  `choose > 1`), the whole form refreshable so follow-up steps appear on every pick, stale picks
  pruned against the current step ids. Create: refuse an empty name, `create()` with the
  `ValueError` shown verbatim, `text_slug(name)` de-collided against existing character dirs,
  `write_character`, navigate home (the catalog re-reads the directory). Home page gains one
  "New character" button row per engine. No preview pane, no wizard, no draft persistence.
- The package boundary holds without new plumbing: the page reaches the capability as
  `runtime.engine(id).creation` — attribute access typed through `Runtime`, no `aidm.engines`
  import — and its own imports are `state.creation`, `content.store`, `app.session`.

### 5. What the adversarial review changed

A review pass ran over the staged diff with the mandate to close the state gaps the first cut had
deferred. It found the framework half clean (`Creation` mirrors `Advancement` honestly,
`check_picks` is not a copy of `violation`, the tests are minimal and end-to-end, no comment or
test deletions warranted) and rewrote the 5e half:

- **The deferrals were real gaps, and three of four are now closed.** Feature pools: `UseFeature`
  on a created fighter's second-wind died at `counter_of` ("has no counter") — the pool table
  above is the fix. Skill proficiencies: the Director reads rendered `proficiencies` refs when
  setting `Check.bonus`, so a character without them plays measurably below kael — the skill
  steps are the fix. Racial ability bonuses (a gap the review found, not one the phase had
  named): a created elf wizard had DEX 13 where the SRD gives 15.
- **Left deferred with traced evidence, not assumption**: starting gear (items are world entities
  needing `profile.items` authoring; `Attack` works through `attack_bonus`/`damage` and play
  grants items) and spell choice (`resolve_cast_spell` checks only the class ref's `spellcasting`
  fact and slots — no known-spell list exists for a character to miss).
- One real bug fixed beyond the gaps: every `slot-N` counter recharged on long rest, including
  the warlock's pact slots, which the SRD returns on a short rest.
- The maintainer's play-test (2026-08-12) drove one more pass, all same-day: a subrace step
  (`<race>-subrace`, grouped off each subrace record's `race` fact, flat bonuses applied with the
  race's before AC/hp — a subrace with a `choice` bonus entry is refused at engine build until a
  pack ships one), follow-up prompts that name what is chosen ("Half-Elf: choose 1 (languages)"),
  and a live preview pane beside the form — every pick re-runs the pure `create()` and the pane
  renders either the character (traits, numbers, `current/maximum` counters, refs) or the refusal
  text, which doubles as "what's still missing" feedback. Not built, ticketed instead: spell and
  cantrip choice (02, a casting-model decision) and the three real ability-generation methods
  (04, roll / 27-point buy / free assignment — each breaks the pick-from-options ceiling).
- Second play-test round, same day: every race now grants its automatic languages as refs
  (`_RACE_LANGUAGES`, nine transcribed rows verified at engine build — Common and the race's own
  tongue are visible sheet state, not prose), and the background language step stops offering
  Common or anything the race already speaks. Deliberate ceiling kept: double-picking one
  language across the two *choice* steps still dedupes to a single ref. The preview became
  progressive — name/brief and a "choices so far" row per step (picked labels, dim "—" when
  unpicked) render always; the full sheet appears under a divider once the pick set is legal;
  the refusal is demoted to one dim "Not ready yet" line instead of being the whole pane.
- Two review findings closed in a follow-up pass: acolyte's "choose 2 languages" became a
  `_BACKGROUND_LANGUAGES` table + `<background>-languages` step over the whole `languages`
  collection, with `Sheet.refs` now deduped order-preservingly (a half-elf acolyte can legally
  pick the same language twice and writes one ref — tested); and the UI's slug + `write_character`
  moved inside the try, so "already exists" notifies like every other refusal.
- Still deferred, now specced instead of loose: `.scratch/creation-remaining-state/` holds the
  spec and three triaged tickets — starting gear (an owned item is a world `Entity` plus an
  overlay ref, and armor breaks the `armor-class = 10 + DEX mod` derivation), spell choice (a
  casting-model decision: `resolve_cast_spell` reads no known-spell list, so the state must not
  be seeded before something reads it), and the pack's `fighter-1` "choose 2 of 7" flattening
  (an SRD-importer/pack-shape fix that `Advancement.offered` consumes too).

### 6. Verification and numbers

- Four tests, all through the real files: a story character (spread + both traits) and a 5e
  fighter and wizard each go `create` → `write_character` → `load_character` → `begin_game` on
  whispering-vault — every validator the hand-authored path has, exercised end to end; plus the
  shared refusal test (unknown step / wrong count / unknown option / duplicate directory). The
  fighter asserts skills, the second-wind pool, and the half-elf bonus flipping AC 11 → 12 (the
  ordering tripwire: bonuses must land before AC/hp derivation); the wizard asserts slots and
  elf DEX 15 → AC 12. 138 → 142 tests.
- Step 4 (advisor front-end) not built, per the plan's own gate: "build only if hand-picking
  feels slow in practice", which only play can answer.
- No golden moved, no `SAVE_VERSION` bump (no persisted or model-facing byte changed — creation
  writes new files, it does not reshape existing ones), `characters/kael` untouched.
- Net Python: src **+706** (43 creation state, 102 story, 386 dnd5e, 102 ui page, 73 across
  loader/store/authored/rules/app/home), tests **+157**. A feature phase; the framework floor is
  the 43-line state module plus the two-method ABC. The 5e file more than doubled in review, and
  nearly all of it is transcribed SRD prose (skill lists, pool table) that the pack keeps as
  text — data the engine now owns and verifies at build rather than lacking at play.

### 7. The deferred tickets, triaged 2026-08-12

The maintainer triaged `.scratch/creation-remaining-state/` and approved all four, in this order:
gear (01), known spells and cantrips end to end (02, the casting-model change), the level-row
grant/choice split (03), the three real ability-generation methods (04).

**01 — starting gear: DONE.** Decisions taken at triage: the options source is a *curated* bundle
list per class derived from the SRD equipment prose (the pack ships no structured starting
equipment — upstream 5e-database has it, but re-importing needs the missing external checkout and
a `SAVE_VERSION` bump), and `create()` computes final AC from the picked armour rather than moving
AC derivation into the rules layer.

- `engines/dnd5e/equipment.py` (new): 12 classes × 3 bundles over concrete records; 46 authored
  one-line item briefs (a record's own text is mechanical prose, an owned item's brief is fiction
  the Narrator reads); `armor_class`; and `verify`, run from `Dnd5eCreation.__init__`, refusing a
  missing bundle, an unknown record, a missing brief, a repeated bundle id or item, and two
  armours in one bundle — a typo fails at engine build, not at play. The module exists because
  440 lines of authored data would push `create.py` past the 1000-line cap.
- `create.py`: a `<class>-equipment` step, gear written as `profile.items` entities plus a
  per-item overlay `Sheet(refs=…)` — kael's lantern shape, so a carried weapon reaches `Attack`
  through `first_ref_record` with no new plumbing — and `armor-class` now read off the armour:
  `armor-base` plus DEX capped by `dex-limit` where the record adds DEX at all, `armor-bonus`
  (the shield) on top of armoured or unarmoured. `strength-minimum` is deliberately unread: its
  SRD cost is speed, which nothing models.
- The adversarial review found one real gap, fixed in the same pass: `monk-1` and `barbarian-1`
  grant Unarmored Defense to every created monk and barbarian, so an unarmoured sheet showing
  10 + DEX contradicted the feature record rendered beside it (a monk with DEX 15/WIS 13 was AC 12
  where its own content lines promise 13, and `resolve_attack` reads that number). `armor_class`
  now takes the picked features: `_UNARMORED_DEFENSE` adds WIS for the monk and CON for the
  barbarian while no armour is worn, and only the barbarian keeps it behind a shield.
- Left as known ceilings, not fixed: an item entity id is the bare record index, so a future
  scenario authoring an entity called `dagger` makes an already-saved character refuse at
  `begin_game` ("authored entity id appears twice") — loud, at launch, and no shipped scenario
  collides; and quantities are not modelled, so "javelins" is one javelin entity with a plural
  brief.
- Verification: 142 → 143 tests. The fighter round trip now asserts AC 18 (chain mail 16, no DEX,
  plus a shield) and that the longsword's own item sheet carries its weapons ref; the wizard
  asserts the unarmoured 10 + DEX and its three carried items surviving write → load; one unit
  test pins the AC rule where a round trip would be wasteful — scale mail capping DEX +3 to +2,
  the shield stacking, the monk's 10 + DEX + WIS, and armour switching Unarmored Defense off.
  The UI preview gained one line so carried gear shows beside the traits. No golden moved, no
  `SAVE_VERSION` bump: creation writes new files.

**02 — known spells and cantrips: DONE.** The maintainer chose the known list end to end over
recording "any class spell is castable" as permanent. Decisive facts, traced before any code: spell
refs on a sheet already work (the eval caster `elowen` has held six since phase 9), `spells` is not
in `PROJECTING`, so a spell ref projects no int fact onto the character and no state format moved;
and all 319 spell records carry `classes` as `", "`-joined display names, which are the class
records' own `name`s.

- `engines/dnd5e/spells.py` (new): `castable` (a class's spells at one level; a cantrip is a record
  with no `level` fact, and `subclasses` — domain bonus lists a base class never gets — stays
  unread), `known_at_level_one`, `growth`, `KEYS` owning the cantrips-then-spells ordering, and
  `verify` refusing at engine build a caster whose pack list cannot fill its own count.
- **Prepared casters, recorded as a deliberate deviation**: the pack counts what a class *knows*,
  so bard, sorcerer and warlock come straight off `cantrips-known`/`spells-known`. Cleric, druid
  and the wizard's spellbook are prose only, so `_PREPARED_AT_LEVEL_ONE` authors them (wizard 6,
  cleric and druid 3 = casting modifier + level at the standard array) and `_PREPARED_GROWTH` grows
  them. One list is seeded and play reads only that: a prepared caster cannot re-prepare on a long
  rest, which is the SRD rule this trades away for a single piece of state.
- Creation: `<class>-cantrips` and `<class>-spells` steps; the high elf's cantrip arrives through
  the pack's own `traits/high-elf-cantrip` record (`choose 1` of 14) linked by `_SUBRACE_TRAITS`,
  so the generic choice machinery builds the step and lands the ref. Picking one spell in two steps
  now refuses — the language dedupe would have swallowed it and cost the player a pick.
- Play: `resolve_cast_spell` refuses a spell that is not a ref on the caster's own sheet, and
  `director.md` now states the list is exhaustive. `spell_of` returns its parsed ref so nothing
  parses twice; the check sits in the resolver, not in `spell_of`, because `rules._labels` calls
  that before any legality check and would mislabel contested branches.
- Level-up: `LevelUp.spells` beside `picks` (which `violation` still gates one-for-one against the
  offer's options), the offer text carrying the legal pool minus what is already held, `violation`
  checking cantrips and spells against their own allowance, and `advance` adding the refs and
  keeping `cantrips-known`/`spells-known` in step with the new row — engine-side, never from model
  output.
- The adversarial review found four real defects, all fixed: a high-elf **non-caster** was seeded a
  racial cantrip the resolver then refused (a fighter with High Elf Cantrip casts it off
  Intelligence, so the resolver now falls back to INT when a known spell comes without a casting
  class); the duplicate pick above; a level-up pool that still offered spells already held (the
  refusal came from `add_ref` deep in the dry run instead of the offer); and a wizard's invented
  `spells-known` number, which would have read as a smaller list than the refs beside it.
- Verification: 143 → 149 tests. The new end-to-end one is the load-bearing one: a created wizard
  goes through `write_character` → `load_character` → `begin_game`, then `check_plan` accepts a
  cast of a cantrip it picked and refuses one it did not — pinning that creation's
  `sibling("spells", …)` refs are ref-equal to what the resolver parses out of model output.
  Goldens moved: `instructions/dnd5e/director.txt` (director.md), `instructions/dnd5e/advisor.txt`
  (advancement.md), `schemas/dnd5e/proposal.json` (the new field). No `SAVE_VERSION` bump: the
  state shape did not change.
- Known ceiling, measured not guessed: a created caster's ten spell refs add 1,824 characters to
  the player sheet, which renders in four role prompts per turn (~7.3KB), and about 30 characters
  per line are the `classes=`/`subclasses=` facts that tell the Director nothing. Filtering them in
  `mechanics._ref_line` is the follow-up if prompt cost bites.

**03 — level rows: grants split from choices: DONE.** Two decisions taken before any code, because
both changed the shape of the work. **The pack shape**: `Record` grows `granted: tuple[ContentRef,
...]` and *keeps* its single `options`/`choose` pair — not ticket 05's `choices: tuple[Choice, ...]`.
The audit the ticket demanded settled it: of 290 level rows, 253 carried options, 240 of them with
`choose == len(options)` (a grant dressed as a choice); 13 are real choices and only four mix the two
(`fighter-1`, `paladin-2`, `ranger-2`, `draconic-1`); across every other collection with options
(features 14, races 2, traits 5) not one record anywhere needs two independent choice groups. So the
multi-group shape would have been built for data that does not exist, and `AdvancementOffer` — which
also holds one pair — would have had to grow with it. 05 can add `choices` when it has class records
that need it; it re-projects and bumps anyway. **The checkout**: `../5e-database` was cloned at the
`source_commit` the manifest pins (`3f5593ea`), and the importer was run *before* any change to prove
the round trip — byte-identical across all 22 collections. That is what makes the regression check
real: after the change exactly two files moved.

- `scripts/srd/project.py`: the flattening was one line — `choose = len(record.features)` over picks
  gathered per feature entry. The entry boundary *is* the grant/choice line, so `level()` now splits
  on it: an entry the feature-choice map answers becomes `options`/`choose`, every other entry becomes
  a `granted` ref. A row carrying two choice entries raises at import rather than flattening
  silently — honest about the one-pair limit, and unreachable in the shipped SRD.
- `packs.Record`: `granted` beside the pair, and one validator refusing a ref that is both granted and
  offered — the state that would otherwise blow up deep inside `add_ref` as "already held".
- **One latent bug the audit exposed**: `subfeature_options` dropped upstream's own `choose`, so every
  choice became "choose 1". `metamagic-1` is choose **2** of 8 in the SRD, and `sorcerer-3` said 1 —
  contradicting its own `metamagic-known: 2` fact. The projector now carries the count through; that
  is the whole of `features.json`'s one-line diff.
- Play: `Dnd5eAdvancement.advance` adds `row.granted` itself — engine-side, never from model output —
  and `offered` carries the refs on the offer, which the advisor prompt renders as `HANDED OVER` where
  it used to print `PICK EXACTLY 1`. The review caught that dropping them entirely was a real loss:
  `LevelUp.granted` is the only route a level's pool reaches the sheet, its `counter` is a slug, and
  with the refs gone the model would have invented that key off a display name while creation keys the
  identical pool by record index. `advancement.md` now names the feature's own index as the key.
- Creation: `_features` merges what a picked record hands over with what was picked from it, so a
  fighter is *given* Second Wind and chooses one style. Everything downstream — the feature pools,
  Unarmored Defense reaching `equipment.armor_class` — already read that one tuple.
- Verification: 149 → 150 tests. The new one is `paladin-2`, the only reachable row that both grants
  and offers: two features handed over, one fighting style of four, and the pick-count rule pinned
  both under and over (the fighter test can no longer carry it — Fighter 2 asks for nothing). The
  fighter creation round trip picks one style and still asserts the Second Wind counter; the wizard
  asserts `wizard-1` spawns *no* step. Goldens moved: `advisor.txt` (both), `proposal.json`, and
  `save_version` 50 → 51 across six state/save/turn fixtures — a regenerated pack invalidates saves.
  Every moved byte was read: no golden drifted for a reason other than these.

**04 — the three real ability-generation methods: DONE.** `_MIGHT`/`_GRACE`/`_FOCUS_REST` are gone;
roll, point buy and standard array replace them. Two decisions taken first, both about how a number
reaches a pure `create(name, brief, picks)`:

- **A rolled spread travels as its seed.** The UI cannot hand `create` six numbers it rolled and call
  them picks — the ticket's own "re-check against some legal 4d6 outcome" is unenforceable. So the
  seed is the answer, `create` re-derives the six scores with `Random(seed)`, and the same picks
  always rebuild the same character. Typing another number is the reroll. Verified byte-identical
  across three processes under different `PYTHONHASHSEED`s; nothing touches the global RNG.
- **The framework grew a numeric-allocation step** rather than faking allocation as five shrinking
  pick steps: `AllocationStep` (entries, one `minimum`/`maximum` pair), `Amounts`,
  `type Step = CreationStep | AllocationStep`, `picked()`/`allocated()` narrowing one `Picks` bag
  that now holds either shape, and a second `check_picks` rule. `ui/create.py` renders a row of
  number inputs. Both engines and the page still pass one picks object end to end.
- What each method must add up to stays in the engine, not the framework: point buy walks the SRD
  ladder (8:0 … 14:7, 15:9) against 27 and refuses "point buy spends 31 of 27"; roll and array both
  compare the multiset and refuse "the scores to assign are 17, 15, 13, 13, 12, 10, not …". Bounds
  are the step's, so 8–15 is checked before racial bonuses, as the SRD has it. Each method keys its
  own step (`abilities-roll`, `abilities-point-buy`, `abilities-standard-array`), so switching method
  prunes the scores the old one held instead of leaving a 17 in a field that stops at 15.
- **The adversarial review found two real defects, both fixed.** A non-int amount reached the engine
  as a crash rather than a refusal — `KeyError: 14.5` off the cost ladder, `TypeError` off the bounds
  comparison, and a float seed silently rolled a *different* spread — because `Amounts` is a bare
  alias with no validator behind it; `check_picks` now refuses anything that is not a whole number,
  and `_rolled` treats an unusable seed as no seed, since `steps()` runs before `check_picks` has
  vouched for anything. And the page's new "rebuild only when the step list moved" rule compared id
  and prompt alone, so switching half-orc to dragonborn left the language select still offering
  Draconic and the stale pick unpruned — the signature now covers every option id and bound the
  widget renders.
- Known ceiling, measured: the cursor rule protects the six ability fields (their shape never moves
  while a score is typed) but not the seed field itself — a new seed changes the next step's prompt
  for 58 of 59 consecutive seeds, so the form rebuilds and the seed input is recreated. The value
  survives; only focus is lost, 400ms after typing stops. Per-step refreshables are the fix if it
  bites.
- Verification: 150 → 152 tests. The two existing round trips are unchanged in outcome — the fighter
  still lands STR 16 and AC 18, the elf wizard DEX 15 → AC 12 — because the standard array is exactly
  27 points, so the same six numbers are legal under either method, which is what makes them a real
  regression check rather than a rewrite. The new roll round trip goes seed 12 → 17, 15, 13, 13, 12,
  10 through `write` → `load` → `begin_game` with a human's flat +1 landing on every rolled score and
  hp following the *post-bonus* CON — the ordering invariant the phase has pinned since creation
  shipped. One refusal test covers a tampered roll, an overspent point buy, a score out of bounds and
  a fraction. No golden moved, no `SAVE_VERSION` bump: creation writes new files.

### 8. Advancement, made correct 2026-08-12

The completeness audit that closed §7 asked the other half of the question — can a created character
be *played* to twenty — and the answer was no: two thirds of the classes stopped at level 2 or 3, and
where advancement worked it took its numbers from the model instead of from the level row.
`.scratch/advancement-correctness/` holds the spec and five tickets; 01–04 are done, 05 (subclasses)
stays untouched because it reopens creation and is sequenced behind the importer ticket.

The through-line is this repo's own rule, which creation already honoured and advancement broke: the
model proposes, engine code resolves and records. Every fix below is the same move — read the level
row, write what it says — and the shape 02 settled is what let 03 delete four fields rather than
check them.

**01 — a level-up can create a counter: DONE.** `_set_pool` grants a pool the sheet does not hold
yet, full, and raises one it does; `_raise_pool` alone refused the only correct proposal, so every
caster was frozen at `slot-1` (paladin and ranger from level 2, six more classes from level 3). Pact
magic rides on it: warlock rows *migrate* the slot key rather than accumulate (`warlock-3` names
`slot-2` and nothing else), so `_drop_stale_slots` drops any `slot-N` counter the reached row does
not name. Safe for the other eleven: no non-warlock table ever stops naming a slot level it once
named, checked across all 290 rows. Recharge follows `spells.slot_recharge`, now the one place that
knows pact slots return on a short rest — `create._slot_counters` reads it too.

**02 — the row writes its own numbers and pools: DONE.** `_apply_row` walks every int fact the
reached row carries and writes it the way the sheet holds it: `slot-N` and the nine keys of
`POOL_FACTS` as counters, everything else — the level itself, the proficiency bonus, the spell
counts, each class's own dials — as numbers. Before this a barbarian at 20 still held
`rage-damage-bonus: 2` where `barbarian-20` says 4 and had never gained `brutal-critical-dice`, a
level-20 wizard still held `arcane-recovery-levels: 1`, and a monk at 5 held one counter, `hp`, so
every `UseFeature` on ki died at `counter_of` — the exact failure §7's review fixed for creation.

- `POOL_FACTS` is the one judgement call: which int facts are pools rather than dials. Nine keys —
  action surges, channel divinity, indomitable, ki, the four mystic arcana, sorcery points — each
  with the rest that refills it. Everything else the rows carry (a die size, an aura range, a count
  of things known) is a number, because nothing spends it.
- `_count_known` is gone, subsumed: writing the row's `cantrips-known`/`spells-known` lands exactly
  what adding `spells.growth` landed, and a count the row does not carry still stays off the sheet,
  so a prepared caster's list size remains prose.
- A pool the pack spells as anything but an int fact — rage, lay on hands, bardic inspiration, wild
  shape — is out of `_apply_row`'s reach entirely; `pools.py` carries those, see the review below.

**03 — no number a level-up writes can disagree with the row: DONE.** The ticket offered a choice —
check each field against the row, or derive it and drop the field — and deriving is much the smaller
surface. `LevelUp` lost `hit_points`, `proficiency_bonus`, `slots` and `granted` (and `PoolGrant` with
them); what is left is `picks`, `spells`, `abilities`, `why`. `hit_points=99` and
`proficiency_bonus=17` no longer have anywhere to be written. hp is now 5e's fixed rule — the hit
die's average plus the CON modifier, at least 1 — read off `hit-die`, which the class ref already
projects onto the sheet, and applied *after* the improvement, so a Constitution raised this level is
felt in the same level's hit points.

- The ability score improvement is the one number the row cannot answer, so it stays proposed and is
  now demanded: `_improvement` hands over two points per improvement the row grants, and `_improve`
  refuses a proposal that spends more, less, or none. A level that offered an improvement and got an
  empty `abilities` used to commit and silently skip it.
- **The improvement is counted from the granted feature, not from the row's own tally.** The rows
  carry `ability-score-bonuses`, a running count, and it looked like the obvious source — but the
  pack's rogue counts *down* as often as up (level 10 says 3, level 11 says 2, 12 says 4, 20 says 5
  where the SRD gives six improvements). Diffing that tally paid a rogue 18 points instead of 12; the
  granted features are right for all twelve classes, at exactly 4/8/12/16/19 plus the fighter's 6/14
  and the rogue's 10. The tally still lands on the sheet as the pack's own number; nothing reads it.
- The row's prose names the feature and never the points, so the offer now carries a line saying how
  many points this level spends — the advisor cannot spend what it cannot count. A sheet already at
  20 everywhere spends what room is left, so a maxed-out character cannot deadlock its own level.

**04 — an offer lists only what is still takeable: DONE.** One line beside the `_spell_pools` filter
it mirrors: a feature already on the sheet leaves `options`. A sorcerer at 10 was offered all eight
metamagics including the two taken at 3, and picking one met `"Hero already holds content
srd-2014/features/metamagic-careful-spell"` from deep inside `add_ref` instead of the offer's own
readable refusal. No reachable row can be emptied by the filter — the sorcerer takes 4 of 8 across
levels 3/10/17, every other choice row is offered once.

**The adversarial review found three real defects inside the tickets, all fixed, and two outside
them, both recorded.** Its sharpest finding was against the load-bearing test, not the code: the
sweep read `POOL_FACTS` to decide what had to be a counter, so it agreed with whatever the engine
believed — emptying the table entirely was green. The test now names, per class, every pool a
level-20 sheet holds, and asserts the counter and number keys are disjoint. Four mutations were run
against it afterwards and all four fail it: moving a key out of `POOL_FACTS`, shifting hp by 3,
dropping the retroactive Constitution, and writing the tally. The other two:

- **Hit points ignored 5e's retroactive Constitution rule.** With improvements now compulsory a
  Constitution modifier actually moves, and the SRD pays that raise on *every* level already taken;
  a fighter reaching 20 was 33 hp light, 16%. `_hit_points` now derives the whole maximum the level
  is worth rather than the level's own share, and `_raise_pool` moves the sheet to it — the
  retroactive raise falls out of deriving instead of accumulating, and a maximum that has drifted
  for any other reason heals itself.
- **A ref named twice in one proposal still met `add_ref`'s opaque refusal** — `spells=(shield,
  shield)` counted as two against a two-spell level — which is the exact message shape 04 set out to
  end. `violation` refuses a repeat by name now, as `create` already did.
The review's other two findings were outside the tickets, and both were fixed straight after it
because 03 is what made them bite — an improvement is compulsory now, so the scores they hang off
actually move.

- **`armor-class` was derived once, at creation, and nothing recomputed it.** A driven monk held 13
  where its own numbers said 16, the rogue 13, the barbarian 14 where they said 17 — and `resolve`
  rolls every attack against that number. `advance` re-derives it from the armour the character
  carries, the way creation does; `equipment.armor_class` now takes refs rather than creation's
  `Gear` bundle, so both callers reach one rule. Ceiling: a level-up is the only moment that
  re-asks, so armour picked up mid-adventure is not felt until the next one.
- **A pool the pack spells as anything but an int fact never grew.** `pools.py` (new, 48 lines)
  transcribes the class prose the way `create._CLASS_SKILLS` transcribes the skill lists, and both
  creation and advancement read it: a level-20 barbarian rages 6 times rather than 2, a paladin
  lays on 100 hit points rather than 5, a bard's inspiration returns on a short rest from level 5,
  a druid holds a `wild-shape` counter at all. `bardic-inspiration-d6` is now `bardic-inspiration`,
  since the die is already on the sheet and reaches 12 while the key claimed six. A pool that works
  out below one use is not granted, so a paladin with a Charisma penalty no longer carries a 0/0
  `divine-sense` — and gains it if the score ever rises. Ceiling: the SRD's level-20 rage is
  unlimited and a counter with a recharge needs a maximum, so the ladder stops at 6.

- Verification: 152 → 166 tests. The load-bearing one drives a *created* character of each of the
  twelve classes from 1 to 20 — 228 level-ups — picking only from what the offer's own text says,
  parsed the way the advisor reads it, and then asserts the level-20 sheet against the level-20 row:
  every int fact present at its own value, slot counters exactly the keys the row names at the row's
  maxima and the class's recharge, and the ability points spent equal to twice the improvements
  actually received. It fails if any of the four regressions returns. Two focused tests pin the
  refusals a sweep cannot: the level-10 metamagic offer shrunk to six with the stale pick refused by
  the offer, and a fighter 4 that skips its improvement, overspends it, or takes it. `advancement.md`
  and the `LevelUp` schema moved `instructions/dnd5e/advisor.txt` and `schemas/dnd5e/proposal.json`,
  regenerated with `AIDM_GOLDEN_REGEN=1` in the same change. No `SAVE_VERSION` bump: no persisted
  shape changed, and a save written before this is still read the same way — it simply advances
  correctly from here.
- Measured, not fixed: the offer's spell list is the whole legal pool as prose, which for a wizard
  runs 1.1 kB at level 2 and 7.1 kB at 17 — around 1.8k tokens on one advisor prompt, growing with
  any pack that adds spells. A level-banded list is the fix if it bites.
- Net: `advance.py` 266 → 407 lines, `pools.py` 50 new, `mechanics.py` 261 → 273
  (`ABILITIES`, `modifier` and `drop_counter` — the first two pulled out of `create.py` and
  `resolve.py` so one rule has one home).

### 9. The importer takes back the authored tables, 2026-08-12

`.scratch/creation-remaining-state/` 05, at **maximal** scope: delete every line of authored SRD
data from `src/` that the upstream data can answer, equipment included. The maintainer's rule was
that no table stays because moving it is awkward, only because nothing upstream answers it. Two
things were settled before a line was deleted, and both changed the shape of the work.

**The sibling-collection idea holds, and the framework does not move at all.** The triage concluded
that 39 equipment groups across 12 classes — 21 of them picking from an open category, 2 nesting a
category inside a bundle — needed a recursive step model in `state/creation.py`, `check_picks` and
`ui/create.py`, and recommended not moving them. That conclusion was wrong, and testing it first is
what made the rest of the ticket cheap. Each group is one record with `options`/`choose`; an option
that hands over several things *and* leaves a category open is one more record, carrying `granted`
for what it gives and its own `options`/`choose` for what it still asks. `create.py` already spawns
a step from any picked record that carries a choice — that is how a class reaches its level-1 row —
so yielding a picked option record the same way is the whole of the nesting. `CreationStep`,
`AllocationStep`, `Picks`, `check_picks` and the page are **untouched**; the one new thing in
`create.py` is `_record_step`, six lines, shared by both families of record.

**The dangling-ref check landed first.** Deleting a table deletes its `__init__` verification, and
nothing anywhere checked that a `granted` or `options` ref resolved — `validate_pack` checks facts
only, and refs cross packs, so `packs.loaded()` is the only place that can. It went in before the
first deletion, against a pack with 0 dangling refs, and it is what makes the deletions safe.

- **`scripts/srd/project.py` (+153), `build.py` (+32), `upstream.py` (+7).** `Class.proficiency_choices`
  is byte-for-byte the deleted `_CLASS_SKILLS` for all 12 classes, so the skill choice becomes the
  class record's own `options`/`choose` — the pair 03 kept free, and no `Record.choices` was needed
  after all. `Race.languages` becomes race `granted`, `Subrace.racial_traits` subrace `granted`,
  `Background.starting_proficiencies` background `granted`. A background's `language_options` names
  its pool as a `resource_list` **URL**, so `background()` takes the languages file and expands it.
  Equipment is a new `equipment_options` collection, 75 records: 11 unconditional-grant records, 39
  groups, 25 option records; `build.py` now reads `5e-SRD-Equipment-Categories.json`, which it never
  had to before. Every option type the importer does not understand raises at import rather than
  being dropped — `extra="ignore"` had been silently eating `of`, `items` and `choice`.
- **`create.py` 663 → 455, `equipment.py` 478 → 264.** Gone: `_SKILLS`, `_CLASS_SKILLS`,
  `_RACE_LANGUAGES`, `_BACKGROUND_SKILLS`, `_BACKGROUND_LANGUAGES`, `_SUBRACE_TRAITS`,
  `_CLASS_EQUIPMENT`, `_skill_ref`, `_skill_steps`, `_language_steps`, `equipment_step`, `_Bundle`.
  Skills, languages, traits and gear all arrive through the one generic rule now. The one rule the
  tables carried that the pack cannot state — *a skill the background grants leaves the class's
  list, a language the race speaks leaves the background's* — is one line in `_follow_ups`: what any
  chosen record hands over is never also offered.
- **What stays, each with its one-line note saying why upstream cannot answer it**: `_ITEM_BRIEFS`
  (fiction the Narrator reads; upstream `Equipment.desc` is null for almost every startable item),
  `_UNARMORED_DEFENSE` (`feature_specific` is None for both records), `pools.feature_pool` (None for
  all six; every size is `desc` prose), the ability-generation constants (5e-database ships no
  standard array and no point-buy ladder), and `_PREPARED_*` (the recorded deviation). Everything
  else authored in the 5e package is gone. `_ITEM_BRIEFS` grew 46 → **75**, which is exactly the
  reachable set: full category expansion makes 75 items startable, and `verify` refuses at engine
  build if the two ever disagree in either direction.
- **Behaviour that changed, all of it upstream being more complete than the curated tables were.**
  A subrace now hands over *all* its traits, 7 across 4 subraces where `_SUBRACE_TRAITS` linked 1:
  a high elf gets Elf Weapon Training and an extra-language step beside its cantrip, a rock gnome
  Artificer's Lore and Tinker. The druid gains its wooden shield (AC 13 → 15) and the barbarian
  loses hide armor entirely, because the SRD gives it none — its Unarmored Defense is the point.
  A record picked in two steps is now **refused** rather than deduped, for languages as it already
  was for spells; the dedupe cost the player a pick.
- **The adversarial review found three things.** Two are fixed: `upstream.Option.count` was dead on
  arrival (counts are deliberately unread — one ref is one carried item), and `equipment.verify`
  proved only "at most one *group* can reach armour" where `armor_class`'s last-wins loop needs "no
  single answer holds two"; `_most_armour` now computes the exact maximum through the option records
  and the `choose` counts. The third is **recorded, not fixed**: the SRD cleric's "(if proficient)"
  branches — a warhammer and chain mail — are options again, where the deleted table curated them
  away, so a created cleric can reach AC 18. Both honest fixes are worse than the ceiling: a general
  proficiency filter would contradict upstream for the druid and monk, whose own "any simple weapon"
  offers weapons they are not proficient with, and a prose-keyed one re-introduces the interpretation
  this ticket exists to delete. Nothing in this engine models weapon or armour proficiency, and the
  only cleric subclass the SRD ships grants heavy armour.
- Left as a known ceiling, measured: the `_follow_ups` filter could in principle shrink a record's
  options below its `choose`, or to nothing, and `steps()` is called by the page outside any
  try/except — a `CreationStep` validation error would reach the browser rather than a refusal. It
  is unreachable on the shipped pack (the tightest case is the cleric, 5 skills − 2 acolyte grants
  = 3, choose 2), and 4,000 randomized traversals plus ~30,000 exhaustive equipment enumerations
  raised nothing that is not a clean `ValueError`.
- Verification: 166 tests, unchanged in count — this phase deletes data, it does not add behaviour
  the suite was not already asserting. The two round trips still land the same sheet they landed
  before (fighter AC 18 from chain mail and a shield, elf wizard DEX 15 → AC 12), which is what
  makes them a regression check; the fighter now reaches its longsword through the nested step
  ("a martial weapon and a shield" hands over the shield and asks for the weapon) and asserts that
  Common, Elvish and the acolyte's Insight are absent from the lists that would otherwise offer them.
  `filled_picks` in the test support fills a round at a time rather than one pass, because answering
  one step is now what offers the next. **The round trip is the scoping check**: after the change
  exactly five pack files moved — `classes`, `races`, `subraces`, `backgrounds`, `manifest` — plus
  the new `equipment_options`, and the other 19 collections are byte-identical from the pinned
  `source_commit`. `SAVE_VERSION` 51 → 52 across the six state/save/turn fixtures; `save_version` is
  the *only* byte that moved in any of them, and no prompt or schema golden moved at all.
- `scripts/` stayed under basedpyright strict — the type-free-zone escape the maintainer offered was
  not needed.

### 10. Subclasses exist, 2026-08-12

`.scratch/advancement-correctness/` 05, the last of the five and the one sequenced behind §9. 50 of
the pack's 290 level rows and all 12 subclass records were unreachable: a created cleric held
`divine-domain` and no domain, a fighter reached 20 with no archetype, and `champion-3`, `life-1`,
`draconic-1` and `hunter-3` were dead weight the loader carried and nothing read.

**The choice lands on the class's own level row, and that is the whole design.** The ticket asked
for a second level ref and a merge of two rows; what settled it is the same audit that settled §7's
one `options` pair, read one table further down. A subclass is a record carrying a `class` fact,
exactly as a subrace carries `race`; a class level row is a `Record` like any other; and §9's rule
— a picked record that carries a choice spawns one more step — is already what turns a picked class
into its level-1 row. So the row that hands over "choose an archetype" carries the archetypes as its
own pair, and a picked subclass answers with its own level rows. `AdvancementOffer`, `Record`,
`CreationStep` and `check_picks` are untouched, and `Record.choices` stayed unbuilt for the second
phase running.

- **The importer decides where that pair belongs, from what upstream states.** A subclass names its
  class and the level rows name the subclass whose table they belong to, so the level a class
  decides at is the level its subclass table starts (`project.subclass_choices`; `project.py` 1330 →
  1359, `build.py` 147 → 150). Checked before writing it: of the 12 rows this touches not one
  already carried a feature choice, and the importer raises rather than flattening if an edition
  ever makes one do both. **The round trip is the scoping check**: exactly one pack file moved,
  `levels.json`, 96 added lines and none removed — 12 rows × 8 — and the other 21 collections plus
  the manifest are byte-identical from the pinned `source_commit`. Every moved line was read; the
  derived levels are the SRD's own (cleric, sorcerer, warlock 1; druid, wizard 2; the other seven 3).
- **Creation** (`create.py` 455 → 469): `_level_rows` yields a class's level-1 row and then the
  level-1 row of any subclass picked from it, so cleric, sorcerer and warlock choose at creation and
  land what the domain, origin or patron hands over — Bonus Proficiency and Disciple of Life for a
  Life cleric — and `draconic-1`'s dragon ancestor becomes one more step after the origin is picked,
  through the same nesting equipment uses. `_option_ref` is gone for a `_picked_options` that
  filters rather than indexes: `steps()` runs before `check_picks` has vouched anything, and the old
  `next(...)` would have met a stale pick with `StopIteration` inside a generator.
- **Advancement** (`advance.py` 407 → 452): `_subclass_rows` reads the second table at a level,
  `offered` merges both rows' text, grants and the one open pair, and `advance` applies the subclass
  row *after* the picks land — a fighter picks Champion at 3 and Improved Critical is handed over in
  the same level-up, because the row granting it is unreachable until the ref is on the sheet.
- **The one shape a single pair cannot hold, and what it cost.** The ranger is the only class whose
  subclass row asks something at the very level the subclass is chosen: `hunter-3` offers Hunter's
  Prey, and nothing can offer it before Hunter is held. `_deferred` carries an unanswered
  subclass-row choice to the next offer, so the ranger meets it at 3 and takes it at 4. A ranger who
  stops adventuring at 3 never takes it; that is the price of one offer holding one pair, and it is
  the whole price. Measured, not assumed: `champion-10` is the only subclass row whose options
  overlap a class row's — the six fighting styles, one already held from level 1 — and §8's
  already-held filter shrinks it to five with no new code.
- **One framework field moved, and it was overdue.** `CreationOption.id` was a strict `Slug` while a
  content index is the laxer `ContentSlug`, so `dragon-ancestor-red---fire-damage` could not be
  rendered as an option at all. That record has been in the pack since the first import and was
  simply unreachable; the widening is what this change would otherwise have crashed on.
- **The adversarial review found no defect in the shipped behaviour and three holes in the tests,
  all closed.** Three mutations survived the suite it was handed: an `offered` that ignores subclass
  rows entirely (every subclass choice merely arrives one level late, through `_deferred`), and a
  `granted` or `text` built from the class row alone. The last two are exactly what the advisor
  reads as `HANDED OVER` and `RULES TEXT`, and the fighter is where it shows — `fighter-7` and
  `fighter-10` say only "Martial Archetype feature", so with the merge dropped the model would pick
  a second fighting style from three bare refs and no prose. The new fighter test pins all three at
  their own levels, and all four mutations (including the pair the reviewer combined) now fail it.
  It also caught the sweep's own weak spot: the fighter's level-1 style satisfied "this row's
  choice was answered" for `champion-10`, so the test now asserts a level-20 fighter holds two.
  Two comments claimed more than the pack does and were corrected rather than defended: `_deferred`
  is answered by any of a row's options being held, and two rows *do* carry choices at one level —
  `ranger-3` and `sorcerer-1` — when the second one is the subclass question itself.
- **The ticket's own example was wrong**, which the review caught in a test comment repeating it:
  `domain-spells-1` is granted by `cleric-1`, the class row, and has been landing on every created
  cleric since §7. What never landed is which domain those spells are, and that is what the pick
  now says.
- Verification: 166 → 169 tests. `SAVE_VERSION` 52 → 53 across the six state/save/turn fixtures,
  where `save_version` is again the only byte that moved; no prompt or schema golden moved at all,
  because `advancement.md` did not have to change — "exactly the alternatives the offer lists" was
  already the rule, and a subclass ref is an alternative like any other.
- Known ceiling, measured: a subclass's domain spells reach the sheet as its record's own prose
  (`subclass-spells`, 204 characters on a Life cleric's ref line, 12 on a Champion's) and not as
  spell refs, so `resolve_cast_spell` still refuses a domain spell the cleric did not pick from its
  own list. The pack states the grants structurally, gated by a `"Cleric 1"` string; landing them
  is a spells-side change, not this one.

## Next

- All five deferred tickets in `.scratch/creation-remaining-state/` are closed (see §7 and §9).
- The `5e-database` checkout now exists at `../5e-database`, pinned to the manifest's `source_commit`.
  It is not vendored, so a fresh clone of this repo has to make it again before any importer run.
- Phase 11's live probe: settled (see phase 11). Phase 12's manual pass: done 2026-08-12 —
  the play-test's easy findings (subrace step, follow-up prompts naming the collection,
  background languages, a live preview pane) shipped the same day; the advisor front-end still
  waits on the page feeling slow.
- All five tickets in `.scratch/advancement-correctness/` are closed (see §8 and §10). Every level
  row and every subclass record in the pack is now reachable from play.
- The same audit found five things that are not advancement's; §9 closed one of them — racial traits
  now reach the sheet, through the subrace's own `granted`. Left: a created 5e character has no
  traits at all, saving-throw proficiency is modelled nowhere, background equipment and money are
  not granted, and a long rest never restores hit points (`hp` is written with no `recharge`, so
  `refill` skips it — one line, plus kael's json). None is ticketed yet.
- Phase 13 — scenario creator — next unshipped phase.
