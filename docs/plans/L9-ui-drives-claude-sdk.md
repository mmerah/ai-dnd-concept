# L9: code mode learns to launch its own agent

Code mode has one submode today: you run `claude` or `codex` yourself and `uv run aidm` polls the save
(`ui/game.py:391 poll_save`), because the agent's MCP server is a second process holding a second
`Runtime`. L9 adds the submode where the app launches the agent — for Claude, in-process, one writer.
The poc (`docs/chat-claude-mock/claude-ui-poc.py`) proves the UI half, the harness half already exists
(`harness/mcp.py`, `codemode.py`), and the poc's trick — chat fed by tool calls, not assistant prose —
is *already* how this app works. Reusable: poc:227-248, 266-283, 298, 307; dead: poc:82-118, 125-168,
319-458 (the thread bridge, `say_to_user`/`ask_user`, the Tk shell).

## Does the SDK earn its place?

The alternative is one subprocess driver reading JSONL — `claude -p --input-format stream-json
--output-format stream-json --verbose`, `codex exec --json`, the opencode equivalent — covering every
agent with no new dependency. **Verdict: keep the SDK, for one reason.** Out-of-process means the MCP
server is a second writer, which is what forces `poll_save` *and* what keeps the code-mode UI read-only:
`panels.py:133 _offered_only` and `decision_panel` (`game.py:344`) are disabled because "a second writer
here would race it". Only an in-process server shares the app's `Runtime` and collapses that to one
writer under one `Harness.lock`. Secondary: the four CLIs share no JSONL vocabulary, so one driver is
one spawner plus a parser each, and for Claude the exec driver hand-rolls `SubprocessCLITransport` and
its control channel — more code than the dep. Tripwire: a live in-process failure sends this to exec.

## Naming

One field, not two: `harness: Literal["builtin", "external", "claude"]` — *who plays the turn*: the
app's own Director/Narrator roles, an agent you run yourself, or one the app launches. `codex` and
`opencode` are the next values. `code_mode` (`config.py:129`) becomes `self.harness != "builtin"`, so
every reader keeps working (`runtime.py:376-377`, `ui/app.py:88,250`, `panels.py:133`, `mcp.py:main`).
Under two fields `harness="builtin", agent="claude"` is representable and meaningless, so a validator
would have to reject it; one field makes it unrepresentable — the fail-fast shape. (`external` over
`terminal`: the agent may run in an IDE; over `direct`: names nothing.) Transport follows the value in
one place, the driver factory in `ui/app.py`, and `GameView.viewing` becomes `harness == "external"` —
the one submode where a second process writes the save.

## Wiring

1. `Driver` (new `harness/claude.py`) builds `Harness(settings, runtime)` (`codemode.py:140`) on the
   *same* `Runtime`, so `open_game` returns the page's memoised `GameSession` and each `commit` lands
   in the object the page renders — no polling to see a turn.
2. `mcp_servers={"aidm": {"type": "sdk", "name": "aidm", "instance": build_server(harness)}}`:
   `harness/mcp.py:177` already returns an `mcp.server.Server`, exactly what `McpSdkServerConfig` takes
   — no second tool surface, no stdio subprocess, no duplicated schema.
3. `ClaudeSDKClient(options)`, `query(text)`, then over `receive_response()`: `AssistantMessage` blocks
   → `TextBlock.text` and `ToolUseBlock(id, name, input)` to the dev log; a `UserMessage` carrying a
   `ToolResultBlock` means a tool committed → `view.refresh_all()`; `ResultMessage` ends the turn. The
   bubble is free — `end_turn` committed it and `chat()` draws it.

Verified against claude-agent-sdk 0.2.144 (context7 + upstream): every name above, plus `interrupt`,
`get_mcp_status` and the step-4 options. `_mcp_compat.py` supports mcp 1.x **and** 2.x, and
`sdk_mcp_bridge.py` serves the given `Server` over mcp's in-memory transport — ours works verbatim.

## Dev tab

`game.py:435` already has a dev tab (`trace`, `state`). Add an `agent` expansion holding one
`ui.log(max_lines=500)`: native, no refreshable, no list state, pushed from the coroutine reading the
stream. Fields: `ToolUseBlock.name`/`.input` through poc's `describe()`, `TextBlock.text`,
`ToolResultBlock.is_error`, and one closing line per turn from `ResultMessage.total_cost_usd` and
`.usage`. The rest of `ResultMessage` (`permission_denials`, `duration_ms`, `num_turns`, `model_usage`)
is one line away when someone asks; a running-total label is a dashboard, not a dev log.

