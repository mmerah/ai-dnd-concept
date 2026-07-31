# Refactor progress

Tracking `REFACTOR.md`. One bullet per gated step.

## 1a — merge the distributions (pure move)

- [ ] Move four `src/` trees to a single root `src/`
- [ ] Merge test dirs into `tests/{core,story,dnd5e,ui}`
- [ ] Collapse five `pyproject.toml` into one real distribution
- [ ] Retarget `test_package_boundary.py`
- [ ] Gate: `uv run pytest`, `ruff check`, `basedpyright` green with import edits only

## 1b — delete the engine seam and versioning

- [ ] `engine_for(engine_id, config)` replaces `EngineRegistry`
- [ ] One concrete `Engine` per ruleset; `StoryDirection | Dnd5eDirection` unions
- [ ] `domain/actions.py` moves into the Story engine
- [ ] Delete stamps/descriptors/compatibility
- [ ] `save_version` required and checked in `FileSaves.load`; stale trace refused
- [ ] Gate: tests green, stale save/trace refused with a readable error
