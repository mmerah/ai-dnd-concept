import json
import logging
from asyncio import shield, subprocess, timeout
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from os import environ, killpg
from signal import SIGKILL
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Annotated, Protocol

from pydantic import Field, ValidationError

from aidm.app.builtin import run_builtin
from aidm.config import CliProvider, Role, RoleConfig, Settings
from aidm.core.entities import Loose, Refusal, parse_json
from aidm.core.tools import Tools

LOGGER = logging.getLogger(__name__)

# The child inherits nothing else: the shell that started the app may hold keys no role should see.
KEPT_ENV = ("PATH", "HOME", "LANG", "TERM")
PROMPT_MAX_BYTES = 131_072  # Linux MAX_ARG_STRLEN: the prompt is one argv element
# A resumed conversation id is fed back as an argv element; a leading `-` must not parse as a flag.
ConversationId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]


@dataclass(frozen=True, slots=True)
class RunResult:
    text: str
    conversation: str | None


class Driver(Protocol):
    """A driver never starts a process."""

    @property
    def secrets(self) -> tuple[str, ...]: ...

    def command(
        self, role: Role, config: RoleConfig, conversation: str | None, url: str
    ) -> Sequence[str]: ...
    def read_result(self, output: str) -> RunResult: ...


class Spawner(Protocol):
    async def run(
        self, role: Role, prompt: str, conversation: str | None, tools: Tools | None = None
    ) -> RunResult: ...


class _ClaudeResult(Loose):
    """What `--output-format json` prints."""

    result: str
    session_id: ConversationId
    # A failed run can still exit 0 and put its error where the answer goes.
    is_error: bool = False


class _CodexItem(Loose):
    type: str
    text: str = ""


class _CodexEvent(Loose):
    """`type` is required: a bare answer object must not parse as an event."""

    type: str
    thread_id: ConversationId | None = None
    item: _CodexItem | None = None


@dataclass(frozen=True, slots=True)
class ClaudeDriver:
    secrets: tuple[str, ...] = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")

    def command(
        self, role: Role, config: RoleConfig, conversation: str | None, url: str
    ) -> Sequence[str]:
        """The prompt follows the last flag, so that flag takes no list."""
        argv = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--model",
            config.model,
            "--effort",
            config.effort,
            *(() if conversation is None else ("--resume", conversation)),
            # Measured: `--tools ""` disables nothing, naming one tool does.
            "--restricted",
            "--tools",
            "Read",
        ]
        if role == "master":
            argv += ["--allowed-tools", "mcp__aidm", "--mcp-config", _claude_mcp(url)]
        return (*argv, "--strict-mcp-config")

    def read_result(self, output: str) -> RunResult:
        try:
            result = parse_json(_ClaudeResult, output)
        except Refusal:
            try:
                result = parse_json(_ClaudeResult, final_message(output))
            except Refusal as broken:
                LOGGER.warning("claude printed no JSON result: %s", output[-500:])
                raise Refusal("claude printed no JSON result") from broken
        if result.is_error:
            LOGGER.warning("the run failed: %s", result.result[-500:])
            raise Refusal("the run failed")
        return RunResult(final_message(result.result), result.session_id)


@dataclass(frozen=True, slots=True)
class CodexDriver:
    secrets: tuple[str, ...] = ("OPENAI_API_KEY",)

    def command(
        self, role: Role, config: RoleConfig, conversation: str | None, url: str
    ) -> Sequence[str]:
        argv = ["codex", "exec", *(() if conversation is None else ("resume", conversation))]
        argv += [
            "--json",
            "--model",
            config.model,
            "-c",
            f"model_reasoning_effort={config.effort}",
            "-c",
            "web_search=disabled",
            # The account's own MCP servers, which `--ignore-user-config` leaves standing.
            "--disable",
            "apps",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
        ]
        if role == "master":
            # Only `--approve-for-me` lets an MCP call through, and it refuses `--sandbox`.
            return (*argv, "--approve-for-me", "-c", f"mcp_servers.aidm.url={url}")
        # `resume` takes no `--sandbox`, so a writer's box rides `-c`, which both forms accept.
        return (*argv, "-c", "sandbox_mode=read-only", "-c", "approval_policy=never")

    def read_result(self, output: str) -> RunResult:
        events = _codex_events(output)
        thread = next((event.thread_id for event in events if event.thread_id is not None), None)
        return RunResult(_said(events) or final_message(output), thread)


DRIVERS: Mapping[CliProvider, Driver] = {"claude": ClaudeDriver(), "codex": CodexDriver()}


