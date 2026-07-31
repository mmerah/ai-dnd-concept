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

## Next — item 3: one scene snapshot

`SceneSnapshot` + `VisibleScene`, deleting the four `*Context` models and two of three scene
builders. `aidm_5e/scene_state.py` dies once the Director stage takes the real `GameState`.
