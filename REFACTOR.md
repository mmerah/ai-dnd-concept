# Refactor plan

Seven sequenced refactors. Execute in order — each one unblocks the next. The guiding rule:

> **Do not make Story and 5e mechanics look alike. Make their integration shell tiny.**

Baseline: 193 Python files, 11,348 non-blank source lines, 4,941 test lines.
Target: roughly 7,500–8,000 source lines with no loss of 5e or Story capability.

This plan has been adversarially reviewed against the source. Corrections from that review are folded in; the places where the original estimate was wrong are called out inline so the next session does not re-derive them.

---

## Decisions already made

These are settled. Do not relitigate them.

| Question | Decision |
|---|---|
| Existing saves in `saves/` | **Disposable.** Delete them and their traces. No migration code ships. |
| Trace contents | **Typed facts, persisted.** Engines return typed facts; core renders core facts and delegates engine facts. |
| Turn record | **Keeps the full `GameState` snapshot** and all rendered prompts, as today. |
| Mutability | **Mutable models, validated commit.** See the correction below — "frozen commit" is not expressible and has been restated. |
| Packaging | **One package**, `src/aidm/`, with `engines/story/` and `engines/dnd5e/`. |
| Per-entity engine state | **Aggregate on `GameState`**, id-keyed, not a field on the entity. |
| `domain/actions.py` | **Moves into the Story engine.** 5e keeps its own mechanics. |
| Versioning machinery | **`save_version` only.** No `EngineStamp`, `EngineRef`, `EngineDescriptor`, `DependencyStamp`, `PackStamp`, `TRACE_VERSION`. |
| Advancement UI | **Engine-owned renderers**, registered with the engine. Not a declarative form schema. |
| Scenario authoring | **Shared base + engine overlay** directories. A scenario/character offers an engine iff that overlay file exists. |
| Maintainer + Creator | **Stay separate.** Not in scope. |
| 5e content pack format | **Unchanged.** See "Explicitly out of scope". |

### Correction to the mutability decision

"Mutable draft, frozen commit" cannot be expressed in Pydantic V2 without either parallel model hierarchies — which resurrects exactly the `Legacy*` duplication item 2 deletes — or abandoning deep immutability. `model_config` is class-level; the same `StatBlock` cannot be frozen inside a committed `GameState` and mutable inside a draft of it.

**What ships instead:** domain models are mutable (`frozen=False`). Committing is

```python
def commit(draft: GameState) -> GameState:
    return GameState.model_validate(draft.model_dump())
```

a fresh, fully-validated value. The invariant that matters is preserved by the caller, which rebinds `self.state` only on success:

> A failed turn never replaces the committed state.

**What is lost, stated plainly:** deep immutability is gone. Nothing at the type level stops `state.world.entities[x] = …` on a committed state. That guarantee is replaced by a test — the ported purity assertion from `test_engine_contract.py:38` (`state.model_dump_json()` is unchanged after `resolve`). **That test is now load-bearing. Do not delete it.**

**What is gained:** today `updated()` (`utils/models.py:39`) does a full `model_dump(round_trip=True)` + `model_validate` **per field change, per event**. After this, the same round trip happens **once per turn**. The saving is N→1, not N→0. Do not claim otherwise.

**Second consequence:** per-field validators stop running on every mutation. `StatBlock`'s consistency check and `StoryActorState._consistent` become end-of-turn checks. A mid-turn crash therefore leaves a half-mutated draft — safe only because the draft is discarded, never committed.

### Consequence of "`save_version` only"

Pack drift is no longer detected at load. Today it is caught twice: as a launcher label and as a hard raise in `GameApplication._resumable` before the game opens, because pack versions ride in `EngineStamp.dependencies`.

After item 1, **a stale save loads successfully.** `Ruleset.provides(ref)` only catches *removed* content refs. A pack whose content *changed* — a feature's uses per rest, a class's slot table, a monster's AC — passes load and then fails mid-turn with "cannot refill …" or "cannot spend …", after the model calls have been paid for. Actor `stats` are snapshots, so the character silently keeps pre-regeneration numbers until then.

**Mitigation, and it must be enforced, not documented:** the SRD pack build bumps `SAVE_VERSION`. A human protocol ("remember to delete `saves/`") is not sufficient. Write the bump into `scripts/srd/build.py` or hash the pack manifest into the version.

---