@dataclass(frozen=True, slots=True)
class RoleRunner:
    settings: Settings

    async def run(
        self, role: Role, prompt: str, conversation: str | None, tools: Tools | None = None
    ) -> RunResult:
        config = self.settings.roles.for_name(role)
        started = monotonic()
        try:
            async with timeout(config.timeout):
                match config.provider:
                    case "claude" | "codex":
                        driver = DRIVERS[config.provider]
                        port = self.settings.server_port
                        result = await run_cli(role, config, driver, port, prompt, conversation)
                        detail = "resumed" if conversation is not None else "cold"
                    case "openrouter" | "local":
                        provider = self.settings.providers.for_name(config.provider)
                        text, rounds = await run_builtin(role, config, provider, prompt, tools)
                        result = RunResult(final_message(text), None)
                        detail = f"over {rounds} rounds"
        except TimeoutError:
            raise Refusal(f"the {role} answered nothing in {config.timeout:.0f}s") from None
        LOGGER.info(
            "%s answered: provider=%s model=%s effort=%s %s in %.1fs",
            role,
            config.provider,
            config.model,
            config.effort,
            detail,
            monotonic() - started,
        )
        return result


async def run_cli(
    role: Role, config: RoleConfig, driver: Driver, port: int, prompt: str, conversation: str | None
) -> RunResult:
    """The only thing in the codebase that starts a process."""
    if (size := len(prompt.encode())) >= PROMPT_MAX_BYTES:
        raise Refusal(
            f"the {role} prompt is {size} bytes; "
            f"the command line takes fewer than {PROMPT_MAX_BYTES}"
        )
    url = f"http://localhost:{port}/mcp/"
    argv = driver.command(role, config, conversation, url)
    # An empty working directory, so a role cannot read this repository even if it tries.
    with TemporaryDirectory(prefix=f"aidm-{role}-") as empty:
        output = await _spawn(role, argv, prompt, driver.secrets, empty)
    return driver.read_result(output)


def final_message(output: str) -> str:
    fenced = output.rsplit("```", 2)
    if len(fenced) == 3:
        body = fenced[1]
        if body.startswith("json") and "\n" in body:
            body = body.split("\n", 1)[1]
        else:
            body = body.removeprefix("json")
        # A fence holding something else is prose about the answer, not the answer.
        with suppress(json.JSONDecodeError, RecursionError):
            json.loads(body)
            return body
    tail = output.rstrip()
    # Only the first `{`: digging past a broken one costs a whole re-prompt on a chatty answer.
    start = tail.find("{")
    if start != -1:
        try:
            _, end = json.JSONDecoder().raw_decode(tail, start)
        except (json.JSONDecodeError, RecursionError):
            pass
        else:
            if end == len(tail):
                return tail[start:]
    return output


def child_environment(secrets: Sequence[str]) -> dict[str, str]:
    return {name: environ[name] for name in (*KEPT_ENV, *secrets) if name in environ}


async def _spawn(
    role: Role, argv: Sequence[str], prompt: str, secrets: Sequence[str], cwd: str
) -> str:
    try:
        process = await subprocess.create_subprocess_exec(
            *argv,
            prompt,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=child_environment(secrets),
            # Its own group, so an abandoned spawn cannot leave children playing on.
            start_new_session=True,
        )
    except OSError as failed:
        raise Refusal(f"the {role} could not be started: {failed}") from failed
    try:
        streamed = await process.communicate()
    finally:
        # A no-op once it exited; an abandoned or timed-out spawn dies with its children.
        await _kill(process)
    output = streamed[0].decode(errors="replace")
    if process.returncode != 0:
        LOGGER.warning("the %s exited %s: %s", role, process.returncode, output[-500:])
        raise Refusal(f"the {role} exited {process.returncode}")
    return output


def _claude_mcp(url: str) -> str:
    """A string, not a file: `--mcp-config` takes either, and a string needs no cleanup."""
    return json.dumps({"mcpServers": {"aidm": {"type": "http", "url": url}}})


def _codex_events(output: str) -> list[_CodexEvent]:
    events: list[_CodexEvent] = []
    for line in output.splitlines():
        with suppress(ValidationError):
            events.append(_CodexEvent.model_validate_json(line))
    return events


def _said(events: Sequence[_CodexEvent]) -> str | None:
    """The last agent message is the answer; a resumed thread carries earlier ones."""
    spoken = (
        event.item.text
        for event in reversed(events)
        if event.item is not None and event.item.type == "agent_message" and event.item.text
    )
    return next(spoken, None)


async def _kill(process: subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        killpg(process.pid, SIGKILL)
    # Shielded: a second cancel (`Tasks.close` after `hush`) would abandon a bare await mid-reap.
    await shield(process.wait())
