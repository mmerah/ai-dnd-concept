# Meanwhile

The world changes while the player is somewhere else.

Brainstorm notes. Nothing is decided.

## The two families need different things

The difference is whether the player can check.

**Rooms** keeps the map. Every place, npc, item and way has a location, and `visits`
(`rooms/world.py:115`) records the walk. The player can go back and find the change.

**Scenes** throws the map away. `apply_scene` replaces `run`, and a scene the player
left survives only as a title in `runs`. The player never goes back, so a change there
looks the same as a new scene written through `arc` (`scenes/world.py:50`).

Rooms needs a simulation. Scenes needs pacing.

## Ideas for rooms

1. **Code moves people when the player moves.** Give `Dweller` a disposition. When
   `RoomEngine.move` runs, roll its `Random` and move roaming dwellers along known ways.
   No role starts, no wait, tests stay deterministic. `Thing.fact()` sets
   `told=self.known`, so the facts stay hidden for free. **Best option.**
2. **A `meanwhile` master tool.** Fits beside `move_item` and `unlock_way`, but gives
   the master the whole map every turn and costs tokens when nothing should move.
3. **A worldsmith request on move, like `EXTEND`.** Best writing, worst cost. `EXTEND`
   is rare (it needs `frontier() == 0`) and `STEP_COPY` says the worldsmith takes
   minutes. One call per room walked is too slow.
4. **Move items, not only people.** `move_item` works only in the current place today. A
   thief could carry the idol two rooms away, and the player finds out on the way back.
5. **Doors lock again.** The player opens a way and leaves; later it is shut. One bool,
   and the route changes.

## Ideas for scenes

1. **A clock that feeds `arc`.** When the count is reached, add one line to the
   `render_next` intent. The existing `arc` revision does the rest. **Best option.**
2. **Count in `leaving()`.** The hook exists, loner3e already uses it, and it runs in
   `depart()` before the next scene installs. Time has passed there.
3. **Use `COMPLICATION` for the loud version.** It already writes something arriving at
   the current place. No new request type.
4. **Do not build a list of offscreen threads.** Only one family would use it, against
   "do not add an abstraction until two things need it".

## An idea for both families

**A meanwhile for the party.** Both families have `party` and `leave_party`. Where did
the companion who left go, and do they come back different? It reuses the interjection
code, and the player understands it at once. Possibly the best value for the work.

## Does the clock work for both families?

The counter works for both. The `arc` part does not.

Put the counter on `World` in `engines/base.py`. `SceneWorld` (`scenes/world.py:47`) and
`RoomWorld` (`rooms/world.py:114`) both inherit it already: one field, two families, no
new abstraction.

| | scenes | rooms |
|---|---|---|
| has an `arc` to revise | yes | **no** |
| a worldsmith call already running | yes, the `DEPARTURE` write | **no**, `move` starts nothing |
| how it reaches the game | revise `arc` in the next `NextDraft` | `draft.note(...)`, master plays it next turn |

Rooms works by another route. `Game.note()` (`core/model.py:114`) is on the shared model
and empties into the turn (`turn/run.py:48`), so rooms can instruct the master with no
extra role and no wait.

One problem: a scene crossing is rare, a room walk is common, so the same count gives
very different pacing. Better to **count turns** — the one unit both families share.

## Costs

- **Every save becomes invalid.** A new `Dweller` field or counter breaks them all.
  Acceptable now, but choose it on purpose.
- **Keep the facts untold**, or the narrator tells the player a secret. `Thing.fact()`
  is safe; a hand-built `Fact` is not.
- **Frequency is the real choice**, not the mechanism. Too rare and nobody notices; too
  often and the player stops trusting the map.
