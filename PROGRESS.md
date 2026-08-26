# PROGRESS

Tracks [PLAN.md](PLAN.md). One bullet per step; a step is ticked only once `uv run pytest`,
`ruff check`, `ruff format --check` and `basedpyright` are green.

## Phase 0 — L1: make a pending decision unmistakable

- [x] 1. `ui/theme.py` — `.game-decision` accent rule
- [x] 2. `ui/game.py` `decision_panel` — header row (icon + kind + waiting line), readable prompt, composer pointer
- [x] 3. `ui/game.py` `_composer_placeholder` — takes the `GameView`, prompts for an answer while a decision is open
- [x] 4. `ui/game.py` `chat` — drop the `Paused:` echo for the still-open decision
- [x] 5. `engines/loner3e/rules.py` `conflict_prompt` — name the moves
- [x] 6. `harness/codemode.py` `_waiting` — prefix the kind

## Phase 1 — L2: death is a reserved trait plus one `kill` command

- [x] 1. `state/entities.py` — `DEAD` slug constant
- [x] 2. `state/actions.py` — `kill` resolver
- [x] 3. `state/actions.py` `require_actor_here` — refuse a dead actor before the player early return
- [x] 4. `state/model.py` `_check_party` — reject a dead member
- [x] 5. `turn/run.py` `consume_answer` — refuse a segment once the player is dead
- [x] 6. `engines/world.py` — `Kill` args + `kill` core command
- [x] 7. `turn/prompts/director.md` — name death in the post-roll consequence list
- [~] 8. `turn/context.py` `_headline` — reverted: `entity_state` already prints
  `traits: Dead[id=dead]` in the same block, so the headline marker was a second copy
- [x] 9. `ui/game.py` — dead marker in the scene header, composer lockout
- [x] 10. `evals/turn_eval.py` — `loner3e/finish-the-rat` case
- [x] Goldens regenerated (`AIDM_GOLDEN_REGEN=1`), `test_actions.py` covers `kill`

**Phase 0 and Phase 1 are done.** `uv run pytest` 245 passed, `ruff check`, `ruff format --check`
and `basedpyright` all clean. Not run: the two live exit checks in PLAN.md, which need `uv run aidm`
and a model — a loner fight taken to a surviving exchange, and a `kill` on the rat.

## Phase 2 — L5: cut the ceremony an engine pays before it writes a rule

Steps 1 (signed `DiceEvent`) and 6 (optional `Engine.advancement`) ship with L7/L8; step 2 landed
before the phase.

- [x] 7. `engines/registry.py` — `ENGINES` discovered over `engines/*/engine.py`, in 16 lines
- [x] 8b. `authoring/draft.py` — `AuthoringBrief.label` + `BRIEFS`; `ui/create.py` `_BRIEF_LABELS` gone
- [x] 8a. loner3e `rules.py` — `outcome_for` returns a frozen `Outcome`; `HARM` gone. 24XX kept a
  `Slug` and tests `!= "success"`: an `Outcome` for one bool cost more than `HURT` it replaced
- [x] 3. `engines/core.py` — `Decision` base, `Engine.decisions`; both engines' `check_pending`/`resume` gone
- [x] 5. `engines/packs.py` — `PackCreation` base; both `Creation` classes lose the pack preamble
- [x] 4. `SheetBase.rows()` — `describe`/`sheet_view`/`overlay_rows` concrete on `SheetEngine`
- [x] Goldens regenerated, tests corrected, four checks green
- [x] Over-engineering pass, then an adversarial review: net -46 lines, four checks green

**Phase 2 is done.** `uv run pytest` 245 passed, `ruff check`, `ruff format --check` and
`basedpyright` all clean.

## Phase 3 — L9 + L10: code mode learns to launch its own agent

- [x] 1. `pyproject.toml` — `claude-agent-sdk==0.2.144`, no resolver conflict with `mcp==2.0.0`
- [x] 2. `config.py` — `harness: Literal["builtin", "external", "claude"]`, `code_mode` is
      `!= "builtin"`; `mcp.py:main` now refuses unless `HARNESS=external`, since `claude` serves
      the same tools in-process
- [x] 3. `tests/core/test_package_boundary.py` — `harness` moved from `TOPS` into `LAYERS`, so the
      flow is `app <- harness <- ui`
