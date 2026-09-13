# PROGRESS

Newest first. One entry per landed phase.

## Phase 1 — the note-drop fix, the clock, the switch and the scenes nudge

| count | before | after | planned |
| --- | --- | --- | --- |
| `src` | 10,020 | 10,061 | ~10,063 |
| `tests` | 10,412 | 10,535 | ~10,557 |
| `qa` | 1,759 | 1,760 | 1,760 |
| tests passing | 659 | 667 | ~666 |

No golden fixture moved, as planned. Nothing under `engines/rooms/` reads `meanwhile_due`; the
rooms half is phase 2.

### Where the clock ended up, and why it is not the shape PLAN.md draws

Both adversarial reviewers landed on the same complaint — the plan's `Engine.tick` and
`SceneEngine.install` write `World` fields directly, and those four lines were the only places in
`engines/` where an engine assigned a world field instead of calling a world method. CLAUDE.md is
plain about that, so the maintainer chose the standing rule over the plan's quoted body. Pulling on
that thread simplified three things at once:

- **`World` owns its clock.** `World.count_turn(tempo)` counts a turn and arms the flag on reaching
  the tempo; `World.disarm()` puts it down. `Engine.tick` and `SceneEngine.install` call them.
- **`Engine.tick(draft, *, counted: bool)` lost its `enabled` argument.** With the switch handled
  at the app layer (below), the `enabled` branch was dead code in production. The engine no longer
  carries a notion of the setting at all, which is what "nothing under `engines/` reads settings"
  wants anyway.
- **The app owns the switch, at the one chokepoint where a game loads.** `GameService.resume`
  disarms a save whose flag was armed before the switch went off. This closes a real hole the plan
  left: `GameService.act` → `_grow` → `SceneEngine.depart` → `render_next` reaches a worldsmith
  write with no turn in it, so with the disarm living only in `Turn.finish`, a player who armed the
  flag and then switched meanwhile off still got one stray nudge. `Settings.meanwhile`'s comment —
  "off stops the clock and disarms it" — is now true.
- **`Turn.played` replaced two spellings of the same condition.** `begin` computed
  `draft.pending is None` for the note drain and `GameService._turn` computed it again for the
  master gate; it is now one field, set once in `begin`, read by the drain, by the runtime and by
  `finish`. `Turn.meanwhile` and the `begin` keyword went with it: `finish(lines, *, enabled)`
  takes the switch at the one call that uses it.

**Phase 2 must be re-read against this.** Its step 6 draws `RoomEngine.tick` with an `enabled`
parameter and clears `meanwhile_due` by hand; the override is now

```python
def tick(self, draft: G, *, counted: bool) -> None:
    ...
    was_armed = world.meanwhile_due
    super().tick(draft, counted=counted)
    if was_armed and counted:
        world.disarm()
```

which is shorter than the planned version, not longer. Its step 5 (`self.meanwhile_due = False`
inside the `meanwhile` tool) becomes `self.disarm()` for the same reason.

### Other decisions made off-plan

- **`turns_played: int = Field(default=0, ge=0)`, not a bare `int = 0`.** The plan says "no
  validator" on the ground that every non-negative `int` is reachable. That argues for the floor
  rather than against it: a save file is a boundary, CLAUDE.md says reject bad data at once, and
  the repo already spells a saved counter this way (`broken_times` in `twentyfourxx/world.py`).
- **Two tests beyond the plan's list.** The plan pins the counting, the skipping and the switch but
  never the arm itself, so `>` instead of `>=` would have shipped green
  (`tests/engines/test_seam.py`); and the switch test now opens a second table on an armed save, so
  it pins the load-time disarm rather than only the turn-time one (`tests/turn/test_turn.py`). Both
  were mutation-checked: each fails when its guarantee is removed.

### Review findings refuted

Two independent Opus reviewers read the staged phase (`codex` is not installed on this machine, so
the second Codex Sol review was replaced by a second Opus reviewer).

| # | finding | why it was refuted |
| --- | --- | --- |
| 1 | The floor message should name the minimum ("two is the floor") | It is developer-facing, the fault is legible from the number it prints, and the test matches on `ticks every`. |
| 2 | Assert `TunnelGoonsEngine.meanwhile_turns == 4` | That is wiring, not behaviour; CLAUDE.md's test rule excludes it. The tempo is exercised through `tick`. |
| 3 | Drop the `FileStore` round trip from the stale-save test | The claim under test is that a *file* written before this feature still loads, so it goes through the store on purpose. |

Every other finding from both reviews was fixed.

### Known and accepted

- **`act()` undercounts.** `act` reaches `_turn` only when `_grow` returned True, so a player action
  whose worldsmith write failed ticks nothing. The plan accepts this; erring slow is the safe
  direction.
