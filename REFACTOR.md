# Vision refactor — phased plan

Decided 2026-08-07. Supersedes the 2026-08-06 kernel plan: its phases 1–2 shipped
(PROGRESS.md), its remaining phases are folded in here, reordered and extended to
implement VISION.md in full. VISION.md holds the destination and the argument; this file
holds the route, the code-level decisions, and the evidence rules. Where this plan
deviates from the vision's own phase order, the deviation is stated at the phase that
makes it.

The finish line, from the vision's success list in this codebase's terms:

- story and ironsworn ship no runtime Python beyond a ~10-line plugin shim;
  `dnd5e/actions.py` and `dnd5e/resolve.py` are deleted, their mechanics VM programs
  over content facts. A mechanic the VM cannot express cleanly stays Python as a named
  exception in the shim, never scattered.
- A new content pack introduces no Python record classes; `EnginePlugin.record_types`
  shrinks toward empty.
- Locations connect, and NPCs join the party, through first-class relations.
- A quest advances because committed Facts fired hooks and moved threads — no engine or
  scenario Python.
- Memories outlive the history window. Every role stays one bounded call; the host owns
  the workflow (`default_workflow` already does; keep it true).
- Live evals never end a phase below where it started. Through phase 7 `src/aidm`
  shrinks (~5.5k → ~4.9k lines) while gaining relations, threads, hooks, and the VM;
  phases 8–10 are features that add code and pay in capability, not LOC — each names
  what it deletes when promoted to build-ready.

Cross-phase rules:

- **Golden fixtures are the behavior contract.** A phase regenerates exactly the fixture
  families it names; any other fixture moving is a bug. `SAVE_VERSION` bumps in every
  phase that changes persisted bytes; stale saves are refused, never converted
  (`content/store.py` enforces this). The `Effect` union is model-facing: any phase
  changing it also regenerates `engines/examples.json` (the loader's every-op-once
  vocabulary check), the `instructions/*` family, and both plan schemas.
- **The current implementation is the oracle.** Before deleting a resolver, the
  replacement runs against it on identical state and seeded `Random`; facts and
  committed state must match. Delete only at parity.
- **Eval gates compare like for like.** Any phase touching a model-facing schema or
  prompt re-runs the live suite against a same-hour HEAD run from a worktree — never a
  stale baseline file (phase-2 lesson). A regression that prompt tuning cannot recover
  takes the phase's named bail-out. `scripts/evals/run.py` imports `director_stage`,
  `TurnWorkspace`, `PlanContext`, `resolve_step`, `render_director`; `probes.py` matches
  effect-op strings, fact kinds, and sheet keys — phases moving any of those update the
  scripts in the same branch.
- **Output-mode caution is standing policy.** gpt-oss has failed `NativeOutput` on large
  schemas before (director history): every new or grown role schema gets a live probe
  before its output mode is trusted.
- **Every phase PR reports the `src/aidm` line delta.** Budgets below are estimates, not
  contracts (phase-1 lesson: the work can be right and the budget wrong) — but a phase
  far over budget sheds scope rather than growing the framework.
- **Phase resolution.** Only the next unshipped phase carries build-ready detail. Later
  phases are held at gate resolution deliberately — their specs depend on earlier
  outcomes — and are rewritten to build-ready detail in this file when they become next.

## Phase 0 — Close the eval debt (~1 day, LOC ≈ 0 in `src/aidm`)

The vision makes evals the architectural test; today only the Director is measured.
Every model surface later phases rewrite gets a baseline first. All but the worldkeeper
evals are already-recorded debt (IDEAS.md).

- Advisor evals: cases that run `advisor` + `render_proposal` against a real offer
  (story growth spend; 5e level-up via `advancement-ready`), checking
  `Engine.violation(...) is None` plus per-case sheet probes. Extend `run.py` with a
  role dimension rather than a second harness.
- Live-probe the advisor's `NativeOutput(SheetDelta)` on gpt-oss (never done; the
  worldkeeper probe pattern applies).
- Worldkeeper evals: narration → expected creations/no-creations, reusing the
  turn-pipeline path.
- The owed director cases: an advantage scenario, concentration replacing a spell,
  story checks in both directions.

Done when: director, advisor, and worldkeeper all have measured baselines the later
gates can compare against.

## Phase 1 — One change language (~3 days, budget −100)

**Vision: the VM instruction set (§10) and the single vocabulary hooks, threads, and
advancement speak.** This is the old plan's phase 5, promoted first because every later
phase writes changes in it; its prerequisites (advisor evals, output-mode probe) are
phase 0.

