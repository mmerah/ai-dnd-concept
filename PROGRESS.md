# Progress

Tracking PLAN.md: one entry per shipped phase, plus the facts a later phase would otherwise have
to rediscover. Step-by-step detail lives in git history, not here. Every entry was green on
`uv run pytest && ruff check && ruff format --check && basedpyright`.

## Done

### Phase 1 — Scenario creator

Done-when met: `scripts/create_scenario.py rats-of-thornhill "..."` produced
`scenarios/rats-of-thornhill/`, which appears on the home page and plays under both engines.

- `scripts/create_scenario.py <slug> "<premise>"` is a three-line shim over
  `aidm.app.scenario_creator`, which lives in `app` because it composes engines, `Stage`, and
  `begin_game`. Role key `scenario_creator` drives every call.
- **The world is authored agentically, not in one answer.** A one-shot
  `NativeOutput(ScenarioWorld)` was built first and failed live: weak models answered the huge
  schema with a `"..."` template, and one bad field threw away the whole document. It was
  replaced by an agent that builds a `WorldDraft` (its `deps`) through four tools —
  `worked_example`, `scenario_so_far`, `write(ScenarioPatch)`, `validate_scenario` — where a
  patch upserts by id, so "modify" needs no second tool. Editing a scenario conversationally in a
  later phase is the same agent with a draft loaded from disk.
- **The run ends on a `finish` tool** (`ToolOutput(str, name="finish")`, argument `response`), not
  on bare text: an author that only ever calls tools never ends its own turn, which hung the first
  real run until the request limit. Its output validator refuses `finish` while the draft does not
  play, so the agent is asked again with the reason. `UsageLimits(request_limit=40)` bounds a
  spinning run.
- The overlay stayed one-shot `NativeOutput(TypedOverlay[engine.sheet_type])` (parametrised at
  runtime from the dynamically imported engine, one narrow pyright ignore) with
  `ask_until_playable`: its output is small and it never failed. Overlays are written with
  `exclude_defaults=True`, so a generated file is as terse as a hand-written one.
- `Playtest` (engine + the shipped `kael`) is what refuses a world; `playability()` adds the
  authoring bar and reports **every** unmet item at once, because an author fixing one per round
  burns the request limit. `authored_world` revalidates after the run — the agent saying "ok" is
  never trusted — and `main()` folds any failure into one readable line.
- **Validation gained four canon invariants**, all on `ScenarioWorld` and never on `WorldState`:
  the Worldkeeper creates locations mid-game, so a commit-time reachability rule would fail the
  turn. They are: every location reachable by any `connected` way; every *known* location
  reachable by *known* ways (a place the player knows of but cannot walk to is a dead end); hook
  `match.data` ids exist; hook *effect* ids exist. The last two share one pooled-id helper with
  `check_hooks`. Ids an effect **creates** (`trait_id`, `stage`) are deliberately not policed.
- `HookMatch.kind` is `HookFactKind`, a `Literal` of the fact kinds core emits from world ops.
  Engine kinds (`conflict_lost`, `job_completed`, advancement growth) are excluded for the same
  reason hook effects are: one `world.json` is loaded by every ruleset. `hook_fired`/`hook_failed`
  are excluded too — `fire_hooks` feeds each round's facts back in, so matching them self-feeds to
  the round cap. A test greps the emit sites both ways so the `Literal` cannot rot. **A
  consequence worth knowing: an authored hook can no longer react to any engine fact.** Wanting
  that means a per-engine hook surface, not a wider `HookMatch.kind`.
- No new `Engine` API was needed for PLAN step 3's "engine-provided authoring guidance": the
  strict sheet schema carries the fields and defaults, and the shipped
  `whispering-vault/<engine>.json` is the worked example.
- `scenario_creator` carries its own defaults in `config.ROLE_DEFAULTS` (strong model, 32k tokens,
  high reasoning — the turn-loop 2048 cannot emit a world). `Settings.role` merges a partial
  `ROLES__SCENARIO_CREATOR__...` override over them through a real validation call, so setting one
  field does not silently reset the rest.
- `write_scenario` takes `Mapping[EngineId, ScenarioOverlay]`: nothing lands on disk until every
  shipped engine validates. Tests build `Settings` with `env_file=None` — the suite was reading
  the checkout's `.env`. No persisted-byte change: `SAVE_VERSION` unmoved, no fixture moved.
- Quality of a generated scenario is judged by playing it, not by the validator. What the first
  one got wrong and no rule can catch: the thread's destination was an empty room, and the
  creature the title turns on had no hook. Both are now questions in the prompt's review pass.

## Next

- PLAN.md Phase 2 (progressive world expansion: Expander tool, strict topology, Adventure
  triple, premise-start), Phase 3 (source system: PDF ingestion, grounded expansion, fused
  authoring), Phase 4 (media), Phase 5 (player-facing UI per docs/ui-mock + journal export).
- 2026-08-17: `docs/ADVENTURE-SOURCES-RESEARCH.md` and `docs/SYBYL-LEARNINGS.md` were adopted
  into the plan. Decisions: Expander behind a Director tool (not Director-owned create effects);
  Worldkeeper keeps creation but locations are created with a connection; the full
  `GameState + CanonSource + ExpansionPolicy` triple with a real PDF source system, no interim
  stand-ins; scenario authoring and PDF ingestion share one source system.
