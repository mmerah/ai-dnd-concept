# PLAN: Meanwhile, in two phases

Every few turns the world moves where the player is not looking. Code keeps a turn clock on the
shared `World`; when it fires it arms a flag, and each family spends that flag its own way. In
**rooms** the game master is told, is shown the places the player has walked, and may call one
`meanwhile` tool to move a dweller, move a loose item, and shut a door. The player gets one vague
card. In **scenes** the flag adds one nudging line to the next worldsmith scene write, and that
write clears it.

Phase 1 is the clock itself: two fields on `World`, `Engine.tick`, the `counted` wiring through
`Turn.finish`, the settings switch, the note-drop fix, and the scenes nudge. Phase 2 is the rooms
half: the `meanwhile` tool, the `ELSEWHERE` section, `rooms/rules.md`, and the two goldens those
move. The split is chosen so that **phase 1 leaves the suite green on its own with the feature
inert in rooms** — nothing in `engines/rooms/` reads `meanwhile_due` until phase 2, so an armed
flag there changes no prompt, no tool surface and no golden.

Counted against the real code, the plan adds about **130 lines** to `src`, from 10,020 to about
10,150: phase 1 about +37, phase 2 about +93. `tests` grows about +230, from 10,412. This feature
adds; no step here deletes anything but the three lines it rewrites.

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
2. Change a shape and its tests in the same step. Two existing tests change: the rooms tool-order
   assertion (phase 2, step 7) and nothing else. If a test you did not touch fails, the step is
   wrong.
3. Golden files live in `tests/core/fixtures/`. **Phase 1 moves none of them.** Phase 2 moves
   exactly two, both tunnelgoons, and phase 2 step 8 is the only place a regeneration is allowed.
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

## Phase 1: the clock, the switch, the note-drop fix and the scenes nudge

About **+37** lines in `src`, **+105** in `tests`. No golden moves. At the end of this phase the
clock counts and arms on every engine, scenes spends the flag, and rooms ignores it.

### Steps

1. **`src/aidm/engines/base.py` — the two fields on `World`.** Add to `World`, below `party`:

   ```python
   turns_played: int = 0        # counted turns since the last fire
   meanwhile_due: bool = False  # the clock has fired and nothing has spent it yet
   ```

   Both defaulted, so existing saves keep loading: `Mutable` sets `extra="forbid"`, which rejects
   unknown keys in a file, not keys the file omits. `SceneWorld` (`scenes/world.py`) and
   `RoomWorld` (`rooms/world.py`) both inherit `World` already — no new base class, no new
   abstraction. No validator: any non-negative `int` and any `bool` is a state the clock can
   reach. **+2 / −0.**

2. **`src/aidm/engines/seam.py` — the tempo, its check, and `Engine.tick`.** Three edits to
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
   uses. **+14 / −0.**

3. **`src/aidm/engines/tunnelgoons/engine.py` — the override.** In the class attribute block of
   `TunnelGoonsEngine`, beside `art_style` and `look`:

   ```python
   meanwhile_turns = 4
   ```

   **+1 / −0.**

4. **`src/aidm/turn/run.py` — the `meanwhile` field, `finish(played=)`, and the note-drop fix.**
   Three edits to `Turn`:

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

   - **Decision 18, the note-drop fix.** `begin` currently drains `draft.notes` unconditionally,
     and `runtime._turn` then skips the master when an answer re-suspended a decision. The drained
     notes are discarded and no model ever reads them — it already loses the `PAUSED_TO_ASK` note
     that `_consume` wrote a line earlier. Drain only when the master will run. The existing
     comment stays; the two lines under it become three:

     ```python
     # Notes are read once; a note a tool writes after this steers the next turn.
     if turn.draft.pending is None:
         turn.notes, turn.draft.notes = turn.draft.notes, []
     ```

     A re-suspended turn keeps its notes for the next turn, where they accumulate with that turn's
     own. Both pauses happened and the master should read both.

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
     cascade. **+7 / −2.**

5. **`src/aidm/app/runtime.py` — the plumbing, mirroring `interjections` exactly.** Four edits:

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

   Nothing in `engines/` reads settings — the engine only ever sees the `enabled` argument.

   Known and accepted undercount: `act()` reaches `_turn` only when `_grow` returned True, so a
   player action whose worldsmith write failed ticks nothing. Left alone; it is rare and erring
   slow is the safe direction. **+7 / −1.**

