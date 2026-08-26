from dataclasses import dataclass

from pydantic import JsonValue

from aidm.harness.driver import clip
from aidm.harness.exec import ExecDriver, described

# `codex exec` cancels every MCP call under its default `never` policy (openai/codex#24135);
# `--approve-for-me` reviews them instead, which the full bypass flag would do by dropping the
# sandbox as well.
_FLAGS = ["--json", "--skip-git-repo-check", "--approve-for-me"]


@dataclass
class CodexDriver(ExecDriver):
    def argv(self, text: str) -> list[str]:
        return ["codex", "exec", *_FLAGS, *self.chosen(), text]

    def line(self, event: dict[str, JsonValue]) -> str | None:
        match event:
            case {"type": "thread.started", "thread_id": str(thread)}:
                return f"thread {thread}"
            case {"type": "item.completed", "item": {"type": "mcp_tool_call", **call}}:
                return _tool_call(call)
            case {"type": "item.completed", "item": {**item}}:
                return f"{item.get('type')}: {described(item)}"
            case {"type": "turn.completed", "usage": {**usage}}:
                spent = f"{usage.get('input_tokens')} in, {usage.get('output_tokens')} out"
                return f"— turn ended · {spent}"
            case {"type": "turn.failed", **rest}:
                return f"failed: {described(rest)}"
            case _:
                return None


def _tool_call(call: dict[str, JsonValue]) -> str:
    """A refusal is the whole story of a failed turn, so it is never the part that gets clipped."""
    failed = call.get("error")
    if failed is not None:
        return f"{call.get('tool')} refused: {clip(str(failed))}"
    return f"{call.get('tool')}({clip(str(call.get('arguments')))})"