- Unify `Effect` (`state/effects.py`, 10 ops) and `DeltaChange` (`state/sheet.py`,
  7 ops) into one union named `Effect` in `state/effects.py`; `DeltaChange` and its ops
  are deleted. Net new ops after merging the duplicates (set-number, set-note,
  add/remove-tag): `grant-counter`, `change-counter`-with-maximum (fold into
  `adjust-counter` as an optional `maximum` field), `add-ref`.
- Every sheet-writing op carries `entity_id` (the advisor writes `player`) and
  `why: str = ""` — optional so the Director's schema is not forced; the advisor's
  output validator requires it non-empty, preserving the `CORE_ADVISOR` promise and the
  confirmation panel's per-change reasons. Shape decisions where the duplicates
  disagree, named now: `adjust-counter.reason` becomes this `why`; `add-tag` keeps the
  effect shape (`tag_id` + `text`, name derived — the delta's free-form `SheetTag`
  goes); `set-note` clearing an absent key stays a quiet no-op; `adjust-counter`'s new
  `maximum` is advancing-only.
- Context is a flag, not a vocabulary: `apply_effect(..., advancing: bool = False)`. At
  turn time `set-number` refuses unknown keys and `grant-counter`/`add-ref` are refused
  outright; advancing refuses any op that is not a sheet write on the player (one union
  must not hand the advisor `move-actor`) and grows the sheet (today's `apply_delta`
  semantics, ported exactly). `apply_delta`/`SheetDelta` become a thin wrapper or die;
  `violation` and the advancement panel keep their behavior, now trialling on a
  `GameState` draft rather than a bare sheet copy.
- One op set, per-surface schemas: the plan model's `effects`/`branches` publish a
  turn-time subset alias of the same op classes (no `grant-counter`/`add-ref`), the
  advisor publishes the sheet-op subset, and `_effect_vocabulary` renders exactly the
  Director's subset — a model is never shown an op its surface always refuses.
- Creation stays out of the union: `GameState.add` and `GainImprovisedItem` already are
  the creation bookkeeping.
- Fixtures: `schemas/{story,dnd5e}/turn_plan.json`, `schemas/sheet_delta.json`,
  `instructions/*` (the vocabulary block), `fixtures/turn/*` fact traces.
  `SAVE_VERSION` bump. `probes.py` op strings updated.
- Gate: full director suite + phase-0 advisor suite at parity. Bail-out (explicitly
  allowed): keep two vocabularies and extract the shared mutation helpers. It is
  cheap — the true duplication is ~60 lines, and hooks can speak the existing turn-time
  `Effect` unmerged — so take it without ceremony if the advisor-surface rework drags;
  the merge is preferred, not sacred.

## Phase 2 — Relations (~3 days, budget +150 — a feature)

**Vision §2: relations are first-class state.** Proved by the vision's own two features:
stateful location connections and party membership.

- `Relation(Mutable)` in `state/world.py`: `id: Slug`, `kind: Slug`,
  `source: EntityId`, `target: EntityId`, `directed: bool = True`,
  `known: bool = False`, `tags: list[Slug] = []`. `WorldState.relations:
  dict[Slug, Relation]`; `_consistent_world` checks endpoints exist. Notes and
  per-relation sheets wait for a feature that needs them.
- `parent_id` stays for containment — the holder topology is load-bearing in
  `check_placement`, scene building, and item effects, and the vision calls the split
  an implementation detail. Relations carry the non-containment truths.
- New ops in the unified union: `add-relation`, `remove-relation`, `tag-relation`,
  `untag-relation` (kind is a free `Slug`; endpoint existence validated; the id derived
  from (kind, source, target); a duplicate refused, endpoints compared unordered when
  undirected). A separate `reveal-relation` op — overloading `reveal` would mix the
  entity and relation id namespaces and weaken its unknown-id refusal.
- Core interprets exactly two kinds and one tag, as named constants with load-time
  checks (`CONNECTED`, `PARTY_MEMBER`, `LOCKED_TAG` in `state/world.py`): a `connected`
  relation must join two locations, a `party-member` an actor to the player — a typo'd
  slug fails at load instead of silently disabling movement gating.