## Explicitly out of scope

- **Restructuring the 5e content JSON to match runtime profiles.** The 2.5 MB SRD pack is derived by `scripts/srd/` from an external upstream checkout, and byte-identical round-trip is its regression check. Reshaping the disk format means rewriting the importer and regenerating the pack. `pack_ruleset.py` stays.
- **Merging Maintainer and Creator.** The extra model call per new entity is a deliberate trade.
- **Generics on the engine API.** Once engines are importable, `StoryDirection | Dnd5eDirection` unions delete the `isinstance` guards outright.
- **Deduplicating topology semantics between the engines.** `engines/dnd5e/mechanics/movement.py` and `inventory.py` are near-verbatim reimplementations of `domain/actions.py` — same witness guard, same reveal-then-move ordering, same error strings. Moving `actions.py` into Story (item 1) makes that duplication permanent. **This is knowingly accepted**: the two engines must be free to diverge on what "take an item" means. If it later proves stable, extract shared topology helpers then.

---

## Tests

The original plan's delete list was wrong in three places. Corrected accounting for all 32 test files:

### Delete outright — machinery only

```
packages/aidm-core/tests/test_frozen_json.py          # FrozenJson/FrozenMap recursion
packages/aidm-core/tests/test_registry.py             # EngineRegistry
packages/aidm-core/tests/test_reducer_boundary.py     # RuleEvent stamps, rules-only patches
packages/aidm-rules-5e/tests/test_conversion.py       # legacy <-> core conversion
apps/aidm-ui/tests/test_bootstrap.py                  # registry + isinstance composition
packages/aidm-rules-5e/tests/test_advancement_adapter.py  # BaseModel adapter layer
```

### Keep and port — these pin behaviour that must not change

```
packages/aidm-rules-5e/tests/test_events.py           # SEE BELOW — misclassified originally
packages/aidm-core/tests/test_engine_contract.py      # SEE BELOW — holds the purity assertion
packages/aidm-core/tests/test_package_boundary.py     # SEE BELOW — 18 lines, retarget it
packages/aidm-core/tests/test_context_boundary.py     # SEE BELOW — the Narrator boundary
packages/aidm-rules-5e/tests/{test_combat,test_spells,test_progression,
    test_feature_progression,test_consequences,test_resolve,test_rules,
    test_dnd5e_rules,test_content,test_feature_content,test_character_content}.py
packages/aidm-rules-story/tests/{test_story_rules,test_advancement,test_lifecycle}.py
packages/aidm-rules-5e/tests/test_package_data.py     # guards the SRD pack path; item 7 moves it
```

**`test_events.py` does not test event encoding.** Despite the name it imports `aidm_5e.domain.reducer.apply` and pins HP clamping at 0 and at max, take/drop/give container moves, actor movement, discovery scope, entity creation ordering, and fail-fast on impossible events including "a location has no hit points". It is **the acceptance test for item 4**. Rename it `test_state_application.py` when you port it.

**`test_engine_contract.py:38`** asserts `state.model_dump_json()` is unchanged after `resolve` — i.e. resolution does not mutate its input. Item 4 replaces immutability-by-construction with mutation, so a `draft()` that shallow-copies is exactly how you silently break this. Port this assertion first; it is the only thing standing between you and a corrupted committed state. It also asserts the narrator rendering of an engine fact never leaks the raw payload — keep that too.

**`test_package_boundary.py`** is an 18-line AST scan and is the only automated enforcement of the import-direction rule this plan explicitly keeps. Retarget `CORE_SOURCE` / `FORBIDDEN_ROOTS` to the new tree in item 1. Cost: four lines.

**`test_context_boundary.py`** (232 lines) was omitted from the original plan entirely, yet item 3 deletes every symbol it imports. It holds the Narrator-sees-no-hidden-canon test, the prompt-id control-character escaping test, and the narrator-rejects-a-hidden-speaker test. All three must survive.

### Split

`packages/aidm-core/tests/test_integrity_boundaries.py` — 5 of its 7 tests cover envelopes, registry, and stamps and go. `test_world_and_game_state_reject_inconsistent_topology` and `test_scenario_topology_and_dependency_stamps_are_normalized` pin invariants that survive (`WorldState._keys_match_ids`, `_consistent_world`, scenario `starting_location_id` validation, definition round-trip). Keep those two.

