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

---

# Redesign — structured-plan director

commit: b7f65bc   date: 2026-08-05   model: openai/gpt-oss-120b   retries: 3
Same harness, scenarios, probes, and 207-turn budget (three suites) as the baseline.

| metric | pooled (n=207) | run 1 | run 2 | run 3 | spread | baseline pooled | delta |
|---|---|---|---|---|---|---|---|
| overall | 86% | 88% | 84% | 86% | 4 | 33% | +53 |
| completion | 100% | 99% | 100% | 100% | 1 | 89% | +11 |
| interpretation | 86% | 90% | 84% | 86% | 6 | 37% | +49 |
| mean duration/turn (s) | 8.9 | 11.0 | 8.4 | 7.1 | 3.9 | 15.6 | −6.7 |

| tag | pooled | n | run 1 | run 2 | run 3 | baseline pooled | delta |
|---|---|---|---|---|---|---|---|
| checks | 100% | 18 | 100% | 100% | 100% | 67% | +33 |
| combat | 89% | 135 | 91% | 87% | 89% | 27% | +62 |
| conditions | 0% | 18 | 0% | 0% | 0% | 17% | −17 |
| rest | 72% | 18 | 83% | 67% | 67% | 6% | +66 |
| spells | 91% | 54 | 94% | 89% | 89% | 30% | +61 |
| story | 100% | 27 | 100% | 100% | 100% | 63% | +37 |

## Worst cases

| case | mean of 9 | dominant failure |
|---|---|---|
| condition-lifted | 0% | `poisoned` never removed — the plan writes no `remove-tag` effect |
| condition-rider | 0% | the attack rolls, but no branch adds `prone` on success |
| long-rest-recharge | 44% | `slot-1` not refilled — the rest never resolved as a `rest` action |
| monster-attack-on-player | 44% | the model attacked the rat instead: rat hp −5, wanted 0 |
| healing-clamped-at-max | 89% | one run left hp delta 0 |

## Verdict

Against the Phase 6 criteria: **interpretation 86% clears baseline + 15 (52%) by 34 points**, and
`spells` (91%, n=54) clears its 0.8 floor. `rest` lands at 72% — up 66 points from 6% but short of
its 0.8 floor. Mean duration 8.9s misses "half of baseline" (7.8s) by 1.1s, with per-run means of
11.0/8.4/7.1 — provider latency, not turn structure, decides it, and run 3 is under the bar. No tag
sits below baseline − drift.

Two structural notes beyond the criteria. First, the drift that made the baseline unreadable is
gone: overall moved 4 points across three suites where the baseline moved 28, so a single suite is
now meaningful. Second, completion is 100% — the retries-exhausted deaths (22 of 207 baseline
turns) disappeared with the tool loop.

The one flat failure is `conditions` (0/18, both cases, every run, same two reasons): the model
never writes `add-tag`/`remove-tag` into branches or effects. That is one prompt section — the
effect vocabulary in `director.md`/`examples.json` — not a resolver. `rest`'s misses and
`monster-attack-on-player` are the same shape: action selection, taught in the same file. Iterate
there; the architecture stands.

---

# Phase 8 — residual failures diagnosed

date: 2026-08-05   model: openai/gpt-oss-120b   retries: 3   over the staged tree on 3d7c936

Method: the harness now records what Phase 6 could not see — `RunRecord` carries the Director's
dumped plan, every validator refusal it burned, and each fact's trace. The four signatures were
re-run at `--runs 9` and the plans read before anything was touched. Scenarios and probes are
unchanged.

## What the captured plans showed

| signature | cause found in the plans | fix (owning file) | case, before → after |
|---|---|---|---|
| conditions 0/18 | branches always `[]`: with `NativeOutput`, gpt-oss-120b **never once emitted an `Effect` object** — 60+ plans, zero effects/branches, unmoved by prompt fixes, `reasoning_effort=high`, `max_tokens=8192` | director output mode → `ToolOutput` (`pipeline.py`), plus condition teaching below | 0% → 70% (n=10); 67% in the final suite |
| monster-attack 44% | 5/9 plans had the player counter-attack the rat; nothing said the turn's actor can be an NPC | `CORE_DIRECTOR`: the actor is whoever the fiction puts on the acting side | 22% → 100% (n=9) |
| rest 72% | misses resolved the prompt's first clause ("I barricade the door…") as an `improvise`; the sleep never ran | `director.md` rest bullet + `Rest` docstring: the rest is the action, preparations are intent | 33% → 67% (n=9); 100% in the final suite |
| healing 89% | the one miss in nine is a degenerate generation (null action, mojibake tone) — same family as the `Invalid JSON: trailing characters` retries: gpt-oss channel bleed, provider-side | none owed | 89%, unchanged |

