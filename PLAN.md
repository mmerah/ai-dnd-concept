# PLAN: Meanwhile, in two phases

Every few turns the world moves where the player is not looking. Code keeps a turn clock on the
shared `World`; when it fires it arms a flag, and each family spends that flag its own way. In
**rooms** the game master is shown the places the player has walked, under a heading that says
time has passed, and may call one `meanwhile` tool to move a dweller, move a loose item, and shut
a door. The player gets one vague card. In **scenes** the flag adds one nudging line to the next
worldsmith scene write, and that write clears it.

Phase 1 is the clock itself: the note-drop fix on its own, two fields on `World`, `Engine.tick`,
the `counted` wiring through `Turn.finish`, the settings switch and the one qa line it moves, and
the scenes nudge. Phase 2 is the rooms half: the `meanwhile` tool, the `ELSEWHERE` section, the
arm guard, `rooms/rules.md`, the docs tool list, and the two goldens those move. The split is
chosen so that **phase 1 leaves the suite green on its own with the feature inert in rooms** —
nothing in `engines/rooms/` reads `meanwhile_due` until phase 2, so an armed flag there changes no
prompt, no tool surface and no golden.

Counted line by line against the real code, the plan adds about **190 lines** to `src`, from
10,020 to about 10,210: phase 1 about +49/−6, phase 2 about +148/−1. `tests` grows about +286,
from 10,412 to about 10,698. `qa` grows by one line, from 1,759 to 1,760. `rules.md` and the docs
are markdown and fall outside all three counts. An earlier draft of this plan said 130; that
number was a guess and the per-step arithmetic below replaces it.

## How to work

