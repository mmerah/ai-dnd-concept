# PROGRESS

One entry per phase of `PLAN.md`: the four line counts at its start and its end, the decisions
taken off-plan, the review findings refuted and why, and what is known and accepted.

## Phase 1: engines and packs

Counts, start → end: `src` 10,904 → 10,510 (target about 10,510); `tests` 12,403 → 12,365
(target about 12,263: the plan's count did not include the six tests the reviews asked for or
the boundary tests the parts added); `qa` 2,005 → 2,005; `scripts` 390 → 390; 795 → 781 tests
collected. One golden moved: `tests/core/fixtures/prompts/tunnelgoons/worldsmith.txt`.

Decisions off-plan:

- All three parts were implemented by opus, not sonnet: each touched ten or more source files
  with generic-typing and strict-pydantic subtleties.
- `Engine.pack_ids` is gone; `select_packs` prepends the SRD itself (one caller, no override).
- The pack `select` runs once, in `Engine.admit`, for both families; `SceneEngine.author` no
  longer selects on its own, and `RoomEngine.author` is covered too. `restore` keeps its own.
- `packs` is a distinct tuple at every file boundary: `core/model.py` `Packs` carries
  `check_unique`, which `PackSelection` used to carry.
- `RoomWorld.require_dweller` / `require_prop` resolve a dweller and a prop; `RoomEngine.
  meanwhile` and `require_member_here` call them, so the refusal texts have one home.
- `Engine.edited` refuses a `name`, `source` or `license` box.
- The scenario page's pack select is written back from `self.packs` when a choice is refused.
- The refusal order of `meanwhile` changed: the destination is resolved before the "stands with
  the player" / "is here with the player" checks. No test pinned the old order.

Refuted review findings:

- "`check_addable` should scan the rebuilt pack against every installed pack": 44 ids are
  shared across the shipped Loner packs, so that scan would refuse most written packs. Only a
  selection combines packs, and `select` refuses the overlap at `begin` and `restore`.
- "Inline `BOX_ROWS`": it sits beside `MONOSPACE`, a single-use constant of the same kind.

Known and accepted: an in-play game whose written pack is later edited into an id collision
with the other supplement in play is refused at the next `restore`, not mid-turn (before this
phase it failed on the next tool call).
