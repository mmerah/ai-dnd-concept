from collections.abc import Iterable, Sequence

from aidm.core.entities import CheckedEntityId, EntityId, Frozen
from aidm.core.play import Exchange, PendingDecision, SceneRecord, Speaker

type Rows = tuple[tuple[str, str], ...]

SCENE_EXCHANGES = 20
TAIL_EXCHANGES = 3


class Subject(Frozen):
    id: CheckedEntityId
    name: str
    brief: str


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


class PlayerView(Frozen):
    """What the pages read: scene art and subjects live on the narrator view, not here."""

    player: Subject
    panels: tuple[Panel, ...]
    prompt: PendingDecision | None
    over: str | None


def sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def speaker_of(subject: Subject) -> Speaker:
    return Speaker(name=subject.name, id=subject.id)


def render_history(scenes: Sequence[SceneRecord]) -> str:
    """Every role reads the story back through this: the last two scenes whole, older ones bound."""
    if not any(record.exchanges for record in scenes):
        return "(the game has not started yet)"
    total = len(scenes)
    return "\n\n".join(_block(record, index, total) for index, record in enumerate(scenes))


def told_narration(scenes: Sequence[SceneRecord]) -> tuple[str, ...]:
    """What the player has already read, so continuity costs the narrator no hidden canon."""
    return tuple(
        one.narration
        for record in scenes[-2:]
        for one in record.exchanges[-SCENE_EXCHANGES:]
        if one.narration
    )


def _block(record: SceneRecord, index: int, total: int) -> str:
    header = f"SCENE: {record.title}\n{record.question}"
    if index >= total - 2:
        body = _told(record.exchanges[-SCENE_EXCHANGES:])
    elif record.recap:
        body = f"what happened: {record.recap}"
    else:
        body = _told(record.exchanges[-TAIL_EXCHANGES:])
    return f"{header}\n\n{body}"


def _told(exchanges: Sequence[Exchange]) -> str:
    return "\n\n".join(f"> {one.prompt}\n{one.narration}" for one in exchanges) or "(nothing yet)"
