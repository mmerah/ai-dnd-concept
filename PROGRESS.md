# Refactor progress

Tracking `REFACTOR.md`. One bullet per gated step.

## 1a — merge the distributions (pure move) — done

- Four `src/` trees collapsed into one root `src/`; tests into `tests/{core,story,dnd5e,ui}`
- Five `pyproject.toml` became one real `aidm` distribution (hatchling, `aidm` script)
- `scripts/srd/` moved to the repository root; `test_package_boundary.py` retargeted
- Gate green: 219 tests, `ruff check`, `basedpyright` — only import edits touched sources

## 1b — delete the engine seam and versioning — done

- `EngineRegistry`, five engine protocols, and both facades replaced by two concrete engine
  values (`aidm_story/factory.py`, `aidm_5e/factory.py`) plus `aidm/engines.py::engine_for`
- `EngineId = Literal["story", "dnd5e"]`; `StoryDirection | Dnd5eDirection` unions replace
  `BaseModel` parameters, so every `isinstance(direction, ...)` guard in the engines is gone.
  Core pairs engine with direction once in `engines.resolve`/`engines.record`
- `domain/actions.py` moved to `aidm_story/actions.py`
- Deleted `EngineStamp`, `EngineRef`, `EngineDescriptor`, `DependencyStamp`, `PackStamp`,
  `TRACE_VERSION`, `require_direction`, `require_envelope`, `save_mismatches`,
  `stamp_mismatches`, `application/compatibility.py`, `engine_api/`
- `GameState.save_version` is required; `FileSaves.load` and `FileTraces.load` refuse a stale
  file with a readable message before validating the rest
- `scripts/import_srd.py` bumps `SAVE_VERSION` whenever it rewrites the shipped SRD pack
- `Dnd5eConfig` folded into `Settings.dnd5e`; the composition root memoises per engine id
- Scenario/character JSON now carries `"engine": "story"`; stale `saves/` deleted
- Core test support builds on the real Story engine — a third engine id is no longer
  representable, by design
- Deleted tests: `test_registry`, `test_reducer_boundary`, `test_conversion`,
  `test_bootstrap`, `test_advancement_adapter`
- Gate green: 210 tests, `ruff check`, `basedpyright`; new game + save + resume verified for
  both engines through the composition root

## Review pass on 1b

Two Opus reviews ran against 1a (pure-move proof) and 1b (adversarial). 1a verified pure:
68 of 72 moved files differ by one isort blank line, 219 identical test ids, wheel ships the
SRD pack and the console script. Acted on 1b's findings:

- `home.py::_action` now consults `catalog.unreadable`. A save the loader refuses used to fall
  through to a "Start game" button that crashed on navigation — the exact flow the
  `SAVE_VERSION` bump manufactures. Regression test added
- `store.py` probe fields default to 0, so a save or trace written before `save_version`
  existed reports "is version 0" instead of a raw `ValidationError` naming a private model
- `_resumable` compares the player's brief again, as the deleted `save_mismatches` did
- Restored `test_advancement_adapter` (the 5e level-up flow is engine behaviour, not wiring,
  and it needed no edit) and the codec schema check, now the only guard on payload
  `schema_version`. The reviewer also wanted `test_bootstrap`, `test_reducer_boundary`, and
  `test_conversion` back; those pin composition wiring and machinery the next items delete,
  so they stay deleted
- `import_srd.py` decides "shipped" by resolved path, not argument count
- `DirectionBase` moved into `aidm_story` (its only implementor); `Engine.id` is a `ClassVar`;
  `Dnd5eConfig` is a plain `BaseModel` so `pack_paths` has one env spelling

210 tests, ruff and basedpyright clean.

## 2 — one canonical state — done

- `GameState.engine: StoryState | Dnd5eState`, discriminated on an `engine` tag. `engine: EngineId`
  and `rules: EngineData` are gone; `state.engine_id` reads the tag off the aggregate
- Per-entity engine state is an id-keyed side table (`actors`, `items`) on that aggregate.
  `BaseEntity.rules` deleted; a commit-time validator asserts the side-table keys equal the world's
  actor and item ids — the replacement for the abandoned rules-only-patch guarantee
- `Dnd5eActor` / `Dnd5eItem` join views (frozen dataclasses over entity + state) keep every 5e
  mechanic reading one object, so `mechanics/`, `procedures`, `rules`, `spells`, `features` and
  `progression` were re-typed, not rewritten