- Connections: `world.json` gains `relations: tuple[Relation, ...]` (`ScenarioWorld`,
  `content/authored.py`; kind `connected` between locations, undirected). **Movement
  rule:** if the player's current location has any `connected` relation, `_move_actor`
  for the player requires a known, un-`locked`-tagged connection from here to the
  destination; a world with no connections keeps free movement — compat for unmigrated
  worlds only, since whispering-vault is the shipped scenario for both engines and all
  23 eval cases, so the gate is live everywhere once it authors connections. The
  refusal string teaches the model the legal exits.
- Party: kind `party-member` (NPC → player). A party member moves with the player in
  `_move_actor` and is therefore always "here". Joining/leaving is the Director writing
  `add-relation`/`remove-relation` when the fiction says so.
- Prompts: scenes gain an EXITS section (known connections from here, locked state
  shown) and party members are marked in HERE WITH THE PLAYER. `VisibleScene` carries
  only `known` relations — a hidden connection is a secret passage, and the Narrator's
  input type stays leak-free by construction.
- whispering-vault authors its connections (study–cloister–bell_tower–vault) and at
  least one locked/hidden one (the vault seal is exactly this).
- Fixtures: `save/*`, `state/*`, `prompts/*`, both plan schemas. `SAVE_VERSION` bump.
  Gate: the grown Director schema is live-probed on gpt-oss **before** fixtures are
  built (schema size is the known reliability lever); then full suite plus one
  movement-legality case and one party case. Bail-out, priced like phase 4's: if the
  relation ops sink the suite, the Director's turn subset keeps only `reveal-relation`
  and relation maintenance moves to hooks (phase 3) and the worldkeeper — the state
  model and movement gating ship regardless.

## Phase 3 — Threads + hooks (~3 days, budget +200 — a feature)

**Vision §§3–5: Facts drive world systems.** The old plan's phase 6 plus Threads, so a
quest advances from committed Facts without engine code.

- `Thread(Mutable)` in `state/world.py`: `id: Slug`, `kind: Slug`, `title: str`,
  `status: Literal["active", "resolved", "dormant"]`, `stage: Slug | None`,
  `note: str = ""`. `GameState.threads: dict[Slug, Thread]`; scenario `world.json`
  authors the initial set. Deliberately small — a quest, an investigation, and a
  countdown must all fit or the schema is wrong.
- New op `advance-thread` (status and/or stage, `why` required when the advisor rule
  does not apply — hooks supply their hook id). Written by hooks now and the
  Threadkeeper later; the Director may write it too (it is validated like any effect;
  hooks remain the reliable path).
- Hooks, exactly as previously specified: data in `world.json`
  (`hooks: tuple[Hook, ...]`) — id, match (`kind` + exact-equality `data` fields),
  `effects: tuple[Effect, ...]`, optional `note`. Shape-validated at load, no trial
  application; composed onto `GameState` at world build like the threads, so the hook
  step, `run.py`'s `_turn`, and saves all see them. `Hook` lives beside `Thread` in
  `state/world.py`; the step in `turn/pipeline.py`. A code step **between resolve and
  narrator** runs one single pass per turn over unfired hooks against the facts so far:
  apply effects, emit `hook_fired`, add to `GameState.fired_hooks: set[str]`, and
  recompute `ws.evidence` — the Narrator narrates hook consequences the turn they
  happen. Worldkeeper facts never feed hooks and lose nothing real: its creations carry
  runtime-generated ids no authored match could name. Chaining across turns only; no
  fixpoint. A refusing effect on authored-content bugs records `hook_failed` with the
  reason, skips that hook's remaining effects (earlier ones stand), and marks the hook
  fired — never kills the player's turn.
- Notes go to the **Director only, next turn**: `GameState.pending_notes:
  tuple[str, ...]`, rendered as a SCENARIO NOTES section, cleared on the draft after
  rendering. The Narrator needs no note channel — hook facts reach it through the
  recomputed evidence, leak-filtered per fact by `Fact.narrator` like every other
  fact — and a scenario-authored free-text note shown to the Narrator would be a
  canon-leak channel by construction.
- The Director's prompt gains an ACTIVE THREADS section (title, stage, note). The
  Narrator does not see threads.
- whispering-vault ships one thread (the vault seal) advanced by authored hooks
  (e.g. `entity_discovered: vault` → stage moves, note steers the Director).
- Fixtures: `save/*`, `turn/*`, director `prompts/*`, plan schemas (`advance-thread`).
  `SAVE_VERSION` bump. Gate: full suite; one eval case asserting a hook fired, its
  thread moved, and its facts landed in the narrator evidence — `run.py`'s `_turn` runs
  director + resolve only today and must append the hook pass in the same branch, or
  the case can never fire. `advance-thread` shares phase 2's bail-out: if it hurts the
  Director suite it becomes hooks-only and leaves the turn subset.

