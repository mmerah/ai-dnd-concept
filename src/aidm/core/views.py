from collections.abc import Iterable, Sequence
from typing import Self

from pydantic import model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Refusal
from aidm.core.play import (
    ChapterRecord,
    Exchange,
    HistoryRecord,
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


# Three row shapes, told apart in this order: a way on (`intent`), an entity (`icon_id`),
# a labelled value (`detail`), else a bare label.
class PanelRow(Frozen):
    label: str
    detail: str
    icon_id: EntityId | None = None
    intent: str = ""


class Panel(Frozen):
    title: str
    rows: tuple[PanelRow, ...]


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
    over: str | None


def sections(parts: Sections) -> str:
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def lines_of(parts: Iterable[str]) -> str:
    return "\n".join(parts) or "- (none)"


def render_history(records: Sequence[HistoryRecord]) -> str:
    """Every role reads the story back through this: the last two scenes whole, older ones bound."""
    if not any(record.exchanges for record in records if isinstance(record, SceneRecord)):
        return "(the game has not started yet)"
    total = len(records)
    return "\n\n".join(_block(record, index, total) for index, record in enumerate(records))


def told_narration(records: Sequence[HistoryRecord]) -> tuple[str, ...]:
    """What the player has already read, so continuity costs the narrator no hidden canon."""
    return tuple(
        exchange.narration
        for record in records[-WHOLE_SCENES:]
        if isinstance(record, SceneRecord)
        for exchange in record.exchanges[-SCENE_EXCHANGES:]
        if exchange.narration
    )


def render_whole(scenes: Sequence[SceneRecord]) -> str:
    """Every exchange and every fact, told or not: what the worldsmith reads to sum a job up."""
    return "\n\n".join(_whole_scene(scene) for scene in scenes)


def _block(record: HistoryRecord, index: int, total: int) -> str:
    if isinstance(record, ChapterRecord):
        return (
            f"CLOSED: {record.title} ({record.verdict})\n"
            f"what happened: {record.summary}\n"
            f"scenes: {'; '.join(record.scenes)}"
        )
    header = _header(record)
    if index >= total - WHOLE_SCENES:
        body = _told(record.exchanges[-SCENE_EXCHANGES:])
    elif record.recap:
        body = f"what happened: {record.recap}"
    else:
        body = _told(record.exchanges[-TAIL_EXCHANGES:])
    return f"{header}\n\n{body}"


def _header(scene: SceneRecord) -> str:
    return f"SCENE: {scene.title}\n{scene.focus}"


def _told(exchanges: Sequence[Exchange]) -> str:
    return (
        "\n\n".join(f"> {exchange.prompt}\n{exchange.narration}" for exchange in exchanges)
        or "(nothing yet)"
    )


def _whole_scene(scene: SceneRecord) -> str:
    body = "\n\n".join(_whole_exchange(exchange) for exchange in scene.exchanges) or "(nothing yet)"
    return f"{_header(scene)}\n\n{body}"


def _whole_exchange(exchange: Exchange) -> str:
    facts = "\n".join(f"- {fact.trace}" for fact in exchange.facts)
    return "\n".join(part for part in (f"> {exchange.prompt}", facts, exchange.narration) if part)
