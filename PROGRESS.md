# Simplification plan — progress

Tracks `PLAN.md`. The check is `uv run pytest && uv run ruff check && uv run ruff format --check && uv run basedpyright`.

## Phase 0 — One rule in `AGENTS.md` — DONE

- Pre-stability bullet added under `## Engineering`, after the "Build every agreed capability" line.

## Phase 1 — One identifier grammar — DONE

- 1.1 `SLUG_PATTERN` / `SLUG_MAX` / `Slug` moved from `config.py` into `state/entities.py`; `config.py` now imports `Slug` from state. `aidm.config` added to the `state` forbidden set in `tests/core/test_package_boundary.py`.
- 1.2 `ContentSlug` deleted; `loner3e/rules.py`, `twentyfourxx/rules.py`, `state/creation.py` use `Slug`.
- 1.3 `CheckedEntityId = Annotated[EntityId, Field(...)]` added in `state/entities.py`; applied to `Exit.to`, `Entity.id`, `Entity.parent_id`. No other `EntityId` annotation touched, so director tool schemas are unchanged; `Entity`/`Exit` JSON schemas are byte-identical to before the phase.
- 1.4 `state/entities.py::slug` deleted; `text_slug` is the one generator and `actions.improvise` calls it, because an uncapped id now fails `Entity.id`'s 64-character rule. `_unused` lost its `join` and `limit` parameters with it.
- 1.5 `OptionId` deleted; `state/play.py`, `engines/core.py`, `twentyfourxx/engine.py`, `twentyfourxx/rules.py`, `app/codemode.py`, `tests/core/test_decisions.py` use `Slug`.
- 1.6 Ten underscore ids rewritten to hyphens across 22 files (two `world.json`, the golden fixtures, seven tests, `evals/turn_eval.py`, `scenario_world.md`). Five more test-local ids the plan did not list (`sub_crypt`, `frayed_rope`, `loose_stone`, and `test_media.py`'s generated ids) failed the new `Entity.id` pattern and were rewritten too. The stale save under `saves/` was deleted, not migrated.
- 1.7 `scenario_world.md` line 15 now says "unique lowercase id of words joined by hyphens".

Review follow-ups (adversarial pass):
- `content_id` now checks `SLUG_MAX` too; it silently accepted over-long directory names that no `Slug` field would take.
- `_SAVE_SLUG_PATTERN` in `content/io.py` dropped its underscore allowance — save stems are three kebab ids joined by `--`.
- `text_slug` renamed to `slug`: it is the only generator now, so the prefix was noise. Two shadowing locals in `ui/create.py` became `character_id` and `scenario_id`.
- Deferred to Phase 3: `EntityId = NewType("EntityId", Slug)` deletes `CheckedEntityId` outright, but it also constrains every `EntityId` director tool parameter and so moves the golden schemas. Revisit once Phase 3 stops deriving tool schemas from function signatures.

Verified: `grep -rn "ContentSlug\|OptionId" src/ tests/` finds nothing. `test_entity_ids_use_one_grammar` pins the new rule and `test_actions` pins the id cap on improvised items. `uv run pytest` 261 passed, `uv run basedpyright` 0 errors. `ruff check` / `ruff format --check` report only pre-existing failures in `docs/chat-claude-mock/claude-ui-poc.py` and in the untracked `PLAN.md`; nothing this phase touched is flagged.

## Phase 2 — Required engine capabilities — TODO

## Phase 3 — Framework-free commands — TODO

## Phase 4 — Package moves — TODO
