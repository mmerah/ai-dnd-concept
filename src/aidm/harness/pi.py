from dataclasses import dataclass

from pydantic import JsonValue

from aidm.harness.driver import clip
from aidm.harness.exec import ExecDriver, described

# AGENTS.md and CLAUDE.md are this repository's rules for changing it, which a turn of play is
# not; `--` keeps a player's action from being read as flags or as `@file` attachments.
_FLAGS = ["-p", "--mode", "json", "--no-context-files"]


@dataclass
class PiDriver(ExecDriver):
    """Its MCP servers arrive through the user's `pi-mcp-adapter` extension: pi ships none."""

    spent: float = 0.0

    def argv(self, text: str) -> list[str]:
        return ["pi", *_FLAGS, *self.chosen("--model"), "--", text]

    def line(self, event: dict[str, JsonValue]) -> str | None:
        match event:
            case {"type": "session", "id": str(session)}:
                self.spent = 0.0
                return f"session {session}"
            case {"type": "tool_execution_start", "toolName": str(tool), "args": {**args}}:
                return f"{tool}({described(args)})"
            case {
                "type": "message_end",
                "message": {"usage": {"cost": {"total": int() | float() as cost}}},
            }:
                self.spent += cost
                return None
            case {"assistantMessageEvent": {"type": "text_end", "content": str(text)}}:
                return clip(text) or None
            case {"type": "agent_end"}:
                return f"— turn ended · ${self.spent:.4f}"
            case _:
                return None
