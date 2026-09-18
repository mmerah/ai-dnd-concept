import json
from dataclasses import dataclass

import pytest

import aidm.app.spawn as spawn
from aidm.app.spawn import (
    PROMPT_MAX_BYTES,
    ClaudeDriver,
    CodexDriver,
    RunResult,
    child_environment,
    final_message,
    run_cli,
)
from aidm.config import Role, RoleConfig
from aidm.core.entities import Refusal
from aidm.core.io import decode


@dataclass(frozen=True, slots=True)
class _StubDriver:
    argv: tuple[str, ...]
    secrets: tuple[str, ...] = ()

    def command(
        self, role: Role, config: RoleConfig, conversation: str | None, url: str
    ) -> tuple[str, ...]:
        del role, config, conversation, url
        return self.argv

    def read_result(self, output: str) -> RunResult:
        del output
        raise AssertionError("the run fails before there is a result to read")


CODEX_OUTPUT = "\n".join(
    (
        '{"type":"thread.started","thread_id":"abc-123"}',
        '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"lines\\": []}"}}',
        '{"type":"turn.completed","usage":{"input_tokens":900,"cached_input_tokens":700}}',
    )
)


def test_only_the_master_is_let_out_of_the_sandbox_and_no_role_sees_the_account() -> None:
    config = RoleConfig(provider="codex", model="gpt-5", effort="low")
    master = CodexDriver().command("master", config, None, "http://localhost:1/mcp/")
    narrator = CodexDriver().command("narrator", config, None, "")

    # `resume` accepts no sandbox flag, so a writer's box rides `-c`, which both forms accept.
    assert "--sandbox" not in master and "--sandbox" not in narrator
    assert "--approve-for-me" in master and "--approve-for-me" not in narrator
    assert "sandbox_mode=read-only" in narrator and "approval_policy=never" in narrator
    assert "mcp_servers.aidm.url=http://localhost:1/mcp/" in master
    assert not any(line.startswith("mcp_servers") for line in narrator)
    for argv in (master, narrator):
        # `--ignore-user-config` leaves the account's own MCP servers standing; this removes them.
        disabled = argv.index("--disable")
        assert list(argv[disabled : disabled + 2]) == ["--disable", "apps"]
        assert "--ignore-user-config" in argv
        assert "web_search=disabled" in argv


def test_a_failed_claude_run_does_not_quote_its_raw_result() -> None:
    output = json.dumps(
        {"result": "HIDDEN HERE the arc", "session_id": "abc-123", "is_error": True}
    )

    with pytest.raises(Refusal, match="the run failed") as failed:
        _ = ClaudeDriver().read_result(output)

    assert "HIDDEN HERE" not in str(failed.value)


async def test_a_missing_cli_binary_is_a_refusal_not_a_crash() -> None:
    config = RoleConfig(model="opus", effort="high")

    with pytest.raises(Refusal, match="could not be started"):
        _ = await run_cli("master", config, _StubDriver(("aidm-no-such-binary",)), 1, "PLAY", None)


async def test_a_prompt_over_the_cap_is_refused_before_any_command_is_built() -> None:
    config = RoleConfig(model="opus", effort="high")

    with pytest.raises(Refusal, match="takes fewer than 131072"):
        _ = await run_cli(
            "worldsmith",
            config,
            _StubDriver(("aidm-never-run",)),
            1,
            "x" * PROMPT_MAX_BYTES,
            None,
        )


async def test_a_crashed_roles_raw_output_never_reaches_the_player(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        returncode = 3

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"HIDDEN HERE the arc", b""

    async def fake_create(*_argv: str, **_kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(spawn.subprocess, "create_subprocess_exec", fake_create)
    config = RoleConfig(model="opus", effort="high")

    with pytest.raises(Refusal, match="master exited 3") as failed:
        _ = await run_cli("master", config, _StubDriver(("aidm-crashing",)), 1, "PLAY", None)

    assert "HIDDEN HERE" not in str(failed.value)


@pytest.mark.parametrize(
    ("driver", "output", "conversation"),
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
def test_a_driver_reads_the_conversation_its_cli_reported(
    driver: ClaudeDriver | CodexDriver, output: str, conversation: str
) -> None:
    assert driver.read_result(output).conversation == conversation


def test_a_deeply_nested_answer_is_refused_not_a_bare_recursion_error() -> None:
    depth = 12000
    nested = '{"lines": ' + "[" * depth + "]" * depth + "}"

    assert final_message(nested) == nested
    assert final_message(f"```json\n{nested}\n```") is not None
    with pytest.raises(Refusal, match="not JSON"):
        _ = decode(nested)


def test_the_child_environment_holds_nothing_but_the_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A_KEY_NO_ROLE_SHOULD_SEE", "secret")
    monkeypatch.setenv("PATH", "/bin")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    env = child_environment(ClaudeDriver().secrets)

    assert "A_KEY_NO_ROLE_SHOULD_SEE" not in env
    assert env["PATH"] == "/bin"
    assert env["ANTHROPIC_API_KEY"] == "k"
