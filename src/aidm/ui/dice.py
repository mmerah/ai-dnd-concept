from collections.abc import Sequence

from nicegui import ui

from aidm.core.facts import DiceEvent, Fact, cards
from aidm.core.views import DiceLook


class DiceOverlay(ui.element, component="dice_overlay.js"):
    """Dice thrown across the whole page as they land; the card below keeps the result."""

    def __init__(self, look: DiceLook) -> None:
        super().__init__()
        self.classes("game-dice-overlay").style(
            f"--die-body: {look.body}; --die-ink: {look.ink}; --die-glow: {look.glow}"
        )

    def toss(self, events: Sequence[DiceEvent]) -> None:
        if dice := thrown(events):
            self.run_method("toss", dice)


def thrown(events: Sequence[DiceEvent]) -> list[dict[str, int | bool]]:
    """One die per rolled value; in a group that keeps some, the others land dimmed."""
    return [
        {"faces": face, "value": value, "kept": not event.highlight or index in event.highlight}
        for event in events
        for index, (face, value) in enumerate(zip(event.faces, event.rolled, strict=True))
    ]


def rolled_since(facts: Sequence[Fact], seen: int) -> tuple[DiceEvent, ...]:
    """The dice on the cards that landed after the first `seen` facts."""
    return tuple(event for fact in cards(facts[seen:]) for event in fact.dice)
