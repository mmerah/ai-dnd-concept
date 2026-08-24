from collections.abc import Sequence
from typing import Annotated, Self

from pydantic import Field, JsonValue, model_validator

from aidm.state.entities import EntityId, Frozen, Slug, require_unique
from aidm.state.facts import Fact


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


class EventBadge(Frozen):
    label: str
    value: str


class DiceEvent(Frozen):
    label: str
    faces: tuple[int, ...]
    rolled: tuple[int, ...]
    kept: int

    @model_validator(mode="after")
    def _rolled_matches_faces(self) -> Self:
        if len(self.rolled) != len(self.faces):
            raise ValueError("one rolled value per face")
        for die, face in zip(self.rolled, self.faces, strict=True):
            if not 1 <= die <= face:
                raise ValueError(f"a d{face} cannot show {die}")
        if self.kept not in self.rolled:
            raise ValueError("the kept die must be among those rolled")
        return self


class MechanicEvent(Frozen):
    """Player-facing: no field for model-authored free text, so a canon leak has no channel."""

    source: str
    title: str
    badges: tuple[EventBadge, ...] = ()
    dice: tuple[DiceEvent, ...] = ()
    outcome: str = ""
    effects: tuple[str, ...] = ()
    icon: str = "casino"


# Laxer than `Slug`: 24XX's defence options are carried-item entity ids, which allow underscores.
OptionId = Annotated[str, Field(pattern=r"^[a-z0-9_-]+$", max_length=64)]


class DecisionOption(Frozen):
    id: OptionId
    label: str = Field(min_length=1)
    detail: str = ""


class PendingDecision(Frozen):
    """One decision the game waits on; None at `Game.pending` means the composer is the only way."""

    kind: Slug
    # A prose-less segment replays into model history from this alone, so it can never be empty.
    prompt: str = Field(min_length=1)
    options: tuple[DecisionOption, ...]
    free_text: bool = True
    payload: dict[str, JsonValue]

    @model_validator(mode="after")
    def _is_answerable(self) -> Self:
        require_unique("option ids", (option.id for option in self.options))
        if not self.options and not self.free_text:
            raise ValueError(f"the {self.kind!r} decision offers no way to answer it")
        return self


class Answer(Frozen):
    """What the player submits: a chosen option or written text, never both."""

    option_id: OptionId | None = None
    text: str = ""

    @model_validator(mode="after")
    def _answers_one_way(self) -> Self:
        if (self.option_id is None) == (not self.text):
            raise ValueError("an answer is either a chosen option or written text")
        return self


class Exchange(Frozen):
    prompt: str
    place: str
    lines: tuple[Line, ...]
    events: tuple[MechanicEvent, ...] = ()
    # The suspending decision's prompt: the pause has to survive after `Game.pending` clears.
    decision: str = ""

    @property
    def narration(self) -> str:
        return narration_text(self.lines)


class StepTrace(Frozen):
    name: str
    prompt: str
    output: dict[str, JsonValue] | str


class TraceEntryBase(Frozen):
    """A trace entry records what occurred, never the resulting state."""

    facts: tuple[Fact, ...] = ()


class TurnTrace(TraceEntryBase):
    prompt: str
    narration: str
    steps: tuple[StepTrace, ...] = ()


class AdvanceApplied(TraceEntryBase):
    """One advancement change: the same transaction as a turn, without a prompt or a narration."""

    subject_id: EntityId


class WorldExtended(TraceEntryBase):
    """Canon a background authoring run appended."""


type TraceEntry = TurnTrace | AdvanceApplied | WorldExtended