Full check, from the repository root, `UV_CACHE_DIR` unset:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright src tests
```

1. Do the phases in order, and the steps in a phase in order. Each step names its file and its
   symbols; there are no line numbers, so find the symbol. Where a step gives a signature or a
   body, that is the exact shape — several are quoted from the settled specification and are not
   to be improved on.
2. Change a shape and its tests in the same step. Exactly one existing **test** changes: the rooms
   tool-order assertion (phase 2, step 9). One existing **fixture** grows in the same file:
   `_scenario()` gains an item. One **qa** script changes: the tab list in `qa/s_settings.py`
   (phase 1, step 8). Nothing else. If a test you did not touch fails, the step is wrong.
3. Golden files live in `tests/core/fixtures/`. **Phase 1 moves none of them.** Phase 2 moves
   exactly two, both tunnelgoons, and phase 2 step 10 is the only place a regeneration is allowed.
   A golden that drifts anywhere else is a bug in the step, not a fixture to refresh.
4. `PROGRESS.md` gets one entry per phase, newest first: `src`, `tests` and `qa` line counts
   before and after (`find src -name '*.py' | xargs cat | wc -l`, the same for `tests` and `qa`;
   at the start `src` is 10,020, `tests` 10,412, `qa` 1,759 and 659 tests pass), decisions made
   off-plan with the reason, and refuted review findings with the reason. Phase 1 creates the
   file; the last commit deleted the previous one.
5. `pyproject.toml` already excludes `PLAN.md` from `ruff format` (it formats Python inside
   markdown fences and this file's fences are class-body fragments). Leave that line alone.
6. `CLAUDE.md` is not edited by any step. `scenes/rules.md` is not edited by any step.
7. The standing rules hold: no `Any` beyond the `Game[P]` bound; exact types; `Refusal` is the one
   message-bearing exception and an unreachable state is a `ValueError`; a class owns its state; a
   world method changes fields and writes facts while an engine tool method resolves ids; side
   effects stay at the edges; nothing under `engines/` reads settings; imports flow
   `core <- engines <- turn <- app <- ui`; `__init__.py` files stay empty; module layout is
   imports, constants, classes, public functions, private functions; 100-character lines; no
   comment unless the reason is invisible in the code, and then one line.
8. The game stays playable at the end of every phase: `uv run aidm`, open the tunnelgoons
   scenario, take a turn.

## Phase 1: the note-drop fix, the clock, the switch and the scenes nudge

About **+49 / −6** lines in `src`, **+1** in `qa`, **+145** in `tests`. No golden moves. At its end
of this phase the clock counts and arms on every engine, scenes spends the flag, and rooms ignores
it.

### Steps

1. **`src/aidm/turn/run.py` — the note-drop fix, alone (decision 18).** This step is **unrelated
   to the rest of the plan** and could be committed on its own; it is here because the maintainer
   asked for the bug fixed as part of this work, not because meanwhile needs it. Since the
   `ELSEWHERE` heading carries meanwhile's whole instruction (phase 2, step 6), this feature never
   writes a note at all.

   The bug: `Turn.begin` drains `draft.notes` unconditionally, and `Runtime._turn` then skips the
   master when an answer re-suspended a decision, so the drained notes are discarded and no model
   ever reads them. It already loses the `PAUSED_TO_ASK` note that `_consume` wrote one line
   earlier. Drain only when the master will run. The existing comment stays; the one line under it
   becomes two:

   ```python
   # Notes are read once; a note a tool writes after this steers the next turn.
   if turn.draft.pending is None:
       turn.notes, turn.draft.notes = turn.draft.notes, []
   ```

   A re-suspended turn keeps its notes for the next turn, where they accumulate with that turn's
   own. Both pauses happened and the master should read both. Ship it with its test (behaviour 9
   below) and stop; the clock starts at step 2. **+2 / −1.**

2. **`src/aidm/engines/base.py` — the two fields on `World`.** Add to `World`, below `party`:

   ```python
   turns_played: int = 0        # counted turns since the last fire
   meanwhile_due: bool = False  # the clock has fired and nothing has spent it yet
   ```

   Both defaulted, so existing saves keep loading: `Mutable` sets `extra="forbid"`, which rejects
   unknown keys in a file, not keys the file omits. `SceneWorld` (`scenes/world.py`) and
   `RoomWorld` (`rooms/world.py`) both inherit `World` already — no new base class, no new
   abstraction. No validator: any non-negative `int` and any `bool` is a state the clock can
   reach. **+2 / −0.**

3. **`src/aidm/engines/seam.py` — the tempo, its check, and `Engine.tick`.** Three edits to
   `Engine`:

   - Declare the tempo in the block beside `art_style` and `look`, with a value (this one has a
     default; the rest are set per engine):

     ```python
     meanwhile_turns: int = 6
     ```

   - In `__init__`, beside the duplicate-tool-name check, add the floor. At 1 the arm-then-spend
     order of `RoomEngine.tick` cannot work, and an unreachable state is a bug, not a `Refusal`:

     ```python
     if self.meanwhile_turns < 2:
         raise ValueError(f"the {self.id!r} engine ticks every {self.meanwhile_turns} turns")
     ```

   - Add the clock itself, after `land` and before `begin`. The specification fixes its signature
     and its three branches: `enabled` false clears `meanwhile_due` and leaves `turns_played`
     alone; `counted` false returns unchanged; otherwise `turns_played` rises and, on reaching
     `self.meanwhile_turns`, resets to zero and arms the flag.

     ```python
     def tick(self, draft: G, *, counted: bool, enabled: bool) -> None:
         world = self.world_of(draft)
         if not enabled:
             world.meanwhile_due = False
             return
         if not counted:
             return
         world.turns_played += 1
         if world.turns_played >= self.meanwhile_turns:
             world.turns_played = 0
             world.meanwhile_due = True
     ```

   No `armed` or `spend` hook on the seam: two abstractions only one family uses is what
   CLAUDE.md forbids. Rooms layers its own override in phase 2, the shape `master_tools` already
   uses. **+15 / −0.**

4. **`src/aidm/engines/tunnelgoons/engine.py` — the override.** In the class attribute block of
   `TunnelGoonsEngine`, beside `art_style` and `look`:

   ```python
   meanwhile_turns = 4
   ```

   **+1 / −0.**

5. **`src/aidm/turn/run.py` — the `meanwhile` field and `finish(played=)`.** Three edits to
   `Turn`:

   - Add the field after `notes`:

     ```python
     meanwhile: bool = True
     ```

   - `begin` gains a keyword-only parameter and passes it into the constructor:

     ```python
     def begin(
         cls,
         engine: AnyEngine,
         state: AnyGame,
         answer: Answer,
         rng: Random,
         *,
         meanwhile: bool = True,
     ) -> Self:
         turn = cls(engine=engine, draft=state.draft(), rng=deepcopy(rng), meanwhile=meanwhile)
     ```

   - `finish` gains the flag and rings the clock. This is the one place that runs exactly once per
     player turn; `Engine.close` is wrong, it also runs for interjections and worldsmith writes:

     ```python
     def finish(self, lines: tuple[SpokenLine, ...], *, played: bool) -> AnyGame:
         self.engine.tick(self.draft, counted=played and bool(self.facts), enabled=self.meanwhile)
         return self.engine.close(self.draft, lines, tuple(self.facts), words=self.words)
     ```

     **Do not use `Turn.landed()`.** It is true when `pending is not None` even with zero facts.
     `TunnelGoonsEngine.level_up` returns `[]` and sets `pending`, chaining to the next party
     member, so one combat beat that levels three characters would tick three or four times on
     turns the master never played — at tempo 4 the clock could fire entirely inside a level-up
     cascade. **+11 / −3.**

6. **`src/aidm/app/runtime.py` — the plumbing, mirroring `interjections` exactly.** Four edits:

   - `GameService` gains `meanwhile: bool = True`, beside `interjections`.
   - `GameService.resume` gains the keyword-only `meanwhile: bool = True` and passes it to the
     constructor, exactly as it does `interjections`.
   - `Runtime._open` passes `meanwhile=settings.meanwhile` in the `GameService.resume(...)` call,
     beside `interjections=settings.interjections`.
   - `_turn` captures `played` **before** the master runs and hands it to `finish`:

     ```python
     played = turn.draft.pending is None
     if played:
         await self.roles.master(turn)
     ...
     state = turn.finish(lines, played=played)
     ```

     The existing comment above that branch ("An answer that re-suspended leaves every tool
     refused: nothing for a master to do.") still explains it; keep it.

   `GameService.resume` must also pass `meanwhile=self.meanwhile` into `Turn.begin`; that is the
   line the plumbing test below pins. Nothing in `engines/` reads settings — the engine only ever
   sees the `enabled` argument.

   Known and accepted undercount: `act()` reaches `_turn` only when `_grow` returned True, so a
   player action whose worldsmith write failed ticks nothing. Left alone; it is rare and erring
   slow is the safe direction. **+7 / −2.**

7. **`src/aidm/config.py` — the player switch.** In `Settings`, beside `interjections`:

   ```python
   # The world moves offscreen every few turns; off stops the clock and disarms it.
   meanwhile: bool = True
   ```

   No UI **code** at all: the settings page builds its widgets from the model (`_shown` walks
   `model_fields`, `_widget` renders a `bool` as `ui.switch`), so the switch and its tab appear
   with nothing added under `ui/`. One qa script does change — step 8. **+2 / −0.**

8. **`qa/s_settings.py` — the tab list.** `body()` asserts the settings tabs verbatim:
   `providers, roles, media, speech, interjections, source max chars, server port`. A new
   top-level `Settings` field is a new tab, so `Settings.meanwhile` makes that assertion fail, and
   **no pytest covers it** — the qa scripts are Playwright drivers run by hand. Insert
   `"meanwhile",` after `"interjections",` in that list, keeping the model's field order. Nothing
   else in `qa/` moves. **+1 in `qa` / −0.**

9. **`src/aidm/engines/scenes/engine.py` — the worldsmith nudge, and nothing else.** Three edits:

   - A module constant beside the other prompt strings, in the tone of THE ARC — what can come,
     never what must:

     ```python
     MEANWHILE_NUDGE = (
         "Time has passed since the player last saw the people they are not with. Let one of "
         "them have moved on without the player, if the scene has room for it."
     )
     ```

   - In `render_next`, after the `world.arc` block and before `render_request`:

     ```python
     if world.meanwhile_due:
         intent += f"\n\n{MEANWHILE_NUDGE}"
     ```

   - In `install`, immediately after `world.apply_scene(scene)`:

     ```python
     world.meanwhile_due = False
     ```

   `depart` and `complicate` both route through `write_next` → `render_next`, so both carry the
   nudge, and both install, so both clear the flag — decision 12's "the crossing clears it".
   `SceneEngine` does **not** override `tick`. **+9 / −0.**

### Tests this phase adds

Behaviours 1, 2, 3, 8 and 9 of the specification's nine, plus the three coverage gaps a review
found. Behaviour and boundaries only; no test here asserts prose.

- **9 — decision 18, and it ships with step 1.** `tests/turn/test_decisions.py`, beside
  `test_an_answer_that_re_suspends_spawns_no_master`, which already sets up the re-suspending
  option (`CHAINING`) through `_suspend(table, CHAINING)`. Assert the state after that turn still
  carries the `PAUSED_TO_ASK` note in `draft.notes`, and that the following turn's master prompt
  carries it under NOTES FROM THE RULES. ~15 lines.
- **1 — the clock counts a played turn that landed facts, and ignores a turn that landed none.**
  `tests/turn/test_turn.py`. Two turns through `play_turn` on the loner3e table: one with a tool
  call that lands a fact, asserting `state.payload.turns_played == 1`; one with no calls,
  asserting it stays where it was. ~25 lines.
- **2 — the clock does not count a turn the master never played.** In
  `tests/tunnelgoons/test_play.py`, asserted against the real level-up cascade. The shipped
  `buried-keep` scenario ships **no sheeted npc** (`grix`, `crawler` and `lurker` all have
  `sheet: null`) and `next_to_level` filters on `member.hired`, so the cascade must be built by
  hand, the way `tests/tunnelgoons/test_tools.py` does at
  `test_level_up_for_the_player_opens_the_members_decision`:

  1. `open_table(tmp_path, engine_id=TUNNELGOONS, state_type=TunnelGoonsGame)`.
  2. On the live state: `world.npcs[GRIX].sheet = GoonSheet(abilities={...})` and
     `world.party.append(GRIX)`. `grix` already stands at `entrance`, the start place, which
     `RoomWorld._playable` requires of every party member and `Engine.land` re-checks.
  3. Pre-save a pending decision, the `_suspend` pattern of `tests/turn/test_decisions.py`:
     `table.service.save(...)` a state whose `pending` is `world.player.level_decision()`.
  4. `play_turn(table, Answer(option_id=...))`. `_consume` applies the player's level, then
     `next_to_level` chains to `grix` and re-suspends, so `_turn` skips the master.

  Assert `turns_played` did not move even though facts landed, and that
  `[role for role, _ in table.spawner.prompts]` names no master. ~35 lines.
- **3 — the clock is inert and clears the flag when the switch is off, through the real
  plumbing.** In `tests/turn/test_turn.py`. **Do not set `table.service.meanwhile` directly** — a
  forgotten `Runtime._open` line would leave the suite green. `Settings` is frozen, so build the
  table with the switch off:
  `settings=offline_settings(tmp_path).model_copy(update={"meanwhile": False})`, passed to
  `open_table`.
  Arm the flag by hand on the saved state, play a turn that lands facts, and assert `turns_played`
  did not move and `meanwhile_due` is false. This one test pins the whole chain
  `Settings → _open → GameService.resume → Turn.begin → Turn.finish`. ~25 lines.
- **the tempo floor.** Beside the duplicate-tool-name test for `Engine.__init__`: a subclass with
  `meanwhile_turns = 1` raises `ValueError` on construction. `pytest.raises(ValueError,
  match="ticks every")`. ~10 lines.
- **a save written before this feature still loads.** In `tests/core/test_store.py`, beside
  `test_a_saved_games_history_round_trips`: dump a committed state to JSON, delete
  `turns_played` and `meanwhile_due` from the payload, write it through `FileStore`, and assert
  `engine.restore(raw)` returns a state whose `turns_played` is 0 and `meanwhile_due` false. This
  is the claim "defaulted, so existing saves keep loading", made testable. ~15 lines.
- **8 — the scenes nudge appears in `render_next` only when armed, and `install` clears the
  flag.** `tests/engines/test_scenes.py`, beside
  `test_the_next_scene_prompt_carries_the_scene_as_it_stands`, which already renders a prompt from
  a built state. Assert the nudge's first clause is absent from `render_next` on a fresh state,
  present once `meanwhile_due` is set, and that `install` leaves the flag down. ~20 lines.

No new fixture file, no new support module: every table, engine stub and helper these need already
exists in `tests/support/table.py`, `tests/support/game.py` and `tests/support/tunnelgoons.py`.

### Line budget, phase 1

| step | file | added | removed |
| --- | --- | --- | --- |
| 1 | `turn/run.py` (note-drop) | +2 | −1 |
| 2 | `engines/base.py` | +2 | −0 |
| 3 | `engines/seam.py` | +15 | −0 |
| 4 | `tunnelgoons/engine.py` | +1 | −0 |
| 5 | `turn/run.py` (clock wiring) | +11 | −3 |
| 6 | `app/runtime.py` | +7 | −2 |
| 7 | `config.py` | +2 | −0 |
| 9 | `scenes/engine.py` | +9 | −0 |
| | **`src` total** | **+49** | **−6** |
| 8 | `qa/s_settings.py` | +1 | −0 |
| | `tests` | ~+145 | ~−0 |

`src` lands near 10,063, `qa` at 1,760. 659 tests before, about 666 after. Zero goldens move: the
scripted golden turn plays one turn at tempo 4 so no tick fires, and the worldsmith goldens build
a fresh state with the flag down so the nudge does not appear. Step 1 changes no golden either —
that turn has no pending decision, so it drains as before.

## Phase 2: the rooms tool, the ELSEWHERE section, the arm guard and the two goldens

About **+148 / −1** lines in `src`, **+141** in `tests`, plus two markdown files that fall in no
count. Exactly two goldens regenerate.

### Steps

1. **`src/aidm/engines/rooms/tools.py` — the description and the schema.** The description string
   lands verbatim in a regenerated golden, so it is fixed here, beside `MOVE`, `MOVE_ITEM` and
   `UNLOCK_WAY`:

   ```python
   MEANWHILE = (
       "Time has passed where the player is not. Move a dweller, move a loose item, and shut a "
       "way they know — any combination, in one call, while ELSEWHERE is shown."
   )
   ```

   Then the model. The specification fixes the field set, and the six-field shape is **kept**: any
   combination of the three powers, in one call, which spends the flag either way (decisions 9 and
   13).

   ```python
   class Meanwhile(Frozen):
       dweller_id: Slug | None = None
       dweller_to: Slug | None = None
       item_id: Slug | None = None
       item_to: Slug | None = None
       shut_from: Slug | None = None
       shut_to: Slug | None = None
   ```

   Give each field a `Field(default=None, description=...)` in the style of the neighbours: the
   dweller and where they walk to, the loose item and where it ends up, and the two ends of the
   way that shuts. Then one `model_validator(mode="after")` over the three pairs — one loop, not
   three checks:

   ```python
   @model_validator(mode="after")
   def _paired(self) -> Self:
       pairs = (
           (self.dweller_id, self.dweller_to),
           (self.item_id, self.item_to),
           (self.shut_from, self.shut_to),
       )
       for first, second in pairs:
           if (first is None) != (second is None):
               raise ValueError("each of the three pairs takes both ends or neither")
       if all(first is None for first, _ in pairs):
           raise ValueError("give a dweller, an item or a way to shut")
       return self
   ```

   A validator raises `ValueError`; `parse` turns it into the refusal. The module gains
   `model_validator` on the pydantic import and `Self` from `typing`. **+34 / −1.**

2. **`src/aidm/engines/rooms/world.py` — the one destination method.** Add to `RoomWorld`, beside
   `map_so_far`:

   ```python
   def elsewhere(self) -> list[Place]:
       """Visited, de-duplicated in order, minus where the player stands."""
       seen: dict[Slug, Place] = {}
       for place_id in self.visits:
           if place_id != self.current.id:
               seen.setdefault(place_id, self.require_place(place_id))
       return list(seen.values())
   ```

   This is the single source of legal destinations, and **three callers share it**: the
   `ELSEWHERE` renderer (step 3), the arm guard (step 4) and the tool's destination refusals
   (step 5). They cannot drift.

   Decision 15 applies to the **tool** as well as the section: the master is shown these places
   and may target only these. Without it the master would guess ids it was never shown and eat
   `UNKNOWN_ID` on most armed turns, and a move into a place the player never returns to is a
   write nobody reads. **+8 / −0.**

3. **`src/aidm/engines/rooms/world.py` — the section's renderer.** Add beside `place_lines` and
   `ways_lines`:

   ```python
   def elsewhere_lines(self) -> str:
       return lines_of(
           f"- {place.tag} — "
           + (", ".join(thing.tag for thing in self.things_at(place.id)) or "(nobody, nothing)")
           for place in self.elsewhere()
       )
   ```

   `map_so_far()` is close but worldsmith-shaped (descriptions, the full id list). **Do not widen
   it.** The split is kept: `elsewhere()` has three callers and `elsewhere_lines()` matches
   `place_lines`/`ways_lines`. **+7 / −0.**

4. **`src/aidm/engines/rooms/world.py` — the arm guard's predicate.** The clock must not arm when
   there is nowhere legal to move, and an empty `elsewhere()` is not the only such state: a
   non-empty one that no unlocked directed way reaches refuses just as hard. Add beside
   `elsewhere`:

   ```python
   def can_move_offscreen(self) -> bool:
       """Something the master could move, and a visited place offscreen to move it to."""
       here = self.current.id
       away = {place.id for place in self.elsewhere()}
       if not away:
           return False
       if any(item.on not in (here, self.player.id) for item in self.items.values()):
           return True
       return any(
           way.to in away
           for npc in self.npcs.values()
           if npc.alive and npc.place != here
           for way in self.ways.get(npc.place, ())
           if not way.locked
       )
   ```

   It answers the two powers that need a destination. Shutting a way is not counted;
   see "Open concerns". **+12 / −0.**

5. **`src/aidm/engines/rooms/world.py` — `RoomWorld.meanwhile`, the work and the facts.** A world
   method, per CLAUDE.md: it changes the fields and writes the facts; the engine's tool method
   only forwards. Three module constants first, beside the family's others, so the told trace and
   the card are written once:

   ```python
   NOTHING_OFFSCREEN = "nothing has moved offscreen yet"
   MOVES_OFFSCREEN = "something moves where the player cannot see"
   MOVED_CARD = "Elsewhere, something moves."
   ```

   One private helper, which is where every destination refusal lists the legal places, the way
   `move` already lists the ways out:

   ```python
   def _offscreen_place(self, place_id: Slug) -> Place:
       away = self.elsewhere()
       found = next((place for place in away if place.id == place_id), None)
       if found is None:
           options = ", ".join(place.name for place in away) or "(none)"
           raise Refusal(f"{place_id!r} is not a place the player has walked away from: {options}")
       return found
   ```

   Then the method. Signature, keyword-only, each argument optional:

   ```python
   def meanwhile(
       self,
       *,
       dweller_id: Slug | None,
       dweller_to: Slug | None,
       item_id: Slug | None,
       item_to: Slug | None,
       shut_from: Slug | None,
       shut_to: Slug | None,
   ) -> list[Fact]:
   ```

   Open by refusing an unarmed clock with `NOTHING_OFFSCREEN`, then apply each given pair in order
   — dweller, item, way — collecting one hidden fact per thing moved, and close with exactly one
   told fact.

   **The dweller, resolved exactly.** `require_member_here` is the wrong helper: it refuses anyone
   who is *not* at `current.id`, the opposite of what is wanted. `Dungeon.require` is wrong too:
   it returns `Person | Prop | Place`, so a place or item id would pass and then need narrowing.
   Read the npc dict directly, which both narrows for basedpyright and rejects a non-dweller id:

   ```python
   npc = self.npcs.get(dweller_id)
   if npc is None:
       raise Refusal(UNKNOWN_ID.format(entity_id=dweller_id))
   if not npc.alive:
       raise Refusal(IS_DEAD.format(name=npc.name))
   if npc.place == self.current.id:
       raise Refusal(f"{npc.name} stands with the player; that is not offscreen")
   destination = self._offscreen_place(dweller_to)
   way = self.way(npc.place, destination.id)
   if way is None or way.locked:
       raise Refusal(f"no unlocked way leads from {npc.place!r} to {destination.name}")
   ```

   `UNKNOWN_ID` and `IS_DEAD` are already imported in this module. `Way.known` does **not** gate
   the walk: a dweller walks ways the player has not found. **There is no "travels with the
   player" refusal** — `RoomWorld._playable` pins every party member to `current.id`, so the
   "stands with the player" refusal above already covers them.

   The item, then the way, with the same shape:

   - the item is unknown → `UNKNOWN_ID`; `item.on` is the player or their place → refused.
   - **the item's holder is here with the player → refused.** An item on a dweller carries
     `item.on == <dweller id>`, not a place, so the refusal above does not catch it, and an item
     in the hands of an npc standing beside the player would otherwise pass every check — the
     master could lift it while the player watches. Resolve the holder through `world.here()`,
     the way `require_item_here` already does (`rooms/world.py:183`). An item on a dweller who is
     *elsewhere* stays legal: see "Open concerns" 2.
   - `item_to` goes through `_offscreen_place`.
   - the way from `shut_from` to `shut_to` does not exist, is already locked, or is **not
     `known`** → refused; shutting a door the player never found is invisible.
   - either end of that way is the player's place → refused. They would see it shut, or be walled
     in on the spot.

   Shutting locks the one directed `Way` named, matching `unlock_way`, which unlocks one
   direction. Stranding is accepted, not guarded: `unlock_way` already exists for a way out of
   wherever the player stands, so a shut door reroutes rather than traps.

   **The leak — read this before writing the method.** Do not copy `move_item`'s shape for the
   facts. `move_item` opens with `facts = item.reveal()`, and `reveal()` sets `known = True`
   *before* building the fact, so what comes back is `told=True` and names the item. This method
   must call **no** `reveal()`, and must not use `Thing.fact()` — that sets `told=self.known`, so
   a dweller the player has already met would have their offscreen move narrated to them. Build
   the facts by hand; `Fact.told` defaults to false, so the hidden ones are one line each:

   ```python
   facts.append(Fact(trace=f"{npc.name} walks to {destination.name}"))   # one per thing moved
   facts.append(Fact(trace=MOVES_OFFSCREEN, told=True, card=MOVED_CARD))  # exactly one, at the end
   ```

   A card cannot be hidden from the narrator: `cards()` needs `told=True`, and
   `traced(facts, told_only=True)` feeds the narrator off the same flag. There is no third state.
   The told trace stays exactly as written so the narrator can suggest unease and cannot name what
   changed. Decision 14: **one fixed card string**, appended only when something actually moved —
   a call is never empty, since the validator refuses one, so in practice this fact always lands,
   but write it off the collected facts and not off the arguments.

   Clear `self.meanwhile_due = False` before returning: the flag is spent by a successful call,
   and `RoomEngine.tick` clears it a turn later otherwise. **+62 / −0** (4 constants, 8 helper,
   50 method).

6. **`src/aidm/engines/rooms/engine.py` — the heading, the tick override, the section and the
   tool.** Five edits, and **no note**: the heading carries the instruction, so there is no
   `MEANWHILE_NOTE` and no notes channel in this feature at all.

   - One module constant beside `MORE_MAP` and `MAP_UNWRITTEN`, matching how
     `HIDDEN HERE (the player has not found these)` already reads in `master_sections`:

     ```python
     ELSEWHERE = "ELSEWHERE (time has passed; you may move what the player cannot see)"
     ```

     Instruction and data now arrive together or not at all: the section renders only when armed,
     and when it renders it says what the master may do about it.

   - The override, layered on the seam's, with the arm guard first:

     ```python
     def tick(self, draft: G, *, counted: bool, enabled: bool) -> None:
         world = self.world_of(draft)
         if not world.meanwhile_due and not world.can_move_offscreen():
             return
         was_armed = world.meanwhile_due
         super().tick(draft, counted=counted, enabled=enabled)
         if was_armed and counted and enabled:
             world.meanwhile_due = False  # the armed turn is spent; one chance, not several
     ```

     The guard returns **before** `super()`, so `turns_played` is not spent on a turn the flag
     could not be used: the count is kept and the clock retries on the next counted turn. It is
     safe against the switch too — the only thing `super()` does with `enabled` false is clear the
     flag, and the guard only fires while the flag is already down.

     What is left, in three lines: the clock fires this turn → flag up and `ELSEWHERE` renders
     next prompt. The armed turn ends, counted → flag down, which is what stops `ELSEWHERE`
     rendering forever. The armed turn ends, not counted → flag stays up. There is no fourth row
     any more; the note it guarded is gone.

   - In `master_sections`, after WAYS OUT, the section as one ternary — no private renderer for a
     single expression:

     ```python
     *(((ELSEWHERE, world.elsewhere_lines()),) if world.meanwhile_due else ()),
     ```

     Only when `meanwhile_due` is true, so between ticks the master's prompt is byte-identical to
     today.

   - In `master_tools`, append last, after `move`, so no existing schema entry shifts:
     `master_tool("meanwhile", MEANWHILE, Meanwhile, self.meanwhile)`.

   - The forwarding method beside `move`:

     ```python
     def meanwhile(self, draft: G, args: Meanwhile, _rng: Random) -> list[Fact]:
         return self.world_of(draft).meanwhile(
             dweller_id=args.dweller_id,
             dweller_to=args.dweller_to,
             item_id=args.item_id,
             item_to=args.item_to,
             shut_from=args.shut_from,
             shut_to=args.shut_to,
         )
     ```

   The tool rolls no dice and starts no process, so the turn stays deterministic and offline.
   No new UI component: `ui/game.py` renders the card like every other one. **+25 / −0.**

7. **`src/aidm/engines/rooms/rules.md` — one short section.** Append after "The party": a
   `## Meanwhile` heading, three or four sentences — what the tool is for, its three powers (move
   a dweller, move a loose item, shut a way the player knows), that every destination must be a
   place the player has walked and never the place they stand in, and that it is callable only on
   a turn ELSEWHERE is shown. `scenes/rules.md` is untouched. Markdown: outside every line count.
   **+6.**

