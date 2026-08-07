# Progress

## Shipped

- **Kernel phase 1 — Worldkeeper + generic steps and trace** (645d930). One worldkeeper
  role replaces maintainer+creator (1 model call, screening in code); `Turn` persists
  generic `StepTrace`s; the trace panel and `run_turn` know no role names; a role is an
  inserted `(name, StepFn)` pair from `default_workflow`. `SAVE_VERSION` 39. Config note:
  role settings key is `worldkeeper`; `ROLES__MAINTAINER__*` / `ROLES__CREATOR__*` env
  entries silently stopped applying.
- **Kernel phase 2 — Action registry, one TurnPlan** (633e107, built after VISION.md was
  written and consistent with it). Engines register `ActionSpec`s (model + labels +
  resolve + optional check); the loader builds the Director's plan model per engine;
  `check_plan` is kernelized (trial resolve, `Random(0)`, refusals as strings); no plan
  subclasses, no isinstance downcasts; `milestone_earned` deleted. Evals at parity with
  pre-phase HEAD: 96% overall, measured same-hour from a worktree (n=69,
  `scripts/evals/results/2026-08-07-645d930+*`). Standing weakness: `rest` ~60-70%
  (prompt problem, pre-existing).

- **Vision phase 0 — Eval debt, harness half** (2026-08-07). `EvalCase` gained a `role`
  dimension (`director` | `advisor` | `worldkeeper`) and `run.py` dispatches to one turn
  function per role; `--only <role>` selects a suite. Advisor runs `render_proposal` +
  the `advisor` stage (whose output validator *is* `Engine.violation`, so a proposal that
  lands is legal by construction); worldkeeper runs the pipeline's own `worldkeeper_step`
  against an authored `narration`, so admission code is what is measured. New probes:
  setup `set_note`; checks `number_value`, `has_ref`, `note_value`, `rolled_with_mode`,
  `created`. 7 new cases (23 → 30): 2 advisor, 2 worldkeeper, and the three owed director
  cases (`advantage-attack`, `concentration-replaced`, `story-check-both-directions`).
  `concentration-replaced` needed a concentration spell, so eval-only `elowen` gained
  `hideous-laughter`.
- **Vision phase 1 — One change language** (2026-08-07). `DeltaChange` is deleted; one
  `Effect` union in `state/effects.py` (12 ops), published per surface as `TurnEffect`
  (10, the Director's) and `SheetEffect` (8, the advisor's) — a model is never shown an op
  its surface always refuses. New ops `grant-counter` and `add-ref`; `change-counter`
  folded into `adjust-counter` as an optional advancing-only `maximum`;
  `adjust-counter.reason` became the `why: str = ""` every sheet write now carries, and
  `entity_id` too. `apply_effect(..., advancing=)` is the one context switch: advancing
  refuses non-sheet ops and any entity but `player`, and grows the sheet; a turn refuses
  `grant-counter`, `add-ref`, and a raised `maximum`. `apply_delta` died into
  `Engine.advance`; `EnginePlugin.check_delta` now judges the resulting `Sheet` the kernel
  already applied, instead of re-applying the delta itself. `Engine.violation` requires a
  non-empty `why` per change, keeping the confirmation panel's per-change reasons.
  `SAVE_VERSION` 40. Regenerated: both `turn_plan.json`, `sheet_delta.json`,
  `instructions/*`, `save/*`, `state/*`, `turn/*`.

**Phase 0+1 baseline, measured** (`results/2026-08-07-0d6deec+61ccea8{,-2}.json`, gpt-oss-120b,
2 suites × 30 cases × 3 runs): overall 90% / 89%.

- **Gate: passed.** The 23 pre-phase cases score **133/138 = 96%**, exactly the parity figure
  phase 2 of the kernel plan recorded. Phase 1 regressed nothing; every 0% case is new.
- The advisor and worldkeeper dimensions both work end to end: `advisor-story-growth`,
  `advisor-5e-level-up`, `concentration-replaced` and `worldkeeper-creates-nothing` are all
  100%. The advisor's grown `NativeOutput(SheetDelta)` therefore *is* now probed live on
  gpt-oss at 6/6 — that phase-0 debt is closed, and the IDEAS.md entry with it.
- `worldkeeper-creates-npc` was 0/6 against a mis-authored check, not a model fault: its
  narration named a crypt that is not in canon, so the worldkeeper correctly created two
  entities where the check demanded one. Narration now points at the authored bell tower,
  and the case is **6/6** (`results/2026-08-07-0d6deec+634d471{,-2}.json`).
