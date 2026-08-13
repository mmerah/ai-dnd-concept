# Full redesign refactor: engine contract, roster, subsystems, packs

The approved plan for PLAN.md's redesign phase. Produced 2026-08-13 by exploration + design
agents, reconciled against a second AI's proposal whose claims were verified
in code. Explicitly overrides the "defer until the second engine" rule: the maintainer chose a
full redesign now, with 24XX implemented at the end as the architectural proof.

## Context

Production LOC must decrease or stay ~flat while making these much easier — new engines at
Loner3e fidelity (24XX, Cairn 2e), plug-and-play combat subsystems, NPC party advancement,
quest/clock systems, the AI scenario creator, and user-addable content packs. Roster rethink
authorized.

Baseline: 4,823 prod LOC (`wc -l`), 3,962 nonblank. Projected after refactor: **~flat**
(adversarial recompute 2026-08-13: 4,780–4,880), before the 24XX phase (a feature, counted
outside the refactor budget). Any decrease is a win; do not force deletions to hit a target.

Verified findings this plan fixes (beyond the exploration's resistance list):

- Core `src/aidm/turn/prompts/scene_director.md:7` carries Loner 3e's Dramatic/Quiet/Meanwhile
  scene-mood taxonomy (prose judgment derived from the d6 table at docs/LONER-3E.md:539-552) —
  a provenance leak into a cross-engine prompt; a future 24XX game would inherit Loner pacing
  vocabulary.
- `src/aidm/engines/loner3e/pack.py:52-63` raises unless exactly one loaded pack carries a
  twist table — a second user pack bricks the launcher at import.
- `Loner3eEngine.commit()` silently backfills a blank `Sheet()` for actors created mid-turn
  (`rules.py:56`) — wrong contract for a Cairn-class engine whose NPCs need real stats.
- `Advancement` (subject-less, player hardcoded in 5 files) and `Creation` are two
  incompatible capability shapes; combat would be a third.

Non-negotiable invariants (CLAUDE.md/AGENTS.md): model proposes, resolvers resolve;
draft/commit transactions; Narrator leak-proof by type (`VisibleScene`); one composition root;
refuse stale saves; deterministic no-network tests; golden fixtures are the behavior contract.

## Design summary

**Roster: 3 in-turn LLM roles (was 4).** Merge Scene Director + Rules Director into one
**Director**. Both already read the identical rendered canon (`render_director`,
`turn/prompts.py:13`, serves both via an optional arg); the directive is a lossy hop between
two instances of the same small model; the memories asymmetry (`prompts.py:20`) disappears.
`TurnPlanBase` gains `focus` (required), `pressure`, `stakes`, `speaker_id` — ordered before
the action so the model writes scene judgment first. Director keeps `ToolOutput` +
`plan_from_text` fallback + `ChannelSafeModel` (the small-model lessons). **Worldkeeper
survives** — removing it would fatten the Director schema against the hard-won gpt-oss lesson
(large schemas → zero effects); rejected with a live-probe gate on the merge instead. Narrator
unchanged. Engines contribute guidance via `director_instructions` only — roster stays
platform-owned, never engine-declared stage DAGs.

**Engine contract** (`src/aidm/engines/loader.py`): the 5 abstract methods survive, with one
split. Changes:

- `rules_type: ClassVar[type[BaseModel]]` — the typed authored-overlay payload (Loner3e:
  `Sheet`). Used at *load* for early field-level errors on overlays; `begin` keeps its
  raw-mapping signature and the engine validates as it already does
  (`Sheet.model_validate(authored or {})`) — no `BaseModel` downcasts in engine code.
- `commit` splits into **pure `validate(state)`** (refuses missing mechanics, never repairs)
  and **`seed(draft, entity, rng)`** — the engine gives an entity created during play its
  mechanics, called by the pipeline for **every `entity_created` fact** in the transaction:
  Worldkeeper creations *and* resolver-created entities (`GainImprovisedItem`), else a pure
  `validate` kills the turn on an item an engine tracks. Loner3e `seed` writes today's default
  `Sheet()` but sets `milestones.current` to the current resolved-thread count, so a joining
  NPC holds no instant advancement back-pay; a Cairn-class engine rolls real NPC stats there,
  traced as dice Facts.
- `effect_adapter` — a `TypeAdapter` over the engine's own effect union, built in `__init__`:
  the named surface that parses persisted `Hook.effects` JSON at load and at fire time.
  Threaded into `load_scenario` as a parameter exactly like `rules_type`, so content stays
  below engines in the layering.
- `__init__(extra_packs: Path | None)` — user packs from `Settings.packs_dir / engine.id`.
- `advancement` slot → `subsystems: tuple[Subsystem, ...]`.
- Combat: NOT a pipeline concern. Cairn rounds = engine `CombatState` in its mechanics
  payload; one app turn = one round; `pending_notes` carries round status (same channel as
  loner3e's twist). No in-turn loop seam — no documented engine needs one.
- `Branched`/`check_effects`/`check_action` stay; per-action outcome labels are computed
  engine-side in `check_plan` (`match plan.action`), no core change. Action-shape unions live
  in the engine's `plan_type`.
- `roll_pool(faces, reason, rng)` in `state/dice.py` (keep highest die); delete
  `RollMode`/advantage (advantage = `roll_pool([6,6])`). Serves 24XX skill dice + Cairn
  multi-attacker.

**Subsystem** (unified capability, replaces `Advancement`; `Creation` stays separate —
different lifecycle, writes content files not game transactions):

```python
class Offer(Frozen):        # subject_id: EntityId (NEW), prompt, text
class Subsystem(ABC):
    id: ClassVar[Slug]; proposal_type: ClassVar[type[ProposalBase]]
    # instructions from engine_dir/f"{id}.md"
    offers(state) -> tuple[Offer, ...]        # subject-aware; NPC advancement falls out
    resolve(draft, offer, proposal, rng) -> tuple[Fact, ...]   # rng: 24XX rolled credits
    violation(state, offer, proposal) -> str | None
```

Naming: `resolve`, not `apply` — mirrors `Engine.resolve_action` and avoids colliding with
`apply_effect`, the `Apply[E]` alias, and loner3e's `mechanics.apply`. `subject_id` follows
the repo's `*_id` convention. Rng contract: `violation` and the preview both trial with
`Random(0)`; the confirm-time `resolve` uses the session rng, and the preview panel labels
rolled values as illustrative — the previewed facts are promises, not the committed rolls.

Trace: `Advance` → generic `Applied(entry="subsystem", capability: Slug,
subject_id: EntityId)`; union stays closed at `{Turn, Applied}` forever — new subsystems
never edit core. Session: `Advancer` → `dict[Slug, Stage]` of advisors;
`offer/propose/preview/apply_proposal` take a capability slug, and `session.drafted` becomes
keyed by that slug (one draft per tab). UI: `advancement_panel` → generic `subsystem_panel`,
one tab per subsystem; Cairn's combat panel later = zero new UI code. Deferred to their first
consumer (YAGNI): `Subsystem.status()` (a tab-header string nothing needs yet) and the
`CreationStep` discriminator for `AllocationStep` — adding either when Cairn/24XX lands costs
the same edit then as now.

**Quests/clocks/hooks:** `Counter` moves to `state/base.py`. `Thread.clock: Counter | None`;
`AdvanceThread.tick: int` (clamped; a tick on a clockless thread **refuses** — a `ValueError`
the trial turns into a Director retry — never a silent no-op that fakes progress; clock
values land in the `thread_advanced` fact data so hooks can match a filled clock, and that
match is exact int equality: author `{"clock_current": 6, "clock_maximum": 6}`).
`Hook.once: bool = True` (repeating hooks for clocks); `Hook.effects` →
`tuple[JsonValue, ...]` validated at engine-bound load through `engine.effect_adapter` —
hooks can now reach engine effects (`counter-change`); core-only scenarios stay
engine-portable. `fire_hooks(draft, facts, apply)` takes the engine's apply and runs
**twice**: after resolve (as today) and again over the Worldkeeper report's facts — the
report's `thread_moves` land at pipeline step 6, *after* the existing hook pass, so a clock
ticked by the Worldkeeper could otherwise never fire its filled-clock hook. The second pass
is post-narration, which is consistent: a hook's `note` steers the *next* turn's Director
(loner3e's twist is one turn late by the same design). Matching stays subset-equality — no
expression language. `_effect_vocabulary`'s completeness raise moves to a test; adding an op
= union member + apply case + example + one golden regen.

**Content/creator-readiness:** `write_scenario` beside `write_character`
(`content/store.py:59-67`), ~12 LOC. `Hook.effects` as JsonValue also removes the embedded
`WorldEffect` union from `ScenarioWorld`'s JSON schema — the NativeOutput bloat the creator
was going to hit. The creator script then binds to: `ScenarioWorld`, `Engine.rules_type`, the
effect adapter, `write_scenario`, `begin_game`. The script itself stays the scenario-creator
phase.

**Packs:** `Settings.packs_dir` (layout `packs/<engine_id>/*.json`); user packs merge over
shipped by stem. Bad pack files → logged skip, never a launcher crash. Twist table resolved
per game: `Sheet.pack: ContentSlug = "srd"` written at creation → pack identity persists in
saves; `twist_table` singleton raise deleted. The resolver reads the **player's** `sheet.pack`
(NPC sheets are seeded with the default and must not select the table), and a resumed save
whose pack is no longer installed is **refused at load** like a stale save — never silently
switched to `srd`. No generic core pack format — engines keep their own strict `Pack` models;
shared helper is just `pack_paths(shipped, extra)`.

**Config:** `Providers` → `dict[str, ProviderConfig]` (new providers = .env only);
`_keys_present` rejects unknown role keys at startup; `packs_dir` added.

## Phases

Each phase: suite green, separately committable, goldens regenerated only in the phase that
moves them (`AIDM_GOLDEN_REGEN=1 uv run pytest`, read every diff line). **Every SAVE_VERSION
bump moves the save, state, and turn fixture families** — the version number is embedded in
all three — so each bumping phase regenerates those plus whatever its list adds; in the diff,
the `save_version` line is expected everywhere, and the rules below about "what may move"
exclude it. Phases 4 and 5 may share one bump/regen commit if convenient — that cuts one of
the regen cycles.

1. **Core folds + config** (no fixtures, no SAVE_VERSION, ≈ −40 LOC — the dup-detection sites
   are 2–3 lines each): `trial()` helper folding `state/plan.py:_trial` + `check_action`'s
   try + `advance.py:71-84 violation`; `require_unique()` folding the dup-detection loops
   (`authored.py:153` already is the shared shape — reuse it; `world.py:134-157`, `plan.py:82`,
   `base.py:94`); delete `apply.py:_require/_require_kind`, move model-facing messages onto
   `WorldState.require/require_kind`; fold `slug`/`text_slug` internals (`base.py:40-56`);
   config cleanup (`packs_dir` waits for phase 7).
2. **Roster merge** (SAVE_VERSION bump; regen also instructions/prompts/schemas): delete
   `SceneDirective` (`state/turn.py:40-75`), `scene_stage` (`roles.py:146-167`),
   `Stages.scene`; extend `TurnPlanBase`; `check_speaker` → Director validator; merge
   `scene_director.md` into `rules_director.md` **keeping only system-neutral guidance — the
   Dramatic/Quiet/Meanwhile mood taxonomy moves to `engines/loner3e/director.md`** (the
   provenance leak); `plan_from_text` (`roles.py:254-268`) answers a missing `focus` with
   `ModelRetry` naming the field — never invents scene judgment from prose; **edit
   `engines/loner3e/examples.json` for the new required `focus`** (it is validated against
   `plan_type` at engine construction — the engine is unbuildable until it's updated); single
   `render_director`; `TURN_STEPS` → 5 entries; update `core_test_support.py` stubs.
   **Gate: one live probe of the merged Director schema on gpt-oss-120b before regenerating
   goldens** (PLAN.md working rule 2). Fallback if the probe fails: keep two director calls
   sharing one render — the rest of the plan is unaffected.
3. **Subsystem unification + subject-aware advancement** (SAVE_VERSION bump):
   `Subsystem`/`Offer` in loader; `Applied` trace entry; generalize `session.py` (advisor map,
   capability-keyed methods, `drafted` keyed by slug), `roles.advisor` → `subsystem_stage`,
   `render_proposal` takes the subject entity (`prompts.py:91-95`), `subsystem_panel` + tabs
   (`ui/panels.py:107`, `ui/app.py`); loner3e `offers()` = one per `{player} ∪ party()` member
   with milestone surplus, seeded members back-paid (design summary). New test: NPC party
   member gets an offer and advances.
4. **Dice pools** (SAVE_VERSION bump): `roll_pool`; delete `RollMode`; port loner3e `_pair`
   (`resolve.py:197-203`) and probe engine if touched. Fact data: `mode` out, `kept` in —
   beyond the version line, the fixture diff must move only in rolls.
5. **Threads/clocks/hooks** (SAVE_VERSION bump; regen also worldkeeper + director schemas):
   Counter move; `Thread.clock`; `AdvanceThread.tick` (refuses clockless threads);
   `Hook.once`; `Hook.effects` JsonValue validated through `engine.effect_adapter` in
   `load_scenario` (the "hooks advance only authored threads" check moves to that
   engine-bound pass); `fire_hooks` takes apply and gains the second pass over the
   Worldkeeper report's facts; vocabulary raise → test. whispering-vault unchanged. Tests:
   repeating clock hook ticks twice; a Worldkeeper-ticked clock fires its hook; loner3e hook
   applies `counter-change`; tick on a clockless thread refuses.
6. **Typed overlays + validate/seed + write_scenario** (no persisted-byte change):
   `Engine.rules_type` + `effect_adapter`; `load_scenario`/`load_character` gain both as
   params (passed from `app/session.py:_open` — layering preserved); `commit` → pure
   `validate` + `seed` driven by `entity_created` facts (Worldkeeper creations and
   `GainImprovisedItem` alike; loner3e seed writes the identical default `Sheet()`, so no
   persisted bytes move); loner3e `begin` simplifies; `write_scenario` + store test; delete
   `Rules` alias. `test_engine_contract.py` **inverts**
   `test_a_created_entity_gains_engine_state_in_the_same_commit`
   (tests/core/test_engine_contract.py:66-93): bare `validate` on a state missing an actor's
   mechanics must now raise where `commit` used to repair.
7. **Packs** (SAVE_VERSION bump): `packs_dir`; `Runtime.engine` passes it; `pack_paths`;
   graceful skip; `Sheet.pack`, twist table read from the player's sheet; a save whose pack
   is missing is refused at load. Tests: bad pack skipped with launcher alive; save records
   pack; two twist-carrying packs coexist; missing-pack save refused.
8. **Docs + trim**: CLAUDE.md/AGENTS.md (3-role roster, Subsystem, packs dir, validate/seed
   contract wording), README roster section, docs/LONER-3E.md deviations if touched, PLAN.md
   superseded entries; comment trim; final LOC audit vs budget.
9. **24XX engine — the architectural proof** (feature, outside refactor LOC budget; ~400–600
   LOC package): implement per docs/24XX.md sketch — `Attempt` action,
   `skills: dict[str, Literal[8,10,12]]` (unlisted → d6), `roll_pool` resolution,
   `disaster/setback/success` labels, credits Counter, advancement ladder as a Subsystem,
   `rules_type` overlay, packs dir support, `ENGINE_MODULES` + one registration line.
   Acceptance: touches no file in `state/`, `turn/`, `app/`, `ui/` except the registration
   tuple. Anything awkward here is evidence a boundary from phases 1–7 is wrong — fix the
   boundary, not the engine.

## LOC budget (prod, refactor phases 1–8 only)

Baseline 4,823. The original −270 projection was recomputed adversarially (2026-08-13) and
found 2–3× optimistic: phase 1 is ≈ −40 (not −90), the roster merge nets ≈ −55 (deletes ≈95,
adds ≈40 of plan fields + validator + fallback handling), and phases 3/5/6/7 are net
**additions** of ≈ +100–150 (Offer/Applied/session map/tabs; clocks + hook validation + second
pass; validate/seed + write_scenario; packs plumbing). Realistic landing: **4,780–4,880
(~flat)** after phase 8's trim. The acceptance bar stays ≤ baseline; treat any decrease as a
win and never force deletions to hit an arithmetic target. Features gained at ~zero net LOC:
clocks, repeating hooks that reach engine effects, NPC advancement, typed overlays,
`write_scenario`, dice pools, user packs, pack-in-save — plus the 24XX engine (phase 9,
additive).

## Acceptance bar

- Refactor-only prod LOC ≤ baseline; new engine = one registration line, zero edits in
  state/turn/app/ui; new subsystem = zero new session/trace/UI branches; new pack = zero
  Python.
- `test_package_boundary.py` layering tables untouched; probe engine stays the isolation
  template.

## Verification

Per phase: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
`uv run basedpyright` (never set `UV_CACHE_DIR`). Golden regen in the same commit as its
cause, diff read line-by-line (outside the embedded `save_version` line: dice traces move
only in phase 4, save keys only in named phases). Phase 2 has the live-probe gate before
goldens. End-to-end: `uv run aidm`, play a
turn of whispering-vault/kael, confirm resume of a fresh save; after phase 9, create a 24XX
character and play a turn once content exists (or via a probe-style test if no 24XX scenario
ships yet).
