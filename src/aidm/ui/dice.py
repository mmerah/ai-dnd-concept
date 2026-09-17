from collections.abc import Sequence
from pathlib import Path

from nicegui import ui

from aidm.core.facts import Fact, cards

DICE_SOUND = Path(__file__).parent / "roll.mp3"
DICE_SOUND_ROUTE = "/dice/roll.mp3"


class DiceSound(ui.element, component="dice_sound.js"):
    def __init__(self) -> None:
        super().__init__()
        self._props["src"] = DICE_SOUND_ROUTE

    def play(self) -> None:
        self.run_method("play")


def rolled_since(facts: Sequence[Fact], seen: int) -> bool:
    """Whether any told card fact after `seen` carries dice."""
    return any(fact.dice for fact in cards(facts[seen:]))
