# Collapse refactor — progress

Plan: `PLAN.md`. One section per phase; each ends green on
`uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.

## Phase −1 — green committed tree — DONE

- The in-flight work landed as its own commits (`f71aa7c`, `13804fc`); the tree at HEAD is green
  (100 tests). No fixture was cut before that.

## Phase 0 — behaviour locks — DONE

- `tests/core/golden_test_support.py`: `golden()` / `golden_json()` compare against a checked-in
  fixture, reporting a unified diff on drift, and rewrite only under `AIDM_GOLDEN_REGEN=1`.
  `tests/conftest.py` fails any run with that variable set, so a switch left exported in a shell
  cannot turn the locks into a rubber stamp. Regenerate in the commit that justifies the change.
- `tests/dnd5e/test_content_parity.py` + `fixtures/mechanics_parity.json`: `SpellFacts`/
  `WeaponFacts` for all 319 spells and 37 weapons of the shipped pack (1 weapon types to null).
  This is the Phase 4 gate and outlives the refactor.
- `tests/core/test_golden_state.py` + `fixtures/state/{story,dnd5e}.json`: the initial `GameState`
  JSON per engine, plus the `SAVE_VERSION` assertion. **Version is 28, not the 27 PLAN.md names**
  (the landed commits bumped it); Phase 4 is still the only phase that may move it.
- `tests/core/test_golden_prompts.py` + `fixtures/instructions/<engine>/*.txt`: assembled
  instructions for all five roles (director, narrator, maintainer, creator, advisor) per engine,
  read off the built `Stage`s, plus the rendered advisor prompt in `fixtures/prompts/`.
- `tests/core/test_golden_turn.py` + `fixtures/{prompts,turn,save}`: one scripted turn per engine
  (`FunctionModel` stubs, `Random(11)`) — the same fiction resolved by each engine's own action.
  Locks the four rendered turn prompts, the `Turn` trace JSON, and the post-turn save JSON. The
  turn runs from a state carrying two exchanges, and covers a roll, branch selection, an
  unconditional effect, history rendering, and one created entity.
- `tests/core/test_golden_schemas.py` + `fixtures/schemas/`: the plan type's JSON schema and the
  director toolset's tool definitions per engine, plus the `Growth`/`EntityDetail`/`SheetDelta`
  schemas. Added after review found that field descriptions and the `read_content` docstring —
  all model-facing, all touched by Phases 1-2 — could change with the whole suite green.
- Shared stubs (`plan`, `text`, `structured`, `scripted`) and the `game(engine_id)` builder moved
  into `core_test_support.py`; `test_pipeline.py` imports them instead of holding its own.
- Each lock was proven falsifiable: a prompt edit, a resolver constant change, a parser change, and
  three field-description edits each fail their own fixture and nothing else.
- Gate green: 115 passed, ruff clean, basedpyright 0 errors.

## Phase 1 — collapse the generic — DONE

- `core/sheet.py`: `Sheet(Mutable)` declares `kind: Kind` first, so the serialized field order is
  what inheriting from `EngineRules` produced. `core/world.py`: `EngineRules`, `BareLocation` and
  `rules_of` deleted; `Record.rules: Sheet` (no `SerializeAsAny`); `Record`, `WorldState`,
  `GameState` lost the type parameter. The transaction and every validator are untouched.
- **Not in PLAN.md, forced by the import graph:** `sheet_of`/`player_sheet` moved from `sheet.py`
  to `world.py`. With `Record.rules: Sheet`, `world` imports `sheet`, so `sheet` may no longer
  import `world`. Import lines changed in 17 files; the two bodies are now one attribute read.
- De-genericized across `core/` (`effects`, `plan`, `content.compose_world`, `engine`,
  `enginepack`, `store`), `workflow/`, both engines, `scripts/evals/`, and the tests.
- `Engine.state_type` deleted with the generic it erased: call sites construct `GameState(...)`
  and `GameState.model_validate_json(...)` directly. `FileSaves.load(slug)` drops its
  `state_type` parameter for the same reason.
- `registry.AnyEngine` + its `cast` deleted; `build_engine` returns `Engine` and keeps the
  `isinstance` check on the plugin's `object`-typed build.
- `dnd5e/advance._level_ref` is now public `level_ref`; `scripts/evals/probes.py` imports it
  instead of carrying its own copy, and its `_sheet` re-narrowing is gone.
- Only erasure-shaped test removed: `test_a_record_may_not_hold_another_engines_payload` (with
  `ForeignRules`) — with one concrete payload there is no foreign payload to refuse.
  `test_package_boundary.py` needed no change.
- Review pass: `story_game`/`dnd5e_game` now delegate to `game(engine_id)` — their reason to
  exist was the `Sheet`-typed return the collapse erased; `compose_world` lost its always-
  `WorldState` `world_type` parameter; two now-redundant `GameState` annotations deleted.
- Gate green: 114 passed (115 minus that one), ruff clean, basedpyright 0 errors. **The golden
  fixtures pass unchanged and were never regenerated** — the phase's real proof. Net −112 lines.

## Phase 2 — one loader, four hooks — DONE

- `core/registry.py` and `core/enginepack.py` are gone; `core/engine.py` is the one loader:
  `EngineSpec`, `AdvancementOffer`, a typed `EnginePlugin` (id, badge, engine_dir, plan type, four
  hooks), `Engine`, discovery (`plugins`/`engine_ids`/`plugin_for`/`as_engine_id`), and
  `load_engine(plugin, pack_paths)` / `build_engine(engine_id, config)`.
- `Engine` is data plus derived methods: `default_rules`, `initial_world`, `entity_state`,
  `renderer`, `validate_state`, `violation`, and the four hook forwarders. Every body was moved,
  not rewritten. `EngineParts`, `ProposalSpec`, the `Offered`/`Check`/`Parts*` aliases and the
  closure wrapping in `load_engine` are deleted; `engine.proposal.X` is now `engine.X`.
- Hooks take the `Engine` first (`parts.content` → `engine.content`). Refusal strings untouched.
- **Deviations from PLAN.md, both deliberate:** `EnginePlugin.record_types` is *not* introduced —
  nothing reads it until Phase 4 and an unused field is speculative; Phase 4 adds it in one line.
  `Engine.toolsets` (a one-key mapping) collapsed to `director_toolset`.
- **Both engines now have the same shape**, on the maintainer's call (PLAN.md wanted story
  collapsed into a single `rules.py`; one template for every engine reads better than a
  size-dependent one): `rules.py` declares `PLUGIN` and nothing else, `actions.py` the plan type,
  `resolve.py` the two turn hooks, `advance.py` the two advancement hooks. 5e adds `content.py`,
  the only difference. `engine.py`/`identity.py` are gone from both; `ENGINE_MODULES` names the
  two `rules` modules.
- `Settings.engines` is typed `dict[EngineId, EngineConfig]` with one `pack_paths` field, read by
  `build_engine`; `Dnd5eConfig` is gone.
- `scripts/evals/probes.py` lost its private pack read (`shipped_content`): the `Engine` it already
  holds exposes `content`. `scripts/srd/build.py` and the evals runner repointed.
- Tests: `test_enginepack.py` → `test_loader.py`, building an `EnginePlugin` over a tmp dir.
  Story's advancement test now goes through `engine.violation` (the shared check plus the engine's
  own), which is the path production takes.
- Gate green: 114 passed, ruff clean, basedpyright 0 errors. **The golden fixtures pass unchanged
  and were never regenerated.**

## Phase 3 — packages named by what they hold — DONE

- Layout now: `state/` (base, facts, dice, packs, sheet, world, effects, plan, turn),
  `content/` (authored.py, store.py), `engines/` (loader.py, examples.json, story/, dnd5e/),
  `turn/` (pipeline, prompts, roles, advancement), `app/` (launcher, session), `ui/`, plus
  `aidm/config.py`. `core/` and `workflow/` are gone.
- **Two deviations from PLAN.md's table, both forced by the import direction:**
  `packs.py` sits in `state/`, not `content/` — `Sheet` holds `ContentRef` and `render_sheet`
  reads a `LenientRecord`, so the pack format is *below* the state machine; putting it above
  would invert the arrow. `config.py` sits at `aidm/config.py`, not `app/` — `turn/roles.py`
  reads `Settings`, so config must be a leaf every layer can read, not a layer above `turn/`.
- `AdvancementOffer` moved from the loader to `state/sheet.py`, beside `SheetDelta`: the
  advancement panel renders it, and `ui` may not import `engines`.
- Discovery's consumers moved off it: `read_scenarios`/`read_characters` take the engine-id
  tuple, `LauncherCatalog` carries an `EngineOption` per engine so `show_engine_badge` takes the
  badge it was handed, `as_engine_id` lives in `app/launcher.py`, and `build_engine` (the only
  reader of `Settings.engines`) lives in `app/session.py` — so `engines/loader.py` imports no
  config at all and exposes `load_engine(plugin, pack_paths)`.
- `workflow/session.py` split: `app/launcher.py` (catalog, options, controller, `LaunchTarget`)
  and `app/session.py` (`build_engine`, `GameSession`, `Runtime`).
- `test_package_boundary.py` now states the whole direction as one table
  (`state ← content ← engines ← turn ← app ← ui`) and asserts that only `loader.ENGINE_MODULES`
  names a concrete engine. `ui → engines` stays forbidden, and now nothing in `ui/` imports an engine module at all.
- `scripts/import_srd.py`'s hardcoded `SAVE_VERSION` path repointed to `state/base.py`; the evals
  and SRD scripts follow the new module names.
- Test packages were **not** renamed (`tests/core/` still holds the cross-cutting suites): the
  golden fixtures are anchored under `tests/core/fixtures/`, and moving them buys nothing.
  README's layout section and one ROADMAP path were refreshed — pulled forward from Phase 5
  because they named deleted directories.
- Gate green: 117 passed, ruff clean, basedpyright 0 errors. Golden fixtures again unchanged.

## Adversarial review pass — DONE

Run against the staged Phases 2–3 diff; everything below is folded in and green.

- **One real regression, fixed:** `EngineConfig` was a plain `BaseModel`, so a typo in a settings
  engine section (`pack_pathz`) was silently ignored where `Dnd5eConfig(Value)` used to refuse it.
  It is `extra="forbid"` again.
- `check_delta` narrowed to `(state, delta)`: neither engine read the `Engine` or the offer it was
  handed, and the shared `violation` already judges the offer. Two `del` lines and a wider
  contract than anyone uses, gone.
- `narrator_evidence` + `NOTHING_MECHANICAL` moved to `state/facts.py`. Its only input is
  `Sequence[Fact]`; it was in the loader by accident of history.
- `test_every_registered_engine_builds_itself` trimmed to the build loop: the two other asserts
  restated `Engine.id`'s one-line body and a field's type.
- `load_catalog`'s local `offered` renamed `engine_options` — it collided with the advancement
  hook of the same name.
- Docstrings the review cut that carry a *why* were restored: the authored models' on-disk file
  mapping (`world.json` / `<engine>.json` / `base.json`), the overlay-typo rule, the launcher's
  deliberate skip of half-written content, and `_StoredVersion`'s reason for defaulting to 0.
- Reported and **not** acted on: moving `Settings` back under `app/` would mean `turn/roles.py`
  taking its role config from the composition root instead of reading `Settings` — a real
  improvement, but a turn-pipeline change, not a layout one. Left for a later phase.
- `src/` is 55 lines lighter than HEAD across Phases 2–3, with 9 modules deleted and 3 added.

## Next — Phase 4: typed pack mechanics

Blocked on a checkout of `5e-bits/5e-database` at `manifest.json`'s `source_commit`. Both script
repoints Phase 3 owed it are in. `EnginePlugin` gains `record_types` there, in one line.
