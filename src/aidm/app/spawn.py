import json
import logging
from asyncio import subprocess, wait_for
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from os import environ, killpg
from signal import SIGKILL
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Protocol

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from aidm.config import CliProvider, Role, RoleConfig, Settings
from aidm.core.entities import Loose, Refusal

RETRIES = 1
# The child inherits nothing else: the shell that started the app may hold keys no role should see.
KEPT_ENV = ("PATH", "HOME", "LANG", "TERM")
# What `ask` asks of the value it parsed, beyond its own schema; the reason re-prompts.
type Check[T] = Callable[[T], str | None]

LOGGER = logging.getLogger(__name__)

_EVENT: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


@dataclass(frozen=True, slots=True)
class RunResult:
    text: str
    session: str | None


class Driver(Protocol):
    """Builds a command line and reads what it printed. A driver never starts a process."""

    @property
    def secrets(self) -> tuple[str, ...]:
        """Beyond `KEPT_ENV`: what this CLI needs to authenticate."""
        ...

    def command(
        self, role: Role, config: RoleConfig, session: str | None, url: str
    ) -> Sequence[str]: ...
    def parse(self, output: str) -> RunResult: ...


class _ClaudeResult(Loose):
    """What `--output-format json` prints."""

    result: str
    session_id: str
    # A failed run can still exit 0 and put its error where the answer goes.
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class ClaudeDriver:
    secrets: tuple[str, ...] = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")

    def command(
        self, role: Role, config: RoleConfig, session: str | None, url: str
    ) -> Sequence[str]:
        """The last flag takes no list, because the prompt follows it."""
        argv = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--model",
            config.model,
            "--effort",
            config.effort,
            *(() if session is None else ("--resume", session)),
            # Measured: `--tools ""` disables nothing, naming one tool does.
            "--restricted",
            "--tools",
            "Read",
        ]
        if role == "master":
            argv += ["--allowed-tools", "mcp__aidm", "--mcp-config", _claude_mcp(url)]
        return (*argv, "--strict-mcp-config")

    def parse(self, output: str) -> RunResult:
        try:
            said = _ClaudeResult.model_validate_json(output)
        except ValidationError as broken:
            raise Refusal(f"claude printed no JSON result: {output[-500:]}") from broken
        if said.is_error:
            raise Refusal(f"the run failed: {said.result[-500:]}")
        return RunResult(said.result, said.session_id)


@dataclass(frozen=True, slots=True)
class CodexDriver:
    secrets: tuple[str, ...] = ("OPENAI_API_KEY",)

    def command(
        self, role: Role, config: RoleConfig, session: str | None, url: str
    ) -> Sequence[str]:
        argv = ["codex", "exec", *(() if session is None else ("resume", session))]
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

    def parse(self, output: str) -> RunResult:
        events = [one for line in output.splitlines() if (one := _object(line)) is not None]
        return RunResult(final_message(output), _string(events, "thread_id"))


DRIVERS: Mapping[CliProvider, Driver] = {"claude": ClaudeDriver(), "codex": CodexDriver()}


class Spawner(Protocol):
    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult: ...


@dataclass(frozen=True, slots=True)
class CliSpawner:
    """The only thing in the codebase that starts a process."""

    settings: Settings

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        config = self.settings.roles.for_name(role)
        driver = DRIVERS[config.provider]
        url = f"http://localhost:{self.settings.server_port}/mcp/"
        argv = driver.command(role, config, session, url)
        started = monotonic()
        # An empty working directory, so a role cannot read this repository even if it tries.
        with TemporaryDirectory(prefix=f"aidm-{role}-") as empty:
            output = await _spawn(role, argv, prompt, config.timeout, driver.secrets, empty)
        result = driver.parse(output)
        LOGGER.info(
            "%s spawned: provider=%s model=%s effort=%s %s in %.1fs",
            role,
            config.provider,
            config.model,
            config.effort,
            "resumed" if "resume" in argv or "--resume" in argv else "cold",
            monotonic() - started,
        )
        return result


