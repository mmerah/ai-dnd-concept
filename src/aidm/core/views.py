from collections.abc import Iterable

from aidm.core.entities import CheckedEntityId, EntityId, Frozen
from aidm.core.model import AnyGame
from aidm.core.play import DecisionOption, Speaker

type Rows = tuple[tuple[str, str], ...]


def sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


class Subject(Frozen):
    id: CheckedEntityId
    name: str
    brief: str


class PanelRow(Frozen):
    label: str
    detail: str
    # Set when the row is an entity, so the sidebar can draw its icon.
    icon_id: EntityId | None = None


class Panel(Frozen):
    title: str
    rows: tuple[PanelRow, ...]


class PlayerPrompt(Frozen):
    kind: str
    prompt: str
    options: tuple[DecisionOption, ...]
    allows_text: bool


class NarratorView(Frozen):
    """The Narrator's input type: it has no field that can hold hidden canon."""

    # The place, as the art cache names it: two scenes in one place share one picture.
    place: str
    title: str
    focus: str
    situation: str
    art_prompt: str
    subjects: tuple[Subject, ...]
    # The player and everyone present who may speak; nobody else can be attributed a line.
    speakers: tuple[Speaker, ...]


class PlayerView(Frozen):
    """What the pages read: scene art and subjects live on the narrator view, not here."""

    player: Subject
    panels: tuple[Panel, ...]
    prompt: PlayerPrompt | None
    over: str | None


def speaker_of(subject: Subject) -> Speaker:
    return Speaker(name=subject.name, id=subject.id)


def player_prompt(state: AnyGame) -> PlayerPrompt | None:
    pending = state.pending
    if pending is None:
        return None
    options = tuple(
        DecisionOption(id=one.id, label=one.label, detail=one.detail) for one in pending.options
    )
    return PlayerPrompt(
        kind=pending.kind, prompt=pending.prompt, options=options, allows_text=pending.allows_text
    )
