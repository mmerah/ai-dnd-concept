# Phase 1 progress

- [x] Step 1 — extract `with_enum` into `engines/transact.py`, delete `_with_skill_enum`
- [x] Step 2 — narrow `unlock_exit.to_id` via `_narrow_unlock_targets` prepare in `turn/tools.py`
- [x] Step 3 — delete `reveal`-then-`move` clause from `turn/prompts/director.md`
- [x] Verify — regen prompt goldens (schema goldens pin the unprepared vocabulary — unchanged by design), read diffs, gate green (pytest/ruff/format/basedpyright)
- [x] Stage (no commit); live eval n=9 left to maintainer (manual per AGENTS.md)

# Phase 2 progress

- [x] Step 1 — required `Scenario.engines` (min_length=1); both shipped `world.json` declare `["loner3e", "twentyfourxx"]`
- [x] Step 2 — `load_catalog` reports `scenario.engines` and skips a scenario naming an uninstalled engine with a warning
- [x] Step 3 — `WorldDraft.engines` (hidden from `as_json`, absent from `ScenarioPatch`), `AuthoringSession.engines`, `playtests(config, engines)`, engine multi-select in `ui/scenario_create.py`
- [x] Step 4 — `CharacterOverlay.entities`, `_require_authored` and `Character._overlay_fits_the_character` deleted; `begin_game` rules are `{PLAYER_ID: overlay.character}`
- [x] Step 5 — `EngineBinding` and `Engine.binding()` deleted; `load_character(directory, name, engine, check_overlay)`; six call sites updated (app/session, evals, four test modules)
- [x] Verify — gate green (pytest/ruff/format/basedpyright 0/0/0); no eval run (turn loop untouched); save goldens unchanged (a save holds `ScenarioMeta`, not `Scenario`)
- [x] Adversarial review — trimmed the fat the phase left: `read_scenarios(directory, engines)` yields the playable subset like `read_characters` does (skip and intersect in one place, duplicate ids collapse), write-only `Character.engine` deleted, `actor_sheets` collapsed to the player, `WorldDraft.engines` dropped for `scenario(engines)`
- [x] Stage (no commit) — src/ nets +1 with the new engine multi-select included, about −30 without it
