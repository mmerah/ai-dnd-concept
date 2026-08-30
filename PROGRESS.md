# PROGRESS

Phase 3 shipped at `3b7157d` (284 passing). `PLAN.md` now holds Phase 3.5 and Phase 4.

## Where the refactor stands

`src/**/*.py`: 8956 before the refactor (`f37ba99`) -> 9363 now. Modules 52 -> 60. The first
three phases moved code and added structure; they did not shrink anything. Phase 3.5 is the
correction, and `PLAN.md` opens with the arithmetic.

## Decisions taken 2026-08-30

- **No `rooms_engine` factory.** The dungeon-crawler helper is `world/tools.py:rooms_tools`
  only. A 15-parameter factory re-passing creation/validate/describer/tools is `Engine(...)`
  with renamed keywords: it costs 55-65 lines to save ~65. The tool tuple alone saves ~42.
- **Target 8900**, with the measured estimate at ~9020 written into the plan. The gap is not
  hidden and is not to be closed by the two cuts the plan rules out.
- **`ExecDriver` stays.** Folding it into `CodexDriver` saves ~15 real lines, not the 45-55
  first reported, and destroys the abstraction `harness/claude.py:28` already names as the
  path once the SDK bills like the API. Its inverse (making `ClaudeDriver` a subclass, -80)
  stays gated on that condition.
- **`config.for_name` left alone.** Rewriting the `match` blocks would reintroduce the
  string-keyed dispatch killed once already.
- **The do-not-collapse list held.** Both reviewers tested `Fact`, `Scene`/`VisibleScene`,
  `DirectorTool`/`AuthoringTool`, `Draft`/`ScenarioPatch` and `AuthoringBrief` independently
  and upheld every one. `SceneSection` is the exception and 3.5.6 cuts it.

## Corrections both reviews forced into the plan

- The companion co-location rule cannot move to `validate_rooms`: that runs on live state, and
  `_move_actor` deliberately allows a party member to be witnessed moving away. It goes to the
  authoring `unmet` functions instead.
- `mechanics_patch` must take explicit `entity_maps` per engine. "Drop the id from every
  dict-valued top-level key" would let an entity named `winter` delete `seasons.winter`.
- The turn-trace deletion cannot be verified separately from the golden regeneration: the
  golden test serializes `TurnTrace`. One atomic step.
- The eval file split folds into that same step; done separately it rewrites ~60 predicates
  twice.
- `Game.player` needs no relaxing: `begin_game` always builds the player as an actor.
- `submit` returns `None`, not `Game`; illustration narration comes from the committed
  exchange.

## Next

Phase 3.5 step 1: `rooms_tools`. Record the line count before and after.
