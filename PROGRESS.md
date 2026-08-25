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
- Deferred to PLAN step 3.8: `EntityId = NewType("EntityId", Slug)` deletes `CheckedEntityId` outright, but it also constrains every `EntityId` director tool parameter and so moves the golden schemas. It waits until Phase 3 stops deriving tool schemas from function signatures.

Verified: `grep -rn "ContentSlug\|OptionId" src/ tests/` finds nothing. `test_entity_ids_use_one_grammar` pins the new rule and `test_actions` pins the id cap on improvised items. `uv run pytest` 261 passed, `uv run basedpyright` 0 errors. `ruff check` / `ruff format --check` report only pre-existing failures in `docs/chat-claude-mock/claude-ui-poc.py` and in the untracked `PLAN.md`; nothing this phase touched is flagged.

## Phase 2 — Required engine capabilities — DONE

- 2.1 `engines/sheets.py` merged into `engines/core.py` and deleted; imports fixed in `loner3e/engine.py`, `loner3e/rules.py`, `twentyfourxx/engine.py`, `twentyfourxx/rules.py`, `core_test_support.py`, `test_player_events.py`. Order inside `core.py`: `Advancement` above `Engine` (its annotation needs it), then the counter helpers, then the sheet block — `render_counters` calls `pool`, so `pool` comes first.
- 2.2 `Engine` and `SheetEngine` stay two classes, with the one-line `reportIncompatibleVariableOverride` ignore. The generic fold was not attempted.
- 2.3 `advancement: Advancement` and `creation: CharacterCreation` declared next to `mechanics_type`; the two `= None` assignments in `Engine.__init__` deleted. Every guarded branch in the plan's table removed: `core.py::seed`, `runtime.py` (`build_advisor`, `offers`, `_advancement`), `codemode.py` (`open_game`, `rules`, `propose_advance`), `ui/game.py`, `ui/create.py`.

Review follow-ups (adversarial pass):
- `test_engine.py` needed no capability stub at all: no assertion reads either attribute, so `BareAdvancement`/`BareCreation` and the `advancement.md` fixture went, and the test kept its original name.
- Three narrowing helpers existed only to turn `X | None` into `X` and are now dead: `core_test_support.py::capability` (11 call sites), `test_create.py::_creation`, and four `assert creation is not None` in `test_twentyfourxx_engine.py`. All deleted and inlined.
- `runtime.py::build_advisor` became a passthrough over `advisor_agent(engine.advancement, settings)`; deleted and inlined at its two call sites. `propose`, `preview` and `apply_proposal` bind `advancement` locally rather than repeating `self.engine.advancement`.
- `Harness.advance_args` was an optional field only `open_game` ever set, so both its guards (`codemode.py::propose_advance` and `mcp.py::offered`) were unreachable. It is now a method deriving the model from `opened()`, which also folds `_advance_args` in. `offered()` still publishes the two tools only when a game is open, as PLAN 2.3 asks.
- `CharacterCreation`'s docstring lost its reason with the optional capability; deleted rather than reworded.

Verified: `grep -rn "advancement is None\|creation is None\|advancement is not None\|creation is not None" src/ tests/` finds nothing. 261 tests passed, Ruff check and format passed, basedpyright 0 errors.

## Phase 3 — Framework-free commands — DONE

- 3.1 `Command`, `command()`, `run_command()` and `apply_play` (was `apply_tool_call`) live in `engines/core.py`. `sequential_toolset` and `with_enum` deleted. Refusals are `ValueError`; only the Pydantic AI adapter turns them into `ModelRetry`.
- 3.2 `engines/world.py` holds the nine core commands. `DirectorTool`, `core_toolset`, `_resolved`, the five applicability predicates, `_unlock_targets`, `_narrow_unlock_targets` and `gated_toolsets` deleted from `turn/run.py`.
- 3.3 `Engine.director_commands` replaces `director_toolsets`. 24XX lost `_skills_in_play`, `_narrow_to_skills_in_play`, `_with_skills` and both `.filtered(...)`/`.prepared(...)` chains; `settle_defence` refuses in the resolver instead.
- 3.4 `as_tool` and `director_toolset` are the whole Pydantic AI adapter, at the top of `turn/run.py`; `schema_of` sits in `llm.py` with the rest of the framework boundary.
- 3.5 `reshapes` deleted; `send_tool_list_changed` fires only on `open_game`. `codemode.director_tools` and `_unavailable` deleted; `call_director_tool` is synchronous.
- 3.6 `AdvanceArgs[P: ProposalBase]` replaces `create_model`; `_advance_args` deleted.
- 3.8 **The plan's mechanism does not work.** `NewType("EntityId", Slug)` is not a valid type form — Pydantic unwraps it at runtime, but basedpyright reports 945 errors across 20 files and ruff rejects the `TypeAlias` line written to appease it. `EntityId` stays `NewType("EntityId", str)` and `CheckedEntityId` carries the grammar on every Pydantic field that holds an entity id, which reaches the same schemas. The `Entity`/`Exit`/tool-argument fixture diff is what 3.8 asked for.

