# Baseline — tool-calling director

commit: ba6455d   date: 2026-08-05   model: openai/gpt-oss-120b   retries: 3
harness: `uv run python scripts/evals/run.py` (23 scenarios × 3 runs = 69 turns per suite)

Three suites were run back to back on one commit. The pooled column is all 207 turns together
and is the number to compare against; the per-run columns are what one suite of 69 turns looks
like, and they are the reason a single suite cannot settle anything.

| metric | pooled (n=207) | run 1 | run 2 | run 3 | spread |
|---|---|---|---|---|---|
| overall | 33% | 45% | 17% | 38% | 28 |
| completion | 89% | 81% | 99% | 88% | 17 |
| interpretation | 37% | 55% | 18% | 43% | 38 |
| mean duration/turn (s) | 15.6 | 16.8 | 12.2 | 17.7 | 5.5 |

| tag | pooled | n | run 1 | run 2 | run 3 | spread |
|---|---|---|---|---|---|---|
| checks | 67% | 18 | 100% | 50% | 50% | 50 |
| combat | 27% | 135 | 40% | 7% | 36% | 33 |
| conditions | 17% | 18 | 50% | 0% | 0% | 50 |
| rest | 6% | 18 | 0% | 0% | 17% | 17 |
| spells | 30% | 54 | 33% | 17% | 39% | 22 |
| story | 63% | 27 | 56% | 67% | 67% | 11 |

## Worst cases

Mean of the three runs, with the per-run rates and the reason that dominates.

| case | mean | per run | dominant failure |
|---|---|---|---|
| long-rest-recharge | 0% | 0 / 0 / 0 | nothing rolled; `slot-N` and `second-wind` deltas 0 — `recharge` never called |
| cantrip-spell-attack | 11% | 33 / 0 / 0 | no roll against a target number |
| condition-rider | 11% | 33 / 0 / 0 | no roll; target tag never added |
| monster-attack-on-player | 11% | 0 / 0 / 33 | no roll; player `hp` delta 0 |
| short-rest-recharge | 11% | 0 / 0 / 33 | `second-wind` delta 0 — spend never recorded |
| upcast-damage-scaling | 11% | 0 / 0 / 33 | `slot-2` delta 0; damage not scaled |

Failure reasons across all 207 turns, by count: 60 "0 rolls against a target number", 36
"nothing was rolled against a target number", 11 `second-wind` delta 0, 11 `slot-1` delta 0, 11
"rolls … was 0, wanted 1", 8 `slot-2` delta 0, 8 `hp` delta 0, 7 `poisoned` still present. 22 of
the 207 turns died outright, all `UnexpectedModelBehavior` (retries exhausted on tool arguments).

The three cases at 100% in every run — `empty-slot-refusal`, `no-mechanics-turn`,
`story-taken-out-cannot-risk` — are the ones whose correct answer is to change nothing. They pass
whether or not the model calls a tool, so they carry no signal about the procedure.

## Drift between runs

Max per-tag delta is **50 points** (`checks`, `conditions`); overall moved 28 points and
interpretation 38 points on an unchanged commit. Deltas below those are noise at 3 runs per case.

Run 2 is the extreme: completion rose to 99% while nearly every case that needs a roll failed with
"nothing was rolled", and the three no-op cases passed — the director answered without calling any
mutating tool at all. Its mean duration also dropped to 12.2s. A different OpenRouter backend for
`gpt-oss-120b` would explain that, but run 3 has run 1's duration and still fails mostly the same
way, so the cause is unconfirmed. Treat it as variance in tool use, not a known routing bug.

## Consequence for the Phase 6 gate

PLAN.md asks for `interpretation` ≥ baseline + 15 points with no tag below baseline − drift. At
this drift a 15-point move on one 69-turn suite is unreadable. Compare the redesign against the
pooled 37%, over the same 207-turn budget (three suites, or `--runs 9`), and read per-tag numbers
only where n is large — `combat` (135) and `spells` (54). `checks`, `conditions`, and `rest` have
18 turns each; one case flipping moves them 33 points.