- The 5e mirror is deleted: `conversion.py` (222), `domain/models/{base,entities,state}.py`,
  `engine/campaign.py`, both `codecs.py`, `domain/engine.py`, `EngineData`, `EngineCodec`,
  `EngineInitialization`, `require_engine`, `RuleStatePatch`, `_require_rules_only_change`,
  `attach_initial_rules`, `rules_for_created_entity`, every `Legacy*` alias
- 5e no longer re-declares topology events; its mechanics emit core `EntityCreated`,
  `EntityDiscovered`, `ActorMoved`, `ItemMoved`, and `aidm_5e/domain/reducer.py` applies both
  halves of `Dnd5eEvent` to the real `GameState`. Its 5e semantics (HP clamp, conditions,
  level-up guard, feature/slot spend, rest refills) are relocated, not deleted
- `Lifecycle.initialise` returns the engine state directly. A created entity gains its engine
  state in the same commit, through `RuleReducer.created`
- Authored engine data is a discriminated union too: `ActorDefinition`/`ItemDefinition` carry
  per-kind unions, locations carry none, and the six authored JSON envelopes were flattened.
  `SAVE_VERSION` bumped to 17
- `bestiary` now returns actor/item state from a ref instead of restatting an entity;
  `engines.py::entity_renderer` binds an engine presenter to the state it reads, so scene builders
  stay engine-blind
- `StoryState.items` needed a rule event for advancement-granted gear: `GearAcquired` carries the
  gear onto the created item, and shows up in the trace
- The 5e "only the player may have progression" invariant moved onto `Dnd5eState`
- Deleted tests whose target no longer exists: `test_dnd5e_rules` (rules-only-patch diff),
  the corrupt-payload director case, the wrong-engine-envelope case. `test_events.py` ported to
  `test_state_application.py` with byte-identical assertions
- Deviation from the plan: `domain/json.py` stays. `RuleEvent.payload` and
  `DirectionRecord.mechanics` still need `FrozenJson`, and both die in item 4;
  `test_frozen_json.py` was retargeted at `RuleEvent` rather than deleted early
- Gate green: 206 tests, ruff, basedpyright. `test_combat`, `test_spells`, `test_progression` and
  the ported `test_state_application` pass with the same assertions and RNG seeds. New game +
  save + resume verified for both engines; a resumed save compares equal to the committed state
- 11,324 → 10,732 source lines

## Review pass on 2

An adversarial Opus review ran against the staged item-2 diff. Acted on every finding:

- **Behaviour regression fixed.** Both lifecycles re-derived the authored→entity association by
  *name*, so two starting items called "Rope" — legal before, since core slugs them `rope` and
  `rope_2` — aborted game start. `world_from_definitions` now returns `AuthoredWorld` (world +
  engine data keyed by the id core assigned), `Lifecycle.initialise(authored, character_data)`
  reads it directly, and the name matching, its uniqueness rule and its two failure modes are gone
- Core's topology application is no longer duplicated: `reducer.py::apply_core` is public and 5e's
  intra-resolution fold calls it, so the dry-run and the commit cannot disagree
- `EngineAggregate[ActorState, ItemState]` in `aidm/domain/aggregate.py` holds the id-keyed side
  table once; `StoryState` and `Dnd5eState` add only their tag and their own invariants
- `for_engine` / `for_engine_or_none` live in core, so neither engine's signatures name the other's
  models to narrow authored data
- `created_state` moved into each engine's `state.py`. `Dnd5eRules` and `StoryRules` no longer take
  a lifecycle just to forward it
- `CharacterDefinition.engine` was redundant with `engine_data.engine` and is now a property;
  the field is out of both character files
- `bestiary.statted_*` take the authored definition instead of its unpacked fields;
  `ItemDestination` is core's; `first_level`'s param is `character`, not `sheet`;
  `AdvancementStatus` moved to `domain/advancement.py`; `WorldState.ids_of` dropped a dead TypeVar
- Tests: added the only missing guard — a rule event whose payload `schema_version` is stale is
  refused. Replaced three tautological `is not None` assertions with the field they meant, folded
  the two name-matching lifecycle tests into one that pins colliding starting-item names, and moved
  setup out of a `pytest.raises` block
- 206 tests, ruff, basedpyright clean. New game + save + resume verified for both engines

