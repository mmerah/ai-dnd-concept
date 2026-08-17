# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1, steps 1-3 — one small Director contract (2026-08-14)

- **Step 1, the wire contract.** `state/plan.py` is now `RuleCall(name, args)`,
  `DirectorBeat(roll, effects)` and `DirectorPlan(+focus, speaker_id)` — one shape for every
  engine. `plan_type`/`beat_type` left `Engine`; both Director stages type against
  `DirectorPlan`/`DirectorBeat`. Deleted: the `Action` ABC (`engines/actions.py`), `SheetEngine`'s
  action type parameter, `_resolver`/`_typed`, every per-engine `TurnPlan`/`TurnBeat`, the three
  byte-identical effect unions, and Loner's `TwistTables` protocol (the engine now hands the twist
  table to the resolver).
- **The wire schema fell from ~15-17KB per engine to 2.2KB**, one shared pair of fixtures
  (`schemas/turn_plan.json`, `schemas/turn_beat.json`) instead of six.
- **Actions dispatch by call name, not by an `act` discriminator.** `Engine.actions` is
  `Mapping[Slug, type[Frozen]]`; the name on the wire *is* the discriminator, so nothing smuggled
  into `args` can rename a roll and the `act` field is gone from all five action models. Effects
  keep `op` — authored hooks still write op-shaped JSON — and translate as
  `EFFECTS.validate_python({**args, "op": name})`, discriminator spread last.
- **A union nested undiscriminated reports against every branch it tried.** `EngineEffect` was
  `Annotated[WorldOp | CounterChange, discriminator="op"]`; a faulty `relation-change` retried as
  `relation-change.Reveal.op: Input should be 'reveal'`. Nesting the already-discriminated
  `WorldEffect` instead names the field. The translation error *is* the Director's retry now, so
  check it whenever the union moves.
- **Step 2, the prompt teaches what the schema dropped.** `engines/vocabulary.py` renders both
  cards from the models themselves: docstring line, per-arg description, Literal choices, list
  shape and cap, required/default. `EFFECT_CALLS` is *derived* from the `EngineEffect` union, so
  an effect the union takes cannot be missing from the card. Per-engine `director.md` lost its
  duplicated arg lists; instructions grew ~5KB, the payload that degrades small models shrank.
- The shared `engines/examples.json` is **deleted** (PLAN said reshape it): the card describes
  every effect and every engine's worked plans already show the `{"name", "args"}` envelope. Each
  engine's own `examples.json` stays, in call shape, translated at load — an example naming a call
  the engine has not fails the build. `translate` is a free function in `vocabulary.py`, not a
  port method: nothing about it is per-engine beyond the `actions` mapping it is handed.
- **Step 3, settle vs continue.** `Resolution.flow` became
  `followup: Literal["none","settle","continue"]`; a roll-less resolution returns `"none"`. The
  loop: another full Director beat while the last said `"continue"` and rolled beats < `max_beats`;
  one final **settle** beat when it said `"settle"` or when the cap cut a `"continue"` short; never
  after `"none"`. The settle stage (`prompts/settle.md`) refuses a beat that rolls again —
  pipeline-side, not a new engine method. Closes LONER-3E deviation 6: a twist fired on the last
  beat now reaches the Director the same turn.
- `SAVE_VERSION` 62 -> 63; the `save`/`state`/`turn` fixture families and every `instructions`
  fixture were regenerated in this change.
- **Not done: the live probe** (working rule 2). One real turn per engine on the shrunk contract,
  and one try of `NativeOutput`. `ToolOutput` is kept until a probe says otherwise; needs
  network.

### Phase 1, steps 4-6 — the enrichment proofs (2026-08-17)

Three engine enrichments, **not one byte of wire contract changed** — that was the point of each.
Every one is a new arg or a widened arg on an existing call, taught by the generated vocabulary
card, with no schema growth the Director pays for.

- **Step 4, 24XX ally help** (closes 24XX deviation 1). `Attempt` grew `helper_id` +
  `helper_skill`: the ally rolls their own skill die into the pool. One help die still, as
  `pool_faces` insists — the helper's die when `helper_id` is set, the flat d6 when only `helped`
  names a circumstance, and **naming both is refused at the schema** by a `model_validator`, since
  the SRD leaves stacking to the table. A helper must be here, not the actor, and carry the named
  skill on *their own* sheet; `_require_skill` is shared by actor and helper so both refusals read
  the same. Risk-sharing stays fiction (the engine tracks no harm).
