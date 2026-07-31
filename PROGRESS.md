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

## Next — item 2: one canonical state

`GameState.engine: StoryState | Dnd5eState`, the `Dnd5eActor` join view, and deletion of the
5e mirror (`conversion.py`, `domain/models/{entities,state,base}.py`, both `codecs.py`).
`scene_state.py` can only go once item 3 gives the Director stage the real `GameState`.
