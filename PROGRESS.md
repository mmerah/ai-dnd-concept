# PROGRESS

One entry per phase of `PLAN.md`: counts, decisions made off-plan, refuted findings, known-and-accepted.

## Phase 1 — Breathless

- `src`: 6,750 → 8214 (PLAN target about 8,250). `engines/breathless/`: 1459 Python lines (target 1,700, cap 2,000). 8 tools + 5 arms.
- Off-plan decisions: scenario `drowned-road` (opening `bell-house`, Ovid Sarn + Ivo Casks present, Drowned Marta hidden); registry order loner3e, tunnelgoons, breathless (chronological); `master_sections` takes no packs; loot trouble (1–4) is notes only and the loot die always wears; swap options are `swap-<key>` so item keys never collide with `take` / `med-kit`; `docs/BREATHLESS.md` follows the LONER-3E / TUNNEL-GOONS template (maintainer's call mid-phase) instead of the brief's table.
- PLAN fix (rule 10): §1.3 said an item **rolled at** d4 leaves; the SRD says "When reduced to a d4, the item either breaks, gets lost, or fades away". Code, `rules.md`, docs and PLAN now read "reduced to d4": a d6 item's roll is its last.
- Review fixes folded: item-at-d4 rule; `rules.md` med-kit line contradicted the SRD's "lay low someplace secure"; loot option id collision; `Enter(PLAYER_ID)` refused before lookup as `Leave`; dead `world` parameter of `entity_line`; `_scene_unmet` double spread; `item_id` local in `check`; absent-code comment in `install_scene`.
- Refuted: bare `verb` fields on the arms (same as Loner and Tunnel Goons; `master_tool` checks the args model, the arm's `const` and title describe it); "6. None found" filler and a "Readings" heading (the sibling docs carry neither); deleting "What the AI game master adds" (the sibling template has it).
- Known and accepted: `uv run aidm` smoke boots and lists The Drowned Road; a live turn needs the CLIs, the golden turn plays it offline. SIGTERM shutdown error is NiceGUI/MCP lifespan teardown, not this phase.
- Also this phase (maintainer asked): `README.md` says three engines with a Breathless paragraph and licence line (Phase 4 still does the four-engine rewrite); `docs/MAZE-RATS.md` deleted, `VISION.md` points at its history (`62f95c6`).

## Phase 2 — fold the identical scene code

- `src`: 8,214 → 8,103 (PLAN target about 8,160; −111 against the planned −90). Fixtures byte-identical after regen.
- Off-plan decisions: the fold went to a new flat module `engines/scenes.py`, not `core.py` (maintainer's call mid-phase: `core.py` is the seam every engine imports, `scenes.py` is what only the scene engines import; Tunnel Goons never touches it). PLAN Settled 1, 10 and Phase 2 now say so. `check_named` (was `_check_named`, identical in both engines but for the cast annotation) moved too, typed on `Mapping[EntityId, Entity]` like `resolved_id` — PLAN's "if two of them turn out identical, move them". Loner's `scene_spent(world)` took Breathless' `(run, someone_dead)` shape; its five test calls changed with it. `tests/breathless/breathless_test_support.py` repointed (the brief missed it).
- Stayed in the engines, identical in body but bound to an engine type or constant: `_worldsmith` (reads the engine's `WORLDSMITH`), `_scene` (its `SceneDraft`), `_where` (its world), `record`, `history`, `settled`, `known`, `next_scene` (its game type). Moving any needs a parameter or protocol, which PLAN forbids.
- Reviews (Fable, Codex Sol): no findings, both "phase complete". Nothing refuted.
- Known and accepted: `uv run aidm` boots and serves; the SIGTERM shutdown traceback is the NiceGUI/MCP lifespan teardown noted in Phase 1.
