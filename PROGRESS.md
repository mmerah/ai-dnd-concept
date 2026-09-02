# PROGRESS

One entry per phase of `PLAN.md`: counts before and after, decisions made off-plan, refuted
review findings and why, anything known and accepted.

## Phase 1 — one scene world

- `src` lines: 10,341 before, 9,972 after (target about 9,950). Tests: 453 before, 458 after.
- Goldens: `state/` and `save/` moved exactly as the phase's Done when says (`"party": []`
  after `"player"` for 24XX and Breathless; Loner's player out of `cast` and `present`, filed at
  `"player"`, `"party": []` for `"companions"`, no `"player_id"`; `"alive"` follows `"known"` in
  every sheet). `prompts/`, `schemas/`, `turn/` and every Tunnel Goons fixture unchanged.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).

### Decisions off-plan

- The seam that builds a world from a canon is `scenes.new_world`, not `new_game`: every
  `engine.py` already has a `new_game` that returns the state.
- `SceneWorld._consistent` refuses the player's id in `party` with "the player cannot travel
  with themselves" before `check_party`, keeping Loner's message; `check_party` alone would say
  "not in the cast".
- `Person.unwritten()` is wired into the three `_scene_unmet` bodies now, so one version of the
  rule is alive at the commit; the refusal texts are unchanged.
- `check_game` takes `packs: Collection[str]`: it reads only the pack ids.
- `new_world` has no `PLAYER_ID` guard: the world's validator already refuses a cast that
  holds the player's id, and nothing in the scene lifecycle spells `PLAYER_ID`.
- Loner's `apply_scene` gained 24XX's "the scene rewrites the player" guard: the old refusal
  relied on the player being a cast entry.
- Two tests of a rule the plan removes (`player.id == PLAYER_ID`, refused in the validator) are
  replaced by tests of the rule that replaces it ("the player is in the cast").
- A review found and fixed a bug the phase introduced: at the opening, `_scene_unmet` compared
  `resolved_id(...)` against `None`, so a stray id was dropped instead of refused. One
  regression test added (24XX).

### Refuted findings

- "`members()`, `party_rows`, `party_panel` have no caller": PLAN 1.1 and 1.2 put them in this
  phase; Phase 2 wires them.
- "The party symbols belong in `scenes.py`": PLAN 1.1 puts them in `engines/core.py` so they take
  `Person` rather than a second protocol.
- "`known` seam collides with `known` parameters in `cast_unmet`/`hub_unmet`": PLAN 1.2 names the
  seam `known` (it is `Engine.known`); those parameters are in Phase 2's fold.
- "The player's `last_seen` detail is always empty": kept the single generator over
  `(world.player, *world.cast.values())`; `last_seen` is cheap and Phase 2 folds the renderers.

### Known and accepted

- `world.py` is 121 (24XX), 121 (Breathless) and 128 (Loner) lines against "under 110". What
  remains is what PLAN 1.3 lists plus the rule helpers `tools.py` imports (`raised`, `stepped`,
  `tags_of`/`set_tags`). Not padded (PLAN rule 5); Phase 4's layout audit may move them.
- `uv run aidm` on shutdown by SIGTERM logs an MCP "cancel scope" RuntimeError; `app/` is
  untouched by this phase.

## Phase 2 — one worldsmith, one view

- `src` lines: 9,969 before, 9,419 after (target about 9,550). Tests: 458 before, 463 after.
  `scenes.py` 620 → 995; 24XX 1,224 → 922, Breathless 1,106 → 805, Loner 1,182 → 865.
- Goldens: every fixture unchanged, as the phase's Done when says.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves; a turn needs a spawned CLI the
  container lacks, so that check is manual.

### Decisions off-plan

- basedpyright refuses `isinstance(written, model)` on a parametrized draft class and narrows
  `isinstance(written, SceneDraft)` to `SceneDraft[Unknown]`, so the brief's spellings did not
  type-check. One private `TypeIs` guard, `_is_draft(written, model)`, restores the wrong-subclass
  refusal in `write_next` and narrows without `typing.cast`; it checks against the class the type
  argument was applied to, since pydantic parametrizes by copying, not subclassing.
  `build_scenario` takes a `cast_type` to name its draft, as `write_next` and `render_opening` do;
  `install_scene` keeps PLAN 2.2's one `SceneDraft[Any]`.
