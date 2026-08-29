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

## Phase 2: core/world split and engine ports

- [x] 2.1 `state/tools.py`, `state/threads.py`, `state/scene.py`, `aidm/world/` — 270 passed,
      ruff and basedpyright clean

### 2.1 decisions

- `turn/context.py` does not copy the section renderers; it imports them from
  `world/scene.py` (turn sits above world). `SceneSnapshot`/the old `VisibleScene` keep only
  their field shapes until 2.6, so the two audiences cannot drift before the goldens are read.
- The helpers take `canon: Mapping[EntityId, Entity]`, not `WorldState`: the narrator's canon
  is the known-only subset, which is exactly what filtered the old `VisibleScene`.
- `DIRECTOR_WORLD` (the `world/prompts/director_world.md` text) lives in `world/tools.py`,
  beside the tools its sentences name.
- `Game.record` reads the place through a private `_place()` instead of the deleted
  `player_location`; 2.6 replaces it with the scene label the plan asks for.
- `validate_rooms` runs from each engine's `_checks`, so `engines/core.py` still imports
  nothing from `aidm.world`.
- `Scene.prompts` carries a locked exit as `"<name> (locked)"`, because a prompt is two
  strings and the old lock icon has nowhere else to go.
- `_apply`'s trial run now uses `copy.deepcopy(rng)`; `Random(0)` survives only in
  `succession_decision`, which 2.2 moves and drops.

- [x] 2.2 succession and `over` in `world/succession.py` — 270 passed, ruff and basedpyright
      clean

### 2.2 decisions

