# Meanwhile

Offscreen change: the world moving while the player is not looking at it.

Notes from a brainstorm, not a plan. Nothing here is decided.

## The asymmetry

The two engine families do not want the same feature, and the reason is whether the
player can ever check.

- **Rooms** — the map persists. `RoomWorld` keeps every place, npc, item and way with
  its location, and `visits` (`rooms/world.py:115`) records the walk. The player can
  turn round and go back. An offscreen change is *falsifiable*: they find the treasure
  gone, the door open, the body moved.
- **Scenes** — `apply_scene` replaces `run`; a left scene survives only as a title in
  `runs`. The player never returns. An offscreen change there is indistinguishable from
  the worldsmith inventing it fresh in the next `NextDraft`, which it already does via
  `arc` (`scenes/world.py:50`).

So: rooms wants simulation, scenes wants pacing. Same word, two features.

## Ideas — rooms

1. **Code-only drift on `move`.** Give `Dweller` a disposition; when `RoomEngine.move`
   fires, roll the handed `Random` and relocate roaming dwellers along known ways. No
   role spawn, no latency, deterministic under test. Lands on "Only code changes state
   or rolls dice". Untold for free: `Thing.fact()` already sets `told=self.known`, so
   anything the player has not met cannot leak to the narrator.
   *Cheapest and most in-grain. Current favourite.*
2. **A `meanwhile` master tool.** Sits naturally beside `move_item` and `unlock_way`.
   But it hands the master latitude over the whole map every turn and burns tokens
   whether or not anything should move. Probably no.
3. **A worldsmith `Generation` on move, like `EXTEND`.** Richest writing, wrong cost.
   `EXTEND` is the only worldsmith spawn rooms has and it fires rarely, when
   `frontier() == 0`. `STEP_COPY` already warns the worldsmith takes minutes. Paying
   that per room walked would wreck the pacing.
4. **Items drift, not just people.** `move_item` is currently scoped to here. An
   offscreen variant (a thief carries the idol two rooms over) is the same mechanism
   with a different noun, and backtracking makes it land.
5. **Locks re-lock.** A way the player opened and walked away from closes again. One
   bool, and it changes routing without any new concept.

## Ideas — scenes

1. **A clock, feeding `arc`.** One counter; when it fires, the next scene's `render_next`
   intent gains a line saying the offscreen thing has advanced, and the existing `arc`
   revision does the rest. No new world, no second place, no offscreen register.
   *Favourite.*
2. **Tick in `leaving()`.** The hook already exists and loner3e already uses it (luck
   refill). It runs in `depart()`, before the next scene installs — exactly the seam
   where "time passed" is true.
3. **Reuse `COMPLICATION` as the loud version.** When the clock fires hard, it is
   already a written complication coming down on the current place. No new request type.
4. **Do not build an offscreen register.** A list of threads with their own state is new
   machinery only one family would use, against "do not add an abstraction until two
   things need it".

## Family-agnostic

**A meanwhile for the party.** Both families have `party` and `leave_party`. Where did
the companion who walked out go, what have they been doing, do they come back changed.
Reuses the interjection machinery. Immediately legible to the player in a way a moved
crate is not. Possibly the highest payoff per line of anything on this page.

## Does the clock work for both families?

**The mechanism generalizes. The delivery does not.**

The counter itself can live in one place: `World` in `engines/base.py`, which both
`SceneWorld` (`scenes/world.py:47`) and `RoomWorld` (`rooms/world.py:114`) already
inherit. One field, both families, no new abstraction.

What differs is what happens when it fires:

| | scenes | rooms |
|---|---|---|
| `arc` to revise | yes | **no** — rooms has no arc at all |
| natural tick site | `leaving()`, per scene crossing | `move()`, per room walked |
| is a worldsmith already spawning? | yes, the `DEPARTURE` write | **no** — `move` spawns nothing |
| delivery | revise `arc` in the next `NextDraft` | `draft.note(...)` → the master plays it next turn |

The rooms half works, but through a different door. `Game.note()`
(`core/model.py:114`) is on the shared model and drains into the turn
(`turn/run.py:48`), so a clock firing in rooms can hand the master a directive with no
extra spawn and no latency. That is the bridge — not `arc`.

One cadence wrinkle: a scene crossing is rare and deliberate, a room walk is frequent.
The same period would mean very different pacing. The cleaner generalization may be to
**tick on turns**, which is the one unit both families actually share, rather than on
crossings and moves.

## Costs

- **Every existing save dies.** "Saves have no version field. A stale save is invalid."
  A new `Dweller` field or a clock int invalidates all of them. Fine mid-concept, but
  decide it deliberately.
- **The narrator boundary is the thing to get right.** Any meanwhile fact must be
  untold, or the narrator leaks the world's secrets. `Thing.fact()` defaults the right
  way; anything hand-rolling a `Fact` does not.
- **Frequency is the real design knob**, not the mechanism. Too rare and nobody notices;
  too often and the map stops being trustworthy.
