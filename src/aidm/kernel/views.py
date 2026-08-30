from aidm.state.entities import Frozen
from aidm.state.play import DecisionOption


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

    label: str
    summary: str
    sections: tuple[tuple[str, str], ...]
    prompts: tuple[tuple[str, str], ...]
    art_prompt: str
    subjects: tuple[ArtSubject, ...]


class PlayerView(Frozen):
    """Scene art and subjects live on the narrator view; this holds only what the player owns."""

    player: ArtSubject
    prompt: PlayerPrompt | None


class Views(Frozen):
    director: DirectorView
    narrator: NarratorView
    player: PlayerView


class CreationPreview(Frozen):
    rows: tuple[tuple[str, str], ...]