8. **`docs/TUNNEL-GOONS.md` — the tool list.** "The tools" enumerates every rooms tool the engine
   offers, and a missing entry is a doc that lies. Add one bullet after the `move` bullet:
   `meanwhile` — move a dweller, move a loose item and shut a known way, offscreen, on a turn
   ELSEWHERE is shown. Markdown: outside every line count. **+1.**

9. **`tests/engines/test_rooms.py` — the fixture and the tool-order assertion.** The fixture as it
   stands **cannot exercise the tool**: `WARDEN` starts at `GATE`, the ways are `GATE→YARD`,
   `YARD→CELLAR`, `YARD→WELL` (locked) and `CELLAR→WELL`, all one-way, and `MapDraft` defines
   **no items at all**. After one `move` to `YARD`, `elsewhere() == [GATE]` and `WARDEN` is
   already there, so every dweller pair is refused. Two edits fix it:

   - `_scenario()` gains one `Prop`, lying in `YARD` so no existing assertion about `GATE`'s
     contents moves: a `LANTERN` module constant and
     `items={LANTERN: Prop(id=LANTERN, name="Lantern", brief="A dim lantern", known=False,
     on=YARD)}` on the `MapDraft`. `Dungeon._consistent` accepts it: `YARD` is a place. ~5 lines.
   - In `test_the_familys_tools_are_offered_in_order`, add `"meanwhile"` after `"move"`. +1 line.

   **Two moves, not one.** The tool tests walk `GATE→YARD→CELLAR`, which leaves
   `visits == [GATE, YARD, CELLAR]`, `current == CELLAR` and `elsewhere() == [GATE, YARD]`. That
   state gives all three powers something legal: `WARDEN` at `GATE` walks `GATE→YARD`;
   the lantern at `YARD` moves to `GATE`; and `GATE→YARD`, walked and so `known`, unlocked, with
   neither end at `CELLAR`, is shuttable. **+6 / −0.**

