from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Refusal, Slug
from aidm.core.play import (
    DecisionOption,
    Interjection,
    Line,
    Narration,
    PendingDecision,
    SpokenLine,
)

type Pairs = tuple[tuple[str, str], ...]


# Three row shapes, in order: entity (`icon_id`), labelled value (`detail`), or bare label.
class PanelRow(Frozen):
    label: str
    detail: str
    icon_id: Slug | None = None


class Subject(Frozen):
    id: Slug
    label: str
    detail: str

    @property
    def tag(self) -> str:
        return f"{self.label}[{self.id}]"

    @property
    def headline(self) -> str:
        return self.tag + (f" — {self.detail}" if self.detail else "")

    def row(self) -> PanelRow:
        return PanelRow(label=self.label, detail=self.detail, icon_id=self.id)


class Panel(Frozen):
    title: str
    rows: tuple[PanelRow, ...]


class DiceLook(Frozen):
    """An engine's dice on the table: the body, the ink of the numbers, the glow of a kept die."""

    body: str
    ink: str
    glow: str


type Palette = Mapping[str, str]


class NarratorView(Frozen):
    """The Narrator's input type: it has no field that can hold hidden canon."""

    # The place, as the art cache names it: two scenes in one place share one picture.
    place: str
    title: str
    focus: str
    situation: str
    subjects: tuple[Subject, ...]
    speakers: tuple[Slug, ...]
    # The player first, then who travels with them.
    party: tuple[Slug, ...] = Field(min_length=1)
    # The player's own sheet: theirs to know, so the narrator may show it through detail.
    sheet: Pairs

    @model_validator(mode="after")
    def _everyone_is_a_subject(self) -> Self:
        here = {subject.id for subject in self.subjects}
        if strangers := sorted(set(self.speakers) - here):
            raise ValueError(f"speakers who are not subjects: {strangers}")
        if party_strangers := sorted(set(self.party) - here):
            raise ValueError(f"party members who are not subjects: {party_strangers}")
        if len(set(self.party)) != len(self.party):
            raise ValueError("the party repeats an id")
        return self

    def others(self) -> tuple[Subject, ...]:
        return tuple(subject for subject in self.subjects if subject.id not in self.party)

    def spoken(self, lines: Sequence[Line]) -> tuple[SpokenLine, ...]:
        here = {subject.id: subject for subject in self.subjects if subject.id in self.speakers}

        def spoken_line(line: Line) -> SpokenLine:
            if line.speaker_id is None:
                return SpokenLine(text=line.text)
            who = here.get(line.speaker_id)
            if who is None:
                raise Refusal(f"nobody here has id {line.speaker_id!r}")
            return SpokenLine(speaker_id=who.id, speaker=who.label, text=line.text)

        return tuple(spoken_line(line) for line in lines)

    def speakers_refusal(self, lines: Sequence[Line]) -> str | None:
        spoken = {line.speaker_id for line in lines if line.speaker_id is not None}
        strangers = sorted(spoken - set(self.speakers))
        if not strangers:
            return None
        return (
            f"nobody here has id {', '.join(strangers)}. Only the player or someone here with "
            "them speaks; leave `speaker_id` null for narration."
        )

    def narration_refusal(self, narration: Narration) -> str | None:
        if not narration.lines:
            return "write the narration lines: an empty answer shows the player nothing."
        return self.speakers_refusal(narration.lines)

    def interjection_refusal(self, member_id: Slug, answer: Interjection) -> str | None:
        if any(line.speaker_id != member_id for line in answer.lines):
            return f"only {member_id} speaks here: every `speaker_id` is {member_id!r}"
        if answer.proposal and not answer.lines:
            return (
                "a proposal comes with at least one line of dialogue; keep quiet with no lines "
                "and no proposal"
            )
        return None


class PlayerView(Frozen):
    """What the pages read: scene art and subjects live on the narrator view, not here."""

    player: Subject
    scene_title: str
    situation: str
    panels: tuple[Panel, ...]
    prompt: PendingDecision | None
    action: DecisionOption | None
    over: str | None
