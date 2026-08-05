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

**Decided during phase 2: `openai/gpt-oss-120b` stays.** Four models were compared on the story
suite (table below) and it was the only one that failed in neither direction. The phase-3 gate below
therefore compares like with like and needs no second baseline.

If that decision is ever revisited, the gate is a comparison, so both sides must be measured on the
same model — and it is a **window that closes**: phase 3 deletes the typed 5e engine, and after that
there is nothing left to re-baseline against. Re-measure the 5e suite on the new model *before*
phase 3 lands, record it beside the baseline as a second baseline, and say which one phase 3 is
judged against. Changing the model and the engine in one step measures neither.

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

**The taken-out ban did not hold.** 4 of 6 runs rolled for an actor already at maximum stress.
Typed Story refused this in code — `risk` raised `ModelRetry` when `taken_out` — and as prose it is
the one of the four lost checks that regressed. The instruction existed, but as the last clause of
a bullet about stress rather than a precondition of the risk procedure.

### Phase 2, after the wording fix — and four models compared

Commit `87a6b17`: `director.md` now opens `A RISK` with the taken-out precondition, stated once.
Same suite, same `retries=3`, 2 runs per model. Files `results/2026-08-05-87a6b17-<model>-{1,2}.json`.

| Director model | overall | `no-risk-needed` | `risk-single-roll` | `taken-out-cannot-risk` |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 89% / 89% | 67% / 67% | 100% / 100% | **100% / 100%** |
| `anthropic/claude-sonnet-5` | 89% / 67% | 100% / 100% | 100% / 100% | 67% / 0% |
| `deepseek/deepseek-v4-flash-0731` | 67% / 78% | 100% / 100% | 0% / 33% | 100% / 100% |
| `ibm-granite/granite-4.1-8b` | 67% / 67% | 100% / 100% | **0% / 0%** | 100% / 100% |

**The wording was the cause, not the model.** On the same model as the 33.3% measurement,
`story-taken-out-cannot-risk` went to 100% in 6 of 6 runs and the suite from 66.7% to 88.9%. A
precondition has to be read *before* the procedure it guards, not after it. That is a general
lesson for every `director.md` written from here.

**Failure modes split by direction, and the strongest model is not the best one here.**
`claude-sonnet-5` fails only by *over-acting* — it rolls for a taken-out actor, the same eagerness
phase 0 recorded as multi-action turns — while `granite-4.1-8b` and `deepseek-v4-flash` fail only by
*under-acting*: `risk-single-roll` reports "nothing was rolled against a target number".
`gpt-oss-120b` passes both directions and is the model this project keeps.

**Read the small models' 67% carefully — it is mostly one-sidedness, not competence.** Two of the
three story scenarios (`no-risk-needed`, `taken-out-cannot-risk`) also pass when the Director does
nothing at all, so a model that never rolls scores 67% on this suite. Granite's 0%/0% on the only
scenario that requires an action is consistent with exactly that, and its two 100%s are not evidence
against it. The suite cannot currently tell "did not roll" from "rolled without `vs`" either,
because a run record stores its failures and not the turn's facts. Do not rank models on this suite
until that is fixed — the closing-out list in `REFACTOR-LENIENT.md` carries the item.

`story-no-risk-needed` fails 1 run in 3 under `gpt-oss-120b` by changing the world on a
pure-conversation prompt, and 0 in 6 under every other model. It is a one-sided check, so read the
66.7% as "one turn in three invented state", not as a score.

### Phase 3 — lenient engine on the Sheet

**Measured, and inside the thresholds.** The typed 5e engine is deleted and 5e runs on the `Sheet`.
The gate suite is:

```bash
uv run python scripts/evals/run.py --only dnd5e --runs 3
```

`--only` now also accepts an engine id, and `dnd5e` selects exactly the 21 scenarios the baseline
above was measured on. Without it the runner would mix in the three phase-2 `story` scenarios and
move `overall` and `interpretation` against a baseline that never contained them; `combat` would be
unaffected, but two of the three gate numbers would not compare like with like.

**The suite was frozen for the measurement.** Phase 0 owes two scenarios — advantage via
`keep-highest` and concentration replacing a spell — and phase 3 is the release that makes the
second expressible (a `Sheet` note). Adding either before the measurement would have changed the
denominator the gate is compared against, so both stay on the closing-out list and are written now
that the rates are recorded.

#### Measured — the gate passes

Commit `1b1f3b0`, 2026-08-05, `openai/gpt-oss-120b`, `retries=3`, the same 21 scenarios × 3 runs = 63
turns as the baseline, run twice: `results/2026-08-05-1b1f3b0-oss-120b-a.json` (A) and
`…-b.json` (B).

| Metric | A | B | **Phase 3 (mean)** | Baseline | Move | Threshold | |
|---|---|---|---|---|---|---|---|
| interpretation | 87.3% | 89.5% | **88.4%** | 74.2% | **+14.2** | within 12 | pass, above the band |
| completion | 100% | 90.5% | **95.2%** | 95.2% | **0.0** | ≥ 85.2% | pass |
| combat | 95.6% | 82.2% | **88.9%** | 67.8% | **+21.1** | within 12 | pass, above the band |
| overall | 87.3% | 81.0% | **84.1%** | 70.6% | +13.5 | — | |

