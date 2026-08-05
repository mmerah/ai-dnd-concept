# Eval baseline and the phase-3 gate

The refactor in `REFACTOR-LENIENT.md` trades type-level guarantees for interpretation quality. This
file is where that trade is measured. It holds two things: what the typed 5e engine scores today, and
the thresholds the lenient engine must clear in phase 3.

The thresholds below were written in phase 0, **before any code moved**, so the phase-3 decision is a
comparison against a pre-registered number rather than a judgement made under sunk cost.

## Running the suite

```bash
uv run python scripts/evals/run.py                       # every scenario, 3 runs each
uv run python scripts/evals/run.py --only combat         # one tag
uv run python scripts/evals/run.py --only save-for-half  # one scenario
uv run python scripts/evals/run.py --runs 5 --concurrency 8
```

It needs the network and a configured `director` role, so it never runs under pytest and never in CI.
Every invocation writes `results/<date>-<git-sha>.json` with per-run detail.

## What is measured

Only the **director stage** runs. Narrator, maintainer and creator are not under test: the question is
whether the rules-facing role reads the sheet and the content correctly, rolls before deciding, and
moves the ledger only through tools.

Each scenario builds a real game from the shipped `whispering-vault` scenario, applies its `setup`,
runs one live turn, and checks the committed draft plus the recorded facts. A run passes only if every
check holds. Expectations are **outcome-level** — ledger deltas, whether a roll happened, which pool
moved — never tool names or fact kinds, because those change across the migration.

Characters: `bram` (fighter, longsword + shortbow, Second Wind) and `elowen` (wizard) live in
`scripts/evals/characters/` and exist only for evals. Shipped `kael` carries no weapon and casts
nothing, so the typed `attack` tool refuses him every swing; he still covers the three cases that need
no mechanics, which keeps shipped content inside the suite.

## Coverage

14 of 20 scenarios are tagged `combat`, where arithmetic chains and so misses concentrate.

| Required coverage | Scenario |
|---|---|
| player weapon attack (proficiency + ability mod) | `melee-attack-basic`, `melee-damage-window` |
| monster attack on the player | `monster-attack-on-player` |
| attack against high AC, no damage on a miss | `high-ac-miss` |
| damage dice quoted from monster text | `monster-attack-on-player` |
| spell attack cantrip | `cantrip-spell-attack` |
| leveled spell spends the right slot | `leveled-spell-spends-slot` |
| upcast damage scaling | `upcast-damage-scaling` |
| save-for-half | `save-for-half` |
| a condition rider | `condition-rider` |
| casting on an empty slot (graceful refusal) | `empty-slot-refusal` |
| healing clamped at max HP | `healing-clamped-at-max` |
| dropping to 0 HP | `dropped-to-zero` |
| self-heal with level scaling | `self-heal-scaling` |
| short-rest recharge | `short-rest-recharge` |
| ranged weapon arithmetic | `ranged-damage-window` |
| ability check DC selection | `ability-check-dc` |
| long-rest recharge | `long-rest-recharge` |
| level-up offer | `level-up-offer` |
| condition bookkeeping | `condition-lifted` |
| a turn that must touch nothing | `no-mechanics-turn` |

Two items on the plan's required list are **not** covered, because the typed engine cannot express
them at all. Faking them would produce a baseline number with nothing behind it:

- **advantage via keep-highest** — the typed `attack` tool takes no advantage argument and
  `rolls.roll_attack` rolls one d20. Phase 1's `roll(mode="keep-highest")` is the first time this
  exists; add the scenario in that phase and treat its first measurement as the baseline.
- **concentration replacing a previous spell** — the typed engine holds no concentration state.
  Phase 3 makes it a `Sheet` note; add the scenario then.

Phase 2 added three `story` scenarios covering what Story stopped verifying in code once it moved
onto the Sheet — `story-risk-single-roll` (one roll per risk, rolled against the 7 band, growth
marked at most once), `story-taken-out-cannot-risk` (a taken-out actor is not rolled for at all),
and `story-no-risk-needed` (no roll where nothing is at stake). The fourth lost check, that a
claimed helpful tag actually exists on the sheet, is **not** measurable through the probes: they
read committed state and facts, and the `+1` lives inside the dice expression the director wrote.
It would need a probe that parses `dice_rolled.data["dice"]`; that is deliberately not built,
because a probe that reads the expression is a probe that would have to change again in phase 3.

