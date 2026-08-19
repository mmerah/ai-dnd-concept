from collections.abc import Sequence

from pydantic import Field

from .base import EntityId, Frozen


class Line(Frozen):
    speaker_id: EntityId | None = Field(
        default=None,
        description="Exact id of who speaks this line, or null when it is narration, not speech.",
    )
    text: str = Field(min_length=1, description="One spoken line, or a passage of narration.")


def narration_text(lines: Sequence[Line]) -> str:
    return "\n".join(line.text for line in lines)


class Narration(Frozen):
    """The Narrator's answer: the one role that writes prose now says who speaks each line."""

    lines: tuple[Line, ...] = Field(
        description="The narration in order: 2-4 sentences in all, split by who says them."
    )

    @property
    def text(self) -> str:
        return narration_text(self.lines)


class Exchange(Frozen):
    prompt: str
    lines: tuple[Line, ...]

    @property
    def narration(self) -> str:
        return narration_text(self.lines)