## 3 — one scene snapshot — done

- `SceneSnapshot.of(state)` is the one projection: `player`, `location`, `inventory`, `here`,
  `known_elsewhere`, `hidden`, plus `canon` for the arbitrary lookups placement and the catalogue
  need. `VisibleScene.of(snapshot)` drops `hidden` and `canon`
- `render_narrator` takes `VisibleScene`, so the Narrator boundary is structural: there is no field
  a leak could travel through. `VisibleScene` does **not** subclass `SceneSnapshot` — that would
  make a snapshot substitutable and hand the guarantee back to renderer discipline
- Four renderers replace four `*Context` models plus four prompt builders:
  `render_director` / `render_narrator` / `render_maintainer` / `render_creator`, each taking the
  scene, the bound `EntityRenderer`, and `ScenarioMeta`. `render_maintainer` and `render_creator`
  stay separate because the two prompts differ in everything but the catalogue section
- The Director stage's deps are the real `GameState`. Both directors validate against it, so
  `aidm_5e/scene_state.py` and the `GameState` the Story director fabricated for its dry run are
  gone, along with `DirectorScene.canon` / `.is_here`. `GameState.is_here` serves both engines
- Deviation from the plan: renderers take the bound `EntityRenderer` rather than an
  `(engine_state, presenter)` pair. `engines.py::entity_renderer` already binds a presenter to the
  state it reads, and core cannot dispatch a presenter without the engine value
- Deleted: `DirectorScene`, `NarratorScene`, `CatalogueScene`, `NarratorEntityView`,
  `CatalogueEntityView`, `DirectorContext`, `NarratorContext`, `MaintainerContext`,
  `CreatorContext`, all three scene builders, `entity_placement`, `aidm_5e/scene_state.py`
- Only unused prompt inputs went with them: the Director, Narrator and Maintainer contexts each
  carried a `recent` no prompt rendered. Only the Creator prompt shows history, and it still does
- The three must-survive context-boundary assertions are ported: no hidden canon reaches the
  Narrator (now half structural, half a prompt assertion), prompt ids escape control characters
  and bracket delimiters, and a hidden speaker is rejected
- Gate green: 207 tests, ruff, basedpyright. New game + save + resume verified for both engines
  through the composition root
- `context.py` + `prompting.py`: 414 → 346 lines. 10,732 → 10,534 source lines

## Review pass on 3

An adversarial Opus review ran against the working tree, on a fixture built to hit every render
branch. Findings acted on:

- **The Narrator boundary had regressed for `detail`.** The deleted `NarratorEntityView` carried
  `{id, kind, name, brief, state}`; full entities carry `detail.hook`, which the Creator authors as
  "one sentence about how it may matter later" — GM-only forward canon. No prompt rendered it, so
  nothing leaked, but the guarantee had dropped from structural to renderer discipline. `_undetailed`
  strips it in `VisibleScene.of`, and the boundary test now fails without that call
- The ported boundary test could not have caught it: its only data assertion named the *hidden*
  actor, which is excluded by construction. The fixture now gives a visible actor a detail
- The Story director had lost its eager wrong-engine guard — `_engine(state)` was only reached from
  the actor-consequence path, so an empty `mechanics` against a `Dnd5eState` validated. `validate`
  now narrows once through the existing `state.py::story_state` and threads the result; the
  duplicated private `_engine` is gone
- `-> Self` on both `of` classmethods advertised subclassing that `cls(...)` cannot honour, and
  `VisibleScene`'s whole point is that it is *not* substitutable. Both name their concrete class
- `_character` took `SceneSnapshot | VisibleScene` — the one place in the Narrator path where
  passing a `hidden`-bearing scene type-checked. It takes the player, location and inventory now
- The three `Callable[[Entity], str]` parameters were positionally interchangeable. `label` and
  `placement` are keyword-only, so a swap no longer type-checks

Rejected, with reasons:

- **The dry runs now round-trip the real `history`** rather than the empty history of the state the
  deleted `scene_state.py` fabricated. Measured: 0.11 ms → 0.17 ms per `updated(GameState)` at 60
  exchanges of realistic size. The world and engine state dominate, item 4 deletes `updated()`, and
  a workaround would be dead code by then
- A test asserting `VisibleScene` does not subclass `SceneSnapshot` would be redundant: inheriting
  would add `hidden` and `canon` to `model_fields`, which the existing field-set assertion pins

