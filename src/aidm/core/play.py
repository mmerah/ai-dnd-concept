from collections.abc import Sequence
from typing import Self

from pydantic import Field, JsonValue, model_validator

from aidm.core.entities import CheckedEntityId, Frozen, Slug, require_unique
from aidm.core.facts import Fact


class Line(Frozen):
    speaker_id: CheckedEntityId | None = Field(
        default=None,
        description="Exact speaker id for dialogue, or null for narration.",
    )
    text: str = Field(min_length=1, description="Dialogue only, or one passage of narration.")


class SpokenLine(Frozen):
    """A line as recorded: the speaker's id and name ride on it, so chat, journal and speech
    never resolve an id through state."""

    speaker_id: CheckedEntityId | None = None
    speaker: str = ""  # the name as it was when spoken; empty for narration
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _named_when_spoken(self) -> Self:
        if (self.speaker_id is None) != (not self.speaker):
            raise ValueError("a spoken line names its speaker; narration names nobody")
        return self


class Narration(Frozen):
    """The prose the player reads, split into narration and dialogue."""

    lines: tuple[Line, ...] = Field(
        description="All narration and dialogue in order; 2-4 sentences, or the length "
        "PLAYER ACTION asks for."
    )


class DecisionOption(Frozen):
    id: Slug
    label: str = Field(min_length=1)
    detail: str = ""


class PendingOption(DecisionOption):
    """The frozen tool call an engine plays this option by."""

    name: str = Field(min_length=1)
    args: dict[str, JsonValue] = Field(default_factory=dict)


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
    lines: tuple[SpokenLine, ...]
    # every fact, told or not; `cards` picks the player's
    facts: tuple[Fact, ...] = ()
    # The suspending decision's prompt: the pause has to survive after `Game.pending` clears.
    decision: str = ""

    @property
    def narration(self) -> str:
        return narration_text(self.lines)


class SceneRecord(Frozen):
    """One scene as every role reads it back; `recap` is empty while open or where none was
    written."""

    title: str
    focus: str
    recap: str = ""
    exchanges: tuple[Exchange, ...] = ()


class ChapterRecord(Frozen):
    """A closed stretch of scenes read back as one block: its summary, then its scenes' titles."""

    title: str
    verdict: str  # "done" or "left open", as the ledger says it
    summary: str
    scenes: tuple[str, ...]


class Commission(Frozen):
    """What the game master asked the worldsmith for; `later` files it for the next scene write."""

    kind: str
    brief: str
    later: bool = False


type HistoryRecord = SceneRecord | ChapterRecord


def narration_text(lines: Sequence[Line | SpokenLine]) -> str:
    return "\n".join(line.text for line in lines)