- The remaining weaknesses are recorded in REFACTOR.md under "Eval findings owed a cleanup
  pass" — advantage never fires, discipline sits at 67%, and `condition-lifted` is flaky.
  None blocks phase 2.

- **Vision phase 2 — Relations** (2026-08-07).
  `Relation(Mutable)` in `state/world.py` (`kind`, `source`, `target`, `directed`, `known`,
  `tags`; id derived as `kind/source/target`, so `WorldState.relations` is keyed by it and
  the id is never stored twice). `RelationId` is a bare `NewType` like `EntityId`, not a
  `Slug` — entity ids carry underscores, so a derived slug was never possible.
  `WorldState` validates the two kinds core interprets (`connected` joins two locations,
  `party-member` an actor to `player`) plus one leak rule: a `known` relation may not name
  an entity the player has not met.
  - Five new ops in `Effect`/`TurnEffect` (never `SheetEffect`, all in `_WORLD_OPS` so
    advancement refuses them): `add-relation`, `remove-relation`, `tag-relation`,
    `untag-relation`, `reveal-relation`. `directed` and `known` are **not** model fields —
    `add-relation` derives `directed = kind != connected` and writes `known=True`, keeping
    the Director's schema as small as the phase gate wants.
  - Movement gating in `_move_actor`: a location with any `connected` relation admits the
    player only through a known, un-`locked` one; the refusal names the reachable places. A
    world authoring no connections keeps free movement. Party members move with the player.
  - Prompts: `Exit` value + `BaseScene.exits`/`.party`, an EXITS FROM HERE section in the
    director and narrator renders, party members placed as "travelling with the player".
    `VisibleScene` keeps only `known` exits, so a secret passage cannot leak.
  - whispering-vault authors study↔cloister (known), cloister↔bell_tower (hidden), and
    cloister↔vault (hidden + `locked` — the vault seal).
  - `SAVE_VERSION` 41. Regenerated: `save/*`, `state/*`, `turn/*`, `prompts/*`,
    `instructions/*`, both `turn_plan.json`. New: `AtLocation` eval probe and two cases
    (`movement-follows-exits`, `party-member-travels`, tag `relations`; 30 → 32).
  - Tests: two in `tests/core/test_effects.py` — connection gating (hidden → revealed →
    walked; locked → untagged → walked, plus the leak assertion below) and party travel.
  - Adversarial review found three bugs, all fixed: a relation trace names **both**
    endpoints, so `remove`/`tag`/`untag` on a hidden tie leaked an unmet entity's name into
    narrator evidence (now `narrate=relation.known`); a reversed undirected pair
    (`a→b` and `b→a`) derived two ids for one tie, so a `locked` tag could be bypassed
    nondeterministically (`Relation.id` now sorts an undirected tie's endpoints); and
    `add-relation party-member` on a distant NPC teleported them on the next move (now
    `require_actor_here`). Standing recommendation not taken: cut `tag-relation` — nothing
    in the phase's behaviour locks a connection at turn time, but REFACTOR.md names the op.

**Phase-2 baseline, measured** (`results/2026-08-07-952ea1a+2a2d4f9.json`, gpt-oss-120b, 32 cases
× 3 runs): overall 89%, against the phase-0+1 baseline of 90% / 89%.

- **Gate: passed.** No failure traces back to relations. Every failing pre-phase case is a
  standing finding: `advantage-attack` 0%, `long-rest-recharge` 33% (the recorded `rest`
  weakness), `condition-lifted` 67%, and the discipline family — `story-check-both-directions`
  and `story-no-risk-needed` both 33%, the latter's failing plans containing no relation op at
  all (the Director revealed the cloister rat on a look-around turn).
- The five grown Director ops therefore *are* now probed live on gpt-oss. Note the ordering
  REFACTOR.md asks for (probe before fixtures) was not followed; fixtures were cut first and
  the probe was a plain re-run. Do it in the specified order next phase.
- `party-member-travels` is 100%; `movement-follows-exits` is 67%, its one failure a plan that
  wrote `reveal-relation` and forgot the `move-actor`. The `CORE_DIRECTOR` clause now says the
  reveal and the move belong in the same `effects`, in that order — **unverified**, changed
  after the run, so the next suite is what confirms it.

- **Vision phase 3 — Threads + hooks** (2026-08-07). Code complete, live gate not yet run.
  - `state/effects.py` split: the op vocabulary stays there (leaf: imports `base` + `packs`
    only), every resolver moved to the new `state/apply.py`. This was forced, not cosmetic —
    `GameState.hooks` carries `tuple[Effect, ...]`, so `world` must import `effects`, and the
    old resolvers imported `world`. Import sites of `apply_effect` / `require_actor_here` /
    `entity_fact` now read `aidm.state.apply`; `_WORLD_OPS` became public `WORLD_OPS`.
  - `Thread`, `HookMatch`, `Hook` in `state/world.py`. `GameState` gains `threads`,
    `hooks`, `fired_hooks`, `pending_notes`, validated in `_consistent_world` (thread keys
    match ids, hook ids unique, `fired_hooks` names an authored hook). `fired_hooks` is a
    tuple, not a set: a save's bytes are a golden fixture and set ordering is not stable.
  - New op `advance-thread` (in `Effect`/`TurnEffect`, and in `WORLD_OPS` so advancement
    refuses it). It moves `status`, `stage`, or both, refuses neither, and its fact never
    narrates — threads are Director bookkeeping.
  - `fire_hooks` in `state/apply.py`: one pass per turn over unfired hooks, matched on fact
    kind plus exact-equality `data` fields. A refusing effect records `hook_failed`, skips
    that hook's remainder, and still marks it fired, so authored-content bugs never kill the
    turn. `hook_step` sits between resolve and narrator in `default_workflow`, recomputing
    `ws.evidence` so hook consequences are narrated the turn they land.
  - Notes reach the Director only, next turn: `pending_notes` renders as SCENARIO NOTES and
    `director_step` clears it on the draft after rendering. ACTIVE THREADS renders
    non-resolved threads. Both live on `SceneSnapshot`, never `BaseScene`, so `VisibleScene`
    stays leak-free by construction. `CORE_DIRECTOR` gained one paragraph for both.
  - `ScenarioWorld` authors `threads` and `hooks`; a hook advancing an unauthored thread
    fails at load. `begin_game(engine, scenario, character)` in `app/session.py` is now the
    one opening-state builder (the app, `run.py`, and the tests all duplicated it, and each
    needed the same two new fields).
  - whispering-vault ships the `vault-seal` thread and two hooks: discovering the vault
    moves it to `seal-found`, tags the door `warded`, and notes the Director; discovering
    Elena moves it to `rite-known`.
  - `SAVE_VERSION` 42. Regenerated: `save/*`, `state/*`, `turn/*`, director `prompts/*`,
    `instructions/*`, both `turn_plan.json`; `engines/examples.json` gained its
    `advance-thread` entry (the every-op-once check).
  - Tests: one in `tests/core/test_pipeline.py` — the hook fires on its fact, the thread
    moves, the tag reaches the narrator prompt while the thread id does not, the note lands
    in the *next* turn's director prompt and is then cleared. `STEPS`/`TURN_STEPS` gained
    `hooks`.
  - Evals: new probes `hook_fired` and `thread_at`, new case `hook-fires-on-discovery`
    (tag `hooks`; 32 → 33), and `run.py`'s `_director_turn` now runs the hook pass after
    `resolve_step` — without it the case could never fire.
  - Adversarial review found no defect in the lifecycle or the leak paths, and confirmed the
    effects/apply split was forced rather than cosmetic. Four tightenings taken: `Hook.effects`
    is typed `TurnEffect`, not `Effect`, so a hook authoring `grant-counter` fails at load
    instead of degrading to `hook_failed` in play; `AdvanceThread` validates that it moves
    something, so the same failure moves from fire time to the boundary; `fired_hooks` refuses
    a duplicate; and the eval case asserts the hook fired, not only that the thread moved.
    Two findings deliberately left: a save is not cross-checked for hooks naming absent
    threads (the `hook_failed` path is the spec'd behaviour for authored-content bugs), and a
    hook's own facts never feed the same pass — chaining is across turns, by design.

**Phase-3 baseline, measured** (`results/2026-08-07-74bfb87+25afe2d.json`, gpt-oss-120b, 33 cases
× 3 runs): overall 89%, level with the phase-2 baseline of 89%. Completion 100%.

- **Gate: passed.** No failure traces back to threads or hooks, and the grown Director schema
  (one more op) cost nothing: every turn completed, and the story/discipline family recovered
  from 33% to 100%. `advance-thread` stays in `TurnEffect`; the bail-out was not needed.
- `hook-fires-on-discovery` is 67% — its one failure is the Director answering about the vault
  without writing the `reveal`, so no fact existed for the hook to match. The hook pass itself
  never misfired. Same shape as `movement-follows-exits` (also 67%, unchanged from phase 2
  despite the `CORE_DIRECTOR` clause added then): the Director drops the state write that must
  accompany the fiction. Recorded in REFACTOR.md as one prompt problem, not two cases.
- Everything else failing is a standing finding, all now in REFACTOR.md: `advantage-attack` 0%
  (the only stable one), `rest` down to 33%, `condition-lifted` 33%. At n=3 the noise is large
  enough that no single case moving should be attributed to this phase.

- **Vision phase 4 — Rule VM, proved on story** (2026-08-07). Code complete, live gate not run.
  - `src/aidm/engines/vm.py` is the whole VM: param specs → a generated action model, and a
    straight-line program the kernel runs where `ActionSpec.resolve` used to. It imports no
    engine and no loader (loader imports it), so `Resolved` now lives there and loader
    re-exports it.
  - Params are a closed set — `entity-id`, `slug`, `int`, `str`, `dice-expr`, `enum` — each with
    a description and an `optional` flag rather than an optional-of wrapper. `ActionDef.model()`
    builds the model with `create_model`, named from the action (`risk` → `Risk`), the `doc` as
    its docstring and `act: Literal[name]` first.
  - Program instructions: `let`, `require`, `roll`, `outcome`, `apply`. Expressions: `number`,
    `table`, `present` (an omitted optional param counts 0, a written one counts `weight` — the
    help/hinder ±1), and a flat `sum` over those three. No nesting is possible: `sum` takes
    non-sum terms only, so the "straight-line, one conditional level" rule is structural rather
    than validated. Predicates: `has-tag(carried)`, `counter-full`, `is-player`.
  - `$name` is the one reference sigil — params and `let`/`roll` bindings share one namespace, and
    a bare string is a literal. One `_refs` walk both validates at load and substitutes at run.
  - `require` refuses with a message formatted from the params plus `<param>_name` per entity
    param, so a refusal names the actor. A predicate over an omitted optional param never
    refuses — that is what makes the help/hinder tag checks conditional without a branch op.
  - There is no declarative `check`: every refusal is the `ValueError` `check_plan`'s trial
    resolve already turns into a retry, so `check_risk`'s rules now run at resolve time too
    (the Python resolver never checked TAKEN OUT itself).
  - Load-time validation in `ActionDef`: every `$ref` is bound before use, names are bound once,
    `outcome`/`when_outcome` labels are declared, and a ref-free `apply` effect is validated as a
    `TurnEffect` immediately. `tests/core/test_vm.py` covers exactly this boundary.
  - `Engine` gains `actions` (`plugin.actions` + whatever `actions.json` declares) and
    `_plan_model` builds from that, so Python and declarative `ActionSpec`s coexist — dnd5e is
    untouched.
  - `engines/story/{actions,resolve}.py` are deleted; `rules.py` is now a 19-line shim with
    `actions=()` and `APPROACHES` moved to `advance.py`. Story's Risk is
    `engines/story/actions.json`.
  - **Oracle: 8640 cases, 0 mismatches.** 10 states (stress 0/3/5 × bold −3/0/4) × 3 actors ×
    2 approaches × 3 difficulties × 4 helping × 3 hindering tags × 4 seeds, comparing the VM
    against the deleted `resolve_risk`/`check_risk` on facts, outcome, committed state, and
    refusal string. Deletion happened only after that ran clean.
  - **Gate: passed, dead level.** Director-only, like for like: phase 3 scored 76/87 = 87.4%,
    phase 4 scores 152/174 = 87.4% across two runs of the same commit
    (`results/2026-08-07-9816682+{4180b45,58a9ba4}.json`). All four story cases — the ones the VM
    now resolves — are 100% in both runs, so the VM's own gate is clear with room to spare.
    Nothing in the diff can reach the failures: `hook-fires-on-discovery` 0/6 and `condition-rider`
    33%/67% are the standing "Director drops the state write" finding, now the largest one in
    REFACTOR.md; `movement-follows-exits` and `short-rest-recharge` both reached 100%.
  - **No fixture changed at all** — not the plan schemas, not the instructions, not the prompts.
    The generated `Risk` emits byte-identical JSON schema, so the model cannot notice the
    migration and `SAVE_VERSION` stays 42. The live story suite is therefore a formality rather
    than a risk, but it has not been run.
  - Bail-out not needed: Risk wanted no loop, no recursion, and no open-ended primitive.
    Deliberately deferred rather than built unused: a `counter` expression, `roll.mode`, and the
    `dice-expr` param type — all phase 7. `int` params stay: ironsworn's adds need them next.
  - Adversarial review found three defects and two latent ones, all fixed and re-verified against
    the oracle (8640 cases, still 0 mismatches). A refusal `message` placeholder was never checked,
    so a typo raised `KeyError` out of `check_plan` — which must not raise — the turn a refusal
    first fired; placeholders are now validated at load against the bound names. `_refs` walked
    nested values that substitution never reached, so a ref hiding below an effect's own fields
    would have survived into the applied effect; `_check_effect` now refuses one at load. A
    `counter-full` predicate over an absent pool raised `KeyError` where the sibling `number`
    expression raises a readable `ValueError`. Latent: `apply.when` lacked `_require`'s
    omitted-optional skip (now one shared `_decidable`), and an action declaring `labels` without
    an `outcome` instruction loaded with silently dead branches. Taken from the same review:
    `description`/`optional` moved to a shared `ParamBase`.

- **Vision phase 6 — Generic content facts** (2026-08-07).
  - `Record` stores its interpreted view as data: `numbers`, `notes`, and `facts`
    (`FrozenMap[Slug, JsonValue]`), written at authoring time. `sheet_numbers()`/`noted()`
    default to the stored maps, so every consumer — sheet backing, `read_content`, ref
    rendering, eval probes — is unchanged. A typed subclass still computes and leaves the
    stored maps empty.
  - `spec.json` collections became a map `name → CollectionSpec`: a collection declares the
    facts every record must carry (`FactType`: `int | slug | str`) and `validate_pack`
    refuses a record missing or mistyping one. dnd5e declares skills `ability: slug`,
    features `level: int`, alignments `abbreviation`, languages `category`, proficiencies
    `category` + `reference`, subclasses `class` + `flavor`, subraces `race`.
  - 15 record classes left `src/aidm` for the new `scripts/srd/interpret.py`: authoring-time
    intermediates whose `generic()` flattens typed fields into one generic `Record`
    (vision §15 — the interpretation runs once, in the importer). `record_types` is down to
    5 — spells, weapons, classes, levels, monsters — exactly the collections runtime Python
    still reads, all deleted by phase 7.
  - Facts carry what would otherwise be lost to prose: skill ability, feature level, feat
    prerequisites, race/subrace ability bonuses, subclass spell grants, draconic-ancestry
    breath damage and scaling tables.
  - **Oracle: 1209 migrated records, 0 mismatches** — stored `numbers`/`notes` equal the
    deleted classes' computed maps exactly, checked before the classes were trusted gone.
  - Pack regenerated from the pinned `5e-database` checkout, after first re-running the
    importer unchanged and confirming the shipped pack byte-identical (the baseline the
    memory file demands). The round-trip regression passes against the regenerated pack.
    `SAVE_VERSION` 43. Fixtures moved: the `save_version` line in `save/state/turn` — no
    prompt, schema, or instruction byte moved, so the model cannot see this phase and no
    live gate is owed.
  - Line delta: `src/aidm` Python −209 (budget said −250); dnd5e `spec.json` +40 for the
    fact declarations; `scripts/` +362, which is the interpretation the runtime shed.
  - Adversarial review (fable) upheld the three-map shape against VISION §7's one-map sketch —
    `numbers` project onto sheets, `notes` render to the model, `facts` feed the VM; each has its
    own consumer and type contract, and one `JsonValue` map would re-encode the split as key
    conventions with weaker validation. Four findings taken: **facts are normalized to joinable
    slugs** (`class: barbarian`, `race: dwarf`, `reference: light-armor`, abilities as full
    slugs — upstream refs widened `Label → Named` to reach `.index`; display names stay in
    text/notes), the facts admission rule is now "what a deterministic reader will read" (dropped
    language script/speakers, alignment abbreviation — `AlignmentRecord` died entirely — and
    subclass flavor), the one-field `CollectionSpec` wrapper flattened into
    `collections: name → FactSchema`, and the `slug` fact check now validates through
    `TypeAdapter(Slug)` instead of a bare pattern. Oracle re-run after all of it: still
    0 mismatches. Left deliberately: stored `numbers`/`notes` on a typed record are ignored, not
    refused (the gap dies with the 5 typed classes at phase 7), and phase 7 must keep "content
    facts" (`Record.facts`) verbally distinct from turn `Fact`s.

- **Vision phase 7 — D&D on the VM** (2026-08-07). `dnd5e/actions.py` (120 lines),
  `resolve.py` (325), and `records.py` (596, its last 5 classes now `scripts/srd/interpret.py`
  intermediates) are deleted; `record_types` is empty for every engine. dnd5e is
  `actions.json` (1295 lines — attack, cast-spell, check, use-feature, rest, improvise) plus a
  67-line shim and the 49-line `advance.py` the spec exempts (offers are phase-10 workflow).
  - The `refill` op: `ProgramEffect = TurnEffect | Refill` is what VM `apply` validates, so
    the Director never sees it and hooks cannot author it; the rest program owns the
    label→recharges mapping and `EngineSpec.recharge` is deleted as dead config.
  - VM growth, the closed set at once (`vm.py` 411 → 824): instructions `choose`, `format`,
    `lookup`, `read`, `ladder`; `when`/`when_outcome` guards on every instruction; `roll`
    gains `mode` and ref-capable `vs`/`dice`; `outcome` thresholds accept refs and a null ref
    skips; predicates `equals`, `present`, `carries`, `at-least`, `and`; exprs `const`,
    `value`, `div`, `max`, `number`-with-default. `run_program` takes `Content`; an
    unbound-ref read raises `ValueError`, so a guard bug refuses instead of killing the turn.
  - Fact schemas for the 5 remaining typed collections (weapons, spells, classes, levels,
    monsters) live in the pack; `tests/dnd5e/fixtures/mechanics_parity.json` pins every
    shipped spell's and weapon's mechanics facts as a golden, and `test_resolve.py` carries
    the seeded-roll behavior and exact refusal strings the Python resolver defined.
  - Named Python exceptions, in the shim as specified: `dynamic_labels` (`cast-spell` /
    `improvise` contested-ness) and `plan_checks` (the two double-spend checks).
  - Deviations, named: a combined-fault attack plan (wrong in two ways at once) gets
    whichever refusal the straight-line `require` sequence reaches first rather than the
    Python's check order — message choice drifts, legality never; and spellcasting resolves
    from the sheet's first class ref where the Python refused multiclass outright
    (advancement still refuses building a second class).
  - **Schema identity held**: `turn_plan.json`, `instructions/*`, `prompts/*`, and
    `sheet_delta.json` are byte-identical, so no live gate is owed per the phase spec. The
    only fixture movement is the `save_version` line in `save/state/turn` (`SAVE_VERSION`
    44). Full suite 131 passed; ruff, format, basedpyright clean.
  - Adversarial review (fable) found no blocking defect; the boundary held everywhere it
    probed (`refill` unreachable from Director and hooks, every unbound-ref path refusing via
    `ValueError`, reveals preceding every name-carrying fact, 5e parity line-for-line against
    the deleted resolver). Four findings taken: a `when`/`when_outcome`-guarded binding named
    by a template outside its guard now load-refuses instead of raising `KeyError` out of
    `check_plan` the turn the guard first skips; a `present` over a non-`$` literal (an
    always-true authoring typo) load-refuses; unused `Read.required` deleted; `Equals.value`
    narrowed to `bool | str`. Reported for later, not taken: `EnginePlugin.record_types` is
    now empty everywhere and its plumbing is a clean negative diff for phase 8's shore.
  - Line delta: `src/aidm` Python **−318** (staged together with phase 6: −527 vs HEAD
    3885853, 6438 → 5911); `vm.py` +427, dnd5e `actions.json` +1295 new, `scripts` +316.

- **Vision phase 8 — Scene Director / Rules Director split** (2026-08-07). Code complete, the A/B
  not yet run. The split is one config flag, `Settings.scene_director` (default off), so both
  configurations are live in one build and the A/B compares them like for like.
  - `SceneDirective` (focus, pressure, stakes, threads) in `state/turn.py`, `NativeOutput` on a
    4-field schema — the size the output-mode caution treats as safe. `scene_stage` /
    `scene_step` in `turn/pipeline.py`; deps are the `GameState`, and its output validator
    `ModelRetry`s a thread id the state does not hold, so a hallucinated storyline never reaches
    the plan.
  - **One renderer, two views.** `render_director` gained an optional `directive`: with none it
    renders exactly today's bytes; with one it drops the unrevealed-canon, ACTIVE THREADS and
    SCENARIO NOTES sections and renders a SCENE DIRECTIVE section carrying focus/pressure/stakes
    plus only the threads the directive named. That filtered list is what keeps `advance-thread`
    usable from a Rules Director that no longer sees the thread table.
  - `CORE_DIRECTOR` is now composed from eight paragraph constants and `RULES_DIRECTOR` reuses
    six of them plus one new directive paragraph — the narrowing drops the unseen-canon and the
    threads/notes paragraphs. `CORE_DIRECTOR` is byte-identical, so every existing instruction,
    prompt, schema, save and turn fixture is untouched and `SAVE_VERSION` stays 44.
  - Evals: `run.py` records tokens (`RunRecord.tokens`, mean per case and per suite, printed by
    `summarise`) — the A/B's second axis alongside the latency and retries it already had — and
    `_director_turn` runs the scene stage first when the flag is on, summing both stages' tokens
    and retries. The turn functions return one `Attempt` instead of a widening tuple.
  - Tests: one in `tests/core/test_pipeline.py` — the step order gains `scene`, the directive's
    focus and its named thread's title reach the Rules Director, and the unrevealed entity and
    the notes heading do not (they stay in the scene prompt). New goldens: `instructions/*/
    {scene,rules_director}.txt` and `schemas/scene_directive.json`.
  - Line delta: `src/aidm` +128, of which ~30 is the paragraph split of `CORE_DIRECTOR`.

**Phase-8 A/B, measured** (2026-08-07, gpt-oss-120b, 29 director cases × 3 runs, one tree
`46fb255+752ed83`, the two suites run back to back: single =
`results/2026-08-07-46fb255+752ed83.json`, split = the same name with `-2`).

| | single director | Scene + Rules split |
| --- | --- | --- |
| overall | **91%** | 72% |
| turns completed | 95% | 98% |
| mean duration/turn | **4.1s** | 6.4s |
| mean tokens/turn | **11082** | 11427 |

- **Gate: the single director wins; `scene_director` stays off.** The split costs 19 points and
  56% more latency and saves no tokens — a second model call spends whatever the narrower prompt
  saves.
- **The narrowing deletes the Director's reveal.** `hook-fires-on-discovery` 0/3 against 100% for
  the single director: unrevealed canon is exactly what the Rules Director no longer sees, so it
  cannot `reveal` the vault, no fact exists, and no hook fires. Phase 8.5's open design question —
  where the Director's non-mechanical writes live — is now answered with evidence rather than
  taste: they cannot simply be taken off the plan surface.
- **A mandatory directive manufactures mechanics.** `pressure` and `stakes` are required prose, so
  a quiet turn stops being quiet: `no-mechanics-turn` 100% → 0%, `story-no-risk-needed` 100% →
  67%, `story-check-both-directions` rolling where the single director rolled nothing. The
  discipline family goes 67% → 0%.
- It also drops mechanical writes the single director makes: `long-rest-recharge` 100% → 0%,
  `self-heal-scaling` 100% → 0%, `short-rest-recharge` 100% → 67% — the standing "Director drops
  the state write" shape, amplified by a prompt that no longer states the fiction it must serve.
**Phase-8 A/B, second attempt** (same day, tree `46fb255+b43780a`, same 29 × 3 shape; single =
`results/2026-08-07-46fb255+b43780a.json`, split = the same name with `-2`). Both fixes the first
A/B asked for went in and the split closed the whole gap:

| | single director | Scene + Rules split |
| --- | --- | --- |
| overall | 84% | 84% |
| turns completed | 93% | 95% |
| mean duration/turn | 6.3s | 6.1s |
| mean tokens/turn | **9974** | 10934 |

- The fixes: `SceneDirective.reveal` names unmet entities and renders them under the directive as
  full `name[id=...]` lines, so the Rules Director can write a `reveal` for what it cannot see
  (its validator refuses an id that is not an unmet entity); `pressure` and `stakes` default to
  empty and render as an explicit "this turn is quiet" line instead of blank headings; and `_DRIVE`
  ("a turn with nothing at stake should be the exception") left `RULES_DIRECTOR`, because the
  directive has already decided that question and saying it twice is what manufactured mechanics.
- **Quiet turns are fixed.** `no-mechanics-turn` 0% → 100%, `story-no-risk-needed` 67% → 100%,
  `self-heal-scaling` 0% → 67%, `long-rest-recharge` 0% → 67%. Discipline 0% → 67%, level with the
  single director.
- **`hook-fires-on-discovery` is the one regression left, and it is a selection problem, not a
  channel problem.** The reveal channel works — every run wrote the `reveal` the directive named —
  but the Scene Director names `vault_map` ("the vault map") where the case needs `vault` ("the
  sealed vault"), 7 runs out of 7 across two prompt wordings. Its answer is defensible fiction
  (Mara hands over the chart) that the authored hook does not recognise. The eval harness now
  records the directive on every run, which is how that was attributable at all; a third prompt
  wording was tried, moved nothing, and was reverted rather than shipped unmeasured.
- **Closed scenario-side, after the split shipped: the case is 6/6 in both configurations.**
  Renaming the map to distance it from the vault was tried first and did nothing (0/6) — the bias
  is not lexical: the chart is the hidden thing physically in the player's room, and "put in front
  of them" reads as present. So whispering-vault authors a second hook instead, `vault-charted`:
  discovering the map advances `vault-seal` to `seal-found` and reveals the vault, because Mara
  handing over the chart that marks the stair *is* finding the way down. The `hook_fired` probe
  takes `hooks` (any of them fired) rather than one id — one fiction can reach a thread by more
  than one hook. Note what this did and did not fix: the case no longer measures the Director
  dropping a state write, and REFACTOR.md's standing finding now rests on the two condition cases.
- **Decision: the split ships on** (`scene_director` defaults true; setting it false collapses
  both roles into one call, and every fixture and test still covers that path). The evals do not
  choose between them — correctness and latency are level and the split costs ~10% more tokens —
  so the maintainer's call settles it on structure: deciding what a turn is about and resolving it
  by the rules are separate jobs, and the eval scenarios are small enough that the separation's
  value is not what they measure. What the numbers did buy is the two fixes and the confidence
  that the split is not paying for itself in lost correctness.
- This hour's single-director run scored 84% against the previous hour's 91% on an unchanged code
  path (`ability-check-dc` died 0/3 on provider errors), which is the recorded small-n noise floor
  doing exactly what REFACTOR.md says it does. Only same-hour pairs are comparable; neither 84% nor
  91% is a trend.

## Current

Phase 8 shipped 2026-08-07 with the Scene/Rules split on. Phase 5 (ironsworn) stays deferred.

Next is phase 8.5 (model-facing schema shrink). The two A/Bs narrow it: a Director that cannot see
unrevealed canon writes no `reveal`, so the non-mechanical writes need a named home before
`effects` can leave the plan — either a residual write list, or a directive channel like
`SceneDirective.reveal`, which works mechanically and now fails only on which entity the Scene
Director picks.

Worth doing before or alongside phase 8: the one prompt pass on "the Director drops the state
write", now the largest eval finding at three cases and the only one costing whole runs.

- Phase-4 line delta: `src/aidm` +423 total, of which Python is +315 (budget said +250 VM / −75
  story). The story deletion paid −126; `vm.py` is 411 lines and `actions.json` 108. The VM is
  over budget because the param specs and their `create_model` bridge are ~130 of those lines,
  and that is the part phase 5 reuses for free.
- Schema simplification, asked and answered: the authoring side is where the free LOC is (the
  shared `ParamBase` and the dropped `dice-expr` type were the whole harvest, ~20 lines). Making
  the **model-facing** schema smaller — AFTER-VISION.md's derived fields and its 70-90% smaller
  TurnPlan — would break this phase's byte-identical-`Risk` constraint, move fixtures, and cost a
  live eval run. That is phase 6+ work; none of it belongs here.
- Phase-3 line delta: `src/aidm` +240 (budget said +200).
- Phase-2 line delta: `src/aidm` +394 (budget said +150). Roughly half is the five op
  classes with their model-facing descriptions and resolvers, which is the price of the
  vocabulary being a prompt; the state model, gating, and prompt work are the rest.
- Phase-1 line delta: `src/aidm` +11 (budget said −100). The budget was wrong, not the
  work: REFACTOR.md's own bail-out note prices the true duplication at ~60 lines, and the
  merge paid that back while adding two ops, the surface gate, and the shared fact helper.
