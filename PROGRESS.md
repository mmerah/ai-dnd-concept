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

## Next — Phase 2: one loader, four hooks

Merge `core/registry.py` and `core/enginepack.py` into `core/engine.py`: typed `EnginePlugin`,
one `build_engine(plugin_module, settings)`, derived behaviour as methods. Delete `EngineParts`,
`ProposalSpec`, and the closure wrapping; re-sign the four hooks to take `Engine` first. Story
collapses to one `rules.py`. The golden fixtures must again pass unchanged.