10. **The two goldens.** Regenerate, then check what moved:

    ```bash
    AIDM_GOLDEN_REGEN=1 uv run pytest tests/core
    git status --short tests/core/fixtures
    uv run pytest
    ```

    Exactly two files may appear, both tunnelgoons:

    - `tests/core/fixtures/schemas/tunnelgoons/master_tools.json` — the new rooms tool, one entry
      appended after `move`, carrying the `MEANWHILE` text of step 1 and the six field
      descriptions verbatim.
    - `tests/core/fixtures/prompts/tunnelgoons/master.txt` — the `rooms/rules.md` edit reaching
      `Engine.instructions`, printed under THE RULES OF THIS GAME.

    Goldens that must **not** move: everything under `loner3e`, `breathless` and `twentyfourxx`;
    tunnelgoons's `narrator.txt` and `worldsmith.txt`; and every file under
    `tests/core/fixtures/turn/`. **If a golden master prompt grows an `ELSEWHERE` section, the
    clock is wrong** — the scripted turn plays one turn at tempo 4, so no tick fires. Read it
    of both regenerated files before committing them; a golden is a drift detector, not a fixture
    to refresh past. **2 files changed.**

### Tests this phase adds

Behaviours 4, 5, 6 and 7 of the nine, plus the arm guard. All in `tests/engines/test_rooms.py`, on
the `SixthEngine` fixture as step 9 leaves it. Set `meanwhile_due` on the draft by hand rather than
turning the clock six times.

