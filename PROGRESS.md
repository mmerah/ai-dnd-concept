# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

## Done

- 2026-08-13: recentering decided and PLAN.md rewritten — phases: 1 delete story, 2 oracle→loner3e
  (SRD-compliant, tables resolver-side), 3 docs-only engine shelf, then scenario creator, media.
- 2026-08-13: docs/24XX.md — exact SRD v1.4 (CC BY), engine package sketch filled.
- 2026-08-13: docs/LONER-3E.md — full 3e SRD from the lonersrd GitHub source (CC BY-SA); sketch
  filled; PLAN phase 2 gap list corrected against the exact text (conflict-no-tick is already
  SRD-exact; no Luck-spend rule exists).
- 2026-08-13: docs/CAIRN-2E.md — 2e Player's Guide mechanics extraction (CC BY-SA); sketch
  filled; verdict ~2× loner3e code, stays on the shelf.

- 2026-08-13: Phase 1 done — `cce1701` eval harness deleted (−1,199), `d20da72` story engine +
  tests + fixtures + overlays deleted, core tests repointed to oracle (−3,177/+123), `459a8d7`
  stranded trims: offer choice fields, `AllocationStep`, dice `vs=` (−183/+31). Suite 99 green,
  no SAVE_VERSION bump; only fixture movement is the always-null `vs`/`success` keys leaving
  the turn trace. Reviewed: sweeps clean, probe/oracle engines untouched.

- 2026-08-13: loner3e phase shipped (`dbec49c`) — full rename with SAVE_VERSION 56, twist
  table resolver-side, SRD growth verbs, deviations cut to 10: twists now narrate the turn they
  land (twist fact narratable, note develops it next turn) and the max-4 caps are gone.

- 2026-08-13: two full-tree audits (refactor + loner3e compliance) accepted and sequenced as
  PLAN.md Phase 3 (shrink and comply, 11 steps, one SAVE_VERSION bump in step 8); scenario
  creator and media renumbered to phases 4 and 5; content-pack rejection reversed (Loner
  adventure packs are real upcoming content).

- 2026-08-13: Phase 2 done — README names the engine shelf (24XX, Cairn 2e) and the rule;
  shelf docs were already in. Phase 3 step 6 upgraded to two selectable packs (SRD + AP01
  fantasy, selection as creation step 0; AP01 license ambiguity flagged in step 10).

- Phase 3 in flight (2026-08-13), suite green after each step:
  - step 1: dice.py trimmed to single-term `NdM` — `DiceExpr`/`ConstantTerm`/multi-term/`bonus=`/
    `"disadvantage"` gone; probe engine adds its stat in code.

  - step 2: `entity_fact`/`explained_fact`/`explained` live in `state/facts.py`; world.py
    add/reveal/move and both engines use them; four relation functions → one `_relation_change`,
    traces byte-exact.

  - step 3: launcher `_one` helper + `ContentOption.subtitle` (Scenario/CharacterOption gone),
    `LauncherModel`→`Frozen`; `FileStore` merges FileSaves/FileTraces, `_StoredVersion` gone;
    `GameSession`/`run_turn` take `Settings`+`FileStore`; `page_header` ctx manager,
    `functools.partial` handlers, `stage()`→`Stage.of`.

  - step 4: scene shapes (`Exit`…`_undetailed`) moved verbatim to `turn/scene.py`; prompts.py,
    pipeline, roles, `test_context_boundary` repointed.

  - step 5: five core prompt constants script-generated into `turn/prompts/*.md` (byte-exact,
    no trailing newline), loaded via `engine_text`; instruction fixtures unmoved.

  - step 6: `engines/loner3e/pack.py` (`Pack`/`PackEntry`, `load_packs`, `twist_table`) +
    `packs/srd.json` (curated tables verbatim + SRD twist columns, name "Core tables") and
    `packs/ap01-fantasy.json` (four d66 tables transcribed from the AP01 page, slugified ids,
    empty details, no twist table); creation step 0 "Choose a table set"; twists flow
    engine→`resolve_question(…, twists)`; delegation shim gone (begin/commit/renderer bodies
    live in rules.py), `read`/`write` wrappers → `read_mechanics(state, Model)` in counters.py.
  - step 7: compliance prose — Sibylline Responses section in director.md, three scene moods in
    scene_director.md, lingering-enemy-is-a-thread sentence in advancement.md, narrator recite
    list system-neutral; instruction fixtures regenerated, diff is exactly those four texts.

  - step 8: save-shape commit, SAVE_VERSION 56→57 — `available_tags` takes `Mechanics` and merges
    every carrier's sheet tags (rat's duplicated world trait deleted); edge/burden → skill/frailty
    in TraitChange/Trait docstrings, kael and world content; `Thread.kind`, `Memory.tags`,
    `Memory.turn`, `Counter.minimum`, `Counter.recharge` deleted. Golden regen read: removed keys,
    vocabulary swap, rat trait gone; turn fixture moved only on `save_version`.

  - step 9: `_strike` resets both participants' luck to LUCK_MAX when a side hits 0 (SRD "resets
    after conflicts"), defeat_note kept; tests: reset both pools, zero-luck refusal, opponent
    sheet tags visible to the resolver. No golden movement.

  - step 10: deviations list rewritten (12 entries — luck-reset deviation dropped; hidden twist
    counter, one-change milestones, closed concept menu, unrolled 5W+H added), sketch bullet now
    points at the landed prose; README gains Licensing (CC BY-SA attribution, AP01 ambiguity,
    code license open).

  - step 11: comment trim sweep over every production and test file (all `#` comments, all
    docstrings via AST dump, suppression directives) — nothing to delete; the flagged noise
    left with the files steps 1–6 rewrote. Zero-diff step.

  - adversarial review (fable subagent, full staged diff): no comment/docstring/test violations;
    fixed F1 (luck reset now refills to the sheet's own maximum, not a +LUCK_MAX delta; 10-max
    test) and F3 (creation picks pruned by surviving option on a pack switch, form refreshes
    before preview). F2 (history_window=0 shows all) accepted as intended; F4 (add/move on
    entity_fact silently fixed an unrevealed-mover narrator leak) accepted.

  - Phase 3 done (2026-08-13). Steps 1–11 are uncommitted, staged as one tree; every
    verification (pytest ×102, ruff check, format, basedpyright) green. Production LOC 4,814
    against the plan's ≈4,550 estimate — the remaining gap is the audits' pre-rewrite guess,
    not un-taken findings.

## Next

- Phase 4: scenario creator script (`scripts/create_scenario.py` — pydantic-ai agent with
  `ScenarioWorld` as `NativeOutput`, `creator` role config, validation loop, per-engine
  overlays). PLAN.md carries the full spec.