- `Engine.validate` became a field (2.3's shape) one step early: `kill_tool(validate)` is built
  inside `build()`, where no `Engine` instance exists yet. `engines/core.py:rules_validator`
  builds it from packs + `rules_types` + the engine's own `_checks`.
- `kill` opens the succession decision itself, so `close_segment` lost its `engine` parameter
  and its `DEAD` read; 2.6 gives it back the engine for the scene label.
- The "You died." string now comes from `engine.over`. `ui/game.py` binds the label's text to
  it, so a non-rooms engine with no death rule shows nothing at all.
- `grep -rn "Random(0)" src/` is empty: Breathless's stake probe throws its dice away, so it
  takes an unseeded `Random()`.

- [x] 2.3 new `Engine` contract, mechanics blob, Loner 3e ported — 269 passed, ruff and
      basedpyright clean

### 2.3 decisions

- `Engine` fields renamed in one pass rather than added beside the old ones: `badge`→`title`,
  `director_instructions`→`instructions`, `director_tools`→`tools`, `describe`→`describer`
  (one blob parse per scene), `owed_notes`→`director_sections`. The old names had no second
  reader, so keeping both would have been dead weight for three steps.
- `Engine.rules_types` and `Engine.checks` are gone already: Loner's `validate` is its own
  function, and the two unported engines build theirs with `rules_validator(packs,
  RULES_TYPES, _checks)`. `describe_by`, `carried_by` and `owed_sections` are their shims.
- `Engine.begin` was not built. `begin(a, b) == mechanics_merge(a, b)` for every engine that
  exists or is planned, so `begin_game` calls `mechanics_merge`; a field with one possible
  value is not a seam.
- `Engine.check_overlay` became `Engine.character_mechanics(character) -> Mechanics`: one
  engine-owned function both checks the overlay and shapes it into the blob. 3.1 deletes it
  with `Character.mechanics`.
- `begin_game` branches on `engine.scene is not None` (the ported marker), not on `describer`:
  every engine now has a describer.
- The old `rules(entity, model)` is renamed `entity_rules` for 2.4–2.5 and dies at 2.6; the
  name `rules` is the blob's from here on.
- `check_tool_names` checks uniqueness inside the engine only. The clash with
  `harness/mcp.py:SERVER_TOOLS` and the authoring tools is refused in `harness/mcp.py:offered`,
  the one place all three name lists are in scope — copying those names into `engines/core.py`
  would be the hand-written name table the maintainer rejects. (This half was **missing** until
  the review pass caught it; the claim above was written before the code existed.)
- `ScenarioPatch.mechanics` and `ScenarioDraft.mechanics` had to land here, not at 3.3: a
  Loner scenario cannot be authored at all without a way to write sheets. `ScenarioDraft.apply`
  takes the engine, so core never opens the blob.
- The pack default is `next(iter(engine.packs))` everywhere; no `"srd"` remains in `src/`
  except `loner3e/rules.py:SRD_PACK`.
- That default broke Loner authoring: the first installed pack is `ap01-fantasy`, and
  `twist_pack` still defaulted to `srd`, so every default-pack draft was refused. `twist_pack`
  is now `Slug | None`, and None rolls twists from the game's own first table set. No scenario
  has to name a twist table, and `twist_table` still falls back to the SRD columns.
- `Loner3eCreation` keeps writing the table set the character was built from;
  `_character_mechanics` lifts it out of the sheet into the blob, where character scalars win.

- [x] 2.4 24XX ported — its own `TwentyfourxxState{sheets, items}`, chapter and advance
- [x] 2.5 Breathless ported — `BreathlessState{sheets, items}`, no chapters

### 2.4 / 2.5 decisions

- Engine folders stay identical: every engine is still `__init__.py`, `packs/`, `director.md`,
  `rules.py`, `engine.py`. Phase 2 moves what is inside them, never the layout.
- `describer` is `Callable[[Game], EntityRenderer]` for all three. Only Loner closes over
  `packs` (it renders pack tag meanings); the other two need no such parameter.
- `resolve_luck_test` opens no `rules(...)`: it touches no sheet. Every entry point that reads
  mechanics opens exactly once, and none nest.
- 24XX gear is sheetless until something marks it: `resolve_defence` does
  `game.items.setdefault(item.id, ItemSheet())`, and creation/`buy_gear` write a sheet only for
  bulky gear or gear that breaks more than once.
- Breathless `validate` also refuses an item with no die in `mechanics.items`; the old
  per-entity `ItemSheet` parse enforced that implicitly and a test depends on it.
- Both engines' `authoring_instructions` now name `mechanics.sheets` / `mechanics.items`
  instead of an entity's `rules`, which nothing reads any more.
- `pyproject.toml` gained `tests/twentyfourxx` and `tests/breathless` on `pythonpath` and
  `extraPaths`, so every engine's test-support module is imported the same bare way.
- Neither `director.md` changed: the rendered Director text is byte-identical to the fixture
  before the split, because every tool sentence the core prompt lost is in `director_world.md`,
  which all three engines prepend.

### Evals after 2.5 (`evals/results/step-2.5.json`, label `step-2.5`)

Six named cases in one batch at `--concurrency 24`, against `phase8-r1-full`:

| case | before | after |
| --- | --- | --- |
| loner3e/fight-the-rat | 100% | 100% |
| loner3e/twist-on-the-brink | 100% | 100% |
| twentyfourxx/fight-the-wrecker | 100% | 100% |
| twentyfourxx/buy-the-vest | 100% | 100% |
| breathless/scavenge-on-a-spent-loot-die | 100% | 100% |
| breathless/risky-climb | 81% | 78% |

`risky-climb` is the known-flaky one; `phase8-r1-recheck` caught it at 96% and comparing
against that reads as a 19% drop. Against the full baseline it is 3% on 9 repeats — noise, not
the prompt split. `evals/turn_eval.py` was ported to the blob in the same pass; no `.rules`
attribute access is left in it.

- [x] 2.6 old contract deleted, every consumer reads `Scene` — 270 passed, ruff, format and
      basedpyright clean

### 2.6 decisions

- `render_director` keeps PLAYER ACTION **last**, after `Scene.sections`. PLAN.md puts the
  framing (scenario, threads, notes, action) first and the sections after it, which would move
  the player's action into the middle of the prompt. That is what a weak model reads last, the
  evals were measured with it last, and 2.6 is not an eval gate — so the order stands and only
  the section contents move.
- `engines/core.py` shrank 551 -> 324 lines. `Offer` collapsed into the `(label, args)` pair it
  always was; `offered` yields `(action, label, args)`.
- `ProposalBase`, `party_member` and `ADVANCE_TOOL` left core for the two engines that spend
  advances; each declares its own `subject_id` and `ADVANCE_SPENT`.
- `Illustrator` takes both the `Game` and the `VisibleScene`: the scene holds ids, and drawing
  a likeness needs the entity's name and brief. `scene_key` hashes `Scene.key`, so an engine
  may key a scene on anything without worrying whether it names a file.
- `ui/panels.py` lost the old scene entirely: "Carrying" reads `children(world, player, item)`
  and "What you know of" is met canon that is not here. Both are empty for an engine whose
  world has no elsewhere, which is what 4.4 needs.
- `CharacterProfile` no longer refuses gear that carries rules — `Entity.rules` is gone, so the
  rule is unrepresentable rather than unchecked.
- `rooms_scene` parses the blob twice per build (once in `describer`, once in the engine's
  `director_sections`). Both are read-only and the dict is small; joining them would couple two
  independent engine functions for no measured gain.

- [x] 2.7 goldens regenerated once, every diff read — full check green: **282 passed**, ruff,
      format and basedpyright clean

### 2.7: what the golden diffs say

`prompts/*` did **not change at all** — the rendered Director and Narrator prompts are
byte-identical before and after the `Scene` switch. That is the whole point of keeping
PLAYER ACTION last: `rooms_scene` emits its sections in the order `_scene_sections` did, so
the only thing that moved is where the text is built.

Every other diff traces to a named step:

| fixture | change | step |
| --- | --- | --- |
| `instructions/*` | the same sentences, reordered: core keeps the role, "Run the turn" and "Use the dice"; the world fragment follows with every tool-naming sentence | 2.1 |
| `schemas/*/director_tools.json` | same tools, same bodies, `advance_thread` moves 7th -> 10th (each engine lists the world tools, then core's thread tool). No resolver appears | 2.1 |
| `state/*`, `save/*` | `turn_events` -> `turn_facts`; every entity's `rules` -> `world.mechanics.sheets`/`.items` with nothing lost; `history[].place` -> `history[].scene`; `history[].events` -> `history[].facts` | 1.2, 2.3-2.6 |
| `turn/*` | `facts[].event{title,icon,badges,outcome,effects}` -> `facts[].card` + `facts[].dice`; `dice.kept` -> `dice.result` + `dice.highlight`; dice traces lose their `-> N` tail | 1.1, 1.2 |

Turn behaviour is unchanged in all three engines: same prompt, same narration, same fact kinds
in the same order, same `told` flags. The only trace text that moved is the dice tail, which
1.1 removed and the 2.5 evals already ran on.

## Review pass after 2.7

An adversarial review of the whole phase. Full check stayed green throughout; the golden
fixtures did not move, so none of this changed a prompt.

### Two bugs it found

- **The tool-name clash check did not exist.** `check_tool_names` only ever checked uniqueness
  inside one engine, while PROGRESS claimed the cross-list half was covered elsewhere. It was
  not. An engine tool named `scene` or `end_turn` would be published and then silently shadowed
  by the server's own tool in `harness/mcp.py:call`. Now refused in `offered`, where all three
  name lists are in scope.
- **A death outside `kill` left no way on.** 2.6 moved the succession decision out of
  `close_segment` into `kill`, so `add_trait(player, "Dead")` ended the game with an eligible
  companion standing there. `add_trait` now refuses the reserved `dead` trait id and names
  `kill`. This is invariant 4 in PLAN.md.

### Cuts taken, 9393 -> 9338

- `world/scene.py` 254 -> 223: the `_Rooms` dataclass was a cache for two `blocks` calls; both
  are now locals in `rooms_scene`. Its ten text helpers are private — `turn/context.py` stopped
  importing them at 2.6 and nothing else does.
- `sheet_of(sheets, entity)` is core's, not three identical copies. Breathless keeps
  `item_sheet_of`: an item is a die, not a sheet, and its refusal says so.
- `party_member` and `ADVANCE_SPENT` went back to core's shared vocabulary. They read no engine
  model. `complete_chapter` and `advances_owed` stay per-engine by decision: they touch sheet
  fields the engines name differently.
- `world/topology.py:walk` deleted. It had no caller; 3.2 adds it with the reachability rule
  that wants it. PLAN.md now says so.
- `partial(...)` in place of forwarding lambdas; `mechanics_of` takes a `WorldState` like its
  sibling `rules`; `content/io.py`'s `check_overlay` parameter is `read_mechanics`, which is
  what it now does; `ui/panels.py` reuses `world/scene.py:placement` instead of a second copy
  of the same leak rule.
- Eleven restating docstrings and comments deleted.

### Two cuts tried and reverted

A generic `check_sheet_owners` and a generic `mechanics_without` that walked every top-level
map in the blob. Both are wrong: the blob mixes entity-keyed maps with plain models, and Loner's
`twist` is a `Counter`, whose `current`/`maximum` keys the generic version read as entity ids.
125 tests caught it. The per-engine versions are three honest lines each.

### Size, told straight

`src/` is **9338**, against **8948** before phase 2 — still **+390**. Phase 2 adds a package and
a projection layer; the deletions it unlocks land later. On the plan's own steps the remaining
drop is roughly: 3.1 ~70 (`CharacterProfile`, `CharacterOverlay`, `character_mechanics` x3),
3.3 ~90 (`ExtensionPatch`, `apply_patch`, the draft's duplicated fields), 4.3 ~90 (`StepTrace`,
`TurnTrace`, `TurnResult`, `retry_prompts`, `GameSession.entries`, `trace_panel`), 4.2/4.5 ~30.
That is ~9060, still above 8948. The residue is the `Scene` projection itself
(`state/scene.py` + `rooms_scene`, ~180 lines), which is what buys a non-rooms engine at 4.4.
If that is not worth 180 lines, the projection is the thing to argue about, not the rest.

## Next

Phase 3, step 3.1: one character file per engine.
