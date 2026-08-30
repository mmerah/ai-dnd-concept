# PROGRESS: Phase 0 — probe `change_world`

Counts at phase start (`.py` lines): src 9076, tests 5691, evals 1783.

- [x] 1. Arm telemetry in `evals/turn_eval.py` (`Played.calls`/`Run.calls`, successful tool
      names + union arm). Done before the baseline so `pre-union` records tool names.
- [x] 2. Baseline `pre-union` recorded (9 repeats, seed 1000): walk-and-look 100%,
      three-things 89%, fight-the-rat 100%, fight-the-wrecker 100%; 0 errors, 0 refusals.
      → `evals/results/pre-union.json` (with arm telemetry).
- [x] 3. Union in `world/tools.py`: arms = existing arg models + `verb: Literal` discriminator;
      old tool descriptions became arm docstrings; `advance_thread` folded in as an arm
      (`ADVANCE_THREAD` constant deleted, `advance_thread` function kept); two wrappers
      (`ChangeWorld`, `ChangeWorldWithoutImprovisedItem` for Breathless); one `apply_change`
      match dispatching to `world/actions`. Caught: a union nested through a named `type`
      alias defeats the discriminator (29-error retry text); plain assignment aliases
      flatten, so the full union derives from the no-improvised one and one bad arm yields
      one clean error. `director_world.md` rewritten for verbs; reveal-trigger guardrail
      wording kept, `Call reveal` → `Use reveal` (post-union's single refusal was the model
      calling `reveal` as a tool name; re-gated on a targeted three-things run, below).
      Tool counts: loner3e 14→5, breathless 15→7, twentyfourxx 17→8.
- [x] 4. Tests rewritten to `change_world` arms (`golden_turn_support.py`, `test_pipeline.py`,
      `test_code_mode.py`). Goldens regenerated once: schemas + the three instructions
      fixtures moved; turn/save/prompt fixtures unchanged (same facts through the union).
      Every diff read. Full check green (282 passed, ruff, format, basedpyright).
      `uv run aidm` boots and serves 200.
- [x] 5. Schema sizes (compact JSON, per-engine complete tool list): loner3e 7162→8740 B,
      breathless 9861→11281 B, twentyfourxx 11022→12600 B (+1.4–1.6 KB each — discriminator
      mapping, $defs, verb consts). `change_world` entry alone: 5926 B (5450 B without the
      improvised arm). Bytes up, tool count down 15–18→5–8; the eval decides.
- [x] 6. Re-run `phase0-union` (9 repeats, seed 1000): all four cases 100%; overall
      97%→100% (+3%), errors 0%→0%, director_calls 1.42→1.44, 15.3s→15.8s. One refusal in
      36 runs (the model tried old tool name `reveal` once, recovered on retry).
      Arm telemetry: post-union arm mix matches the pre-union verb mix; no wrong-arm drift.
- [x] **Gate: union SHIPS.** Scores at or above prior on every case; the kit inherits
      `change_world`.

Adversarial review (opus, staged diff): verdict "ship after a short fix list", no
correctness bug — every arm's schema byte-identical to the tool it replaced, refusal texts
intact, `during_suspension` preserved, match provably exhaustive. Fixes applied:
- Unions derived via plain (non-`type`) aliases — the reviewer showed the named `type`
  alias, not nesting itself, breaks the discriminator (−10 src).
- `Call reveal` → `Use reveal` in `director_world.md` (the wording behind the run's one
  refusal); instructions goldens moved, schema goldens only reordered `oneOf`. Re-gated:
  `phase0-union-r2` on `loner3e/three-things` — 100%, 0 refusals.
- Tests: `changed(verb, ...)`/`change_args(verb, ...)` helpers replace 17 repeated
  three-level literals (−41 test lines).
- Deleted a stale `rooms_tools` docstring, an inaccurate telemetry comment (gate-blocked
  calls also land as plain returns — `_called`'s docstring is the accurate record), and
  renamed `_CHANGE_FIELD` → `_CHANGE_DESCRIPTION`.
- VISION.md added to ruff's `extend-exclude` (md-code-block formatting) and its incidental
  reformat reverted.
Known, accepted: the description-guard in `director_tool` sees only the wrapper field; the
arm descriptions are held by the byte-compared schema goldens instead. Union flatness has
no direct test; a regression shows as an invalid-looking `discriminator.mapping` diff in
the schema golden.

Counts at phase end: src 9073 (−3), tests 5708 (+17), evals 1820 (+37). Under the 9076
ceiling; the earlier +9 overrun was erased by the review's union derivation.
