# Progress

Tracking PLAN.md. One bullet per landed step; `uv run pytest && ruff check && ruff format --check
&& basedpyright` green at each.

Reset 2026-08-12 with the reorientation (CONCEPT.md): the D&D 5e engine is being removed in
favor of a first-party tag-based Oracle engine. The prior log — kernel refactor, world/mechanics
boundary, character creation, the full dnd5e build-out — lives in git history up to the commit
tagged before Phase 1's deletion.

## Phase 1 — Delete the D&D 5e engine — DONE 2026-08-12

- **Step 1 — the engine tree.** Deleted `engines/dnd5e/` (2,348 lines Python + 41.5k pack JSON),
  `scripts/srd/` + `scripts/import_srd.py`, `tests/dnd5e/`, the 22 dnd5e eval scenarios, the
  `bram`/`elowen` eval characters, every dnd5e golden fixture family, and the dnd5e overlays
  (`characters/kael/dnd5e.json`, `scenarios/whispering-vault/dnd5e.json` — folded in from step 3
  because the launcher catalog scans overlays). `ENGINE_MODULES` lost one line; `probes.py`
  dropped its dnd5e branches and the five dnd5e-only probe types no surviving eval used
  (`set_number`, `set_level`, `set_note`, `has_ref`, `note_value`). The launcher's withdrawn-save
  test now relabels a story save instead of building a real dnd5e state. 107 files,
  −58,586 lines. Committed (the one commit before the stage-only instruction).
- **Step 2 — `state/packs.py` leaves with its only consumer.** `AdvancementOffer.granted/options`
  are plain strings (prompts and panels only ever rendered them); `ENCODING` now comes from
  `content/store.py`; `ContentSlug` moved inline into `state/creation.py`. The whole
  `pack_paths` plumbing went with it: `Engine.__init__()` takes nothing, `EngineConfig`,
  `Settings.engines`, and `Settings.engine()` are deleted, `build_engine` ignores config. The
  two pack tests in `test_loader.py` and the probe boundary's `aidm.state.packs` entry deleted.
- **Step 3 — docs.** CONCEPT.md and DECISION.md carry the reorientation record (the ADR
  convention left with the uninstalled plugin, docs/adr/ deleted). ROADMAP.md rewritten where it
  named packs, spell preparation, or old plan phases; IDEAS.md dropped the SRD-extension idea;
  README rewritten story-only (one shipped engine, no pack `facts`, Oracle named as next). The
  stale eval `results/` (pre-reorientation, dnd5e-heavy, only same-hour-comparable) deleted.
- **Step 4 — the gate.** `SAVE_VERSION` 53 → 54; golden regen moved exactly one byte family:
  `save_version` in the three story fixtures, no prompt or schema golden. `rg -i dnd5e` over
  src/tests/scripts/content is clean (CONCEPT.md, DECISION.md, and PLAN.md keep the name as
  history). 96 tests, ruff, format, basedpyright all green; story and probe suites untouched
  throughout — the engine boundary held without a single core change.
- **Review pass (adversarial subagent + follow-ups).** Verdict on the diff: correct. Its fixes:
  README's intro still said "Story and 5e are both included" (now story-only), dead `_element()`
  in `ui/create.py`, dead `EVAL_CHARACTERS` lookup in `evals/run.py`, stale `aidm.state.sheet`
  in the probe boundary list, five stale "5e/packs/both engines" comments, `__pycache__` husks.
  Follow-ups applied on maintainer decision: `build_engine(engine_id)` dropped its dead
  `config` param (6 call sites), and `AttackRollHappened` → `ContestedRollHappened` (it counts
  contested rolls, not attacks; three scenario JSONs renamed with it). Kept deliberately:
  `add_tag`/`has_tag`/`branch_adds_tag`/`rolled_with_mode` probes and dice
  advantage/disadvantage — the Oracle engine's vocabulary. AGENTS.md/CLAUDE.md and docs lost
  the uninstalled plugin's conventions (`.scratch` tracker, ADRs, `docs/agents/`).

## Phase 2 — Oracle engine

Not started.