| Tag | A | B | **Mean** | Baseline | Condition 4 |
|---|---|---|---|---|---|
| combat | 95.6% | 82.2% | **88.9%** | 67.8% | held |
| spells | 88.9% | 72.2% | **80.6%** | 55.6% | held |
| conditions | 83.3% | 50.0% | **66.7%** | 83.3% | held |
| rest | 66.7% | 100% | **83.3%** | 100% | held |
| checks | 83.3% | 100% | **91.7%** | 83.3% | held |
| advancement | 0% | 0% | **0%** | 0% | not covered — it was never above 50% |

**Conditions 2 and 4 are satisfied as written. Conditions 1 and 3 are satisfied in direction but not
literally**: "within 12 points" reads as a two-sided band, and interpretation and `combat` both left
it *upward*, by 14.2 and 21.1 points. The band exists to bound how far interpretation may degrade
when arithmetic moves from code into the Director, so a move in this direction is what the phase was
for and the gate passes. Recording it here so no later reader takes a symmetric reading of
"within 12" as having been quietly met.

Drift between A and B is 2.2 points on interpretation, 9.5 on completion, 13.4 on `combat` and up to
33 on the six-run tags — the same envelope the baseline's two identical-code runs showed, and the
reason no single run is read on its own. Every one of B's six lost turns was a tool-argument retry
(`spend`, `adjust`, `read_content`, `add_tag`), not bad arithmetic; A lost none.

**Phase-0 finding 1 landed.** `single-action-discipline` stays 100%, and `save-for-half` — 0% at
baseline because the director cast burning hands twice in one turn — is 100%/67% with the
one-action-per-turn rule opening `director.md`. `spells` rose 25 points, which is where the
double-casting used to be counted.

**Phase-0 finding 2 landed too, and reads both ways.** Flat tool arguments took A to 100%
completion, but B shows the shapes can still cost turns; mean completion is exactly the baseline's
95.2%, so the toolset is no harder to call than the typed one, not yet demonstrably easier.

**`level-up-offer` is 0% in 6 of 6 runs, and the pre-registered diagnosis now resolves.** Phase 0
wrote: "if the rate stays at 0 the cause is the instructions, not the tool shape". The tool shape
changed completely — a dedicated `level_up` tool became `add_tag("advancement-ready")` — and the rate
did not move, so the instruction is the cause. The likely fault is placement: `director.md` puts
ADVANCEMENT last, after everything a turn usually needs, which is the same mistake in kind as the
phase-2 taken-out ban being the last clause of a bullet. Fixing it means editing `director.md` and
re-measuring, which is a change to the thing under test, so it happens *after* this merge, not inside
it. `advancement` was 0% at baseline too, so it cannot trip condition 4 either way.

What changed under the suite, and where it can move the numbers:

- Attack bonuses, save DCs, damage scaling and the half-on-a-save rule are now the Director's
  arithmetic against `engines/dnd5e/director.md`, not code. This is what the gate exists to measure.
- `director.md` opens with the one-action-per-turn rule (phase-0 finding 1) and states every
  precondition before the procedure it guards (the phase-2 wording finding): the slot is spent
  before the spell resolves, a hit is read back before damage.
- The player's `armor-class` is authored content instead of a hard-coded 10 (phase-0 finding 3):
  Kael 12, Bram 12, Elowen 13, each 10 + their Dexterity modifier. `monster-attack-on-player` is the
  scenario this touches — the rat's +4 now meets AC 12, so its hit rate falls by 10 points and its
  `hp` window is unchanged.
- Ability scores are authored post-racial-bonus, so Bram is Strength 17 where the typed engine
  computed it. Every `*-damage-window` bound was checked against the same modifier, so no bound moved.
- One tool call replaced several: `roll`, `adjust`, `spend`, `recharge`, `add_tag`, `set_note`. Watch
  **completion** — phase-0 finding 2 predicted flat arguments would help it, and this is the first
  measurement that can show it.

#### Measured again, on the enriched pack — the gate holds, the content pass did not

Run C, `results/2026-08-05-1b1f3b0-oss-120b-c.json`, one run of the same 21 scenarios at
`retries=3`, on the tree carrying the full content projection.

| Metric | A (lean) | B (lean) | **C (enriched)** | Baseline | C vs baseline | Threshold |
|---|---|---|---|---|---|---|
| interpretation | 87.3% | 89.5% | **63.3%** | 74.2% | −10.9 | within 12: **pass** |
| completion | 100% | 90.5% | **95.2%** | 95.2% | 0.0 | ≥ 85.2%: **pass** |
| combat | 95.6% | 82.2% | **66.7%** | 67.8% | −1.1 | within 12: **pass** |
| overall | 87.3% | 81.0% | **60.3%** | 70.6% | — | — |