- **4 — the armed flag is down after one further counted turn, and survives an uncounted one.**
  Call `engine.tick(draft, counted=..., enabled=True)` directly from a hand-armed state: tick
  counted and assert the flag is down; from the armed state again, tick uncounted and assert the
  flag is still up. No note is written by anything in this feature, so nothing asserts on
  `draft.notes`. ~25 lines.
- **the arm guard — nothing movable, nothing lost.** At the start the player is at `GATE`,
  `elsewhere()` is empty and `can_move_offscreen()` is false. Set `turns_played = 3` by hand, tick
  counted, and assert `turns_played` is still 3 and the flag still down. Then move twice, tick
  counted, and assert it reaches 4: the count was kept and the clock retried. ~20 lines.
- **5 — rooms `meanwhile` moves a dweller, moves an item and shuts a way, and refuses each listed
  case.** One test for the three powers in a single call through
  `change(engine, draft, "meanwhile", ...)` after `GATE→YARD→CELLAR`, asserting `WARDEN.place`,
  the lantern's `on` and the `GATE→YARD` way's `locked`; and one grouped test walking the refusal
  list through `refused(...)` — an unarmed clock, an unknown dweller, a place id given as a
  dweller, a dweller at the player's place, a destination the player has not walked, the player's
  own place as a destination, a way that is not `known`, and a way with an end at the player's
  place — asserting that the destination refusals name the legal places. ~60 lines.
