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

## Current

Next: REFACTOR.md phase 3 (threads + hooks).

- Phase-2 line delta: `src/aidm` +394 (budget said +150). Roughly half is the five op
  classes with their model-facing descriptions and resolvers, which is the price of the
  vocabulary being a prompt; the state model, gating, and prompt work are the rest.
- Phase-1 line delta: `src/aidm` +11 (budget said −100). The budget was wrong, not the
  work: REFACTOR.md's own bail-out note prices the true duplication at ~60 lines, and the
  merge paid that back while adding two ops, the surface gate, and the shared fact helper.