No tag that was above 50% at baseline reached 0, so condition 4 holds too. **The pre-registered gate
passes on every condition** — and reading that as vindication would be a mistake. The honest signal
is the comparison the gate cannot make: against A and B, on the same suite and model, interpretation
fell **25 points** while the observed A↔B drift on that metric was **2.2**. That is a regression the
content pass caused, not noise.

**What failed, and how.** The dominant failure string is `0 rolls against a target number` — the
Director ended the turn without rolling, on prompts that named the action ("I swing my longsword at
the rat"). It appears in `ability-check-dc`, `condition-rider`, `dropped-to-zero`,
`melee-attack-basic`, `melee-damage-window`, `monster-attack-on-player`, `ranged-damage-window` and
all three runs of `save-for-half`, which scored 0% by doing nothing at all. Three further turns died
on `Tool 'roll' exceeded max retries`. `rest` fell to 33% the same way: `recharge` was never called.
This is *under-acting*, the failure direction phase 2 recorded for `granite-4.1-8b` and
`deepseek-v4-flash` — now in `gpt-oss-120b`, whose context roughly tripled when every record's
mechanics moved into the per-turn render.

**The reading**: correct content in front of the Director is not the same as correct play, and past
some volume it costs. That is what `REFACTOR-LENIENT.md`'s new phase 3.5 exists to address — a
referee to carry completion, a reorganised context, and a writing pass over instructions and tool
descriptions.

**A flaw in this record, now fixed.** A, B and C are all stamped `1b1f3b0`: the runner recorded
`git rev-parse HEAD` while the tree under it was uncommitted and changed twice between runs. Two of
these three records were therefore indistinguishable after the fact, which is the one thing a
results file exists to prevent. `run.py::_commit` now appends a short hash of `git diff HEAD`, so an
uncommitted tree stamps as `1b1f3b0+0ac89c6`. The three records above are annotated by hand as
lean (A, B) and enriched (C) because they cannot be told apart from their contents.

#### Measured, then changed: a re-measurement is owed

The rates above were measured at `1b1f3b0`. Review passes **after** the measurement changed what
the Director reads, so those rates describe the measured commit, not the staged code:

- Backing records now render **beside their refs** in the scene render: a ref no longer copies
  notes onto the sheet; each `content` line shows the record's name, notes and tags. Spells
  carry structured notes projected from upstream data — level, save, attack, damage, heal, the
  full scaling ladder, area, range — plus concentration/ritual/component tags; weapons their
  damage dice, property tags and range numbers; armour discrete AC numbers and tags; monsters
  speeds, senses, save/skill bonuses, immunities, multiattack and limited-use lines. The damage
  dice, save DCs and upcast ladders the `combat` and `spells` scenarios test are in the render
  itself, with no `read_content` round-trip. Two of B's six lost turns were `read_content`
  retries, so completion can move as well as interpretation.
- `director.md`'s THE SHEET, AN ATTACK, A SPELL, A CHECK OR A SAVE and `set_number` sections
  teach the new lines (finesse, versatile, `level=cantrip`, `scaling`, armour arithmetic,
  monster save bonuses, passive perception).
- The pack was regenerated from the same pinned checkout (`3f5593e`), record count unchanged
  (2,201). Three importer fixes also feed the render: multi-AC monsters no longer truncate to
  the first entry, breath-variant dragons regained their breath lines, and damage-less save
  actions appear in `attacks`.

- The content-completion pass finished the projection: every structured upstream field is now
  projected or has a written reason in `PROGRESS.md`. Under this suite the visible changes are
  monsters (choice-shaped multiattacks on 33 monsters, one/two-handed damage variants on 16,
  the assassin's save-gated poison, spell/slot lists on 36 casters, lycanthrope/vampire forms,
  worn-armor names in AC lines, lore paragraphs), melee weapons **losing** their misleading
  `Range: 5 ft.` line and `range-normal` number, weapon damage gaining
  `damage-dice-count`/`damage-die` numbers and a type tag **beside** the `damage=1d8 slashing`
  note the Director already copied (the note was briefly removed; the `*-damage-window` scenarios
  run on exactly that path, so it is back and `director.md` points at it), equipment gaining
  `cost-*`/`quantity`/vehicle `speed`/`capacity-lb` numbers, and spells gaining a `classes` note.
  The scene render and `read_content` both carry more per record than at `1b1f3b0`.
- **`director.md` changed**: the ADVANCEMENT section (last in the file, `level-up-offer` 0% in
  6 of 6 runs) moved into the opening rules block, wording near-identical — the phase-2
  hoist-the-buried-rule lesson applied to the one rule the Director never reached. The next run
  measures this fix; `level-up-offer` is the scenario to read first.

`monster-attack-on-player` is the scenario most exposed to the render changes: the rat's line
carries its attack, size and challenge rating inline. Re-run `uv run python
scripts/evals/run.py --only dnd5e --runs 3` (twice, as above) and append the rates here before
merge.
