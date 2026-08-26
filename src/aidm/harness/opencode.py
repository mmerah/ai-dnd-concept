from dataclasses import dataclass

from pydantic import JsonValue

from aidm.harness.driver import clip
from aidm.harness.exec import ExecDriver, described

# A process spawned with no terminal can answer no approval prompt; `--auto` takes that path out.
_FLAGS = ["run", "--format", "json", "--auto"]


@dataclass
class OpencodeDriver(ExecDriver):
    def argv(self, text: str) -> list[str]:
        return ["opencode", *_FLAGS, *self.chosen(), text]

    def line(self, event: dict[str, JsonValue]) -> str | None:
        match event:
            case {"part": {**part}}:
                return _part(part)
            case _:
                return None


def _part(part: dict[str, JsonValue]) -> str | None:
    # A step is one model call and a turn of play is many, so the totals arrive per step.
    match part:
        case {"type": "text", "text": str(text)}:
            return clip(text) or None
        case {"type": "tool", "tool": str(tool), "state": {"status": "completed", **done}}:
            return f"{tool}: {described(done)}"
        case {"type": "step-finish", "tokens": {"input": int(read), "output": int(written)}}:
            return f"— step · {read} in, {written} out"
        case _:
            return None