6. **`src/aidm/config.py` — the player switch.** In `Settings`, beside `interjections`:

   ```python
   # The world moves offscreen every few turns; off stops the clock and disarms it.
   meanwhile: bool = True
   ```

   No UI code at all: the settings page builds its widgets from the model, and a `bool` renders as
   a switch. **+2 / −0.**

7. **`src/aidm/engines/scenes/engine.py` — the worldsmith nudge, and nothing else.** Two edits:

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
   `SceneEngine` does **not** override `tick`. **+8 / −0.**

### Tests this phase adds

Behaviours 1, 2, 3, 8 and 9 of the specification's nine. Behaviour and boundaries only; no test
here asserts prose.

- **1 — the clock counts a played turn that landed facts, and ignores a turn that landed none.**
  `tests/turn/test_turn.py`. Two turns through `play_turn` on the loner3e table: one with a tool
  call that lands a fact, asserting `state.payload.turns_played == 1`; one with no calls,
  asserting it stays where it was. ~25 lines.
- **2 — the clock does not count a turn the master never played.** In
  `tests/tunnelgoons/test_play.py`, asserted directly against the level-up cascade, which is the
  real path that would double-count:
  drive `level_up` to open its decision, answer with an option whose resolver re-suspends on the
  next party member, and assert `turns_played` did not move and that no master prompt was spawned
  for that turn. Build it on `open_table(..., engine_id=TUNNELGOONS, state_type=TunnelGoonsGame)`
  and `play_turn(table, Answer(option_id=...))`. ~30 lines.
- **3 — the clock is inert and clears the flag when the switch is off.** In
  `tests/turn/test_turn.py`.
  Set `table.service.meanwhile = False`, arm the flag by hand on a saved state, play a turn that
  lands facts, and assert `turns_played` did not move and `meanwhile_due` is false. ~20 lines.
- **8 — the scenes nudge appears in `render_next` only when armed, and `install` clears the
  flag.** `tests/engines/test_scenes.py`, beside
  `test_the_next_scene_prompt_carries_the_scene_as_it_stands`, which already renders a prompt from
  a built state. Assert the nudge's first clause is absent from `render_next` on a fresh state,
  present once `meanwhile_due` is set, and that `install` leaves the flag down. ~20 lines.
- **9 — decision 18: a turn whose answer re-suspends keeps its notes for the next turn.**
  `tests/turn/test_decisions.py`, beside `test_an_answer_that_re_suspends_spawns_no_master`, which
  already sets up the re-suspending option (`CHAINING`). Assert the state after that turn still
  carries the `PAUSED_TO_ASK` note in `draft.notes`, and that the following turn's master prompt
  carries it under NOTES FROM THE RULES. ~15 lines.

No new fixture file, no new support module: every table, engine stub and helper these need already
exists in `tests/support/table.py`, `tests/support/game.py` and `tests/support/tunnelgoons.py`.

### Line budget, phase 1

| | added | removed |
| --- | --- | --- |
| `src` | ~+40 | ~−3 |
| `tests` | ~+110 | ~−0 |

`src` lands near 10,057. 659 tests before, about 665 after. Zero goldens move: the scripted golden
turn plays one turn at tempo 4 so no tick fires, and the worldsmith goldens build a fresh state
with the flag down so the nudge does not appear. Decision 18 changes no golden either — that turn
has no pending decision, so it drains as before.

## Phase 2: the rooms tool, the ELSEWHERE section, the rules and the two goldens

About **+93** lines in `src`, **+125** in `tests`. Exactly two goldens regenerate.

### Steps

1. **`src/aidm/engines/rooms/tools.py` — the tool schema.** A description constant beside `MOVE`,
   `MOVE_ITEM` and `UNLOCK_WAY`, and the model. The specification fixes the field set:

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
   way that shuts. Add a `model_validator(mode="after")` that raises `ValueError` (a validator
   raises `ValueError`; `parse` turns it into the refusal) when no pair is complete, and when any
   pair is half given — an id with no partner, or the reverse.

   Six optional fields is the widest tool schema in this codebase. It is the direct consequence of
   decisions 9 and 13: any combination of the three powers, in one call, which spends the flag
   either way. The specification permits one deviation here and only here: *if a narrower shape
   reads better and keeps all three powers in one flag-spending call, take it and record the
   change in `PROGRESS.md`.* Nothing else in this plan is open in that way. **+30 / −0.**