## Phase 4 — Rule VM, story proof (~4 days, eval-gated, budget +250 VM / −75 story)

**Vision §§9–11 and its phase 4: the architectural proof point.** Deviation from the
vision's order, stated: the vision generalizes content (its phase 3) before the VM. We
prove the VM on story first because story ships no content — the proof is cheaper, and
if the VM fails its gate, the content classes were never churned for nothing.

- Engines gain `actions.json`: per action — name, doc, params (a **closed** field-type
  set: entity-id, int with bounds, str with bounds (`Risk.stakes`), slug, dice-expr,
  enum, optional-of; each param carries a description; the loader builds the action
  model with `create_model` exactly as `_plan_model` builds the plan), outcome labels,
  and a `program`.
- A program is a bounded, straight-line instruction list — no loops, no recursion, no
  nesting beyond one conditional level; validated at load. Primitives (closed set,
  mapped to code that exists): `let` (param / sheet number / counter / arithmetic /
  table over an enum param / presence of an optional param as 0 or 1 — the last two are
  `Risk`'s difficulty penalty and help/hinder ±1), `require` (predicate → refusal
  string; becomes the `ValueError` the kernel's trial resolve already turns into a
  retry), `roll` (`state/dice.py`), `outcome` (threshold table over a total → label),
  `apply` (one op from the unified `Effect` union with computed arguments, optionally
  predicated on the outcome label and/or a predicate). Predicates (closed):
  `has-tag(actor, tag, include-carried)` — story's `_helps` walks carried items, and
  that pressure point is designed in, not discovered — `counter-full(actor, key)`
  (TAKEN OUT), and `is-player(actor)` (the growth mark on a player setback).
- The kernel executes programs where `ActionSpec.resolve` runs today; declarative and
  Python `ActionSpec`s coexist during migration (dnd5e stays Python this phase).
- Story's `Risk` reimplemented declaratively: approach bonus, help/hinder ±1, difficulty
  penalty table, 2d6 vs 7/10 → strong/mixed/setback, growth mark on player setback,
  TAKEN OUT and tag checks as `require`. Oracle: `resolve_risk`/`check_risk` kept until
  the VM produces identical facts and state on identical seeds, then deleted.
- The generated action model must emit the same JSON schema as today's `Risk` (fixture
  diff empty or trivially reviewed) — the model must not notice the migration.
- Gate: story suite ≥ phase-0/1 baseline. Bail-out: if Risk needs a loop, deeper
  nesting, or an open-ended primitive, the vision's §11 test failed at the first
  hurdle — stop, keep `ActionSpec` Python as the permanent engine seam, and strike VM
  phases from this file. That outcome is a finding, not a failure.

## Phase 5 — Ironsworn, an engine with no Python (~3 days, LOC excluded — content)

**Vision success criterion 4.** Held at gate resolution until phase 4 ships.

- New engine directory per the canonical layout: shim `rules.py` (id, badge,
  engine_dir, no-op advancement callables), `spec.json` (momentum via `Counter.minimum < 0` — already supported),
  `actions.json` (face-danger and 1–2 more moves), `director.md`, `advancement.md`,
  `examples.json`. No packs until it ships content.
- Playable content: `scenarios/whispering-vault/ironsworn.json` overlay and an
  ironsworn character overlay (`load_scenario`/`load_character` are engine-keyed).
- One permanent eval scenario. Acceptance: zero core changes beyond one `ENGINE_MODULES`
  line; zero engine Python beyond the shim. Any seam that forces more is fixed before
  merging.

## Phase 6 — Generic content facts (~4 days, budget −250)

**Vision §7 and its phase 3.** Held at gate resolution; specified fully when next. The
shape: `Record` gains stored generic data (`numbers`, `notes` become data instead of
per-class computed methods; a `facts` map carries what the VM reads — level, save
ability, damage and scaling tables). `spec.json` collections declare required facts per
collection (data schemas, not classes). Simple collections first (languages,
alignments, conditions are already bare `Record`); the heavy ones (spells, weapons,
monsters, levels) migrate together with the phase-7 mechanics that read them. The SRD
importer moves the interpretation to authoring time (vision §15) and the byte-identical
round-trip regression is re-established against the regenerated pack.

## Phase 7 — D&D on the VM (~2 weeks, eval-gated per mechanic, large −)

