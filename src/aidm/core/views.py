from collections.abc import Iterable, Sequence
from typing import Self

from pydantic import model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Refusal, Slug
from aidm.core.play import (
    Exchange,
    Line,
    Narration,
    PendingDecision,
    SceneRecord,
    SpokenLine,
)

type Rows = tuple[tuple[str, str], ...]  # a sheet
type Sections = tuple[tuple[str, str], ...]  # a prompt

SCENE_EXCHANGES = 20
WHOLE_SCENES = 2
TAIL_EXCHANGES = 3


class Subject(Frozen):
    id: CheckedEntityId
    name: str
    brief: str


# Three row shapes, told apart in this order: an entity (`icon_id`), a labelled value
# (`detail`), else a bare label.
class PanelRow(Frozen):
    label: str
    detail: str
    icon_id: EntityId | None = None


class Panel(Frozen):
    title: str
    rows: tuple[PanelRow, ...]


class Action(Frozen):
    """A way on the engine offers the page; the page sends its id back with the player's words."""

    id: Slug
    label: str
    detail: str = ""
    intent: str = ""  # already resolved by the rules: the page sends it, asking for no words


class NarratorView(Frozen):
    """The Narrator's input type: it has no field that can hold hidden canon."""

    # The place, as the art cache names it: two scenes in one place share one picture.
    place: str
    title: str
    focus: str
    situation: str
    subjects: tuple[Subject, ...]
    # The player and everyone present who may speak; nobody else can be attributed a line.
    speakers: tuple[CheckedEntityId, ...]
    # The player's own sheet: theirs to know, so the narrator may show it through detail.
    sheet: Rows

    @model_validator(mode="after")
    def _speakers_are_subjects(self) -> Self:
        here = {subject.id for subject in self.subjects}
        if strangers := sorted(set(self.speakers) - here):
            raise ValueError(f"speakers who are not subjects: {strangers}")
        return self

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

    def speakers_refusal(self, lines: Sequence[Line]) -> str | None:
        """Only the player or someone here speaks; the leak rule holds by check, not trust."""
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


class PlayerView(Frozen):
    """What the pages read: scene art and subjects live on the narrator view, not here."""

    player: Subject
    panels: tuple[Panel, ...]
    prompt: PendingDecision | None
    action: Action | None
    over: str | None


def sections(parts: Sections) -> str:
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def lines_of(parts: Iterable[str]) -> str:
    return "\n".join(parts) or "- (none)"


def render_history(records: Sequence[SceneRecord]) -> str:
    """Every role reads the story back through this: the last two scenes whole, older ones bound."""
    if not any(record.exchanges for record in records):
        return "(the game has not started yet)"
    total = len(records)
    return "\n\n".join(_block(record, index, total) for index, record in enumerate(records))


def told_history(records: Sequence[SceneRecord]) -> str:
    """The recent blocks the master reads, without recaps: those are the worldsmith's."""
    recent = [record for record in records[-WHOLE_SCENES:] if record.exchanges]
    if not recent:
        return "(nothing yet)"
    return "\n\n".join(
        f"{_header(record)}\n\n{_told(record.exchanges[-SCENE_EXCHANGES:])}" for record in recent
    )


def _block(record: SceneRecord, index: int, total: int) -> str:
    header = _header(record)
    if index >= total - WHOLE_SCENES:
        body = _told(record.exchanges[-SCENE_EXCHANGES:])
    elif record.recap:
        body = f"what happened: {record.recap}"
    else:
        body = _told(record.exchanges[-TAIL_EXCHANGES:])
    return f"{header}\n\n{body}"


def _header(scene: SceneRecord) -> str:
    return f"SCENE: {scene.title}" + (f"\n{scene.focus}" if scene.focus else "")


def _told(exchanges: Sequence[Exchange]) -> str:
    return (
        "\n\n".join(f"> {exchange.prompt}\n{exchange.narration}" for exchange in exchanges)
        or "(nothing yet)"
    )