2. **`src/aidm/engines/rooms/world.py` — the legal destinations, in one place.** Add to
   `RoomWorld`, beside `map_so_far`:

   ```python
   def elsewhere(self) -> list[Place]:
       """Visited, de-duplicated in order, minus where the player stands."""
       seen: dict[Slug, Place] = {}
       for place_id in self.visits:
           if place_id != self.current.id:
               seen.setdefault(place_id, self.require_place(place_id))
       return list(seen.values())
   ```

   Decision 15 applies to the **tool** as well as the section: the master is shown these places
   and may target only these. Without it the master would guess ids it was never shown and eat
   `UNKNOWN_ID` on most armed turns, and a move into a place the player never returns to is a
   write nobody reads. One helper, so the section and the refusals cannot drift. **+8 / −0.**

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
   it.** An empty `elsewhere()` renders `- (none)` through `lines_of`, the same as WAYS OUT.
   **+7 / −0.**

4. **`src/aidm/engines/rooms/world.py` — `RoomWorld.meanwhile`, the work and the facts.** A world
   method, per CLAUDE.md: it changes the fields and writes the facts; the engine's tool method
   only forwards. Signature, keyword-only, each argument optional:

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

   Open by refusing an unarmed clock, then apply each given pair in order — dweller, item, way —
   collecting one hidden fact per thing moved, and close with exactly one told fact. Refusals, all
   of them `Refusal` (a message a role reads), in this order per pair:

   - `meanwhile_due` is false → *nothing has moved offscreen yet.*
   - the dweller is unknown, dead, or travels with the player.
   - the dweller stands where the player stands — that is not offscreen.
   - `dweller_to` is not in `elsewhere()`, or no **unlocked** way leads there from the dweller's
     own place. `Way.known` does not gate this: a dweller walks ways the player has not found.
   - the item is unknown, is on the player, or lies at the player's place. (An item carried by a
     dweller moves with that dweller for free, so no call is needed for it.)
   - `item_to` is not in `elsewhere()`.
   - the way from `shut_from` to `shut_to` does not exist, is already locked, or is **not
     `known`** — shutting a door the player never found is invisible.
   - either end of that way is the player's place. They would see it shut, or be walled in on the
     spot.

   Every destination refusal **lists the legal destinations**, the way `move` already lists the
   ways out: `", ".join(place.name for place in self.elsewhere()) or "(none)"`. Shutting locks the
   one directed `Way` named, matching `unlock_way`, which unlocks one direction.

   Stranding is accepted, not guarded: `unlock_way` already exists for a way out of wherever the
   player stands, so a shut door reroutes rather than traps.

   **The leak — read this before writing the method.** Do not copy `move_item`'s shape for the
   facts. `move_item` opens with `facts = item.reveal()`, and `reveal()` sets `known = True`
   *before* building the fact, so what comes back is `told=True` and names the item. This method
   must call **no** `reveal()`, and must not use `Thing.fact()` — that sets `told=self.known`, so
   a dweller the player has already met would have their offscreen move narrated to them. Build
   the facts by hand:

   ```python
   Fact(trace="<the real change, named>", told=False)          # one per thing moved
   Fact(trace="something moves where the player cannot see",
        told=True, card="Elsewhere, something moves.")          # exactly one, whatever moved
   ```

   A card cannot be hidden from the narrator: `cards()` needs `told=True`, and
   `traced(facts, told_only=True)` feeds the narrator off the same flag. There is no third state.
   The told trace stays exactly as written above so the narrator can suggest unease and cannot
   name what changed. Decision 14: **one fixed card string**, appended only when something
   actually moved — a call is never empty, since the validator refuses one, so in practice this
   fact always lands, but write it off the collected facts and not off the arguments.

   Clear `self.meanwhile_due = False` before returning: the flag is spent by a successful call,
   and `RoomEngine.tick` clears it a turn later otherwise. **+55 / −0.**

