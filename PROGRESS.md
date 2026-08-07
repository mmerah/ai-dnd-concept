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

## Current

Next: REFACTOR.md phase 6 (generic content facts). Phase 5 (ironsworn) is deferred — phase 4
proved the VM on story at oracle parity, so a second engine would re-prove a proved thing and pay
in content nobody plays yet.

Worth doing before or alongside phase 6: the one prompt pass on "the Director drops the state
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
