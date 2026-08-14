# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Next

- PLAN.md Phase 1: the scenario creator script, which binds to `ScenarioWorld`,
  `Engine.rules_type`, `write_scenario` and `begin_game` — all landed.
