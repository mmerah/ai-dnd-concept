from collections.abc import Sequence

from pydantic import Field, JsonValue

from .base import Frozen

CORE = "core"
NOTHING_MECHANICAL = "- (nothing mechanical happened)"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    source: str
    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)


def narrator_evidence(facts: Sequence[Fact]) -> str:
    lines = [f"- {rendered}" for fact in facts if (rendered := fact.narrator) is not None]
    return "\n".join(lines) or NOTHING_MECHANICAL
