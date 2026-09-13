# PROGRESS

Newest first. One entry per landed phase.

## Phase 2 — the rooms tool, the ELSEWHERE section, the arm guard and the two goldens

| count | before | after | planned |
| --- | --- | --- | --- |
| `src` | 10,061 | 10,239 | ~10,209 |
| `tests` | 10,535 | 10,757 | ~10,676 |
| `qa` | 1,760 | 1,760 | 1,760 |
| tests passing | 667 | 675 | ~672 |

Two golden fixtures moved, both tunnelgoons and both named by the plan:
`schemas/tunnelgoons/master_tools.json` (the new tool entry) and `prompts/tunnelgoons/master.txt`
(the `rooms/rules.md` section). Thirteen others untouched. The overshoot on both counts is the
review fold below, which is larger than the plan's arithmetic assumed.

### The two shapes the plan drew that did not survive

- **`RoomEngine.tick` follows phase 1, not PLAN.md.** No `enabled` parameter, and the flag goes
  down through `World.disarm()`. `PROGRESS.md`'s phase 1 entry already called this; it is recorded
  again here because the plan's step 6 still reads the other way.
- **`ELSEWHERE` lists the ways out of each offscreen place, which the plan's `elsewhere_lines()`
  did not.** A reviewer showed the section is the master's *only* view of offscreen geography —
  `map_so_far()` is worldsmith-only and `WAYS OUT` covers the current place — so `shut_from`,
  `shut_to` and a dweller's reachability were blind guesses that mostly refused and burned the one
  armed turn. Each line now ends `; ways: <tag>, <tag> (unfound)`: destinations as tags so the
  master can echo the id straight back, locked ways omitted since neither power can use one, and
  the `(unfound)` marker because a dweller may walk a way the player has not found while a shut
  may not. The maintainer cleared the deviation. No golden moved — the section renders only when
  armed, and no golden turn arms it.

### Decisions made off-plan

- **The arm guard counts only what the section shows.** The plan's `can_move_offscreen()` counted
  an item as movable on `item.on not in (here, player.id)`, which is true of an item in the hands
  of a dweller standing beside the player — the one item the tool must refuse (the plan's own Open
  concern 2) — and true of everything in never-visited places, whose ids the master is never
  shown. Either way the clock armed with nothing legal to do, the exact failure the guard exists
  to prevent. It now counts things in `elsewhere()` places only. The maintainer approved the first
  half before implementation; the second came out of review.
- **Open concern 1 is closed, not carried.** The guard now counts the shut-a-way power alongside
  the two that need a destination, so a state whose only legal move is a shut arms the clock. The
  plan recorded this gap as overflow past a twelve-line budget; there was no budget here.
- **`meanwhile` refuses an item already at its destination.** Both sibling powers refuse their
  no-op and `move_item` refuses this exact case. Without it the master could fire the player's
  `MOVED_CARD` — "Elsewhere, something moves." — for a call that moved nothing, which decision 14
  forbids.
- **A dead dweller is not listed in `ELSEWHERE`.** `thing.tag` carries no "(dead)", so the
  section offered corpses as movable while `can_move_offscreen()` and the tool's `IS_DEAD` refusal
  both treat them as immovable. Their carried items still list; those stay movable.
- **`RoomWorld.holders_here`.** The set `{current.id, whoever stands here}` was spelled three
  times once this phase added its own copy; the guard and the tool are only correct while they
  agree. Two of the three call sites are older code (`require_item_here`, `reveal_hidden`).
- **`RoomWorld._visited()`.** `map_so_far()`'s dedup loop was `elsewhere()`'s body minus one
  filter. Shared; `map_so_far()`'s output is byte-identical, which its untouched goldens prove.
- **`NOTHING_OFFSCREEN` reworded** to "no time has passed offscreen; call this only while
  ELSEWHERE is shown". The old text described a state that is also true right after a successful
  call and invited the master to retry.

### Review findings refuted

None. Two independent Opus reviewers read the staged phase (`codex` is not installed on this
machine, so the second Codex Sol review was again replaced by a second Opus reviewer, at the
maintainer's instruction). Both returned "phase complete: yes"; their six overlapping findings and
all three offered cuts were fixed rather than argued with.

### Known and accepted

- **The tool is wider than the section.** `meanwhile` still accepts a source in a never-visited
  place — an item lying in a room the player has never entered may be moved to one they have. The
  guard no longer arms for it, so the master is never invited to try, but a master that guesses a
  legal id is not refused. Narrowing the tool as well would refuse a write nobody could see
  either way.
- **A refusal partway through a three-power call leaves the earlier pair's mutation on the draft.**
  `move` behaves the same (it opens the way, then can refuse a `with_ids` entry). Not this phase's
  to fix.
- **`uv run aidm` was smoke-launched, not played.** The server comes up clean; driving a turn
  through the page needs the by-hand Playwright scripts in `qa/`. The suite's scripted golden turn
  runs the same runtime path.
- **`uv run basedpyright` with no arguments reports ~1,100 errors, every one in `qa/`** from
  Playwright's untyped API. Pre-existing and untouched here; `uv run basedpyright src tests` is
  clean.

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
