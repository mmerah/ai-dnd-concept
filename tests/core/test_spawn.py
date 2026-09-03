import json

import pytest

from aidm.app.spawn import ClaudeDriver, CodexDriver, RunResult, ask, child_environment
from aidm.config import RoleConfig
from aidm.core.play import Narration

CODEX_OUTPUT = "\n".join(
    (
        '{"type":"thread.started","thread_id":"abc-123"}',
        '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"lines\\": []}"}}',
        '{"type":"turn.completed","usage":{"input_tokens":900,"cached_input_tokens":700}}',
    )
)


def test_the_master_alone_is_given_this_games_tools() -> None:
    config = RoleConfig(model="opus", effort="high")
    master = ClaudeDriver().command("master", config, None, "http://localhost:1/mcp/")
    narrator = ClaudeDriver().command("narrator", config, None, "http://localhost:1/mcp/")

    assert "--restricted" in master and "--restricted" in narrator
    assert "http://localhost:1/mcp/" in " ".join(master)
    # The flag that lets the master reach the server at all.
    assert "--allowed-tools" in master and "mcp__aidm" in master
    assert "--mcp-config" not in narrator
    # A prompt follows the command, so the last flag must not take a list.
    assert master[-1] == "--strict-mcp-config"


def test_a_resumed_command_names_the_conversation_to_carry_on() -> None:
    config = RoleConfig(provider="codex", model="gpt-5", effort="low")
    cold = CodexDriver().command("worldsmith", config, None, "")
    warm = CodexDriver().command("worldsmith", config, "abc-123", "")

    assert "resume" not in cold
    assert list(warm[:4]) == ["codex", "exec", "resume", "abc-123"]
    assert "model_reasoning_effort=low" in warm


def test_only_the_master_is_let_out_of_the_sandbox_and_no_role_sees_the_account() -> None:
    config = RoleConfig(provider="codex", model="gpt-5", effort="low")
    master = CodexDriver().command("master", config, None, "http://localhost:1/mcp/")
    narrator = CodexDriver().command("narrator", config, None, "")

    # `resume` accepts no sandbox flag, so a writer's box rides `-c`, which both forms accept.
    assert "--sandbox" not in master and "--sandbox" not in narrator
    assert "--approve-for-me" in master and "--approve-for-me" not in narrator
    assert "sandbox_mode=read-only" in narrator and "approval_policy=never" in narrator
    assert "mcp_servers.aidm.url=http://localhost:1/mcp/" in master
    assert not any(one.startswith("mcp_servers") for one in narrator)
    for argv in (master, narrator):
        # `--ignore-user-config` leaves the account's own MCP servers standing; this removes them.
        assert ["--disable", "apps"] == [
            argv[i] for i in (argv.index("--disable"),) for i in (i, i + 1)
        ]
        assert "--ignore-user-config" in argv
        assert "web_search=disabled" in argv


def test_a_claude_reply_that_is_not_json_is_a_broken_run() -> None:
    with pytest.raises(ValueError, match="no JSON result"):
        _ = ClaudeDriver().parse("I ask in prose.")


@pytest.mark.parametrize(
    ("driver", "output", "session"),
    (
        (
            ClaudeDriver(),
            json.dumps({"result": "said", "session_id": "abc-123"}),
            "abc-123",
        ),
        (CodexDriver(), CODEX_OUTPUT, "abc-123"),
    ),
    ids=("claude", "codex"),
)
def test_a_driver_reads_the_session_its_cli_reported(
    driver: ClaudeDriver | CodexDriver, output: str, session: str
) -> None:
    assert driver.parse(output).session == session


async def test_a_retry_carries_on_the_refused_attempt_and_sends_only_the_error() -> None:
    asked: list[tuple[str, str | None]] = []

    async def spawn(prompt: str, session: str | None) -> RunResult:
        asked.append((prompt, session))
        return RunResult('{"lines": []}' if session else "not json", "abc-123")

    _ = await ask("narrator", "THE WHOLE BRIEF", Narration, lambda _: None, spawn)

    assert asked[0] == ("THE WHOLE BRIEF", None)
    assert asked[1][1] == "abc-123"
    assert "THE WHOLE BRIEF" not in asked[1][0]


def test_the_child_environment_holds_nothing_but_the_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A_KEY_NO_ROLE_SHOULD_SEE", "secret")
    monkeypatch.setenv("PATH", "/bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    held = child_environment(ClaudeDriver().secrets)

    assert "A_KEY_NO_ROLE_SHOULD_SEE" not in held
    assert held["PATH"] == "/bin"
    assert held["ANTHROPIC_API_KEY"] == "k"