Reworked beyond the review, on maintainer instruction: the Narrator sees placement too. `placement`
was briefly `Placement | None`, with None meaning "the Narrator's scene has no world to locate
against" — an optional encoding an inconsistency rather than a fact.

- `BaseScene` holds the five shared fields plus `placements`, an id-keyed map of rendered placement
  text. `SceneSnapshot` and `VisibleScene` are siblings under it, so a snapshot still cannot reach
  `render_narrator`, and the five field declarations are no longer duplicated
- `_placements(world, entities, nameable)` computes it once per scene. `nameable` is the set of ids
  whose names the reader may be told exist: every id for the Director, only met entities for the
  Narrator. A known item held by an unmet actor therefore renders "held by The Secret" for the
  Director and no placement at all for the Narrator — pinned by a test
- Intended prompt change: the Narrator's `here` and `known_elsewhere` lines gain a placement suffix.
  Diffed against a worktree at the previous commit over a fixture covering every branch — that is
  the *only* difference; the Director, Maintainer and Creator prompts are byte-identical

## 4 — resolution transaction — done

- `Transition{state, facts}` is what an engine returns. `resolve` drafts (`state.model_copy(deep=True)`),
  mechanics mutate that draft directly, and `commit()` revalidates it once —
  `GameState.model_validate(working.model_dump(round_trip=True))`. The N per-event round trips
  through `updated()` became 2 per turn (resolution, then growth + exchange)
- Domain state models are mutable (`utils/models.py::Mutable`); values stay `Frozen`. `hp` is now
  `stats.apply_hp_delta(-total)`, not a nested `updated(...)` chain
- Typed facts replace the `RuleEvent` envelope. One three-part union discriminated on `source`
  ("core" / "story" / "dnd5e") then `fact`; core renders its own topology facts and delegates the
  engine's through `engines.py::narrator_fact` / `trace_fact` — the `isinstance` moved, it did not
  vanish. No encode/decode, no `schema_version`, no JSON payload
- `StoryDirection` and `Dnd5eDirection` carry an `engine` tag, so `Turn.direction` persists as a
  discriminated union instead of `DirectionRecord{mechanics: FrozenJson}`. The Director's output
  schema gains one const field; that is the price of not smart-union-guessing on reload
- Core owns topology application: `GameState.add` / `reveal` / `move_actor` / `move_item` mutate and
  return the core fact. Both engines call them, so `_reveal`/`common.reveal` and the two `_moved`
  helpers collapsed. `add` copies the entity into `EntityCreated`, so a later move in the same turn
  cannot rewrite the record
- The 5e reducer's semantics moved into the mechanics that emit them: HP clamp into `health`,
  conditions into `conditions`, `level_up_available` and the level-up into `progression`, feature and
  slot spend into `features`/`spells`, rest refills into `recharged`. `Resolution.then` and
  `StoryRules._fold`'s re-application are gone — a mechanic reads what the previous one wrote
- Advancement is the second transaction: both `advance` methods return a `Transition`, and
  `GameApplication.advance` appends an `Advance` trace entry. The trace is
  `TraceEntry = Turn | Advance`, so a level-up shows in the trace panel
- Deleted: `domain/{events,presentation,reducer,direction,json}.py`, `aidm_5e/events.py`,
  `aidm_5e/domain/reducer.py`, `RuleEvent`, `DirectionRecord`, `FrozenJson`, `updated()`,
  `EngineAggregate.with_actor`/`with_item`, `WorldState.replacing`/`adding`, both engines'
  `SCHEMA_VERSION`, both `record()` methods, `Revealable`, the level-up replay guard (unreachable
  once nothing replays). `SAVE_VERSION` bumped to 18
- Deviation from the plan: `Frozen` and `FrozenMap` are not deleted outright. `Frozen` still marks
  values that are never part of a draft — facts, directions, consequences, content records — and
  `FrozenMap` survives inside `aidm_5e/utils/models.py` only. A pack loads once and every turn shares
  its record objects, so an edit there outlives the turn that made it; `test_content.py`'s
  "a loaded record cannot be edited" is the test that caught this the moment the annotation went
