import json
import shlex
from asyncio import subprocess, wait_for
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import partial
from os import killpg
from signal import SIGKILL
from typing import Protocol

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from aidm.config import Role, Settings

RETRIES = 1
# What `write` asks of the value it parsed, beyond its own schema; the reason re-prompts.
type Check[T] = Callable[[T], str | None]


class Spawner(Protocol):
    """The game master works through tools and answers nothing; the other two return a value."""

    async def act(self, prompt: str) -> str: ...

    async def write[T: BaseModel](
        self, role: Role, prompt: str, expect: type[T], check: Check[T] | None = None
    ) -> T: ...


def final_message(output: str) -> str:
    """The agent's last message: its own event for a CLI that streams JSON lines, else the last
    fenced block, else the object the answer ends on."""
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


def _last_said(output: str) -> str | None:
    """Two JSON objects on their own lines is an event stream; one is the answer itself."""
    events = [one for line in output.splitlines() if (one := _object(line)) is not None]
    if len(events) < 2:
        return None
    # Backwards, because the reasoning and the tool calls carry text of their own and come first.
    return next((said for one in reversed(events) if (said := _said(one)) is not None), None)


_EVENT: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)


def _object(line: str) -> JsonValue | None:
    if not line.startswith("{"):
        return None
    try:
        return _EVENT.validate_json(line)
    except ValidationError:
        return None


def _said(node: JsonValue) -> str | None:
    """Every event stream we have seen names the message it carries `text`, at some depth."""
    if not isinstance(node, dict):
        return None
    for name, value in node.items():
        if name == "text" and isinstance(value, str):
            return value
        if (found := _said(value)) is not None:
            return found
    return None


def _decodes(body: str) -> bool:
    try:
        _ = json.loads(body)
    except ValueError:
        return False
    return True


async def written[T: BaseModel](
    role: Role,
    prompt: str,
    expect: type[T],
    check: Check[T] | None,
    ask: Callable[[str], Awaitable[str]],
) -> T:
    """The one retry, shared: a role that fails twice fails its step, loudly."""
    asked, refused = prompt, ""
    for _ in range(RETRIES + 1):
        try:
            answer = expect.model_validate_json(final_message(await ask(asked)))
            if (refused := check(answer) if check else None) is None:
                return answer
        except ValidationError as invalid:
            refused = str(invalid)
        asked = f"{prompt}\n\nYour last answer was refused: {refused}\nAnswer again, fixed."
    raise ValueError(f"the {role} answered nothing usable: {refused}")


@dataclass(frozen=True, slots=True)
class CliSpawner:
    """The only thing in the codebase that starts a process."""

    settings: Settings

    async def act(self, prompt: str) -> str:
        return await self._run("master", prompt)

    async def write[T: BaseModel](
        self, role: Role, prompt: str, expect: type[T], check: Check[T] | None = None
    ) -> T:
        return await written(role, prompt, expect, check, partial(self._run, role))

    async def _run(self, role: Role, prompt: str) -> str:
        config = self.settings.roles.for_name(role)
        if not config.command:
            raise ValueError(f"role {role!r} has no command; set ROLES__{role.upper()}__COMMAND")
        process = await subprocess.create_subprocess_exec(
            *shlex.split(config.command),
            prompt,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # Its own group, so an abandoned spawn cannot leave children playing on.
            start_new_session=True,
        )
        try:
            streamed = await wait_for(process.communicate(), config.timeout)
        finally:
            # A no-op once it exited; an abandoned or timed-out spawn dies with its children.
            _kill(process)
        output = streamed[0].decode(errors="replace")
        if process.returncode != 0:
            raise ValueError(f"the {role} exited {process.returncode}: {output[-500:]}")
        return output


def _kill(process: subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        killpg(process.pid, SIGKILL)
    except ProcessLookupError:
        pass


@dataclass(slots=True)
class ScriptedSpawner:
    """Answers from a per-role list and records every prompt it was given. Tests use this."""

    turns: list[Callable[[], None]] = field(default_factory=list)
    answers: dict[Role, list[str]] = field(default_factory=dict)
    prompts: list[tuple[Role, str]] = field(default_factory=list)

    async def act(self, prompt: str) -> str:
        self.prompts.append(("master", prompt))
        if self.turns:
            self.turns.pop(0)()
        return prompt

    async def write[T: BaseModel](
        self, role: Role, prompt: str, expect: type[T], check: Check[T] | None = None
    ) -> T:
        async def queued(asked: str) -> str:
            self.prompts.append((role, asked))
            answers = self.answers.get(role)
            if not answers:
                raise ValueError(f"the scripted {role} has no answer left")
            return answers.pop(0)

        return await written(role, prompt, expect, check, queued)

    def prompt(self, role: Role) -> str:
        """The first prompt the role was given; the golden prompts come from here."""
        return next(text for name, text in self.prompts if name == role)
