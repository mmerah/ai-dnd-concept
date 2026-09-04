from collections.abc import Iterable, Sequence

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Refusal
from aidm.core.play import (
    ChapterRecord,
    Exchange,
    HistoryRecord,
    Line,
    Narration,
    PendingDecision,
    SceneRecord,
    Speaker,
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

    def speaker(self) -> Speaker:
        return Speaker(name=self.name, id=self.id)


# Three row shapes, told apart in this order: a way on (`intent`), an entity (`icon_id`),
# a labelled value (`detail`), else a bare label.
class PanelRow(Frozen):
    label: str
    detail: str
    # Set when the row is an entity, so the sidebar can draw its icon.
    icon_id: EntityId | None = None
    # Set when the row is a way on: the sidebar draws a button that plays Move on with it.
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
    speakers: tuple[Speaker, ...]

    def spoken(self, lines: Sequence[Line]) -> tuple[SpokenLine, ...]:
        """Attribution is denormalized here, so chat and journal never resolve ids through state."""
        here = {speaker.id: speaker for speaker in self.speakers}

        def spoken_line(line: Line) -> SpokenLine:
            if line.speaker_id is None:
                return SpokenLine(text=line.text)
            who = here.get(line.speaker_id)
            if who is None:
                raise Refusal(f"nobody here has id {line.speaker_id!r}")
            return SpokenLine(speaker=who, text=line.text)

        return tuple(spoken_line(line) for line in lines)

    def speakers_refusal(self, lines: Sequence[Line]) -> str | None:
        """Only the player or someone here speaks; the leak rule holds by check, not trust."""
        here = {speaker.id for speaker in self.speakers}
        strangers = sorted(
            {
                line.speaker_id
                for line in lines
                if line.speaker_id is not None and line.speaker_id not in here
            }
        )
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
    """A prompt list, one item per line; an empty one still says so."""
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
    return f"SCENE: {scene.title}\n{scene.question}"


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