- Gate green: 201 tests, ruff, basedpyright. The ported purity assertion holds for both engines
  (`state.model_dump_json()` unchanged after `resolve`, same result for the same seed). New game +
  save + resume verified for both engines; facts and directions round-trip through the trace; a
  level-up commits through the same path and reloads as an `Advance`
- 10,534 → 9,910 source lines

## Review pass on 4

An adversarial Opus review ran against the working tree. It confirmed no mechanics regression —
every fact's `before`/`after`/`delta`/`remaining` and every emission order are value-identical to
the previous commit, the deleted replay guards really are dead, and `commit()` round-trips int slot
keys, `EntityId`, `Decisions` and the discriminated unions losslessly. Acted on its findings:

- **Two aliasing holes, both latent, both fixed.** `bestiary.statted_actor` handed the authored
  `StatBlock` object straight into runtime state — now that `StatBlock` is `Mutable` and pydantic
  does not revalidate instances, two actors from one definition would share an HP pool and damage
  would write back into the scenario the application holds for the process. `progression.advance`
  assigned the same `Progression` object it put inside `LeveledUp`, so a "frozen" fact tracked the
  draft. Both take a `model_copy(deep=True)`, as `GameState.add` already did
- **The load-bearing purity test was vacuous.** Its direction had no mechanics, so "state unchanged
  after resolve" held by construction — it passed with `draft` monkeypatched to the identity
  function. It now takes an item and rolls a risk, and fails under both an identity draft and a
  shallow copy (verified by sabotage)
- `test_a_state_the_commit_refuses_is_never_the_committed_one` never made a commit refuse anything.
  Rewritten: it half-applies a move, breaks the side table, asserts the commit raises, and asserts
  the source state is untouched while the discarded draft keeps its half-applied change
- Added the missing persistence coverage. A 5e `Turn` and an `Advance` now round-trip through
  `FileTraces` and reload as `Dnd5eDirection` and 5e facts. Confirmed the tags are load-bearing:
  stripping `engine` makes the union refuse to discriminate rather than guess
- Added `Advance`'s only end-to-end test: `GameApplication.advance` saves, appends the trace entry,
  and clears the advancement
- Naming: `draft`/`commit` became `GameState.draft()` / `.committed()`, so the noun `draft` is no
  longer shadowed by a function and the `working` variable disappears. Story's `Emitted` moved from
  `rules.py` to `facts.py` beside `StoryFact`, which decouples advancement from rules.
  `narrator_core_fact` + `trace_core_fact` collapsed into `core_fact_summary` — a core fact carries
  nothing private, so one renderer is the honest shape
- Trace panel: an advancement no longer claims a turn number of its own ("after turn N"), and the
  dead `or "- (none)"` on evidence is gone
- CLAUDE.md corrected: a turn runs **two** transactions, not one, and `Frozen` guards a model's own
  fields, not its contents — the trap that produced both aliasing holes
- Rejected nothing. The one SUSPECTED finding — a `ValidationError` escaping the 5e Director's dry
  run now that `commit()` runs inside `resolve` — the reviewer could not reach and neither could I:
  every state invariant is guarded by a mechanic first. It stays a note, not a change
- 203 tests, ruff, basedpyright clean. Gate re-run: new game + save + resume identical for both
  engines, facts and directions round-trip through the trace

## 5 — author-once scenarios and direct save identity — done

- Content is `scenarios/whispering-vault/{world,story,dnd5e}.json` and
  `characters/kael/{base,story,dnd5e}.json`. The canon is authored once: the two scenario files that
  differed only in an engine tag, a title suffix and one entity's data are one `world.json` plus two
  overlays, and the same for the character pair. 293 JSON lines of content became 220
- `world.json` and `base.json` hold runtime `Entity` values directly. `EntityDefinitionBase`,
  `ActorDefinition`, `ItemDefinition`, `LocationDefinition` and `StartingItemDefinition` are gone,
  and with them `world_from_definitions`'s entity-by-entity rebuild — `authored_world` copies the
  authored entities and adds the player, whose placement is the only cross-file fact
- **Authored ids are the ids.** An overlay is `{actors: {id: data}, items: {id: data}}`, keyed off
  what the author wrote, so `slug(name, taken)` no longer decides a starting item's id. It survives
  only for entities the model creates mid-game
- Split into `actors`/`items` rather than one map because `ActorEngineData` and `ItemEngineData`
  discriminate on `engine` alone; a flat id→data map would need a two-field discriminator