def final_message(output: str) -> str:
    """The agent's last message: its own event, else the last fence, else the trailing object."""
    if (said := _last_said(output)) is not None:
        return said
    fenced = output.rsplit("```", 2)
    if len(fenced) == 3:
        body = fenced[1]
        body = body.split("\n", 1)[1] if body.startswith("json") else body
        # A fence holding something else is prose about the answer, not the answer.
        if _decodes(body):
            return body
    tail = output.rstrip()
    decoder = json.JSONDecoder()
    # The first `{` that decodes all the way to the end is the outermost object, not a nested one.
    for start in range(len(tail)):
        if tail[start] != "{":
            continue
        try:
            _, end = decoder.raw_decode(tail, start)
        except ValueError:
            continue
        if end == len(tail):
            return tail[start:]
    return output


async def ask[T: BaseModel](
    role: Role,
    prompt: str,
    model: type[T],
    refusal: Check[T],
    spawn: Callable[[str, str | None], Awaitable[RunResult]],
) -> T:
    """The one retry, shared: a role that fails twice fails its step, loudly."""
    asked, refused, held = prompt, "", None
    for _ in range(RETRIES + 1):
        try:
            spoken = await spawn(asked, held)
            held = spoken.session
            answer = model.model_validate_json(final_message(spoken.text))
            if (refused := refusal(answer)) is None:
                return answer
        except ValidationError as invalid:
            refused = str(invalid)
        told = f"Your last answer was refused: {refused}\nAnswer again, fixed."
        # The retry carries on the refused attempt, which has read the prompt already.
        asked = told if held is not None else f"{prompt}\n\n{told}"
    raise Refusal(f"the {role} answered nothing usable: {refused}")


def child_environment(secrets: Sequence[str]) -> dict[str, str]:
    return {name: environ[name] for name in (*KEPT_ENV, *secrets) if name in environ}


async def _spawn(
    role: Role,
    argv: Sequence[str],
    prompt: str,
    timeout: float,
    secrets: Sequence[str],
    cwd: str,
) -> str:
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
    try:
        streamed = await wait_for(process.communicate(), timeout)
    finally:
        # A no-op once it exited; an abandoned or timed-out spawn dies with its children.
        _kill(process)
    output = streamed[0].decode(errors="replace")
    if process.returncode != 0:
        raise Refusal(f"the {role} exited {process.returncode}: {output[-500:]}")
    return output


def _claude_mcp(url: str) -> str:
    """A string, not a file: `--mcp-config` takes either, and a string needs no cleanup."""
    return json.dumps({"mcpServers": {"aidm": {"type": "http", "url": url}}})


def _last_said(output: str) -> str | None:
    """Two JSON objects on their own lines is an event stream; one is the answer itself."""
    events = [one for line in output.splitlines() if (one := _object(line)) is not None]
    if len(events) < 2:
        return None
    # Backwards, because the reasoning and the tool calls carry text of their own and come first.
    return next((said for one in reversed(events) if (said := _said(one)) is not None), None)


def _object(line: str) -> JsonValue | None:
    if not line.startswith("{"):
        return None
    try:
        return _EVENT.validate_json(line)
    except ValidationError:
        return None


def _said(node: JsonValue) -> str | None:
    """Every event stream we have seen names the message it carries `text`, at some depth."""
    found = _found(node, "text")
    return found if isinstance(found, str) else None


def _string(events: Sequence[JsonValue], name: str) -> str | None:
    """The first event that names it: a stream announces its thread before it says anything."""
    found = next((one for event in events if (one := _found(event, name)) is not None), None)
    return found if isinstance(found, str) else None


def _found(node: JsonValue, name: str) -> JsonValue | None:
    """An event nests its payload, so a name is searched for at any depth."""
    if isinstance(node, list):
        return next((one for item in node if (one := _found(item, name)) is not None), None)
    if not isinstance(node, dict):
        return None
    for key, value in node.items():
        if key == name:
            return value
        if (deeper := _found(value, name)) is not None:
            return deeper
    return None


def _decodes(body: str) -> bool:
    try:
        json.loads(body)
    except ValueError:
        return False
    return True


def _kill(process: subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        killpg(process.pid, SIGKILL)
    except ProcessLookupError:
        pass
