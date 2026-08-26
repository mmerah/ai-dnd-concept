from abc import ABC, abstractmethod
from asyncio import subprocess
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from os import killpg
from signal import SIGTERM

from pydantic import JsonValue, TypeAdapter, ValidationError

from aidm.app.runtime import Runtime
from aidm.harness.driver import clip, opening

_EVENT = TypeAdapter(dict[str, JsonValue])


@dataclass
class ExecDriver(ABC):
    """A coding CLI the app spawns per turn. Its MCP server is a second process, so the page reads
    the turn back off the save rather than out of the agent."""

    runtime: Runtime
    slug: str | None = None
    process: subprocess.Process | None = None
    noise: deque[str] = field(default_factory=lambda: deque[str](maxlen=5))

    def chosen(self, flag: str = "-m") -> list[str]:
        model = self.runtime.settings.turn.harness_model
        return [flag, model] if model else []

    @abstractmethod
    def argv(self, text: str) -> list[str]:
        """The command for one turn."""

    @abstractmethod
    def line(self, event: dict[str, JsonValue]) -> str | None:
        """One log line, or None for an event the player gains nothing from."""

    async def play(self, text: str) -> AsyncGenerator[str]:
        argv = self.argv(opening(self.slug, text))
        process = await subprocess.create_subprocess_exec(
            *argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # pi's closing event carries the whole message history on one line, past the 64 KiB
            # default.
            limit=2**20,
            # Its own group, so `interrupt` reaches the MCP server the CLI spawns under itself.
            start_new_session=True,
        )
        self.process = process
        assert process.stdout is not None
        try:
            async for raw in process.stdout:
                event = self._event(raw)
                line = None if event is None else self.line(event)
                if line is not None:
                    yield line
            code = await process.wait()
        finally:
            # An abandoned generator would otherwise leave the CLI playing on into the next turn.
            await self.interrupt()
            self.process = None
        if code != 0:
            yield f"{argv[0]} exited {code}: {clip(' '.join(self.noise))}"

    def _event(self, raw: bytes) -> dict[str, JsonValue] | None:
        try:
            return _EVENT.validate_json(raw)
        except ValidationError:
            # Log lines and banners share stdout with the stream; keep the last few to explain a
            # non-zero exit.
            self.noise.append(raw.decode(errors="replace").strip())
            return None

    async def interrupt(self) -> None:
        process = self.process
        if process is None or process.returncode is not None:
            return
        try:
            killpg(process.pid, SIGTERM)
        except ProcessLookupError:
            pass

    async def close(self) -> None:
        await self.interrupt()


def described(item: dict[str, JsonValue]) -> str:
    return clip(
        " ".join(f"{key}={value}" for key, value in item.items() if key not in ("id", "type"))
    )
