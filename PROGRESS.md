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
- Loner's `apply_scene` gained 24XX's "the scene rewrites the player" guard: the old refusal
  relied on the player being a cast entry.
- Two tests of a rule the plan removes (`player.id == PLAYER_ID`, refused in the validator) are
  replaced by tests of the rule that replaces it ("the player is in the cast").
- A review found and fixed a bug the phase introduced: at the opening, `_scene_unmet` compared
  `resolved_id(...)` against `None`, so a stray id was dropped instead of refused. One
  regression test added (24XX).

### Refuted findings

- "`PLAYER_ID in canon.cast` in `new_world` duplicates the validator": PLAN 1.2 spells the
  check; its message names the reserved id for the scenario author, the validator's does not.
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