### Rewrite against new shapes, assertions survive

```
packages/aidm-core/tests/{test_pipeline,test_application,test_launcher,test_store,
    test_growth,test_config}.py
packages/aidm-rules-story/tests/{test_presentation,test_instructions,test_story_director}.py
packages/aidm-rules-5e/tests/{test_presentation,test_instructions,test_director}.py
apps/aidm-ui/tests/{test_launcher,test_engine_badge}.py
```

---

## 1. Modular monolith

**Why first:** items 2 and 4 need `GameState.engine: StoryState | Dnd5eState`. Core cannot name those types while `aidm-core` is forbidden from importing the rules packages. The distribution merge is a prerequisite, not a cleanup. Module-level flattening is item 7 — do not do it here.

**Run this as two gated phases.** They are independent, and bundling them means a green gate proves neither.

### 1a — merge the distributions (pure move)

Collapse `packages/aidm-core`, `packages/aidm-rules-story`, `packages/aidm-rules-5e`, `apps/aidm-ui` into one distribution. Five `pyproject.toml` files become one: the four package manifests go, and the root — currently `package = false` — becomes a real distribution with a build backend, the `aidm` console script, and the `src/aidm_5e/data` package data declaration retargeted.

Package layout inside `src/aidm/` stays as-is. **Gate: tests green with import edits only.** Retarget `test_package_boundary.py` here.

### 1b — delete the seam that was never real

**The problem.** An `EngineRegistry` with descriptor round-trip verification, five engine sub-protocols, two factories, and two facade classes made entirely of forwarding properties — yet `bootstrap.py:37-41` does `isinstance(engine, StoryEngine)` to pick an advancement UI. No engine can be installed without editing the UI.

1. Replace the registry with a function. **It must stay a factory taking the pack path** — `create_dnd5e_engine` compiles the 2.5 MB pack on construction, and module-level `DND5E_ENGINE` constants would make that an import-time side effect, break `Dnd5eConfig.pack_paths` (the only way tests inject a different pack), and violate CLAUDE.md's "no globals below the composition root":

   ```python
   type EngineId = Literal["story", "dnd5e"]

   def engine_for(engine_id: EngineId, config: Settings) -> Engine:
       match engine_id:
           case "story":  return build_story_engine()
           case "dnd5e":  return build_dnd5e_engine(config.dnd5e.pack_paths)
   ```

   The composition root memoises per process, as the registry does today.

2. Replace the five protocols and two facades with one concrete `Engine` per ruleset. No `BaseModel` parameters anywhere — use `StoryDirection | Dnd5eDirection` unions.

3. Move `domain/actions.py` (293 lines, imported only by Story and by `core_test_support.py`) into `engines/story/`.

4. Delete `EngineStamp`, `EngineRef`, `EngineDescriptor`, `DependencyStamp`, `PackStamp`, `TRACE_VERSION`, `require_direction`, `require_envelope`, `save_mismatches`, `stamp_mismatches`, and `application/compatibility.py`.

   **`compatibility.py:15` is the only place `SAVE_VERSION` is ever compared.** Deleting it as originally written would leave `save_version` a defaulted field nobody reads — and because it is defaulted, a save omitting it validates. The decision is "`save_version` only", not "no versioning". Therefore:

   - make `save_version` **required, no default**, on `GameState`;
   - check it in `FileSaves.load`, raising a readable error before validation of the rest;
   - do the same for the trace. `TRACE_VERSION` is deleted while the trace's shape changes (events → facts), and `FileTraces.load` is called from `GameApplication.__post_init__` — so a leftover `.trace.jsonl` would crash game *open* with a raw `ValidationError`. Guard `saves/*.trace.jsonl` with the same `save_version`, or delete a trace whose version does not match.

**Deletes:** `engine_api/registry.py`, `engine_api/contracts.py`, both `constants.py` descriptor blocks, `aidm_5e/facade.py`, `aidm_5e/factory.py`, `aidm_story/engine.py`, `application/compatibility.py`, four `pyproject.toml` files and the workspace config, and every `if not isinstance(direction, XDirection): raise TypeError` in both engines.

**Also note:** `load_catalog` currently reads a save's engine from a header field. Once the tag lives inside `GameState.engine`, drawing the home screen fully parses and validates every save including its engine state — so a save with stale engine state becomes an `UnreadableSave` whose `problem` string is a Pydantic traceback. Truncate it before display.

