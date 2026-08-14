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

## Next

- PLAN.md Phase 1 steps 4-6: 24XX ally help, Cairn's `fate`/`reaction` tables, Cairn's widened
  attack. None of them change the wire contract — that is the point of each.
- PLAN.md Phase 2: the scenario creator.
- Close the Cairn 2e, Loner 3e, 24XX fidelity deviations, per their docs' "Deviations in this
  repo" sections.