- The bar refuses a draft that names the party (PLAN 2.1), and `cast_unmet` demanded "one
  existing cast member brought back" from a cast that could be the party alone: with every cast
  member travelling, no draft could pass. The demand now stands only while someone outside the
  party could come back: `cast_unmet`'s `opening` keyword became `needs_return`, false at the
  opening and false when every cast member travels with the player. The maintainer chose this
  over "a party satisfies the demand".
- `install_scene`'s trace reads "the player travelling with A, B": number-neutral, since the
  brief's "and A travel there" was wrong for one companion.
- `subject_of` is private to `scenes.py`; Tunnel Goons keeps its own.
- The three `views.py` import `scenes` as a module and call `scenes.entity_line` and friends.

### Refuted findings

- "The staged `PLAN.md` edit is not part of this phase": the maintainer asked for it in this
  session (the Phase 4 split of `scenes.py` and `engines/seam.py`); one commit per phase.
- "Loner's master prompt now prints `(dead)`": PLAN 2.3 defines the one `entity_line` with it.
- "Fold `scene_unmet` into `scene_refusal`": PLAN 2.1 names both.
- "Replace the 24XX and Breathless `install_scene` wrappers with `partial`": PLAN 2.4 prescribes
  the wrapper, and the three engines' wiring files read alike.
- "Delete the Breathless and Loner tests that run the shared functions through their fixtures":
  this phase's test rule is green plus one test per new behaviour; the audit is Phase 4.

### Known and accepted

- `scenes.py` is 995 lines against "about 700": the file was 620 before the move and the PLAN's
  own function list adds about 370. Phase 4 splits it into a package.
- The three engines land under their "about 1,050" targets; nothing was padded (PLAN rule 5).

## Phase 3 — the recap and the refinements

- `src` lines: 9,419 before, 9,480 after (target about 9,625; nothing padded, PLAN rule 5).
  Tests: 463 before, 469 after.
- Goldens: the nine `state/` and `save/` fixtures of 24XX, Breathless and Loner gain
  `"recap": ""` per run, as the phase's Done when says. `prompts/`, `schemas/`, `turn/` and
  every Tunnel Goons fixture unchanged.
- Reviews: Fable reviewer and a second Opus reviewer (no `codex` on the machine).
- Smoke: `uv run aidm` starts and the home page serves; a turn needs a spawned CLI the
  container lacks, so that check is manual.

### Decisions off-plan

- `scene_history` prints a run through a private `_told(run)`: the recap branch and the
  exchange branch, so the comprehension stays one expression.
- `told_tail` lands in `tunnelgoons/worldsmith.py` as the private `_told_tail`; the constant
  keeps its name `TAIL_EXCHANGES`.
- The launcher test "a save that lists but will not open still reaches the player" is replaced
  by "a save that fails to restore is skipped, not listed": its premise (the payload is read only
  when the game opens) is what PLAN 3.5 changes.
- `tests/core/test_tool_surface.py` keeps its `A_SCENE` without a recap; `_scene` adds `RECAP`
  for the drafts written in play and `_bare_scene` validates an opening against `SceneDraft`.

### Refuted findings

- "The `ui.timer(0.5, ...)` in `game_page` duplicates `_scroll` and carries a magic number":
  PLAN 3.4 prescribes that exact line.
- "`_told` prints every exchange of the open run, uncapped, where the worldsmith prompt held
  three": PLAN 3.1 says a run without a recap prints every exchange; the recap bounds every
  closed run, and the open run is the one the worldsmith must read whole. Known and accepted
  below.
- "`IDEAS.md` item 12 is deleted though a session recap on resume did not land": PLAN 3.6 says
  delete item 12, its second half being 3.4 (resume at the end).
- "The home page now restores every save in full on every load": PLAN 3.5 prescribes
  `engines[game.engine].restored(raw)` in `load_catalog`. Known and accepted below.

### Known and accepted

- A scene played far past `SCENE_TURN_CAP` puts all of its exchanges into the worldsmith prompt
  at the crossing; only that one run is unbounded, and only until it is recapped.
- `load_catalog` decodes each save twice (the header, then `Engine.restored`); the home page
  reads N whole games where it read N headers. `Engine` is outside this phase.
- `src` lands 145 lines under the target: the recap and the terms cost about 60 lines, not 200.
