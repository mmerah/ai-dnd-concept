import json
from dataclasses import replace
from pathlib import Path

import pytest
from core_test_support import ScriptedSpawner, offline_settings, opened, played, updated

from aidm.app.sessions import Conversations, SessionFile, fingerprint
from aidm.app.spawn import ClaudeDriver, CodexDriver, RunResult, answered, child_environment
from aidm.config import RoleConfig
from aidm.core.io import FileStore
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
    # A resumed codex thread refuses every MCP call, so the master is never given one.
    assert "resume" not in CodexDriver().command("master", config, "abc-123", "")


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


def test_a_conversation_started_on_other_instructions_is_a_different_one() -> None:
    config = RoleConfig(model="opus")

    assert fingerprint(config, "the old rules") != fingerprint(config, "the new rules")


def test_a_claude_reply_that_is_not_json_is_a_broken_run() -> None:
    with pytest.raises(ValueError, match="no JSON result"):
        _ = ClaudeDriver().parse("I answered in prose.")


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

    async def ask(prompt: str, session: str | None) -> RunResult:
        asked.append((prompt, session))
        return RunResult('{"lines": []}' if session else "not json", "abc-123")

    _ = await answered("narrator", "THE WHOLE BRIEF", Narration, lambda _: None, ask)

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


async def test_a_second_turn_carries_on_and_a_changed_model_starts_cold(tmp_path: Path) -> None:
    table = opened(tmp_path)

    _ = await played(table, "I look.")
    _ = await played(table, "I look again.")
    resumed = [session for role, session in table.spawner.resumed if role == "master"]
    assert resumed == [None, "master-1"]

    table.service.sessions = replace(
        table.service.sessions,
        settings=updated(table.service.settings, roles={"master": {"model": "haiku"}}),
    )
    _ = await played(table, "I look once more.")
    assert [session for role, session in table.spawner.resumed if role == "master"][-1] is None


def test_a_session_file_that_does_not_validate_is_thrown_away(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    path = store.sessions_path("poc")
    path.parent.mkdir(parents=True)
    _ = path.write_text('{"roles": {"master": "not an entry"}}')
    conversations = Conversations(ScriptedSpawner(), store, offline_settings())

    assert conversations._read("poc") == SessionFile()  # pyright: ignore[reportPrivateUsage]
    assert not path.exists()


async def test_a_turn_thrown_away_takes_the_memory_of_it_with_it(tmp_path: Path) -> None:
    """A master that remembers applying what the game never received would resume on a lie."""
    table = opened(tmp_path)
    _ = await played(table, "I look.")
    sidecar = table.service.store.sessions_path(table.service.slug)
    assert sidecar.is_file()

    def crash() -> None:
        raise OSError("the game master never started")

    table.spawner.turns += [crash, crash]
    with pytest.raises(OSError):
        await table.service.play("I take the map.")

    assert not sidecar.exists()


async def test_a_restart_forgets_what_every_role_remembers(tmp_path: Path) -> None:
    table = opened(tmp_path)
    _ = await played(table, "I look.")
    sidecar = table.service.store.sessions_path(table.service.slug)

    table.service.restart()

    assert not sidecar.exists()