- **Step 5, Cairn's rolled tables** (narrows CAIRN-2E deviation 2 to morale and panic). Two new
  rolls, one union branch and one vocabulary line each: `fate` (one d6 on a `question`, 4+
  favorable) and `reaction` (2d6 on an NPC's `actor_id` into the SRD's five rows, hostile through
  helpful, `reaction_for` resolver-side like `SCARS`). Each writes a fact plus a pending note that
  steers the next Director call — so the answer reaches the same turn's next beat. Morale and panic
  stay willpower-save rulings: the engine counts no casualties and knows no group size.
- **Step 6, Cairn's attack widened** (shrinks CAIRN-2E deviation 3 to detachments alone).
  `weapon_id` -> `weapon_ids` (dual wield: every named weapon's die in the pool, keep highest;
  empty is still the unarmed d4) and `target_id` -> `target_ids` (blast: one roll of the shared
  pool per target, each through the existing `_damage` path). `Resolution.outcome` is the worst
  per-target outcome by `SEVERITY`, **the player's own whenever they are a target**, and
  `_followup` now reads the grave-fact scan against `PLAYER_ID` instead of taking a single target.
  Owned drift: an impaired multi-die pool is several d4s keep-highest, slightly kinder than the
  SRD's flat d4 — inherited from `joined_by`.
- `SAVE_VERSION` 63 -> 64: the 24XX `attempt_resolved` fact gained a `helper` key, so trace bytes
  moved. Regenerated: both engines' `instructions`, and the `save`/`state`/`turn` families.
- **Still not done: the live probe** (working rule 2), unchanged from steps 1-3 — needs network.
  `ToolOutput` stays until a probe says otherwise.

### Fidelity pass — deviations closed, not reworded (2026-08-17)

The deviation lists went **32 entries -> 20** across the three engine docs. What each engine
diverges on is now the honest short list; the rest is implemented as printed.

- **Cairn `stowed` armor** closes the carried-is-worn deviation: `armor_of` skips an item traited
  `stowed`, so a shield counts only while worn or held. The Director stows and dons by
  `trait-change`.
- **Cairn detachments** needed no new state once blast landed: one actor with one sheet, `impaired`
  striking it, `enhanced` plus several `target_ids` striking back, rout on critical damage,
  destroyed at 0 strength — taught in `director.md`, entry deleted. Its "impaired multi-d4" drift
  note went with it: the SRD's impaired die and its keep-highest rule compose to exactly what we
  roll, so there was never a drift to own.
- **Cairn `pass-time`** closes the scar-timing and deprivation-tick deviations. `Mechanics.day` is
  the running tally; `Sheet.mending` records the five SRD rows whose payout defers ("once mended",
  "when you recover", "after recovery"), paid out through the existing `_recover` when the Director
  names the healed actor in `mended_ids`. Deprivation adds one Fatigue per full day, resolver-side
  through `adjust` + `check_load`, so the tick obeys the ten-slot law.
- **The time mechanism is engine-level, deliberately.** Only Cairn has a mechanical consumer of
  elapsed days: 24XX's harm is fiction by its own deviation and Loner's Luck resets per conflict,
  not per day. A core field with one reader is the abstraction the port rule forbids, and the seat
  a second engine would need already exists — its own `actions` mapping and `resolve_roll` rng. It
  is a **roll, not an effect**: deferred scar payouts roll dice and `apply`/hook paths carry no
  `Random`.
- **Naming stays clear of `Thread.clock`** (progress clocks, ticked by `advance-thread`): the call
  is `pass-time`, the tally `day`, the ledger `mending`. `director.md` states the distinction once.
- **Eight entries were reclassified, not implemented** — each rule is either implemented as printed
  or a ruling the SRD explicitly leaves to the table (24XX help stacking "your call!", the bad-luck
  test, "*may* hinder at times", "invent or roll"; Cairn's abstract inventory; Loner's mood roll
  "if you're unsure", the Adventure Maker, Appendix A). They live as one preamble carve-out per doc
  so nothing diverges silently.
- What still blocks the remaining 20: a calendar beyond day counting, group size and casualty
  counting (Cairn morale), content elided from the extractions (Cairn Bonds' 16 rows, 19 background
  pages), creation-form redesigns, and the app's own architecture. Bond rows 10 and 15 are now
  expressible by a later pack step without reopening the time design.
- `SAVE_VERSION` 64 -> 65 (`Sheet.mending`, `Mechanics.day`); `save`/`state`/`turn` and
  `instructions/cairn2e` regenerated. The `turn_plan`/`turn_beat` schemas did not move — every new
  call rides the generic `RuleCall`.

