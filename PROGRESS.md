# PROGRESS

One entry per phase of `PLAN.md`: the counts, the decisions taken off-plan, the review findings
refuted and why, and what is known and accepted.

## Phase 1: one pack, and the saved shape

Counts, `find <dir> -name '*.py' | xargs cat | wc -l`:

| dir   | before | after | change |
| ----- | -----: | ----: | -----: |
| src   |  10506 | 10376 |   −130 |
| tests |  12065 | 11913 |   −152 |
| qa    |   2020 |  2020 |      0 |

Both parts landed as planned. The three worldsmith goldens were regenerated and showed no text
change. Reviewed by two independent Opus reviewers (no `codex` on the machine).

Decisions taken off-plan:

- `Engine.author_pack` loses its `pack_id` positional. Its one reader was `check_addable`, which
  the phase deletes; `Runtime.new_pack` still derives the id against `engine.packs.installed`
  and writes with it. `check_head` builds the pack alone, as `check_body` does; a label that
  makes no id still re-prompts, and a test pins that.
- `ui/create.py` does not import `SRD_PACK` or `AnyEngine`: `tests/core/test_package_boundary.py`
  forbids `ui` from naming `aidm.engines`. The default pack is `Runtime.default_pack`, beside
  `Runtime.default_engine`; `_pack_select(offered, chosen, on_change)` takes the engine's
  `packs.options()` and builds no select when one pack alone is offered.
- `_pack_select` returns nothing: no caller read the select it returned.
- Tests of deleted behaviours went beyond the seven the plan names: the 24XX skill-less
  supplement `select`, the doubled and missing `packs` validators, the "no packs" scene check,
  the two "records the packs it was made with" character tests, `new_scenario`'s `admit`
  refusal, and the two SRD-collision pack tests (`defined_ids` is gone). One new test pins the
  invariant the first of those carried: a written 24XX pack adds no skills to the increase step.

Review findings refuted:

- "`test_choosing_a_pack_refreshes_the_steps…` awaits nothing; make it `def`": a refreshable's
  `refresh()` schedules a NiceGUI background task on the running loop, so the test needs one;
  the reason is now a comment above it.

Known and accepted:

- A game on an Adventure Pack renders that pack's `PACK:` block and special rules alone; the
  SRD's setting block no longer precedes it. One setting per adventure is what the phase asks.
  The shipped scenarios all play `srd`, which is why the goldens did not move.
- `qa/agents.py` has one `basedpyright` error when `qa` is checked explicitly; `pyproject.toml`
  includes `src` and `tests` only, and the error predates this phase.

## Phase 2: the hire flow, and one class per thing

Counts, `find <dir> -name '*.py' | xargs cat | wc -l`:

| dir   | before | after | change |
| ----- | -----: | ----: | -----: |
| src   |  10376 | 10462 |    +86 |
| tests |  11913 | 11964 |    +51 |
| qa    |   2020 |  2020 |      0 |

Both parts landed as planned. The two `master_tools.json` goldens moved by `hire` alone (after
`meanwhile` / after `next_scene`). Reviewed by two independent Opus reviewers (no `codex` on the
machine); every finding was fixed but one, below. `src` is above the +40 estimate because the
strings the reviews sent to one home became constants and reflowed six import blocks; `tests`
grew where the plan expected a cut because the drift test over `unwritten` and the two `Npc`
tests outweigh the two `Sheeted` tests deleted.

Decisions taken off-plan:

- `Engine.unwritten` is a `ClassVar`: it is not generic on `W`, and ruff's `RUF012` refuses a
  mutable class default without one. `SceneEngine`'s `advance` is an `if` chain, not a `match`:
  `DEPARTURE` and `COMPLICATION` are module constants, and a `match` over them needs a guard per
  arm.
- Hire strings keep one home, `engines/tools.py`: `HIRE_PENDING`, `NO_HIRE_TARGET`, `SIGNS_ON`
  beside `HIRE_TOOL`, and `NO_DICE`, `NOT_AN_ACTOR`, `ALREADY_SHEETED` in `engines/base.py`
  beside `UNKNOWN_ID`. The two `hire`/`write_hire` copies and the two worlds' `require_actor`/
  `require_hireable` format them. `WRITES_NO` in `seam.py` is the one text `validate`'s refusal
  and the two `advance` fall-throughs share.
- Tunnel Goons: `sheet_of(actor: Goon | Npc)` and `level_up_decision(actor: Goon | Npc)` are free
  functions in `tunnelgoons/world.py`, not world methods: neither reads the world. The level-up
  body is `GoonSheet.level_up(ability, boost, hp) -> str`, the sheet owning the fields it bumps;
  `Goon.level` and `Npc.level` are two lines each over it. `Goon.level_decision` and
  `Npc.level_decision` went: the engine calls the free function.
