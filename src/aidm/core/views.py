from collections.abc import Mapping, Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Refusal, Slug, check_unique, headline_of
from aidm.core.play import (
    DecisionOption,
    Interjection,
    Line,
    Narration,
    PendingDecision,
    SpokenLine,
)

type Chattiness = Literal["quiet", "normal", "chatty"]
type Rows = tuple[tuple[str, str], ...]


# Three row shapes, in order: entity (`icon_id`), named value (`brief`), or bare name.
class PanelRow(Frozen):
    name: str
    brief: str
    icon_id: Slug | None = None


class Subject(Frozen):
    id: Slug
    name: str = Field(min_length=1)
    brief: str = ""

    @property
    def headline(self) -> str:
        return headline_of(self.name, self.id, self.brief)

    def row(self) -> PanelRow:
        return PanelRow(name=self.name, brief=self.brief, icon_id=self.id)


class Companion(Subject):
    sheet: Rows
    chattiness: Chattiness


class Panel(Frozen):
    title: str
    rows: tuple[PanelRow, ...]
    portrait: bool = False


class NarratorView(Frozen):
    """The Narrator's input type: it has no field that can hold hidden canon."""

    # The place, as the art cache names it: two scenes in one place share one picture.
    place: Slug
    title: str
    focus: str
    situation: str
    subjects: tuple[Subject, ...]
    speakers: tuple[Slug, ...]
    # The player first, then who travels with them.
    party: tuple[Slug, ...] = Field(min_length=1)
    # The player's own sheet: theirs to know, so the narrator may show it through detail.
    sheet: Rows

    @model_validator(mode="after")
    def _everyone_is_a_subject(self) -> Self:
        here = {subject.id for subject in self.subjects}
        if strangers := sorted(set(self.speakers) - here):
            raise ValueError(f"speakers who are not subjects: {strangers}")
        if party_strangers := sorted(set(self.party) - here):
            raise ValueError(f"party members who are not subjects: {party_strangers}")
        check_unique("party members", self.party)
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
            return SpokenLine(speaker_id=who.id, speaker=who.name, text=line.text)

        return tuple(spoken_line(line) for line in lines)

    def check_narration(self, narration: Narration) -> None:
        if not narration.lines:
            raise Refusal("Write the narration lines. An empty answer shows the player nothing.")
        spoken = {line.speaker_id for line in narration.lines if line.speaker_id is not None}
        if strangers := sorted(spoken - set(self.speakers)):
            raise Refusal(
                f"nobody here has id {', '.join(strangers)}. Only the player, or a person here "
                "with the player, speaks. Use null for `speaker_id` in narration."
            )

    def check_interjection(self, member_id: Slug, answer: Interjection) -> None:
        if any(line.speaker_id != member_id for line in answer.lines):
            raise Refusal(f"only {member_id} speaks here: every `speaker_id` is {member_id!r}")
        if answer.proposal and not answer.lines:
            raise Refusal(
                "a proposal comes with at least one line of dialogue. To stay quiet, give no "
                "lines and no proposal"
            )


class PlayerView(Frozen):
    premise: str
    player: Subject
    scene_title: str
    situation: str
    panels: tuple[Panel, ...]
    decision: PendingDecision | None
    action: DecisionOption | None
    ending: str | None


class Look(Frozen):
    palette: Mapping[str, str]


def filled(*pairs: tuple[str, str]) -> Rows:
    return tuple(pair for pair in pairs if pair[1])