- `validate_definition_engines` (22 lines, four scan passes) is replaced by two model validators on
  the composed `Scenario`/`Character`. They check the same engine tags **and** that every overlay id
  names an authored entity of the right kind — a typo'd overlay key used to be silently unread
- An overlay's presence *is* the compatibility check. `engines_offered` globs `<engine>.json`;
  `EngineRef` matching in `compatible_characters` collapses to `engine in option.engines`
- **New axis, forced by the design:** one scenario now offers several rulesets, so the engine is a
  launcher choice. `LauncherController` gains `selected_engine` / `available_engines` /
  `choose_engine`, the save slug is `<scenario>--<character>--<engine>`, and the game route carries
  the engine. Narrowing a routed string goes through `base.py::engine_id`, since `EngineId` is closed
- `GameState.scenario_id` / `character_id` are required and persisted. `_save_option`'s reverse
  matching — matching a save's scenario meta, player name and player brief against every authored
  file, then reporting how many candidates it hit — is one lookup: does that origin still ship the
  overlay this save needs. `SaveOption.scenario_name`/`character_name` stop being optional
- `_resumable` keeps the drift checks (scenario meta, player name and brief) and adds the id check.
  The ids catch "wrong content"; the drift checks still catch "the author edited it since you saved"
- Deviation from the plan: **`runtime()` stays** on `StoryActorDefinition`/`StoryItemDefinition`.
  Merging authored and runtime engine models would put an `engine` discriminator field on every
  entry of `GameState.engine.actors`/`items` and hand a `Mutable` authored object to runtime state —
  the aliasing trap item 4's review closed twice. The authored/runtime split is real there
- Deviation from the plan: `definitions.py` is not folded into the world module. Item 7 moves
  `ScenarioMeta` into `world.py`; doing it now would mix authored and runtime shapes in a module
  item 7 renames anyway
- Intended prompt change: the lantern's id is `lantern`, not the derived `a_guttering_lantern`, and
  the 5e scenario title lost its "— 5e" suffix. Both follow from authoring once
- `SAVE_VERSION` bumped to 19
- Gate green: 208 tests, ruff, basedpyright. New game + save + resume verified for both engines
  through the composition root, with the resumed state equal to the committed one; a story-only
  scenario (its `dnd5e.json` removed) offers Story alone and its save reports the withdrawal
- 9,907 → 9,957 source lines. Item 5 is the one item that adds lines: the engine-selection axis and
  directory-based loading cost more than the deleted hierarchy saved

## Review pass on 5

An adversarial Opus review ran against the working tree. It re-verified the things worth trusting —
no authored object is aliased into runtime state (full object-graph identity check plus a
scorch-and-recompose equivalence check, both engines), all four prompts × both engines are
byte-identical to the previous commit apart from the two declared changes, the content decomposition
is lossless, `LauncherController` is consistent after every public method, and path traversal is
blocked on every content and save path. Findings acted on:

- **Three correctness defects, all "a state item 5 made representable but did not validate".**
  A scenario directory with no overlay was offered, selected first, and left the home screen showing
  "No playable scenario was found." with no way to navigate — the only entry point to the app,
  bricked by a half-written scenario. A stray `notes/` or `__pycache__/` directory under
  `scenarios/` crashed `load_catalog` outright, because `_authored` yielded every subdirectory and
  the name check ran before the "is this content" check. `store.py::_playable` now treats the canon
  file as the "this is content" signal and an overlay as the "this is playable" signal, and skips
  anything failing either — which also folded `read_scenarios`/`read_characters`/`engines_offered`
  into one generator that no longer re-resolves each folder twice
- **A starting item's `known` was authorable and unvalidated.** The deleted `StartingItemDefinition`
  had no such field and core hard-coded `known=True`; `ItemEntity` defaults it to `False`. An
  unknown carried item is simultaneously hidden canon to the Director and in the inventory the
  Narrator is shown, since `SceneSnapshot.inventory` does not filter on `known`. `CharacterProfile`
  now refuses it
- **`_require_one_engine` was dead on arrival.** Its predecessor `validate_definition_engines` was
  reachable because the engine came from the scenario while the character loaded independently; item
  5 threads one engine id into both loaders and the engine value, so the guard could not fail. The
  change destroyed the guard's reason and kept the guard. Deleted