---

## 2. One canonical state

**The problem, part one — envelopes.** Every piece of engine state is wrapped in `EngineData{engine, schema_version, payload: FrozenJson}`, encoded through one of six `EngineCodec`s per engine, and re-validated by `require_envelope` at five call sites. `domain/json.py` recursively freezes the payload into `MappingProxyType`.

**The problem, part two — the 5e mirror.** `aidm_5e/domain/models/{entities,state,base}.py` are a second copy of the core domain, and `conversion.py` (228 lines) translates the entire world back and forth on every turn. `aidm_5e/rules.py:40-51` applies one legacy event, diffs every entity, checks nothing core-visible changed, and re-encodes what did.

Note: `StoryGameState` and `Dnd5eGameState` are **both empty models**. The entire game-level rules vertical — `state.rules`, `EngineInitialization.game_rules`, `GAME_STATE_CODEC`, `RuleStatePatch.game_rules`, `DirectorScene.game_rules`, and `scene_state.py`'s fabricated `GameState` — carries zero data today.

### `aidm_5e/domain/reducer.py` is NOT part of the mirror

This was the original plan's largest scoping error. Core's reducer applies topology events and opaque rules patches. The 5e reducer applies **5e rules**: HP deltas, condition changes, the level-up non-idempotence guard, feature-resource spend accounting, spell-slot spend, and rest refills — roughly 150 lines of genuine mechanics.

**Those semantics are relocated into `engines/dnd5e/mechanics/`, not deleted.** Item 4 turns them from event-application into direct draft mutation. Budget for that; it is not a delete.

**The refactor.**

```python
class GameState(BaseModel):
    save_version: int                 # required, no default
    scenario_id: ScenarioId
    character_id: CharacterId
    scenario: ScenarioMeta            # title + premise; see below
    world: WorldState
    engine: StoryState | Dnd5eState   # discriminated on a Literal tag
    history: tuple[Exchange, ...]
    turn: int

class Dnd5eState(BaseModel):
    engine: Literal["dnd5e"] = "dnd5e"
    actors: dict[EntityId, Dnd5eActorState]
    items: dict[EntityId, Dnd5eItemState]
```

**`ScenarioMeta` stays inline.** Every prompt opens with the scenario title and premise. Holding only `scenario_id` would force the loaded `Scenario` to be threaded through `run_turn` into all four prompt renderers. Two strings on the state is the cheaper answer, and it is what the code does today.

**Keep a join view so mechanics read one object.** Every 5e mechanic today reads a merged actor carrying `name`, `location_id`, `stats`, `progression`, and `ref` on one model. Splitting into `WorldState` + `Dnd5eState` without a join means re-typing every call site in `mechanics/`, `progression.py`, `spells.py`, and `features.py`:

```python
@dataclass(frozen=True, slots=True)
class Dnd5eActor:
    entity: ActorEntity          # name, location_id, known, detail
    state: Dnd5eActorState       # stats, progression, ref
```

Mechanics take `Dnd5eActor`; the draft resolves it by id. This is the difference between item 2 being a re-plumbing and item 2 being a rewrite of the entire 5e engine.

**Keep an invariant check** that `engine.actors` keys track the actor ids in `world.entities`, so the side table cannot drift after an entity is created or removed. This is the replacement for the abandoned rules-only-patch guarantee — see item 4.

**Preserve the genuine 5e mechanics** — progression, features, spells, content packs, resolution. Replace only the duplicated shell.

**Deletes:** `aidm_5e/conversion.py`, `aidm_5e/scene_state.py`, `aidm_5e/domain/models/{entities,state,base}.py`, both `codecs.py`, `engine_api/codec.py`, `domain/json.py`, `domain/engine.py`, `_require_rules_only_change`, every `Legacy*` alias, all per-entity decode/encode loops. `aidm_5e/lifecycle.py` shrinks to a few lines.

**`scene_state.py` can only be deleted once the Director stage takes the real `GameState` as its deps** — that happens in item 3. Sequence it that way or leave `scene_state.py` in place until item 3 lands.

---

## 3. One scene snapshot

**Moved ahead of the resolution transaction.** It depends on item 2 (engine state has moved off the entities), and doing it before the fact plumbing means the Narrator's type-level boundary is already in its final shape when facts land — a leak then shows up as a compile error rather than a design to re-argue.