## Approach

- Skipped: a harness-abstraction layer, chat-history persistence (the save is the transcript),
  `include_partial_messages` (the bubble is committed prose), a new spinner (`session.step` and
  `_inline_status` do it). Reused: `refuse_if_busy`/`working`, `poll_save` as the crash net, poc helpers.
- Media unchanged: art is whatever the app draws (`app/media.py`), in every submode — no agent supplies
  scene art; codex image generation was tried and cut as too slow and unreliable.
- `docs/plans/L10-other-harnesses.md` is the per-harness config table *under* `harness=external` (an
  `opencode.json`; pi excluded, upstream having no MCP). Zero Python, same phase, its table in step 7.

## Steps

1. `pyproject.toml`: add `claude-agent-sdk==0.2.144` (needs `@anthropic-ai/claude-code` on PATH, which
   is there); its `mcp<3.0.0,>=1.23.0` accepts the pinned `mcp==2.0.0`, so no resolver conflict.
2. **changed** `config.py:121-130`: the three-value literal, `code_mode` → `self.harness != "builtin"`,
   comment naming the submodes; `.env` and `mcp.py:main`'s `SystemExit` move to `HARNESS=external`.
3. `tests/core/test_package_boundary.py`: `FORBIDDEN` is *computed* by `_forbidden()` from `LAYERS` and
   `TOPS` (:8-29), so there is no dict entry to edit. The real change is to move `"harness"` out of
   `TOPS` into `LAYERS`, after `"app"`, leaving `TOPS = {"ui": {"aidm.engines"}}`. The flow becomes
   `app <- harness <- ui`; `CONFINED` already keeps `nicegui` out of `harness`.
4. New `src/aidm/harness/claude.py` (~60 lines): `@dataclass Driver` holding `Harness`, options and
   client; `async def play(self, text) -> AsyncIterator[Message]`; `interrupt()`; `close()`. Options:
   `cwd`, `system_prompt={"type": "preset", "preset": "claude_code"}`, `setting_sources=["project"]`
   (CLAUDE.md + the `.claude/skills` symlinks), `skills=["playing-aidm", "growing-aidm"]`,
   `allowed_tools=["mcp__aidm__*"]`, `permission_mode="bypassPermissions"`, `strict_mcp_config=True` so
   `.mcp.json` cannot spawn a *second* writer; first `play` prefixes `f"Play {slug}. Then: {text}"`.
5. **changed** `ui/app.py:221`: `drivers` in `_register_pages`'s closure, from a three-branch factory on
   `settings.harness` — `builtin` → no driver, UI interactive exactly as today; `external` → no driver,
   UI is the read-only viewer exactly as today; `claude` → a `Driver`, UI interactive. So
   `game_page(session, driver)` takes `driver=None` for the first two, and `GameView.viewing`
   (`game.py:196-198`) becomes `settings.harness == "external"` — **not** `driver is None`, which would
   turn builtin read-only, builtin having no driver either. `app.on_shutdown` closes the drivers.
6. `ui/game.py`: `submit` (:331) and `decision_panel` (:344) route to `_send_to_claude(view, text)` when
   a driver is present — set `session.step`, `async with working(session)`, iterate the driver, push to
   the log, refresh on tool results. Add the `agent` expansion at :444 and a stop button.
7. **changed** `README.md`: builtin mode, then code mode's submodes — L10's table under `external`.

## Risk / size

~140 added lines, ~15 changed, one new file, one new dep. Hazards: (a) a turn runs minutes, but
`session.busy` and `bind_enabled_from` already lock the composer and `interrupt()` is the escape; (b) a
tab closed mid-turn leaves the stream half-read and `log.push` raising — `working()` swallows it, the
harness commits per tool call and `poll_save` re-syncs, so keep both timers; (c) a second tab on one
slug is a viewer `refuse_if_busy` blocks, and all of it runs on NiceGUI's own loop, so no thread hop;
(d) unverified until a live run: whether `strict_mcp_config` really suppresses `.mcp.json`. Check: under
`HARNESS=claude`, play one action and assert `get_mcp_status()` lists one connected `aidm` server and the
save advanced a turn; offline, that the built options carry our `Server` as the sdk instance.