- **6 — the offscreen change never reaches the narrator.** On the facts a successful call returns:
  every fact naming a thing is `told=False`, exactly one fact is `told=True`, its card is
  `MOVED_CARD`, and its trace names no entity in the world. ~15 lines.
- **7 — `ELSEWHERE` is absent when the flag is down and present when it is up.** Assert on
  `dict(engine.master_sections(state))`: no `ELSEWHERE` key on a fresh state, the key present and
  naming the visited place once `meanwhile_due` is set. ~15 lines.

### Line budget, phase 2

| step | file | added | removed |
| --- | --- | --- | --- |
| 1 | `rooms/tools.py` | +34 | −1 |
| 2 | `rooms/world.py` (`elsewhere`) | +8 | −0 |
| 3 | `rooms/world.py` (`elsewhere_lines`) | +7 | −0 |
| 4 | `rooms/world.py` (`can_move_offscreen`) | +12 | −0 |
| 5 | `rooms/world.py` (`meanwhile`) | +62 | −0 |
| 6 | `rooms/engine.py` | +25 | −0 |
| | **`src` total** | **+148** | **−1** |
| 7, 8 | `rules.md`, `docs/TUNNEL-GOONS.md` | +7 | −0 (no count) |
| 9 | `tests/engines/test_rooms.py` (fixture, order) | +6 | −0 |
| | `tests` (new behaviours) | ~+135 | ~−0 |