**The problem.** `DirectorScene`, `NarratorScene`, `CatalogueScene`, `NarratorEntityView`, `CatalogueEntityView` and three builders project the same world into slightly different DTOs, then four `*Context` models re-attach `scenario_title`, `scenario_premise`, `prompt` and `recent` — which every prompt builder immediately unpacks. `build_narrator_scene` just calls `build_director_scene` and remaps it.

**The refactor.**

```python
class SceneSnapshot(BaseModel):
    player: ActorEntity
    location: LocationEntity
    inventory: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]
    hidden: tuple[Entity, ...]

class VisibleScene(BaseModel):
    """The Narrator's view. `hidden` is not a field, so a leak is unrepresentable."""
    player: ActorEntity
    location: LocationEntity
    inventory: tuple[ItemEntity, ...]
    here: tuple[Entity, ...]
    known_elsewhere: tuple[Entity, ...]

    @classmethod
    def of(cls, snapshot: SceneSnapshot) -> "VisibleScene": ...
```

**Do not give `render_narrator` a `SceneSnapshot`.** Today `NarratorScene` has no field that *can* hold unrevealed canon, and `test_context_boundary.py:94` asserts the exact field set. Handing the renderer a snapshot containing `hidden` and relying on it not to read that field downgrades a type guarantee to renderer discipline, and CLAUDE.md's "the Narrator never sees unrevealed canon" is not a taste call. `render_narrator(scene: VisibleScene, …)` keeps it structural.

Renderers need per-entity engine state, which after item 2 lives in `GameState.engine`. So each renderer takes the snapshot plus the engine state, and the engine presenter exposes `describe(entity_id, engine_state) -> str`:

```python
render_director(snapshot, engine_state, scenario, prompt, recent) -> str
render_narrator(VisibleScene.of(snapshot), engine_state, scenario, direction, evidence, …) -> str
render_catalogue(snapshot, engine_state, scenario, narration, …) -> str
```

**The Director stage's deps become `GameState`, not a projection.** The 5e Director validator needs arbitrary-id lookup into `canon`, `is_here` (which needs `world.location_of`), and a seeded dry-run that today fabricates a whole `GameState` from the scene. Giving it the real state is what lets `scene_state.py` and `DirectorScene.canon` die.

**Deletes:** `NarratorEntityView`, `CatalogueEntityView`, the four `*Context` models, `NarratorScene`, `CatalogueScene`, `DirectorScene`, two of the three scene builders, `aidm_5e/scene_state.py`. `agents/context.py` (189) and `agents/prompting.py` (230) should land near 250 lines combined.

**Port from `test_context_boundary.py`:** the Narrator-sees-no-hidden-canon assertion (now partly structural), prompt-id control-character escaping, and the narrator-rejects-a-hidden-speaker check.

---

## 4. Resolution transaction

**The problem.** Engine facts are treated as serialized messages though they are produced and consumed in one process:

```
typed event → RuleEvent{engine, schema_version, name, payload: JSON}
  → decode → apply → RuleStatePatch{EngineData payloads}
  → decode → patch state → re-validate whole state
```