The `story` tag is not part of the phase-3 gate below: the gate compares the same 5e suite before
and after, and Story only ever ran on the lenient substrate.

### One-sided checks

`empty-slot-refusal` and `no-mechanics-turn` also pass when the director does nothing at all. They
catch fabrication, not inaction. Read a 100% on either as "nothing was invented", not as "the turn was
handled well".

## Three numbers, not one

The first phase-0 runs made it clear that a single blended pass rate is the wrong instrument. Most
failures were not wrong arithmetic — they were `UnexpectedModelBehavior: Tool 'X' exceeded max retries
count of 3`, the director never producing a tool call the schema accepted. A gate built on the blended
number would mostly track this model's function-calling reliability, not the refactor. So every run is
recorded as one of three outcomes, and the suite reports all three:

- **completion** — the turn reached a director answer at all. A drop here means tool *shapes* or their
  argument schemas got harder to call, not that the rules were read wrong.
- **interpretation** — of the turns that completed, the share whose checks all held. This is the
  rules-reading signal, with crashes taken out. **It is the number the refactor is about.**
- **overall** — passed over all runs, completion failures included. The honest end-to-end figure, and
  the one a player would feel.

`retries` is recorded with each run because it changes completion directly. A comparison is only valid
between runs with the same `retries` and the same model.

## If you change the director model

The gate below is a comparison, so both sides must be measured on the same model. Raising the model
is a good idea and it is also a **window that closes**: phase 3 deletes the typed 5e engine, and
after that there is nothing left to re-baseline against. So if a stronger `director` model is ever
going to be the one the gate runs on, re-measure the 5e suite on it **before** phase 3 lands, record
it beside the baseline below as a second baseline, and say which one phase 3 is being judged against.
Changing the model and the engine in the same step measures neither.

## The phase-3 gate

Phase 3 deletes the typed 5e engine and moves attack bonuses, save DCs and upcast scaling into the
Director's own arithmetic. It merges **only** if, measured on this suite at `--runs 3` against the same
`director` model and the same `retries` as the baseline below:

1. **interpretation** is **within 12 points** of the recorded baseline interpretation rate, **and**
2. **completion** is **not more than 10 points below** the recorded baseline completion rate, **and**
3. `combat` pass rate is **within 12 points** of the recorded `combat` baseline, **and**
4. no *tag* that scored above 50% at baseline falls to 0%.

The 12-point band is not arbitrary: two runs of the identical suite against identical code are recorded
below, and the band is set wider than the drift observed between them. Do not narrow it without a third
repeat measurement to justify the narrower one.

Condition 4 is deliberately at **tag** level, not scenario level. At 3 runs a single scenario swings
100% → 33% on one bad turn, so a per-scenario floor would fire on noise; a tag aggregates 6–45 runs and
a tag falling to zero really does mean a capability stopped working.

There is no absolute floor among the conditions. The baseline is well under 80%, so an absolute
threshold would either be met trivially or block the refactor for a weakness it did not introduce. If
the absolute number matters, raise it by improving the director instructions or the model — measure
that separately, on the typed engine, before phase 3 rather than inside it.

Outside the thresholds: stop, diagnose (director instructions? tool shape? the model?), and proceed
only after writing a revision of this section that explains why the number moved and why the new one is
acceptable. Append the measured phase-3 rates below, next to the thresholds they are compared against —
never overwrite the baseline.

## Recorded rates

### Baseline — typed 5e engine

Commit `e174637`, 2026-08-04, `openai/gpt-oss-120b` via openrouter at `reasoning_effort=medium`,
`retries=3`, 21 scenarios × 3 runs = 63 turns per suite. The suite was run **twice against identical
code** so the gate's band could be set from measured drift rather than guessed. Files:
`results/2026-08-04-e174637.json` (A) and `results/2026-08-04-e174637-2.json` (B).

| Metric | A | B | **Baseline (mean)** | Drift |
|---|---|---|---|---|
| overall | 69.8% | 71.4% | **70.6%** | 1.6 pt |
| completion | 92.1% | 98.4% | **95.2%** | 6.3 pt |
| interpretation | 75.9% | 72.6% | **74.2%** | 3.3 pt |

