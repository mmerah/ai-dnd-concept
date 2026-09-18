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
| src   |  10462 | 10477 |    +15 |
| tests |  11964 | 11811 |   −153 |
| qa    |   2020 |  2020 |      0 |

All three parts landed as planned; no golden moved. The counts are after the reversal below
(as first landed, `src` 10457 and `tests` 11795). Reviewed by two independent Opus reviewers
(no `codex` on the machine). `src` is far off the −150 estimate: the plan counted the test
engines' support under `src`, where they never were (`tests/support/fifth.py` and `sixth.py` are
the −169 in `tests`), and the room loop's body is the same size wherever it sits. The `src` cut
left is the two hooks and `starting_items`, against 24XX's two whole methods.

Reversed the same day, after the phase first landed as `fa72ecb`: `RoomEngine` is back in
`rooms/engine.py` as `RoomEngine[N: Dweller, W: RoomWorld[Any, Any], K: Pack]`, the twin of
`SceneEngine[C, W, K]`, because the two families keep one shape: what `scenes/engine.py` does,
`rooms/engine.py` does. `TunnelGoonsEngine(RoomEngine[Npc, TunnelGoonsWorld, TunnelGoonsPack])` keeps
`new_game` (the Goon's kit), its creation, `player_of`, its dice and its hires. `EXTEND`,
`MORE_MAP` and `MAP_UNWRITTEN` are `rooms/engine.py`'s constants, as `DEPARTURE`, `MOVE_ON` and
`WAY_UNWRITTEN` are `scenes/engine.py`'s. The plan's standing decision and phase 4's sentences
are amended to match.

Decisions taken off-plan:

- `Engine.player_of` is abstract; the check every engine makes is one concrete helper,
  `Engine.player_as(character, sheet)`: the id/known refusal, one `isinstance`, the
  "is not a … sheet" refusal, the copy. Each engine's `player_of` is one line over it. Both
  reviews found the plan's three copies of the override and its string.
- `EXTEND`, `MORE_MAP` and `MAP_UNWRITTEN` are not in `rooms/tools.py`: an operation slug, a
  decision option and a failed-write fact are not tools; they sit beside the loop that reads
  them, as `DEPARTURE`, `MOVE_ON` and `WAY_UNWRITTEN` sit beside `SceneEngine`. `OPENING_SECTIONS`
  is in `rooms/worldsmith.py` beside `MAP_ASK`, as the scene family's sits beside `OPENING`.
- `extend` is inlined into `advance`: two statements, one caller.
- `test_the_clock_does_not_arm_with_nothing_to_move_and_keeps_the_count` seeds `turns_played = 1`:
  the sixth engine's `tempo` was 6, Tunnel Goons' is 4, and the old seed of 3 reached it.
- The loop classes keep the member parameter: `SceneEngine[C, W, K]` and `RoomEngine[N, W, K]`,
  `member: type[C]` / `type[N]`, `install` and `write_next` typed on it. The plan's `member:
  type[Person]` let a `SceneProposal[Person]` type into a 24XX world (both reviews found it,
  and the restored `RoomEngine` hit it at once: a `RegionProposal[Npc]` refused `install`'s
  `RegionProposal[Dweller]`). The member and the world are tied by the subclass's declaration,
  not by the bound: `W: SceneWorld[C]` makes basedpyright read `self.world.opening` through the
  erased bound and refuse `SceneProposal[C]` (three errors), so `W: SceneWorld[Any]` stays.
  `Engine[W, K]` itself is as planned.

Review findings refuted:

- "`TwentyfourxxEngine.master_sections` and `player_view` repeat the family's body; share it
  through free builders or world methods": the plan's standing decision (its second bullet, and
  "Copies are fine"). 24XX's sections and panels splice into the middle of the family's tuples,
  so any shared builder takes the insert as a parameter, which is the hook the phase removes.
- "Drop `P` from `RoomWorld[P, N]`, one subclass is left": `rooms/world.py` cannot name `Goon`;
  `tunnelgoons/` imports `rooms/`, and imports flow one way.

Known and accepted:

- `TwentyfourxxEngine.master_sections` and `player_view` carry the family's order by hand; the
  golden `prompts/twentyfourxx/master.txt` is what catches a drift.
- `RoomEngine` is a base with one subclass, against "no abstraction until two things need it":
  the room loop keeps its own file and class so the two families read alike, by the
  maintainer's call.

## Phase 4: tools and words

Counts, `find <dir> -name '*.py' | xargs cat | wc -l`:

| dir   | before | after | change |
| ----- | -----: | ----: | -----: |
| src   |  10477 | 10432 |    −45 |
| tests |  11816 | 11882 |    +66 |
| qa    |   2020 |  2020 |      0 |

Both parts landed as planned; no golden moved. Reviewed by two independent Opus reviewers (no
`codex` on the machine); every finding was fixed, none refuted. `src` is short of the −60
estimate because a docstring wraps where a constant packed its lines; `tests` grew past the +40
estimate by the five `tools_of` tests.

Decisions taken off-plan:

- A tool's description is its docstring collapsed to one line (`" ".join(cleandoc(doc).split())`),
  not `cleandoc` alone: the master reads a description, not the source's 100-column wrapping, so
  the three `master_tools.json` goldens are byte-identical to before.
- Every declaration check runs where the method is marked, at class definition: `@tool` refuses a
  missing docstring, a third parameter that is no model, and an undescribed field, and records
  the args model in a private `_MARKED` dict. `tools_of` only binds and orders. The plan had
  `tools_of` re-derive the model on every engine construction.
- `_marked` reads a class namespace through `isinstance(value, FunctionType)`, the one thing
  `@tool` can mark, so an unhashable class attribute (`unwritten`, a dict) is skipped by type,
  not by a `callable` proxy.
- `turn/run.py`'s `MASTER_PROMPT` path constant is `MASTER_ROLE`: the method beside it is now
  `master_prompt()`, the whole rendered prompt, and one module does not hold two things under one
  name.
- The word "seam" is retired with the file: `tests/engines/test_seam.py` is `test_engine.py`, and
  the README says `Engine` is the abstract class every engine subclasses.
- Part A ran on opus: typing `tools_of` under strict basedpyright with no `cast`, no
  `# type: ignore` and no `Any` annotation was a shape to decide, not one the plan named.

Known and accepted:

- The phase's "Done when" grep for `master_tool` matches the golden's filename
  (`master_tools.json`) and the name of the MCP test; both are names the phase keeps.
- The `hire` docstring exists twice, on `TunnelGoonsEngine.hire` and `TwentyfourxxEngine.hire`,
  as the plan accepts.