`src` lands near 10,210 against the 10,020 it started at, `tests` near 10,698, `qa` at 1,760.
About 672 tests at the end. Two golden files rewritten, thirteen untouched.

## Do not do this

Each of these was argued in full and decided. A later implementer or reviewer must be able to see
they were chosen, not missed.

- **No `MEANWHILE_NOTE`, and no notes channel for this feature.** The `ELSEWHERE` heading carries
  the instruction, so instruction and data arrive together or not at all, exactly as
  `HIDDEN HERE (the player has not found these)` already works. No `draft.note` call in
  `RoomEngine.tick`, no note constant, no "was the note written twice" branch. Phase 1 step 1 is a
  bug fix in the notes plumbing and is not this feature's use of it.
- **No discovery of the change (decision 17, silent discovery).** The Trail panel lists place names
  only, and the narrator on arrival gets the static `place.description` plus who is present *now*.
  Nothing names who is missing, and that is the payoff: the player notices by remembering. **No
  discovery fact, no per-entity "last seen here" stamp, no changed-since-visit compare, no widening
  of the arrival narration.** Shutting a way is the one power that lands without any of that, which
  is why it is in scope.
- **No scenes tool (decision 10).** Scenes has no offscreen world — `apply_scene` replaces the run
  and the map is gone. The family needs pacing, not simulation. **No scenes tool, no
  `OFFSCREEN CAST` section, no scenes master note, no `scenes/rules.md` edit.** Phase 1 step 9 is
  the whole of the scenes work.
