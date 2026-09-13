# PROGRESS

Newest first. One entry per landed phase.

## Phase 1 — the note-drop fix, the clock, the switch and the scenes nudge

| count | before | after | planned |
| --- | --- | --- | --- |
| `src` | 10,020 | 10,063 | ~10,063 |
| `tests` | 10,412 | 10,531 | ~10,557 |
| `qa` | 1,759 | 1,760 | 1,760 |
| tests passing | 659 | 667 | ~666 |

No golden fixture moved, as planned. Nothing under `engines/rooms/` reads `meanwhile_due`; the
rooms half is phase 2.

### Decisions made off-plan

- **`turns_played: int = Field(default=0, ge=0)`, not a bare `int = 0`.** The plan says "no
  validator" on the ground that every non-negative `int` is reachable. That argues for the floor
  rather than against it: a save file is a boundary, CLAUDE.md says reject bad data at once, and
  the repo already spells a saved counter this way (`broken_times` in `twentyfourxx/world.py`).
  One token; revert it if the plan meant the constraint too.
- **One test beyond the plan's list: the clock actually firing.** The plan's test section pins the
  counting, the skipping and the switch, but never the arm itself, so `>` instead of `>=`, or a
  missed reset, would have shipped green. `tests/engines/test_seam.py` now ticks a `FifthEngine`
  draft to its tempo and asserts the reset and the raised flag.
- The plan's `tests` estimate of ~+145 came in at +119. The behaviours are all covered; the
  estimate was generous, not the coverage thin.

### Review findings refuted

Two independent Opus reviewers read the staged phase (`codex` is not installed on this machine, so
the second Codex Sol review was replaced by a second Opus reviewer).

| # | finding | why it was refuted |
| --- | --- | --- |
| 1 | Replace `finish(lines, *, played)` with a `Turn.played` field set in `begin` (reviewer A) | PLAN "How to work" 1 fixes this signature verbatim as settled specification. The two reviewers also asked for **opposite** refactors of the same two parameters — A to move `played` into `Turn`, B to move `meanwhile` out of it — which is the mark of an API preference, not a defect. |
| 2 | Drop `Turn.meanwhile`; pass `finish(lines, *, played, enabled)` (reviewer B) | Same: PLAN fixes both the field and the `begin` keyword. See above. |
| 3 | The floor message should name the minimum ("two is the floor") | PLAN gives the string verbatim; it is developer-facing and the test matches on `ticks every`. |
| 4 | Assert `TunnelGoonsEngine.meanwhile_turns == 4` | That is wiring, not behaviour; CLAUDE.md's test rule excludes it. The tempo is exercised through `tick`. |
| 5 | Drop the `FileStore` round trip from the stale-save test | The claim under test is that a *file* written before this feature still loads, so it goes through the store on purpose. |

### Known and accepted

- **`act()` undercounts.** `act` reaches `_turn` only when `_grow` returned True, so a player action
  whose worldsmith write failed ticks nothing. The plan accepts this; erring slow is the safe
  direction.
- **A page action can spend a stale arm with the switch off.** The only disarm is in `Turn.finish`,
  but `GameService.act` → `_grow` → `SceneEngine.depart` → `render_next` reaches a scene write with
  no turn at all. A player who arms the flag, switches meanwhile off and then takes the way on gets
  one stray nudge, which that same install clears. It is the same class as the accepted `act()`
  undercount, and the alternative — disarming inside `GameService.resume` — writes state at load
  time, which this phase deliberately avoids. The comment on `Settings.meanwhile` is a turn ahead
  of the code here.

### Awaiting the maintainer

- **Engine code writes `World` fields directly** — `Engine.tick` (three lines) and
  `SceneEngine.install` (one line) are, by both reviewers' grep, the only places in `engines/` where
  an engine assigns a world field instead of calling a world method. CLAUDE.md says a class owns
  its state and that a world method changes fields; PLAN quotes both bodies verbatim as settled
  shape. The code as it stands follows PLAN. If the standing rule wins, the fix is `World.count_turn`
  and `World.disarm`, called from `tick` and from `SceneWorld.apply_scene` — a body-only change that
  leaves `Engine.tick`'s signature, and so phase 2's `RoomEngine.tick` override, untouched.
