from aidm.core.entities import Frozen
from aidm.core.play import DecisionOption, Speaker

type Rows = tuple[tuple[str, str], ...]


class Subject(Frozen):
    id: str
    name: str
    brief: str


class ThreadRow(Frozen):
    title: str
    status: str
    note: str


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
    question: str
    situation: str
    art_prompt: str
    subjects: tuple[Subject, ...]
    # The player and everyone present who may speak; nobody else can be attributed a line.
    speakers: tuple[Speaker, ...]


class PlayerView(Frozen):
    """What the pages read: scene art and subjects live on the narrator view, not here."""

    player: Subject
    question: str
    sheet: tuple[tuple[str, str], ...]
    traits: tuple[tuple[str, str], ...]
    carrying: tuple[Subject, ...]
    present: tuple[Subject, ...]
    companions: tuple[str, ...]
    threads: tuple[ThreadRow, ...]
    scenes: tuple[str, ...]
    settled: bool
    prompt: PlayerPrompt | None
    over: str | None


def speaker_of(subject: Subject) -> Speaker:
    return Speaker(name=subject.name, id=subject.id)