- **One fixed card string (decision 14).** Considered and rejected: naming the place in the card,
  and varying the wording on the rng. The card is `"Elsewhere, something moves."`, always, and only
  when something actually moved.
- **The clock stays on `World`, not on `RoomWorld`.** A reviewer argued it belongs on `RoomWorld`
  because scenes only reads it for one intent line. **Overruled**: `SceneEngine.render_next` reads
  `meanwhile_due` and `install` clears it, so scenes does read it, and hoisting the counter later
  would be the larger change.
- **No `armed`/`spend` hooks on the seam.** Two abstractions only one family uses is what
  CLAUDE.md forbids; `RoomEngine` overrides `tick` and layers, the shape `master_tools` already
  uses. The arm guard of phase 2 step 6 is part of that override, not a new seam hook.
- **Do not tick from `Engine.close`, and do not use `Turn.landed()`.** `close` also runs for
  interjections and worldsmith writes; `landed()` is true with zero facts whenever `pending` is
  set, which the level-up cascade sets on turns the master never played.
- **Do not widen `map_so_far()`** to serve the `ELSEWHERE` section. It is worldsmith-shaped.
- **Do not narrow the six-field schema, and do not merge `elsewhere()` into `elsewhere_lines()`.**
  The schema is decisions 9 and 13 spelled out; `elsewhere()` has three callers and
  `elsewhere_lines()` matches `place_lines` and `ways_lines`.
- **Do not regenerate a golden outside phase 2 step 10**, and do not regenerate one that step does
  not name.

## Open concerns

Four. None is a reason to deviate; they are named so the implementer does not think they were
missed. The old concern about an armed clock with nowhere to point is gone — the arm guard of
phase 2, steps 4 and 6, is the answer to it.

1. **The arm guard does not count the shut-a-way power.** `can_move_offscreen()` answers for
   dwellers and loose items, the two powers that need a destination. A state where no dweller can
   walk and no item is offscreen, but a known unlocked way with neither end at the player exists,
   will not arm, although a shut would have been legal. It under-arms, which is the safe
   direction, and closing it costs four more lines in the same method:
   `any(way.known and not way.locked and from_id != here and way.to != here ...)`. That is the
   overflow past the twelve-line budget the maintainer set for A3, recorded rather than spent.

2. **An item carried by an offscreen dweller is movable, and that is allowed.** The refusal list
   for `item_id` covers unknown, on the player, and at the player's place. It does not refuse an
   item held by a dweller who is elsewhere, though the power is described as moving "one loose
   item". Taken literally, the master may lift an idol out of an offscreen thief's hands and leave
   it in a room. That reads as a fine offscreen event and is invisible to the player, so it stays.

   **This does not extend to a holder who is here.** An item on a dweller carries
   `item.on == <dweller id>`, not a place, so the "at the player's place" refusal does not catch
   it and an item in the hands of an npc standing beside the player would pass every check — the
   master could lift it while the player watches, which is the exact leak this design exists to
   prevent. **Step 5 must refuse an item whose holder is at `world.current.id`**, resolving the
   holder through `world.here()` the way `require_item_here` already does (`rooms/world.py:183`).
   One condition, one refusal message, one test case. This is a fix, not a concern.

3. **The guard is a second method, not one.** The maintainer asked for one `RoomWorld` method
   shared by the arm guard, the renderer and the refusals. `elsewhere()` is that method and all
   three reach it, but a single method cannot both return places to print and answer a yes/no
   about movers, so `can_move_offscreen()` sits on top of it. The destination set still lives in
   one place, so the three cannot drift.

4. **A blocked clock does not accumulate.** With nothing movable the guard returns before
   `super()`, so `turns_played` is kept but does not rise. A long stretch with nowhere to move
   therefore delays the first meanwhile by exactly that many turns rather than banking them. That
   is the requirement as written — the count is not lost and the clock retries — and banking them
   would fire the flag the instant a second place is visited, which is worse.
