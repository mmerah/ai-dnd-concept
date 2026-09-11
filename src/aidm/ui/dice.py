from collections.abc import Sequence
from pathlib import Path

from nicegui import ui

from aidm.core.facts import DiceEvent, Fact, cards
from aidm.ui.theme import DiceLook

DICE_ASSETS = Path(__file__).parent / "dice_assets"
DICE_ASSETS_ROUTE = "/dice/"


class DiceTray(ui.element, component="dice_tray.js", dependencies=["lib/dice-box-threejs.es.js"]):
    """Dice thrown across the whole page as they land; the card below keeps the result."""

    def __init__(self, look: DiceLook) -> None:
        super().__init__()
        self._props["look"] = look.model_dump()
        self._props["assets"] = DICE_ASSETS_ROUTE
        self.classes("game-dice-overlay")

    def toss(self, events: Sequence[DiceEvent]) -> None:
        if dice := thrown(events):
            self.run_method("toss", dice)


def thrown(events: Sequence[DiceEvent]) -> list[dict[str, int]]:
    """One die per rolled value, in event order; the card, not the toss, says which are kept."""
    return [
        {"faces": face, "value": value}
        for event in events
        for face, value in zip(event.faces, event.rolled, strict=True)
    ]


def rolled_since(facts: Sequence[Fact], seen: int) -> tuple[DiceEvent, ...]:
    """The dice on the cards that landed after the first `seen` facts."""
    return tuple(event for fact in cards(facts[seen:]) for event in fact.dice)
