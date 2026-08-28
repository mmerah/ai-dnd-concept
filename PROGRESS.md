# PROGRESS

Tracks `PLAN.md`. One section per phase; closed phases are recorded in git history, not here.

## Phase 3 — preparation — done, staged

- 2026-08-28: Cairn tree committed whole on `cairn-shelved` (`8a9ed4b`); master clean at `cd24b57`.
- [x] 1. Ported from `cairn-shelved`: `PlayerAction`/`play_action` + sheet buttons + MCP `player_action` (no consumer until Phase 4). Left out as planned: the clock (`Game.hour`, `pass_time`, `advance_clock`, `Engine.elapse`) and everything Cairn. `Entity.uses`/`actions.use_item`/`USE_ITEM` were ported and then deleted again in step 2: their one consumer is 24XX's break budget, which is engine data.
- [x] 2. `ItemSheet`: `SheetEngine[S, I]` and `SheetMechanics[S, I]` gained `item_type` and an `items` dict beside `sheets`, so an item's `rules` validate, seed, refuse and render exactly as an actor's (error shape `items.<id>.<field>`). 24XX declares `ItemSheet` (`bulky`, `broken`, `breaks: Counter`), so the `BULKY`/`BROKEN` traits, `BREAK_TEXT` and the director.md paragraph reserving those slugs are gone; Loner declares `item_type = Sheet` but routes nothing to `items` (`uses_item_sheet` is False): SRD "Everything is a Character" keeps a thing that resists in `sheets`, so core has no `isinstance` special case for it, and `LONER-3E.md` deviation 2 stands. `Entity.uses`, `actions.use_item`, `USE_ITEM` and the prompt's `uses left:` line were deleted with the traits: a break budget is engine data, and `Entity.rules` is now the only engine channel on `Entity`.
- [x] 3. Tool bar in `AGENTS.md` Design rules: one Director tool per SRD procedure, never more than 24XX's eight; a core tool one engine reads is added by that engine.
- [x] 4. `test_package_boundary`'s `ENGINES` derives from `engine_ids()`; each engine's golden-turn `SCRIPT` moved to `tests/<engine>/golden_turn.py`, discovered by `test_golden_turn.py` via `importlib.import_module`; shared script pieces (`NARRATION`, `LISTENING`, `take`) live in new `tests/core/golden_turn_support.py`.
- [x] 5. Docs: `docs/CAIRN-BAREBONES.md`, `docs/FATE-CONDENSED.md`, `plans/L5-*`, `plans/L6-*` deleted; README rows/attribution gone, Breathless rows added; `docs/BREATHLESS.md` added; `IDEAS.md` L5/L6 merged.

- [x] 6. Review fixes, 2026-08-28: `Engine.advancement` is optional (Breathless has none) and `Engine.notes` folds the owed lines in; `actions.discard` removes an item and `Engine.forget` mirrors `seed` so mechanics drop it; `actions.improvise` takes `rules`; `SheetEngine[S, I = ItemBase]` with `item_type = None` by default, so Loner declares nothing about items; `Engine.settle` deleted (no reader); one `offered()` in core behind `GameSession.offers()`, and `play_action` refuses args no offer matches; 24XX `ItemSheet` checks `broken == (breaks.current == 0)`.

## Phase 4 — Breathless — not started
