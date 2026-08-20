# Phase 1 progress

- [x] Step 1 — extract `with_enum` into `engines/transact.py`, delete `_with_skill_enum`
- [x] Step 2 — narrow `unlock_exit.to_id` via `_narrow_unlock_targets` prepare in `turn/tools.py`
- [x] Step 3 — delete `reveal`-then-`move` clause from `turn/prompts/director.md`
- [x] Verify — regen prompt goldens (schema goldens pin the unprepared vocabulary — unchanged by design), read diffs, gate green (pytest/ruff/format/basedpyright)
- [x] Stage (no commit); live eval n=9 left to maintainer (manual per AGENTS.md)