Condition teaching also landed where it belongs even though prompts alone measured zero effect on
this model: `remove-tag` next to `add-tag` in `director.md`, the `check` example lifting
`poisoned`, and the branches/`Check` schema descriptions saying a roll settles only what its
branches write.

Exonerated by the same capture: `check_plan` (its only refusals steered retries correctly), the
resolver, and the schema itself — a different model through the identical pipeline wrote the
taught branches on the first try (one diagnostic probe only). Two side findings for the record:
Anthropic models 400 on the plan schema through OpenRouter (`ge`/`le` bounds survive because
`OpenAIChatModel`'s transformer runs for every provider), and `reasoning_effort=high` starves the
2048-token budget before any output.

## One suite, before and after the output-mode switch (n=69 each)

| metric | NativeOutput + prompt fixes | ToolOutput | Phase 6 pooled |
|---|---|---|---|
| overall | 87% | 86% | 86% |
| completion | 100% | 88% | 100% |
| interpretation | 87% | **97%** | 86% |
| mean duration/turn (s) | 16.9 (contended) | **3.1** | 8.9 |
| conditions | 0% | **67%** | 0% |
| rest | 67% | **100%** | 72% |
| checks / combat / spells / story | 100 / 91 / 83 / 100 | 83 / 87 / 72 / 78 | 100 / 89 / 91 / 100 |

## Verdict

The architecture and the prompts were never the conditions problem: the model's output mode was.
Through `response_format` gpt-oss-120b answers with the minimal legal plan; through a tool call it
uses the whole effect vocabulary. The switch buys interpretation (97%) and duration (3.1s — under
the Phase 6 criterion's 7.8s bar at last), and moves every dead tag.

The cost is completion: all 8 deaths (12%) are one crash — the ROADMAP-documented Groq
`finish_reason: "error"` under `tool_choice: required`, which now surfaces as an unparsable
response. That is provider routing, not turn structure; excluding the offending provider via
OpenRouter routing preferences is the follow-up. Per-tag dips against Phase 6 (`spells` 72%,
`story` 78%) are those same deaths landing unevenly across 3-run cases, not new quality misses:
interpretation on completed turns is the highest measured on this pipeline.

The `NativeOutput` roles stay: a live maintainer probe returned both growth requests 3/3 — the
suppression is specific to the Director's 21-`$defs` schema, not to native output as such.

---

# Simplification batch — one naming convention, fewer ops, core effect examples

date: 2026-08-06   model: openai/gpt-oss-120b   retries: 3   Groq excluded via OpenRouter
Same harness and 207-turn budget (three suites: 90% / 94% / 94%).

What changed: every action names its actor `actor_id` and every effect its target `entity_id`;
`take-item`/`drop-item`/`give-item` merged into `move-item` (12 → 10 ops); `AddTag` lost `name`
(derived from the slug); `Rest.label` became a `Literal`; and a core `examples.json` now shows
every effect op once in every engine's director instructions, with a load-time check that the
file and the union agree. Save version 28.

| metric | pooled (n=207) | Phase 8 ToolOutput suite | Phase 6 pooled |
|---|---|---|---|
| overall | 93% | 86% | 86% |
| completion | 100% | 88% | 100% |
| mean duration/turn (s) | 2.5 | 3.1 | 8.9 |

Tags pooled: checks 94%, combat 96%, spells 98%, rest 89%, story 89%, conditions 72%. The
Phase 8 completion deaths were provider routing; with Groq excluded none recurred.

Two residuals. `conditions` (72%) keeps its two lifetime signatures — `poisoned` not removed
3/9, the `prone` rider not added 2/9 — now sampling variance on one branch write, not the old
structural zero. New and attributable: the no-op cases regressed (`story-no-risk-needed` 67% in
every suite, `no-mechanics-turn` once) — the cookbook invites writing an effect on uneventful
turns. Countered in the same commit by one header sentence: an empty `effects` with no branches
is a normal plan. Unmeasured at commit time; check it in the next full run.