5. **`src/aidm/engines/rooms/engine.py` — the note, the tick override, the section and the tool.**
   Five edits:

   - A module constant beside `MORE_MAP` and `MAP_UNWRITTEN`:

     ```python
     MEANWHILE_NOTE = (
         "Time has passed where the player is not. ELSEWHERE lists the places they have walked; "
         "you may call `meanwhile` once this turn to move a dweller, move a loose item, and shut "
         "a way they know."
     )
     ELSEWHERE = "ELSEWHERE (time has passed; the player is not there)"
     ```

   - The override, layered on the seam's, with this exact order:

     ```python
     def tick(self, draft: G, *, counted: bool, enabled: bool) -> None:
         world = self.world_of(draft)
         was_armed = world.meanwhile_due
         super().tick(draft, counted=counted, enabled=enabled)
         if was_armed and counted and enabled:
             world.meanwhile_due = False          # the armed turn is spent; one chance, not several
         elif world.meanwhile_due and not was_armed:
             draft.note(MEANWHILE_NOTE)           # armed by this very tick
     ```

     Every branch: the clock fires this turn → flag up, note written once. The armed turn ends,
     counted → flag down, which is what stops `ELSEWHERE` rendering forever. The armed turn ends,
     not counted → flag stays up and `not was_armed` guards against a second note. The switch is
     off → `super()` clears the flag and the `elif` sees it down and writes nothing.

   - A private method, used once by `master_sections`, so the render stays a render:

     ```python
     def _elsewhere(self, world: RoomWorld[N, P]) -> Sections:
         return ((ELSEWHERE, world.elsewhere_lines()),) if world.meanwhile_due else ()
     ```

   - In `master_sections`, `*self._elsewhere(world),` after WAYS OUT. Only when `meanwhile_due` is
     true, so between ticks the master's prompt is byte-identical to today.

   - In `master_tools`, append last, after `move`, so no existing schema entry shifts:
     `master_tool("meanwhile", MEANWHILE, Meanwhile, self.meanwhile)`, and the forwarding method
     beside `move`:

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
   No new UI component: `ui/game.py` renders the card like every other one. **+28 / −0.**

6. **`src/aidm/engines/rooms/rules.md` — one short section.** Append after "The party": a
   `## Meanwhile` heading, three or four sentences — what the tool is for, its three powers (move
   a dweller, move a loose item, shut a way the player knows), that every destination must be a
   place the player has walked and never the place they stand in, and that it is callable only on
   a turn the rules say time has passed. `scenes/rules.md` is untouched. **+6 / −0.**

7. **`tests/engines/test_rooms.py` — the tool-order assertion.** In
   `test_the_familys_tools_are_offered_in_order`, add `"meanwhile"` after `"move"`. **+1 / −0.**

8. **The two goldens.** Regenerate, then check what moved:

   ```bash
   AIDM_GOLDEN_REGEN=1 uv run pytest tests/core
   git status --short tests/core/fixtures
   uv run pytest
   ```

   Exactly two files may appear, both tunnelgoons:

   - `tests/core/fixtures/schemas/tunnelgoons/master_tools.json` — the new rooms tool, one entry
     appended after `move`.
   - `tests/core/fixtures/prompts/tunnelgoons/master.txt` — the `rooms/rules.md` edit reaching
     `Engine.instructions`, printed under THE RULES OF THIS GAME.

   Goldens that must **not** move: everything under `loner3e`, `breathless` and `twentyfourxx`;
   tunnelgoons's `narrator.txt` and `worldsmith.txt`; and every file under
   `tests/core/fixtures/turn/`. **If a golden master prompt grows an `ELSEWHERE` section, the
   clock is wrong** — the scripted turn plays one turn at tempo 4, so no tick fires. Read the diff
   of both regenerated files before committing them; a golden is a drift detector, not a fixture
   to refresh past. **2 files changed.**

### Tests this phase adds

Behaviours 4, 5, 6 and 7 of the nine. All in `tests/engines/test_rooms.py`, on the existing
`SixthEngine` fixture there: its `_scenario()` starts the player at `GATE` with the `WARDEN`
dweller in it, so one `move` to `YARD` gives `visits == [GATE, YARD]` and leaves `GATE` as a
visited place that is not the player's — exactly the shape the tool needs. Set `meanwhile_due` on
the draft by hand rather than turning the clock four times.

