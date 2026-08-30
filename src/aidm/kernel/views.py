from aidm.state.entities import Frozen
from aidm.state.play import DecisionOption, Speaker


class ArtSubject(Frozen):
    id: str
    name: str
    brief: str


class PlayerPrompt(Frozen):
    prompt: str
    options: tuple[DecisionOption, ...]
    allows_text: bool


class DirectorView(Frozen):
    """The Director's whole picture: an engine states every section, so nothing leaks by
    omission."""

    sections: tuple[tuple[str, str], ...]


class NarratorView(Frozen):
    """The Narrator's input type: it has no field that can hold hidden canon."""

    # Scene identity, as the art cache names it.
    key: str
    label: str
    summary: str
    sections: tuple[tuple[str, str], ...]
    prompts: tuple[tuple[str, str], ...]
    art_prompt: str
    subjects: tuple[ArtSubject, ...]
    # The player and everyone present who may speak; nobody else can be attributed a line.
    speakers: tuple[Speaker, ...]


class PlayerView(Frozen):
    """Scene art and subjects live on the narrator view; this holds only what the player owns."""

    player: ArtSubject
    prompt: PlayerPrompt | None


class Views(Frozen):
    director: DirectorView
    narrator: NarratorView
    player: PlayerView


def speaker_of(subject: ArtSubject) -> Speaker:
    return Speaker(name=subject.name, id=subject.id)


class CreationPreview(Frozen):
    rows: tuple[tuple[str, str], ...]