- [x] 4. `harness/claude.py` — `Driver`: one `Harness` on the page's own `Runtime`, `build_server`
      handed to the SDK as the `sdk` MCP instance, `strict_mcp_config`, `skills`, `interrupt`,
      `close`. `play()` yields dev-log lines, not `Message`: the UI does nothing type-specific
      with a message, and this keeps `claude_agent_sdk` out of `ui/`
- [x] 5. `ui/app.py` — `drivers` dict + `driver_for(slug)` in the page closure, `app.on_shutdown`
      closes them; `game_page(session, driver)`
- [x] 6. `ui/game.py` — `viewing` is `harness == "external"`; the driver branch sits in `_send`,
      the one callee `submit` and `decision_panel` share; `agent` dev-tab `ui.log`, composer stop
      button; `poll_save` kept in both submodes as the crash net
- [x] 7. `README.md` — `HARNESS` mode table, then the per-harness config table (L10); `opencode.json`
      at the repo root; pi excluded
- [x] One offline test — `test_the_driver_serves_this_app_s_own_mcp_server_in_process`
- [x] Live-run fix: the SDK bridge **drops `tools/list_changed`** (`sdk_mcp_bridge.py:109`), so the
      engine's commands never reached the agent and it went hunting through the repo for them.
      `Driver.opened()` opens the game *before* the first listing; `tools=["Skill", "Task"]` is all
      the skill needs, so a stray turn cannot edit the source tree either

**Phase 3 is done.** `uv run pytest` 246 passed, `ruff check`, `ruff format --check` and
`basedpyright` all clean; `HARNESS=claude uv run aidm` serves the home and game pages. Not run: the
`get_mcp_status()` assertion. The live turn itself passed: on a throwaway copy of
`whispering-vault--kael--loner3e`, "I search the study." ran `rules → start_turn → roll_question →
reveal → move → advance_thread → add_trait → end_turn` with no stray tool calls, 34.8s, $0.43, and
the save went from turn 0 to turn 1.

## Phase 3b — every harness the app can launch, and authoring from the UI

Asked for after Phase 3 landed. `claude` proved the shape; the rest of the CLIs share one base.

- [x] `harness/driver.py` — `Driver` Protocol, `opening()` (the first message: which skill, which
      game, and "the tools carry the whole game, do not read the repository" — that last sentence
      cut a codex turn from 1.34M input tokens of repo spelunking to a straight run of tool calls),
      `clip()`
- [x] `harness/exec.py` — `ExecDriver`, the shared subprocess half: spawn, `HARNESS=external` in the
      child's env so its MCP server will run, JSONL off stdout, unparseable lines kept to explain a
      non-zero exit. A subclass writes `argv()` and `line()` and nothing else
