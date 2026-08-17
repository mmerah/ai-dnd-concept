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

### Phase 2 — Progressive world expansion

Done-when met: a game whose `world.json` says `"expansion": "generative"` plays turns in which the
Director materializes canon mid-plan through `expand_world` and walks the player into it; a
`closed` scenario plays with a byte-identical Director agent. No save byte moved — `SAVE_VERSION`
stayed 70, and only the worldkeeper instructions and the `worldkeeper_report` schema fixture drifted.

- **Movement now follows explicit topology, always.** The `_require_open_way` wildcard (an
  exit-less location could reach anywhere) is gone, and `connected` is refused when `directed`.
  The consequence that made step 1 mandatory rather than cosmetic: a Worldkeeper-created location
  would otherwise be unreachable forever, so `apply_report` writes an undirected `connected`
  relation from it to the location its `location` field names — which is why that field's
  description and the worldkeeper prompt now say "the place it connects to". The relation is
  `known` only when the anchor is: a known relation may not name an entity the player has not met,
  and the Worldkeeper is shown unrevealed canon it may anchor to.
- **The adventure triple is `GameState` + `ScenarioWorld.expansion` + a `CanonSource`.**
  `content/sources.py` holds the policy literal, the protocol, and `PremiseSource`;
  `store.read_source` reads the scenario dir's `source.md` and falls back to `meta.premise`.
  Nothing lands on `GameState`, so a save resumes under its scenario's policy and a restart replays
  the same opening. `Runtime._open` is the only place a source is built, through `open_source`,
  which returns None for `closed` — that check is the only reader of the policy, so **no
  `Adventure` record carrying it exists**: an `Adventure(policy, source)` pair was written and
  deleted in review because nothing ever read `policy` back. Phase 3's `grounded` branch adds the
  parameter it actually needs at `build_stages` when it exists.
- **The Expander is a role behind a Director tool, not a pipeline stage.** `turn/expansion.py` is
  the leaf — `ExpansionPatch`, `Expansions`, and `apply_patch`, the one
  resolver that reaches the world. The stage and toolset live in `turn/roles.py` with the other
  role builders: `roles` already owns `Stage` and `PlanContext`, so putting the stage in
  `expansion.py` would have needed both extracted to break a cycle, for nothing.
- **What keeps the leak rule holding by construction:** every entity in a patch is forced
  `known=False`, so `draft.add` emits an `entity_created` fact whose `narrator` is already None;
  relations, threads, and hooks emit `canon_materialized`, a kind `HookFactKind` deliberately
  excludes and which never narrates. The Director's own `reveal`/`relation-change`/`move` effects
  are the only way the player learns anything. The one place this had to be added by hand is
  `_connect`: its trace names the *anchor*, so it narrates only when the anchor is known — gating
  on the created location alone (always `known=True`) put an unmet name in `Fact.narrator`, which
  is persisted and which Phase 5's journal export will read.
- **The tool applies through `transact`**, so created actors are seeded and hooks fire on the one
  mutation sequence. `PlanContext` grew the turn's `rng` and an `Expansions` record; the first
  Director call now receives the turn draft rather than the committed state (byte-identical at that
  point) so the tool has something disposable to write into. A patch is refused twice: by the
  Expander's own output validator (so the *Expander* retries, not the Director), then really by
  `transact` — which is outside the tool's `try`, because a half-applied draft is not a state to
  plan another beat against. **That only holds because the trial runs the whole sequence**: the
  validator wraps `transact` too, not just `apply_patch`, or hook-firing and seeding would be
  unexercised until the real pass, where a failure kills the turn instead of asking again.
  `expand_world` is registered `sequential=True` — two calls in one model answer would otherwise
  interleave on the same draft, each validating against a state without the other's canon, and both
  slipping the cap. Cap is 2 per turn; a bad `anchor_id`, the cap, and an Expander that exhausts
  its retries each get their own retry message, because "plan with what exists" is wrong advice for
  a typo'd id.
- **`--opening` authors a slice, not a scenario.** A `Brief` (instructions + bar + policy) is what
  `playability`, `authoring_toolset`, `world_stage` and `authored_world` now take, defaulting to
  `FULL`. The bar text moved out of `scenario_world.md` into `scenario_bar.md` /
  `scenario_opening.md`. `write_scenario` grew an optional source argument.
- **Live probe passed first try (working rule 2), 2026-08-17.** `ExpansionPatch` is ~5.5 KB of
  JSON schema — 2.5x the DirectorBeat envelope — and gpt-oss-120b answered it cleanly under
  `NativeOutput` at 8192 tokens / medium reasoning. A premise-start scenario, one turn of "I follow
  the road north": the Director called `expand_world`, the Expander returned one location and its
  undirected `connected` relation, and the Director's own `reveal` + `move` walked the player in.
  **The standing "keep the schema tiny" rule was over-fitted to the old 15-17 KB failure** —
  reusing the real `Entity`/`Relation`/`Thread`/`Hook` models is fine, so a later role should probe
  at the size its domain wants rather than hand-shrinking a parallel wire shape first.
- Observed in that probe, not fixed: the Expander wrote `detail.description` in second person
  ("A faint glint catches your eye"). Cosmetic — `detail` reaches the Director and Worldkeeper, not
  the Narrator — but `expander.md` says "you write records, never prose the player reads" and the
  model still drifted. Worth a sharper line there if it recurs.

## Next

- PLAN.md Phase 3 (source system: PDF ingestion, grounded expansion, fused authoring), Phase 4
  (media), Phase 5 (player-facing UI per docs/ui-mock + journal export).
- 2026-08-17: `docs/ADVENTURE-SOURCES-RESEARCH.md` and `docs/SYBYL-LEARNINGS.md` were adopted
  into the plan. Decisions: Expander behind a Director tool (not Director-owned create effects);
  Worldkeeper keeps creation but locations are created with a connection; the full
  `GameState + CanonSource + ExpansionPolicy` triple with a real PDF source system, no interim
  stand-ins; scenario authoring and PDF ingestion share one source system.