- A third golden moved: `tests/core/fixtures/schemas/tunnelgoons/worldsmith_answer.json`, for
  the `Npc` docstring the plan prescribes and `hp` now declared before `sheet`, the order `Goon`
  has and the plan's step 4 lists. Intended drift, checked by eye.
- `tests/twentyfourxx/test_world.py::test_carried_spells_item_notes` became a test of
  `Crewmate.line()`, its one reader once `carried()` was inlined.

Review findings refuted:

- "Declare `sheet` before `hp` on `Npc` so the worldsmith golden does not move": the golden moves
  for the docstring regardless, and `hp` before `sheet` is `Goon`'s order and the plan's.

Known and accepted:

- The phase's "Done when" grep for `hireable` matches `require_hireable`, which the phase itself
  puts on the two hiring worlds; the grep is read minus that name.
- `Goon` has no `required()` beyond `Person`'s: `required_unmet` reads cast pools, never the
  player.

## Phase 3: the seam

Counts, `find <dir> -name '*.py' | xargs cat | wc -l`:

| dir   | before | after | change |
| ----- | -----: | ----: | -----: |
| src   |  10462 | 10457 |     −5 |
| tests |  11964 | 11795 |   −169 |
| qa    |   2020 |  2020 |      0 |

All three parts landed as planned; no golden moved. Reviewed by two independent Opus reviewers
(no `codex` on the machine). `src` is far off the −150 estimate: the plan counted the test
engines' support under `src`, where they never were (`tests/support/fifth.py` and `sixth.py` are
the −169 in `tests`), and `rooms/engine.py`'s body moved onto `TunnelGoonsEngine` line for line.
The `src` cut left is the two hooks, `RoomEngine`'s class header and `starting_items`, against
24XX's two whole methods.

Decisions taken off-plan:

- `Engine.player_of` is abstract; the check every engine makes is one concrete helper,
  `Engine.player_as(character, sheet)`: the id/known refusal, one `isinstance`, the
  "is not a … sheet" refusal, the copy. Each engine's `player_of` is one line over it. Both
  reviews found the plan's three copies of the override and its string.
- `EXTEND`, `MORE_MAP` and `MAP_UNWRITTEN` sit in `tunnelgoons/engine.py`, not `rooms/tools.py`:
  an operation slug, a decision option and a failed-write fact are not tools, and that is where
  the scene family keeps `DEPARTURE`, `MOVE_ON` and `WAY_UNWRITTEN`. `OPENING_SECTIONS` stays in
  `rooms/worldsmith.py` beside `MAP_ASK`, as the scene family's sits beside `OPENING`.
- `TunnelGoonsEngine.extend` is inlined into `advance`: two statements, one caller.
- `test_the_clock_does_not_arm_with_nothing_to_move_and_keeps_the_count` seeds `turns_played = 1`:
  the sixth engine's `tempo` was 6, Tunnel Goons' is 4, and the old seed of 3 reached it.
- `tests/engines/test_scenes.py` builds its two castless drafts as `NextProposal[Person]`, the
  type `install` now takes; `Loner3eCast` is invariant in `SceneProposal`.

Review findings refuted:

- "`TwentyfourxxEngine.master_sections` and `player_view` repeat the family's body; share it
  through free builders or world methods": the plan's standing decision (its second bullet, and
  "Copies are fine"). 24XX's sections and panels splice into the middle of the family's tuples,
  so any shared builder takes the insert as a parameter, which is the hook the phase removes.
- "`install(scene: SceneProposal[Person])` accepts a plain-`Person` cast into a 24XX world; the
  old `C` guaranteed otherwise": in play the proposal reaching `install` is what the worldsmith
  parsed against `NextProposal[self.member]`, the engine's own cast class; the old `C` was never
  tied to `W` (`SceneWorld[Any]`), so `apply_scene` took any cast before too; `Game.commit`
  re-parses. Both reviews said no fix exists without the parameter the plan drops.
- "Drop `P` from `RoomWorld[P, N]`, one subclass is left": `rooms/world.py` cannot name `Goon`;
  `tunnelgoons/` imports `rooms/`, and imports flow one way.

Known and accepted:

- `TwentyfourxxEngine.master_sections` and `player_view` carry the family's order by hand; the
  golden `prompts/twentyfourxx/master.txt` is what catches a drift.
- A test can hand `install` a `SceneProposal[Person]` whose cast is not the engine's; `commit`
  refuses it, not `install`.