**Vision phase 5.** Held at gate resolution. The order is the vision's: checks, rests,
attacks, limited-use features, healing, spell attacks, spell saves, scaling,
concentration, advancement last. Per mechanic: oracle cases (state, action, seed → facts
+ state) against the Python resolver, delete only at parity, full suite at each merge.
Known hard spots, named now: `rest` wants a bounded refill builtin (an engine-neutral
`refill` op in the `Effect` union — not `recharge`, which already names the `Counter`
label field — spec-driven, outside the Director's turn subset); `_attack_terms`' weapon/stat-block
branching and finesse `max(str, dex)` will test the predicate set. A mechanic the VM
cannot express cleanly stays Python as a named exception in the shim — §11's explicit
escape, used sparingly and listed.

## Phase 8 — Scene Director / Rules Director split (~3 days, eval-gated)

**Vision its phase 6.** A `SceneDirective` role step (focus, pressure, relevant threads,
stakes) inserted before a narrowed Rules Director — the step machinery already takes an
inserted `(name, StepFn)` pair. Strictly A/B against the single director on plan
correctness, tokens, latency, retries; configuration keeps whichever wins, per scenario
if the data says so.

## Phase 9 — Memories + keepers (~4 days)

**Vision §6 and its phase 7.** `Memory` records (id, owner entity-or-world, text, tags,
source turn) on `GameState`; authored memories and deterministic retrieval (owner
present in scene → rendered section) first; then a Memorykeeper step proposing few-or-no
memories per turn under admission code, and a Threadkeeper for fuzzy thread transitions
restricted to legal moves. Both output-mode probed before trust.

## Phase 10 — Character creation workflows (~2 weeks)

**Vision §14 and its phase 8.** Declarative choice workflows (steps, legal options from
content, min/max, derived values), generic UI rendering, story first then 5e;
advancement migrates onto the same machinery where practical; the advisor becomes the
optional natural-language front end it already almost is. This is the plan's one
candidate speculative framework: it is not built before ironsworn advancement gives the
workflow engine its second user, and its build-ready spec must name what it deletes.

## Phases 11–12 — Authoring and media

**Vision §§16–18, its phases 9–10.** Scenario creator (premise → the same `world.json` +
overlays the loaders already validate), engine creator (rules source → the declarative
package of phase 5), typed `MediaRequest`s executed at the boundary. Agentic workflows
are allowed here — authoring is not the turn loop — and their output passes the exact
load path, validation, and evals hand-authored content does.

## Eval findings owed a cleanup pass

Not a phase: standing findings the phase-0 baseline exposed, none of them blocking. Each is a
measured weakness in a model-facing surface, so each costs a full re-run to close — batch them
into one pass rather than paying that cost five times.

- **The Director never uses advantage.** `advantage-attack` is 0/6 across two runs: the model
  reads a `prone`, explicitly-helpless target and still rolls `mode: "normal"`. `Attack.mode`
  says "when the fiction grants it" and nothing anywhere states 5e's actual grants. Either
  `dnd5e/director.md` teaches when advantage applies, or the case is measuring a rule the engine
  was never given — decide which before tuning.
- **Discipline is the weakest tag at 67%.** `story-check-both-directions` fails the negative
  direction: a dramatic-sounding but certain action still draws a risk roll. Same family as
  `single-action-discipline`. This is real signal, not a broken case — keep it.
- **`condition-lifted` sits at 67%** across both runs (the `poisoned` tag survives the turn that
  should end it). Pre-existing; it did not move in phase 1.
- **`monster-attack-on-player` fell 100% → 67%** on n=6, one of those a retry-exhaustion death
  rather than a wrong answer. Small-n backend lottery is the likely cause — re-run before
  spending any prompt work on it.
- **`why` is now optional on turn-time counter changes** (phase 1, sanctioned). Nothing measures
  whether the Director still writes reasons. Worth a probe if the trace panel starts reading
  poorly.

## Canonical engine layout (target)

During migration dnd5e keeps `actions.py`, `resolve.py`, `records.py` until phases 6–7
delete them; the file set below is the end state a new engine copies.

```
src/aidm/engines/<engine>/
  rules.py         # ~10-line shim: id, badge, engine_dir
  spec.json        # templates, recharge, collections + required content facts
  actions.json     # declarative actions: params, labels, program, doc
  director.md      # Rules Director instructions
  advancement.md
  examples.json    # worked plans, validated at load against the built TurnPlan
  packs/           # content only if the engine ships it: records + facts, no classes
```