### Drastic simplification — Cairn 2e deleted, wire contract cut to the bone (2026-08-17)

Deliberate reversal of scope, not a loss: Cairn's procedural mechanics wrapped the codebase to
their image the way 5e's once did. Four commits (`848d371`, `c9bbbe5`, `147c45f`, plus
stragglers), every one green on all four suites.

- **Cairn 2e deleted entirely**: the package (~1,600 lines, more than Loner + 24XX combined),
  `tests/cairn2e/`, `docs/CAIRN-2E.md`, its fixtures, the whispering-vault overlay, Kael's sheet.
  With it went the only overrides of `SheetEngine.apply`/`check_overlay` and the whole time
  machinery (`day`, `mending`, `pass-time`) — and most of the remaining deviation ledger.
- **`DirectorPlan` deleted**; `DirectorBeat(roll, effects)` is the one wire type for director,
  beat, and settle stages. `focus` and `speaker_id` gone: the narrator composes from the player's
  prompt, the scene, and the evidence — `check_speaker`, `voice()`, and the SPEAKER prompt
  section went with them. `schemas/turn_plan.json` deleted (was byte-identical to `turn_beat`).
- **`why` deleted from all four effects** (`trait-change`, `relation-change`, `advance-thread`,
  `counter-change`): the mechanical trace stands alone as narrator evidence. `explained()` died;
  `explained_fact` stays for the advancement subsystems' `proposal.why`. `TraitChange.text`
  deliberately kept — it is state, not narration.
- **`counter-change` investigated and kept**: Loner's luck reset/hazards and 24XX's credits are
  fiction-driven ledger moves no roll owns; cutting it would force worse machinery.
- `SAVE_VERSION` 65 → 67 (one bump per byte-moving commit); `save`/`state`/`turn`/`prompts`/
  `instructions` regenerated each time, diffs read. `tests/core/test_golden_state.py` carries its
  own `FIXTURE_SAVE_VERSION` pin — bump both or the suite catches you.

### Seat deletions — one Director stage, one Engine class, one effect shape (2026-08-17)

The live probe passed (maintainer, real turns per engine), which unlocked `NativeOutput` and the
deletion of every abstraction seat holding exactly one implementation. One commit, `SAVE_VERSION`
67 → 68.

- **One Director stage.** `beat_stage`/`settle_stage` deleted; the beat/settle prefaces moved from
  instructions into the rendered prompt (an `ASKED AGAIN` section), and the settle no-roll rule is
  a `PlanContext.settle` flag on the one validator. Instructions are now byte-identical across
  every Director call of a turn — provider prompt caching applies to the ~15.7KB that matters —
  and the per-engine `beat`/`settle` instruction fixtures (~32KB) are gone.
- **`NativeOutput` everywhere.** The Director left `ToolOutput`; `ChannelSafeModel` and
  `Authored._decode_stringified_fields` (both backend shims for tool-call quirks) deleted.
- **`Engine` is one concrete class.** The abstract `Engine`/`SheetEngine` split had one subclass;
  merged into `Engine[S: SheetBase]` in `engines/loader.py`, `sheet_engine.py` deleted.
  `engine_text` moved to `content/store.py` to keep the import graph acyclic.
- **`Subsystem` ABC folded into `ThreadAdvancement`.** `engine.subsystems: tuple` became
  `advancement: ThreadAdvancement | None`; the session's capability-dict and the UI's tabs loop
  went with it. The `Applied` trace entry dropped its constant `capability` field and its `entry`
  literal became `"advancement"` — free inside this same save-version bump. A second out-of-band
  capability re-earns the seat; combat never will — it is the turn loop.
- **Hooks author the wire shape.** `Hook.effects` entries are `{"name", "args"}` like every
  Director effect — one format for authors and for the Phase 2 creator agent. `translate_effect`
  is the one gate both paths share; whispering-vault converted.
- **Small deletions:** `roll_sum`, the `Pools` protocol (`move_pool` types against `SheetBase`),
  `spend`'s dead `why` parameter.
- Fixture movement was exactly the predicted set each step: save-version bytes, the `ASKED AGAIN`
  section, deleted beat/settle instructions, hook envelopes in `state`/`save`. Nothing else moved.

## Next

- PLAN.md Phase 2: the scenario creator.
- Close the Loner 3e and 24XX fidelity deviations, per their docs' "Deviations in this repo"
  sections.
