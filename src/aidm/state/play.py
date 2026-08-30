from collections.abc import Sequence
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.entities import CheckedEntityId, Frozen, Slug, require_unique
from aidm.state.facts import Fact


class Line(Frozen):
    speaker_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact speaker id for dialogue, or null for narration.",
    )
    text: str = Field(min_length=1, description="Dialogue only, or one passage of narration.")


def narration_text(lines: Sequence[Line]) -> str:
    return "\n".join(line.text for line in lines)


class Narration(Frozen):
    """The prose the player reads, split into narration and dialogue."""

    lines: tuple[Line, ...] = Field(
        description="All narration and dialogue in order, 2-4 sentences total."
    )

    @property
    def text(self) -> str:
        return narration_text(self.lines)


class DecisionOption(Frozen):
    id: Slug
    label: str = Field(min_length=1)
    detail: str = ""


class PendingOption(DecisionOption):
    name: str
    args: dict[str, JsonValue]


class PendingDecision(Frozen):
    """One decision the game waits on; None at `Game.pending` means the composer is the only way."""

    kind: Slug
    # A prose-less segment replays into model history from this alone, so it can never be empty.
    prompt: str = Field(min_length=1)
    options: tuple[PendingOption, ...]
    # False where the SRD gives the player a pick and the options are that pick, whole.
    allows_text: bool

    @model_validator(mode="after")
    def _options_are_unambiguous(self) -> Self:
        require_unique("option ids", (option.id for option in self.options))
        return self


class Answer(Frozen):
    """What the player submits: a chosen option or written text, never both."""

    option_id: Slug | None = Field(
        default=None,
        description="Exact id of the listed option the player's words chose, when a decision is "
        "open; null otherwise.",
    )
    text: str = Field(
        default="", description="What the player did, in their words. Empty when option_id is set."
    )

    @model_validator(mode="after")
    def _answers_one_way(self) -> Self:
        if (self.option_id is None) == (not self.text):
            raise ValueError("an answer is either a chosen option or written text")
        return self


class Exchange(Frozen):
    prompt: str
    scene: str
    lines: tuple[Line, ...]
    facts: tuple[Fact, ...] = ()
    # The suspending decision's prompt: the pause has to survive after `Game.pending` clears.
    decision: str = ""

    @property
    def narration(self) -> str:
        return narration_text(self.lines)