- [x] `harness/codex.py` — `CodexDriver`, ~25 lines. `--approve-for-me`, because `codex exec`
      cancels every MCP call under its default `never` policy (openai/codex#24135) and the only
      other way through is the flag that drops the sandbox too
- [x] `ui/create.py` `agent_scenario_page` — the authoring page code mode never had: the same
      fields `BeginScenario` takes, one instruction to the agent, the same log
- [x] `ui/app.py` — `driver_for(slug)` matches on the harness value and memoises one conversation
      per game; `slug=None` is the authoring conversation
- [x] `ui/game.py` — `poll_save` inside the driver loop, since a spawned CLI commits from its own
      process and the save is the only channel back
- [x] `harness/opencode.py` — `OpencodeDriver`, `--auto`. The event type is `tool_use` and the
      part's own type is `tool`: matching the obvious one silently drops every tool line
- [x] `harness/pi.py` — `PiDriver`, `-p --mode json --no-context-files --`. Upstream still ships no
      MCP; the user's `pi-mcp-adapter` extension reaches `.mcp.json` and proxies every tool behind
      one `mcp` tool. `--no-context-files` is load-bearing: pi otherwise reads CLAUDE.md, obeys
      "load the i-have-adhd skill", and spends a turn before touching the game
- [x] `harness/exec.py` `limit=2**20` — pi's closing event carries the whole history on one line and
      asyncio's 64 KiB default raises `ValueError` mid-turn, after the commit
- [x] `harness/mcp.py` — the stdio server accepts any code-mode value, not `external` alone.
      `codex exec` strips the environment of the MCP servers it spawns, so a driver cannot hand its
      child a `HARNESS` at all; the child reads `.env` and must find its own value acceptable

## Phase 3c — adversarial review of 3b, and every mode proven live

- [x] `harness/exec.py` — `play()` gained a `finally`: an abandoned generator (the composer's stop
      button, or any failure inside `working()`, which swallows) used to leave the CLI playing on
      into the next turn
- [x] `harness/exec.py` — `start_new_session=True` plus `killpg`. `terminate()` reached the CLI and
      not the MCP server it spawns underneath itself, so every stop leaked one server holding the
      save. Proven by `test_abandoning_a_turn_kills_the_cli_it_spawned`: 30s before, 0.01s after
- [x] `ui/game.py` — a chosen decision option reaches the agent as `(option_id: …)` in the text.
      `_send` had dropped the `Answer`, so `start_turn`'s `option_id` could never be filled
- [x] `ui/create.py` — the authoring instruction named `source=none` when nothing was uploaded, and
      the tool would have opened a file called `none`
- [x] `ui/app.py`, `harness/*.py` — docstrings that restated the code deleted; `GameView.driver`'s
      comment claimed `claude` only and was wrong for the other three
- [x] `README.md` — rewritten shorter and in simplified English: 178 → 158 lines, 1273 → 1100
      words, licensing collapsed into one table, and the `state ← … ← harness ← ui` import line
      corrected

**Live, one turn each**, on the real save restored to turn 2 between runs, all six advancing it to
turn 3 with `start_turn` and `end_turn` observed:

| harness | result | seconds | reported cost |
|---|---|---|---|
| `builtin` | pass | 64.2 | — |
| `external` | pass (server starts, no `SystemExit`) | — | — |
| `claude` | pass | 34.1 | $0.3315 |
| `codex` | pass | 60.1 | 362 808 in / 2 446 out |
| `opencode` | pass | 36.4 | per-step tokens only |
| `pi` | pass | 45.1 | $0.1381 |

**Session resume was built, then deleted.** A two-turn run proved `pi`, `opencode` and `claude`
resumed correctly and that `codex exec resume` cannot: it takes no `--approve-for-me`, so it
cancels every MCP call (openai/codex#24135 again). Chasing a config equivalent found `auto_review`,
which is a struct with no documented shape. The deletion is not a workaround for that. History
already reaches the agent from the save — builtin rebuilds it as chat messages, code mode as the
`RECENT PLAY` section — so a resumed session was a *second* copy of it. Every harness now opens one
conversation per turn and remembers only what the save carries. `ClaudeDriver` reconnects per turn
for the same reason, which also fixed a client left connected when a turn raised.

- [x] `RECENT PLAY` moved above the scene render: the state nearest the end is what weighs most
- [x] `TurnConfig.recent_exchanges` (20) replaces `RECENT_EXCHANGES`, and builtin now reads the same
      depth, where it used to send the whole history unbounded
- [x] `TurnConfig.harness_model` reaches all four drivers — `-m` for codex and opencode, `--model`
      for pi, `ClaudeAgentOptions.model` — with empty leaving each CLI's own default alone
- [x] Audited offline: on a fresh `Runtime`, every mode is shown turn 1's action and prose exactly
      once, and no driver passes a session flag

**The cards stream in every mode.** In code mode they all appeared at once at `end_turn`, because a
`MechanicEvent` lived only on `Exchange` and an `Exchange` is only built when the turn closes.
`Game.turn_events` now holds the turn in flight, so the save carries it and `poll_save` streams it
for the spawned CLIs too. Written in `TurnRecord.landed`, the funnel every mechanic already passes
through, so no commit site had to remember; cleared in `close_segment`, and in `consume_answer`
because the stop button abandons a turn and leaves its cards on the draft. A driver-side `watch()`
callback was written first and deleted: it could only ever have worked for `claude`.

**Known gaps.** `opening()` tells the agent not to read the repository, but `codex` and `opencode`
have no in-band skill delivery and must read `.agents/skills/…/SKILL.md`; both also load
`i-have-adhd` first, which a turn of play does not need. `agent_scenario_page` has no test. The
in-process `claude` path is the cheap one; the spawned CLIs pay a full context per turn.

## Not started

Phase 4 (I4).
