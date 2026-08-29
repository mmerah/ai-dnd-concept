# PROGRESS

Branch `core-slim`. Phases 1 and 2 share it. Goldens stay stale until step 2.7, so the check
until then is "pytest minus goldens":

```
uv run pytest --deselect tests/core/test_golden_turn.py --deselect tests/core/test_golden_state.py \
  --deselect tests/core/test_golden_prompts.py --deselect tests/core/test_golden_schemas.py
```

## Phase 1: facts, dice, deferred decisions

- [x] 1.1 `DiceEvent` and `roll` — 272 passed, ruff and basedpyright clean
- [x] 1.2 `Fact.card`, delete `MechanicEvent` — 266 passed, ruff and basedpyright clean
- [x] 1.3 deferred decisions — 266 passed, ruff and basedpyright clean
- [x] 1.4 resolvers are not Director tools; the gate stays — 267 passed, ruff and basedpyright clean

Phase 1 is green: **269 passed**, 12 goldens deselected, ruff and basedpyright clean.
`MechanicEvent`, `EventBadge`, `player_events`, `turn_events`, `roll_pool`, `Decision`,
`check_pending`, `Engine.resume` and `DiceEvent.kept` are all gone from `src/`, `tests/`
and `evals/`; `grep -rn "int(.*\.result)" src/` is empty.

### What the review pass caught after the four steps

- `_move_summary`'s "gave an item to an actor" branch put an unmet NPC's name on the player's
  card. The fact's `entity_id` is the item, so `apply_to_draft`'s told-fact guard cannot see it.
  That branch now gates on `destination.known` like its sibling, and a test covers it.
- `keep_highest` returns `(kept, event, fact)`. Eleven rule sites had been parsing the kept die
  back out of `DiceEvent.result`, a field that also holds `"yes-but"` and `"fail"`.
- One `engines/core.py:stake_decision` replaces two identical 13-line bodies; one local closure
  replaces three copies of the loot card.
- The Breathless luck-test card was unreachable (`told` false, and every renderer filters on
  `told and card`). The `card=` is deleted, not made told: Phase 1 must not move what the game
  shows, because 2.7 reads the golden diffs for exactly that. A Director-called Breathless luck
  test therefore still shows no card — pre-existing, worth a decision later.
- `evals` pinned `"Oracle — Advantage"` instead of scanning the whole card for `"Advantage"`;
  the Loner card also carries a model-authored edge tag that could contain the word.

### Two eval predicates that deviate from the plan on purpose

- `luck_die` keeps reading `die.faces[0]`, not the plan's `int(die.result)`. The predicate rates
  the die the Director chose; `result` is what it rolled, so a d8 showing 6 would pass a
  `<= 6` expectation it should fail.
- `_outcome` cuts the trace tail at the first `". "`. Breathless appends a vulnerability warning
  after the outcome, so the plan's bare `rsplit("-> ", 1)[1]` would return `"fail. Ines is …"`
  and `failed_a_check` would never match.

### Carried into phase 2

- `engines/core.py:succession_decision` still passes `Random(0)`, inherited from the deleted
  `_takeover_refusal`. It is inert — `take_over` draws no dice — but the plan's Done-when grep
  bans `Random(0)` in `src/`. Step 2.2 moves this function to `world/succession.py`; drop it there.
- `Engine.tool` does not yet refuse a resolver that shadows a director tool's name. Step 2.3
  adds `check_tool_names` for exactly that; no collision exists today.

## Decisions taken along the way

- `PLAN.md` committed on its own (`c6acc90`) before any code moved.
- 1.1: all three engines keep the highest die, so `engines/core.py:keep_highest` wraps
  `roll` once instead of the ten call sites each building their own `DiceEvent`.
  `state/facts.py:roll` stays engine-agnostic, as the plan asks.
- `PLAN.md` and `PROGRESS.md` joined ruff's `extend-exclude`: ruff 0.16 reformats markdown
  code blocks and would flatten the aligned comments the plan reads by.
- 1.2: the plan's `Exchange.scene` and `Game.record(scene_label, ...)` stay unbuilt; the field
  is still `place` and renames at 2.6 with the rest of the `Scene` switch.
- 1.2: `_move_summary` carries the unmet-destination rule for every caller, not only the
  NPC-leaves branch the plan names — one guard where the callers meet.
- 1.3: `PLAN.md` puts `call` on `DecisionOption`, but that model is also every creation step's
  and every content pack's plain id/label/detail choice (`GearItem`, `Specialty`, `Origin`, …).
  So `DecisionOption` keeps its shape and `PendingOption(DecisionOption)` adds the required
  `call`; `PendingDecision.options` holds `PendingOption`. `PLAN.md`'s target shape now says so.
- 1.3: succession's `allows_text` moved `True` → `False`, as the plan asks. No behaviour change:
  `consume_answer` refuses a dead player's written answer before the `allows_text` guard runs.
- 1.3: each resolver's `DirectorTool` is declared beside the function it calls (`DEFEND` in
  `twentyfourxx/rules.py`, `LOOT_ITEM`/`LOOT_MED_KIT` in `breathless/rules.py`), so the decision
  builder names `DEFEND.name` instead of repeating a string.
- `ui/game.py:_mechanic_event` renamed to `_card` now rather than at 4.2: it pointed at a type
  this phase deleted.

## Next

Phase 2, step 2.1: `state/tools.py`, `state/threads.py` and the new `aidm/world/` package.
Goldens stay deselected through it.