Review follow-ups (adversarial pass):

- `tests/core/test_code_mode.py` was never updated and was the only red in the suite. Its five director payloads used the nested `{"attempt": {...}}` shape; the published schema has always been flat, and pydantic-ai's signature-derived validator was silently tolerating both. `Frozen`'s `extra="forbid"` now rejects the wrong one. Four `offered()` assertions about tool filtering deleted; two `pytest.raises(ModelRetry)` became `ValueError`, which is what the gate raises.
- `tests/core/test_tools.py` deleted. Its two replacements were a hand-written list of the nine command names and an assertion that a tuple is non-empty; `test_golden_schemas.py` already pins names, descriptions and schemas for both engines.
- Two invariants were deleted rather than ported, and are back: `test_one_hit_is_settled_once` in `test_twentyfourxx_engine.py` (the refusal `_settle_defence` still enforces), and the suspension gate, which `test_a_resume_that_re_suspended_may_still_develop_what_the_answer_caused` covers on both branches.
- `command_schema(Command)` became `schema_of(type[BaseModel])` and `ServerTool.published()` uses it too. `propose_advance` was publishing `"title": "AdvanceArgs[AdventureGrowth]"`; every MCP schema now drops the argument class name the same way the director's do.
- `apply_action` in `engines/core.py` wraps the thirteen handlers that call `aidm.state.actions` and never roll. `_world_command` in `world.py` carries `during_suspension=True` once instead of nine times. `NoArgs` replaced three empty argument models.
- 24XX's `director_commands()` closed over nothing and is now the `DIRECTOR_COMMANDS` constant; loner3e keeps a function for `roll_question` alone, which is the only handler that needs `twists`.
- `world.commands(engine)` is the one place core and engine commands merge, for the agent, MCP and code mode alike.

Second review pass (adversarial), after the first was staged:

- `sequential_toolset` set `require_parameter_descriptions=True`; nothing replaced it, so a new argument field could have shipped to the model with no description. `command()` now refuses one at import, and `test_a_command_parameter_the_model_cannot_read_is_refused` pins it.
- `apply_command` renamed `apply_play`: it takes a `Play`, not a `Command`, and it sits three definitions from `Command`, `command()` and `run_command()`, which all do take one.
- `_defence_to_settle` lost its second caller with the `.filtered(...)` chain, and its one survivor raised on `None`; inlined into `_settle_defence`.
- `schema_of` moved from `turn/run.py` to `llm.py`. `mcp.py` was importing it through the turn module to build schemas for `list_games` and `open_game`, which have no turn.
- One `NoArgs` again: `codemode`'s copy deleted, `ServerTool.args` widened to `type[BaseModel]`. `mcp.py` had `_published(Command)` duplicating `ServerTool.published()`; both go through one `_published(name, description, args)` now, and `_advance_tools` is inlined at its one call site.
- Left alone on purpose: `unlock_exit` still refuses without naming the locked ways out, the way `_require_skill` names an actor's skills. PLAN 3.9 sequences that after the eval so the enum removal is measured alone — and the eval says it is not needed.

- 3.9 run against `evals/results/after-stake-flatten.json`, 11 cases x 9 repeats, seed 1000: score 99% -> 99%, errors 0% -> 0%, director_calls 1.19 -> 1.16. `twentyfourxx/open-the-way-and-climb` gained a run and `twentyfourxx/risky-climb` lost one; every other case held at 100%. The removed enums cost nothing measurable — a model guessing ids would have shown up as retries in `director_calls`. Mean seconds moved 11.7 -> 16.1, which is the OpenRouter backend, not the schemas: latency rose on ten of eleven cases while the round-trip count stayed flat or fell (`risky-climb` is +16.1s on *fewer* calls). Recorded in `evals/results/after-commands.json`.

## Phase 4 — Package moves — TODO