- **4 — the armed flag is down after one further counted turn, and survives an uncounted one,
  without writing the note twice.** Call `engine.tick(draft, counted=..., enabled=True)` directly:
  arm it, assert the note was written once and `draft.notes` has one entry; tick again counted and
  assert the flag is down; from the armed state tick again uncounted and assert the flag is still
  up and no second note landed. ~35 lines.
- **5 — rooms `meanwhile` moves a dweller, moves an item and shuts a way, and refuses each listed
  case.** One test for the three powers in a single call through `change(engine, draft,
  "meanwhile", ...)`, asserting the dweller's `place`, the item's `on` and the way's `locked`; and
  one parametrized or grouped test walking the refusal list through `refused(...)` — including an
  unvisited destination and the player's own place, and asserting the destination refusals name
  the legal places. ~60 lines.
- **6 — the offscreen change never reaches the narrator.** On the facts a successful call returns:
  every fact naming a thing is `told=False`, exactly one fact is `told=True`, its card is the
  fixed string, and its trace names no entity in the world. ~15 lines.
- **7 — `ELSEWHERE` is absent when the flag is down and present when it is up.** Assert on
  `dict(engine.master_sections(state))`: no `ELSEWHERE` key on a fresh state, the key present and
  naming the visited place once `meanwhile_due` is set. ~15 lines.

### Line budget, phase 2

| | added | removed |
| --- | --- | --- |
| `src` | ~+93 | ~−0 |
| `tests` | ~+126 | ~−1 |

`src` lands near 10,150 against the 10,020 it started at. About 671 tests at the end. Two golden
files rewritten, thirteen untouched.

## Do not do this

Each of these was argued in full and decided. A later implementer or reviewer must be able to see
they were chosen, not missed.

- **No discovery of the change (decision 17, silent discovery).** The Trail panel lists place names
  only, and the narrator on arrival gets the static `place.description` plus who is present *now*.
  Nothing names who is missing, and that is the payoff: the player notices by remembering. **No
  discovery fact, no per-entity "last seen here" stamp, no changed-since-visit compare, no widening
  of the arrival narration.** Shutting a way is the one power that lands without any of that, which
  is why it is in scope.
- **No scenes tool (decision 10).** Scenes has no offscreen world — `apply_scene` replaces the run
  and the map is gone. The family needs pacing, not simulation. **No scenes tool, no
  `OFFSCREEN CAST` section, no scenes master note, no `scenes/rules.md` edit.** Phase 1 step 7 is
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
  uses.
- **Do not tick from `Engine.close`, and do not use `Turn.landed()`.** `close` also runs for
  interjections and worldsmith writes; `landed()` is true with zero facts whenever `pending` is
  set, which the level-up cascade sets on turns the master never played.
- **Do not widen `map_so_far()`** to serve the `ELSEWHERE` section. It is worldsmith-shaped.
- **Do not regenerate a golden outside phase 2 step 8**, and do not regenerate one that step does
  not name.

## Open concerns

Two, both minor, neither a reason to deviate. Named here so the implementer does not think they
were missed.

1. **An armed clock with nowhere to point.** If the clock fires before the player has left their
   first place, `elsewhere()` is empty: the master gets the note and an `ELSEWHERE` section
   reading `- (none)`, and every `meanwhile` call is refused for want of a legal destination. It
   costs one wasted note in the master's prompt and nothing else, and the flag comes down on the
   next counted turn. The specification does not ask for a guard, so this plan adds none; if the
   maintainer wants one, the cheapest is for `RoomEngine.tick` to skip the note when
   `world.elsewhere()` is empty, and it can be added later without touching anything else.

2. **An item carried by a dweller is movable.** The specification's refusal list for `item_id`
   covers unknown, on the player, and at the player's place — it does not refuse an item held by a
   dweller elsewhere, though the power is described as moving "one loose item". Taken literally
   (which this plan does), the master may lift an item out of an offscreen dweller's hands into a
   place. That reads as a fine offscreen event and is invisible to the player either way, so
   nothing here changes; if it is unwanted, one more refusal — the item is on a dweller —
   belongs in step 4's list.