Every field change goes through `updated()` — a full serialize-and-revalidate of the subtree, once per event. Both engines then re-apply their own events mid-resolution just to read back the state they are producing (`StoryRules._fold`, 5e's `ctx.then`).

**The refactor.** One transaction, one commit:

```python
@dataclass(frozen=True, slots=True)
class Transition:
    state: GameState
    facts: tuple[Fact, ...]

def resolve(state: GameState, direction: Direction, rng: Random) -> Transition: ...
```

**The result type is `Transition`, not `Resolution`.** `engines/dnd5e/mechanics/resolution.py` already defines `Resolution` — the resolution *context* (`state`, `rng`, `ruleset`) threaded through every mechanic. After item 1 they share one distribution. Keep the 5e context named `Resolution`; it is accurate. `Transition` is unused anywhere in the repo today.

Inside, resolution mutates a working copy and commits once:

```python
draft = state.model_copy(deep=True)
# mechanics mutate draft directly:  actor.state.stats.hp = max(0, hp - total)
return Transition(state=commit(draft), facts=tuple(facts))
```

`commit()` revalidates, so end-of-turn invariants — including the `engine.actors` / `world.entities` key agreement from item 2 — run exactly once.

### Facts

The union is three-part, not two:

```python
type Fact = Annotated[CoreFact | StoryFact | Dnd5eFact, Field(discriminator="fact")]
```

Topology facts are **not** per-engine. `EntityCreated`, `EntityDiscovered`, `ActorMoved`, `ItemMoved` are core today, and 5e redundantly re-declares its own copies. Core renders core facts itself and delegates engine facts to `engine.presentation` — the `isinstance` moves, it does not vanish. Say so rather than implying otherwise.

**Every persisted union member needs an explicit tag.** `StoryDirection` and `Dnd5eDirection` are structurally near-identical — `intent`, `tone`, `speaker_id`, `mechanics` — with no discriminator; the tag lives on `DirectionRecord` today, which this item deletes. Persisting a bare union means Pydantic smart-union guessing on reload. Add `engine: Literal["story"] | Literal["dnd5e"]` to both direction models and to every fact model, and discriminate explicitly.

### Advancement is the second transaction

`GameApplication.advance` currently calls `apply(self.state, events, self.engine.rules)`, and `AdvancementEngine.advance` returns `list[Event]` — both of which this item deletes. Advancement must return a `Transition` and follow the same commit rule.

Advancement currently bypasses the trace entirely. Decide deliberately: `LeveledUp` is a fact players will want in the trace panel. Recommended: append an advancement `Transition` to the trace as a turn-less entry.

**Deletes:** `RuleEvent`, `RuleStatePatch`, `domain/reducer.py`, `apply`/`apply_one`, `encode_*_event`/`decode_*_event` in both engines, `aidm_5e/domain/reducer.py` (semantics relocated per item 2), `FrozenMap`, `EMPTY_FROZEN_MAP`, `updated()`, `Frozen`, and the per-event `validate_state` calls.

### The invariant being abandoned

"Core owns topology; engines produce rules-only patches" was enforced by `_require_rules_only_change` and `test_reducer_boundary.py`. Once engines mutate the draft, nothing enforces it — 5e's `inventory.improvise` creates entities and `movement.move` relocates actors, and those come back as core events today.

**Say this plainly in CLAUDE.md rather than keeping the old phrase.** The replacement is the end-of-transaction validator: `engine.actors.keys()` must equal the actor ids in `world.entities`, and the same for items. That is checkable and cheap. If you want the stronger guarantee back, add a topology diff at commit.

Mechanics code becomes readable as RPG rules: `actor.state.stats.hp = max(0, hp - total)` instead of nested `updated(...)` chains.

---

## 5. Author-once scenarios and direct save identity

**The problem, part one.** Parallel hierarchies for authored and runtime entities — `ActorDefinition`/`ActorEntity`, `ItemDefinition`/`ItemEntity`, `LocationDefinition`/`LocationEntity`, `StartingItemDefinition`, `StoryActorDefinition.runtime()`, `Dnd5eActorDefinition` — force `world_from_definitions` and both lifecycles to rebuild almost-identical objects.

Worse, the narrative canon is authored twice. `scenarios/whispering_vault.json` and `whispering_vault_5e.json` differ only in the engine id, the title, and **one entity's** engine data. `characters/kael*.json` follow the same pattern.

**The problem, part two.** `launcher.py:200-251` rediscovers a save's origin by matching scenario metadata, player name, player brief, and engine version, then reports how many candidates it matched.

**The refactor.**

```
scenarios/whispering-vault/
    world.json     # entities, briefs, topology, premise — authored once
    story.json     # approaches, tags, stress
    dnd5e.json     # content refs, stat blocks

characters/kael/
    base.json
    story.json
    dnd5e.json
```

**An overlay file is optional.** A scenario or character that only makes sense in one ruleset ships only that overlay. Presence of the overlay *is* the compatibility check — this replaces `EngineRef` matching in `LauncherCatalog.compatible_characters` entirely: a scenario offers an engine iff `<engine>.json` exists, and a character is compatible iff its overlay set intersects the scenario's.

One entity shape for authored and runtime entities. **`kind` stays** — `Entity` is a tagged union discriminated on it, and `WorldState._keys_match_ids` and `container_of`'s narrowing depend on it:

```python
class ActorEntity(BaseEntity):
    kind: Literal["actor"] = "actor"
    location_id: EntityId
    # no `rules` field — engine state lives in GameState.engine (item 2)
```

Persist save identity directly instead of rediscovering it:

```python
scenario = load_scenario(save.scenario_id, save.engine_id)
character = load_character(save.character_id, save.engine_id)
```

**Deletes:** `EntityDefinitionBase` and its three subclasses and `StartingItemDefinition` — all in `domain/entities.py:15-46`, **not** `definitions.py` as originally stated — plus `world_from_definitions`, `attach_initial_rules`, `validate_definition_engines`, `EngineInitialization`, `_save_option`'s reverse matching, and the `runtime()` methods on both engines' definition models. `domain/definitions.py` shrinks to `ScenarioMeta` and the scenario topology validator, which both survive; fold it into the world module.

---

## 6. Engine-owned advancement

**The problem.** The core exposes `preview() -> BaseModel`, `plan(decisions: BaseModel) -> BaseModel`, `advance(decisions: BaseModel)`, and the UI immediately does `isinstance(preview, StoryAdvancementPreview)` and hand-builds a form. `advancement/story.py` is 286 lines of form extraction and validation, `fivee.py` 125. The `BaseModel` interface is type-safety theatre.

**The refactor.** Register the renderer with its engine:

```python
def build_story_engine() -> Engine:
    return Engine(
        mechanics=StoryMechanics(),
        director=StoryDirector(),
        advancement=StoryAdvancement(),
        advancement_ui=StoryAdvancementUi(),
    )
```

Concrete types flow end to end: `StoryAdvancement.preview() -> StoryAdvancementPreview`, and `StoryAdvancementUi` consumes exactly that. `advance` returns a `Transition` per item 4.

**Deletes:** the `AdvancementEngine` protocol's `BaseModel` signatures, `Composition.advancement_ui`'s `isinstance` dispatch, and every defensive `if not isinstance(preview, …)` / `if not isinstance(plan, …)` guard in the UI. `advancement/flow.py` stays — it is genuinely shared.

The renderers themselves stay roughly their current size. This buys type safety and deletes dispatch, not lines.

---

## 7. Flatten

**Do this last.** Moving files before the concepts are deleted only creates churn.

**Renames that buy nothing are cut.** `store.py` stays `store.py`; `pipeline.py` stays `pipeline.py`. `model.py` and `game.py` are not used at two levels — `from .game import …` inside `ui/` would resolve ambiguously, and `model.py` collides with pydantic-ai's sense of "model" (an LLM), which `config.py` already uses that word for.

```
src/aidm/
├── world.py           # entities, WorldState, GameState, ScenarioMeta
├── application.py     # GameApplication, launcher
├── pipeline.py        # run_turn, Turn, Transition
├── agents.py          # stages
├── prompts.py         # SceneSnapshot, VisibleScene, renderers, instructions
├── store.py           # saves, traces, scenario/character loading
├── config.py          # absorbs aidm_5e/config.py and aidm_ui/config.py
├── engines/
│   ├── story/
│   │   ├── state.py
│   │   ├── actions.py       # moved from core in item 1
│   │   ├── rules.py
│   │   ├── advancement.py
│   │   └── ui.py
│   └── dnd5e/
│       ├── state.py
│       ├── rules.py
│       ├── mechanics/       # combat, health, inventory, movement, conditions
│       ├── progression.py
│       ├── spells.py
│       ├── features.py
│       ├── content/         # pack_ruleset, records, library — unchanged
│       ├── data/srd-2014/   # 2.5 MB package data; update build config + test_package_data
│       └── presentation.py
└── ui/
    ├── app.py
    ├── session.py
    ├── home.py
    ├── panels/              # chat, state, roles, trace
    ├── components/
    └── advancement.py
```

The SRD pack is package data located by a path in the engine factory and declared in the build config; moving it needs both updated, and `test_package_data.py` guards it. `ui/panels/` (93 lines) and `ui/components/engine.py` (36, guarded by `test_engine_badge.py`) keep their homes. Fold `session_model.py` (20), `view.py` (36), and `controller.py` (46) into `ui/session.py`.

The 5e implementation has real domain complexity and keeps several focused modules. Story does not need fourteen. The shell does not need separate `domain/`, `application/`, `engine_api/`, and `utils/` layers.

Respect the 500-line file limit from `CLAUDE.md`; split where it bites.

---

## Target turn flow

```python
async def run_turn(game: GameState, prompt: str, deps: Dependencies) -> Turn:
    scene = SceneSnapshot.of(game)

    direction = await deps.director.run(
        render_director(scene, game.engine, game.scenario, prompt, deps.recent),
        deps=game,                      # the validator needs the real state
    )

    transition = deps.engine.resolve(game, direction, deps.rng)
    after = SceneSnapshot.of(transition.state)
    evidence = render_evidence(transition.facts, deps.engine.presentation)

    narration = await deps.narrator.run(
        render_narrator(
            VisibleScene.of(after), transition.state.engine,
            transition.state.scenario, direction, evidence, prompt, deps.recent,
        )
    )

    growth = await deps.maintainer.run(
        render_catalogue(after, transition.state.engine, transition.state.scenario, narration)
    )
    state, created = await grow(transition.state, screen(growth), deps)

    return Turn(
        state=state.record_exchange(prompt, narration),
        direction=direction,
        facts=transition.facts,
        narration=narration,
        created=created,
    )
```

No rule-event JSON round trip. No state patch. No per-event conversion. No three parallel scene models. The Maintainer → Creator stage is unchanged.

---

## `CLAUDE.md` changes

These invariants are killed by this plan. Rewrite them in the commit that lands each item, or the next session will fight its own instructions.

| Current invariant | Replacement |
|---|---|
| "State evolves only through the pure reducer in `aidm/domain/`, applied to typed events." | State evolves through one engine transaction per turn, which mutates a draft and returns a revalidated `GameState` plus typed facts. A failed turn never replaces the committed state. |
| "Core owns topology and commits; the selected rules package owns typed mechanics and rules-only patches." | Core owns commits. Engines own typed mechanics and mutate the draft directly, including topology. The commit validator asserts that engine state keys agree with world entity ids. |
| "`aidm-core` imports neither rules package nor NiceGUI; `aidm-rules-story` imports no 5e code." | One distribution. `engines/story/` imports no 5e code and vice versa; neither imports `ui/`. Enforced by `test_package_boundary.py`. |
| "Prefer pure transformations, immutable values..." | Prefer pure transformations. Domain models are mutable; the committed `GameState` is a revalidated value and must not be mutated after commit — enforced by the resolve-purity test, not by the type system. |
| "`aidm_ui/bootstrap.py` is the composition root." | Keep, adjusted to the new path. |
| "`aidm/application/` owns the open game behind ports, while `aidm/store.py` performs path-based I/O." | `application.py` owns the open game; `store.py` performs path-based I/O. |
| — (new) | Regenerating the SRD content pack bumps `SAVE_VERSION`. Stale saves are refused at load, not mid-turn. |

Keep unchanged: the Narrator never sees unrevealed canon; each agent has one narrow role; the Narrator translates mechanics into fiction rather than reciting stat blocks; 5e content is derived once by `scripts/srd/`.

---

## Order and checkpoints

| # | Item | Gate before moving on |
|---|---|---|
| 1a | Merge distributions | Tests green with import edits only; `test_package_boundary` retargeted |
| 1b | Delete the engine seam and versioning | `save_version` checked in `FileSaves.load`; stale trace refused, not crashed |
| 2 | One canonical state | `test_events.py` (ported) plus `test_combat`, `test_spells`, `test_progression` pass with **byte-identical assertions and the same RNG seeds** |
| 3 | One scene snapshot | `render_narrator` does not accept a type with a `hidden` field; ported context-boundary tests green |
| 4 | Resolution transaction | Ported purity assertion green: `state.model_dump_json()` unchanged after `resolve`. Advancement commits through the same path |
| 5 | Author-once scenarios and save identity | New game + save + resume works for both engines; a story-only scenario is offered for Story and not 5e |
| 6 | Engine-owned advancement | Level-up works end to end in both engines |
| 7 | Flatten | Everything green; no file over 500 lines; SRD pack still located |

**Item 2 is the riskiest, and its original gate would not have caught failure.** Deleting `domain/models/entities.py` re-types every 5e mechanic, and the mechanics tests construct merged actors carrying `stats` — so "tests pass unmodified" is false on contact, and the natural reaction to a failing gate is to weaken it rather than notice the item was mis-scoped. The `Dnd5eActor` join view above is what keeps this a re-plumbing instead of a rewrite. Hold the gate at byte-identical assertions.

**Do not start item 2 before 1a is green.** The typed unions do not exist until the packages are merged.