| Tag | A | B | **Baseline (mean)** | Drift | Runs |
|---|---|---|---|---|---|
| combat | 68.9% | 66.7% | **67.8%** | 2.2 pt | 45 |
| spells | 61.1% | 50.0% | **55.6%** | 11.1 pt | 18 |
| conditions | 83.3% | 83.3% | **83.3%** | 0.0 pt | 6 |
| rest | 100% | 100% | **100%** | 0.0 pt | 6 |
| checks | 66.7% | 100% | **83.3%** | 33.3 pt | 6 |
| advancement | 0% | 0% | **0%** | 0.0 pt | 3 |

**The gate's numbers are `interpretation` 74.2%, `completion` 95.2%, and `combat` 67.8%.** Drift on
those three is 1.6–6.3 points across identical code, which is what the 12/10/12-point bands are sized
against. Tags with 6 or fewer runs drift up to 33 points and must not be used as a gate on their own —
condition 4 only asks that they not collapse to zero.

Two scenarios never passed in either run, and both are honest findings rather than harness faults:

- **`level-up-offer` 0%** — the director never calls `level_up`, even on a prompt written as an earned
  milestone. Phase 3 replaces that tool with `add_tag("advancement-ready")`; if the rate stays at 0
  the cause is the instructions, not the tool shape, and `advancement` is already at the floor so it
  cannot trip condition 4.
- **`save-for-half` 0%** — the director casts burning hands **twice** in one turn, spending two slots,
  even when the prompt says "and do nothing else this turn". Nothing in the typed engine or the
  instructions enforces one action per turn.

That second finding is the suite's most useful result: multi-action turns, not bad arithmetic, are the
largest single source of check failures today. `single-action-discipline` measures the tendency directly
on an open-ended prompt (100% in both runs, so the director *can* hold to one action), and the
`*-damage-window` scenarios name a single action in the prompt so they isolate arithmetic. When the
phase-1 director procedure is written, an explicit one-action-per-turn instruction is the cheapest
available win, and this suite will show whether it landed.

One scenario's bound was corrected **after** these runs: `ability-check-dc` accepted target numbers
8–20, which rejects the DC 5 "easy" tier that `roll_check` itself documents. It now accepts 5–20. The
change can only raise that scenario's rate, so the recorded 83.3% `checks` baseline is a lower bound.

### Phase 2 — Story on the substrate

Commit `654154e`, 2026-08-05, same model and `retries=3` as the baseline, 3 scenarios × 3 runs = 9
turns per suite, run twice: `results/2026-08-05-654154e-1.json` (A) and
`results/2026-08-05-654154e.json` (B). These do not feed the phase-3 gate — that gate compares the
same 5e suite before and after, and Story only ever ran on the lenient substrate.

| Metric | A | B |
|---|---|---|
| overall | 66.7% | 66.7% |
| completion | 100% | 100% |
| interpretation | 66.7% | 66.7% |

| Scenario | A | B |
|---|---|---|
| `story-risk-single-roll` | 100% | 100% |
| `story-no-risk-needed` | 66.7% | 66.7% |
| `story-taken-out-cannot-risk` | 33.3% | 33.3% |

Both runs agree scenario by scenario, so these are the engine's real rates at this wording.

**The risk procedure holds.** `story-risk-single-roll` passed 6 of 6: one contested roll, rolled
against 7, and growth marked at most once. That is the arithmetic chain Story's deleted `risk` tool
used to own, now carried by `director.md` plus `roll`.

**The taken-out ban does not hold.** 4 of 6 runs rolled for an actor already at maximum stress.
Typed Story refused this in code — `risk` raised `ModelRetry` when `taken_out` — and as prose it is
the one of the four lost checks that actually regressed. The instruction exists, but it is the last
clause of a bullet about stress rather than a precondition of the risk procedure. The cheap fix is
to hoist it into the `A RISK` section and re-measure; do not read a later improvement as noise, the
33.3% is reproducible.

`story-no-risk-needed` fails 1 run in 3 by changing the world on a pure-conversation prompt. It is a
one-sided check, so read the 66.7% as "one turn in three invented state", not as a score.

### Phase 3 — lenient engine on the Sheet

Not measured yet.