- **`BaseEntity.authored` is deleted.** It was written at four production sites and never read
  anywhere — dead since before this item, but `world.json` validating as `Entity` made it authorable
- Dropped `_resumable`'s player name/brief comparison. `state.scenario` is a *duplicate* of authored
  data that core carries outside the world and renders in every prompt, so a stale copy changes
  model output; the player entity is world state the game mutates, and comparing two of its thirty
  sibling authored strings pinned nothing structural. The id check now carries the identity weight
- `Slug` annotations on the routed ids were promising a check that never ran — `Slug` is `str` at the
  type level and narrows nothing outside pydantic. `base.py::content_id` narrows both ids at the
  route, as `as_engine_id` already did for the engine, so `Slug` downstream is a fact
- Naming: `engine_id` clashed with a property, a field and four parameters (it forced `app.py` to
  read `engine_id(engine)`) and is now `as_engine_id`. `CharacterBase` read like a base class in a
  codebase with three real ones → `CharacterProfile`, field `Character.profile`. `_withdrawn`
  returned `str | None` under a boolean's name → `_unplayable_reason`, and it now distinguishes
  content that is gone from content that dropped an overlay
- **Tests: 190 → 187 functions, and 3 of the 4 item 5 added are gone.** Deleted
  `test_a_save_names_its_own_origin` (it asserted `_begun` copied two fields it was handed, and its
  docstring described a resume it never performed) and the gear-collision lifecycle test, whose
  premise — core deriving ids from names — item 5 deleted; its own rewritten docstring conceded it.
  Merged the two stale-save launcher tests, the two resume-refusal tests, and the two
  overlay-visibility tests. Moved the surviving `Character` validator tests out of
  `tests/story/test_lifecycle.py` (deleted) into `test_integrity_boundaries.py`, where the code they
  test lives. Dropped the `Scenario` round-trip assertion — `store.py` builds `Scenario`
  field-by-field, so it is never deserialised in production. Added the only missing guard: a routed
  content id that escapes its directory
- Cut two pre-existing wiring tests the review flagged and the maintainer's "too many tests" covers:
  `test_every_role_resolves_to_its_explicit_configuration` (its `isinstance` is the return
  annotation, which basedpyright already checks) and `test_engine_badge.py` (`engine_appearance` is
  an exhaustive match on a closed literal, so a new engine already cannot compile without a badge;
  the test only pinned the colours). Kept the ambient-environment test — determinism is a
  requirement, and that one guards it
- Rejected one recommendation: the flat (scenario × engine) launcher option, which the reviewer
  priced at −30 source lines. It pays for them by collapsing a `Slug` and an `EngineId` into one
  parsed string, which is the wrong trade here
- 208 → 205 tests, ruff, basedpyright clean. Both load-bearing tests re-verified by sabotage: a
  shallow `draft()` fails 7 tests including the purity assertion, and an identity `_undetailed`
  fails the Narrator boundary. Gate re-run: new game + save + resume for both engines, no aliasing
- Net cost of item 5 fell from +58 to **+50 source lines**, and the test suite is 3 tests and 1 file
  smaller than before item 5 started. The correctness fixes cost lines the cuts had freed; that is
  the honest number, not the reviewer's −25 estimate

## 6 — engine-owned advancement — done

- Story and 5e `preview`, `plan`, and `advance` now take and return their concrete types; the
  `BaseModel` signatures, runtime decision adapters, and defensive UI type guards are gone
- The composition root memoises a private engine-bound renderer cache. `StoryAdvancementUi` owns a
  `StoryEngine`, `Dnd5eAdvancementUi` owns a `Dnd5eEngine`, and `Session` requires its application
  and renderer to share that exact engine instance; engine packages remain UI- and NiceGUI-free
- Each renderer calls its concrete service directly. The shared confirmation flow passes the closed
  Story/5e decision union to `GameApplication`; core pairs it with the selected engine and still owns
  validation, save, and trace commits, so an arbitrary transition cannot pose as an advancement
- The controller reads the engine's shared availability method inside its guarded submission flow;
  the duplicate renderer delegates are gone and a failed query cannot leave the session busy
- Gate green: 205 tests, `ruff check`, and `basedpyright`; Story advancement commit/save/trace and
  the full 5e preview/plan/advance flow remain covered. Source delta: +18 lines for the closed
  decision dispatch, engine/UI identity invariant, and fail-fast registration checks
