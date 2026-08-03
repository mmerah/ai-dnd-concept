from pydantic import Field, JsonValue

from .base import Frozen

CORE = "core"


class Fact(Frozen):
    """One thing that occurred, rendered where its values were in scope."""

    source: str
    kind: str
    trace: str
    narrator: str | None = None
    # The structured values behind the prose, so a test or a richer trace reads them untyped.
    data: dict[str, JsonValue] = Field(default_factory=dict)
