from pathlib import Path

import aidm.ui.theme
from aidm.core.facts import DiceEvent, Fact
from aidm.core.views import DiceLook
from aidm.ui.dice import rolled_since
from aidm.ui.theme import dice_variables

TWO_D6 = DiceEvent(label="2d6", faces=(6, 6), rolled=(2, 5))


def _fact(*, told: bool) -> Fact:
    return Fact(trace=TWO_D6.label, told=told, card=TWO_D6.label, dice=(TWO_D6,))


def test_only_told_dice_after_the_seen_facts_count_as_landed() -> None:
    facts = (_fact(told=True), _fact(told=False), _fact(told=True))

    assert rolled_since(facts, 1)
    assert rolled_since(facts, 0)
    assert not rolled_since(facts, 3)
    assert not rolled_since(facts[:2], 1)


def test_dice_look_reaches_theme_css_through_the_variables_set_look_writes() -> None:
    """theme.css reads `var(--game-die-*)` off what `set_look` writes; a rename must fail here."""
    css = Path(aidm.ui.theme.__file__).with_name("theme.css").read_text()
    variables = dice_variables(DiceLook(body="#202020", ink="#f5f5f5", glow="#ffb703"))

    assert len(variables) == len(DiceLook.model_fields)
    assert all(f"var(--{name})" in css for name in variables)
