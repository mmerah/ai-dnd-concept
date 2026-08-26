import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    Message,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from pydantic import JsonValue

from aidm.app.runtime import Runtime
from aidm.harness.codemode import Harness
from aidm.harness.driver import clip, opening
from aidm.harness.mcp import SERVER_NAME, build_server

LOGGER = logging.getLogger(__name__)


@dataclass
class ClaudeDriver:
    """Runs on the app's own `Runtime`: the agent and the page share one writer, so no polling.

    Worth its dependency only while the SDK stays out-of-band of billing; the day it bills like the
    API, `claude -p --output-format stream-json` is an `ExecDriver` subclass the size of `codex.py`.
    """

    runtime: Runtime
    slug: str | None = None
    harness: Harness = field(init=False)
    client: ClaudeSDKClient | None = None

    def __post_init__(self) -> None:
        self.harness = Harness(settings=self.runtime.settings, runtime=self.runtime)

    def opened(self) -> Harness:
        """The SDK bridge drops `tools/list_changed`, so the engine's commands must be published
        before the agent's first listing rather than after its `open_game`."""
        if self.slug is not None:
            self.harness.open_game(self.slug)
        return self.harness

    async def play(self, text: str) -> AsyncIterator[str]:
        # One conversation per turn: `start_turn` already hands back the play so far, so a kept
        # session would only be that history a second time.
        self.opened()
        client = ClaudeSDKClient(options=self.options())
        await client.connect()
        self.client = client
        LOGGER.info("driver query: slug=%s", self.slug)
        try:
            await client.query(opening(self.slug, text))
            async for message in client.receive_response():
                line = _line(message)
                if line is not None:
                    yield line
        finally:
            self.client = None
            await client.disconnect()

    def options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.runtime.settings.turn.harness_model or None,
            system_prompt={"type": "preset", "preset": "claude_code"},
            # Playing needs the server, a skill and a subagent to grow the world — nothing else.
            tools=["Skill", "Task"],
            mcp_servers={
                SERVER_NAME: {
                    "type": "sdk",
                    "name": SERVER_NAME,
                    "instance": build_server(self.harness),
                }
            },
            # Without this `.mcp.json` starts the stdio server too: a second writer on this save.
            strict_mcp_config=True,
            allowed_tools=[f"mcp__{SERVER_NAME}__*"],
            permission_mode="bypassPermissions",
            setting_sources=["project"],
            skills=["playing-aidm", "growing-aidm", "authoring-aidm"],
        )

    async def interrupt(self) -> None:
        if self.client is not None:
            await self.client.interrupt()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.disconnect()
            self.client = None


def _line(message: Message) -> str | None:
    match message:
        case AssistantMessage():
            return "\n".join(filter(None, (_block(block) for block in message.content))) or None
        case ResultMessage():
            cost = "" if message.total_cost_usd is None else f" · ${message.total_cost_usd:.4f}"
            return f"— turn ended in {message.duration_ms / 1000:.1f}s{cost}"
        case _:
            return None


def _block(block: object) -> str | None:
    match block:
        case TextBlock():
            return clip(block.text.strip()) or None
        case ToolUseBlock():
            return f"{block.name}({clip(_args(block.input))})"
        case _:
            return None


def _args(params: dict[str, JsonValue]) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in params.items())
