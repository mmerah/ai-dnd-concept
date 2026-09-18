from pathlib import Path

import pytest
from support.table import ENGINE_IDS, ENGINES_BUILT

import aidm.ui.theme
from aidm.core.entities import EngineId
from aidm.core.facts import DiceEvent, Fact
from aidm.ui.transcript import rolled_since

TWO_D6 = DiceEvent(label="2d6", faces=(6, 6), rolled=(2, 5))
DIE_KEYS = ("game-die-body", "game-die-ink", "game-die-glow")


def _fact(*, told: bool) -> Fact:
    return Fact(trace=TWO_D6.label, told=told, card=TWO_D6.label, dice=(TWO_D6,))


def test_only_told_dice_after_the_seen_facts_count_as_landed() -> None:
    facts = (_fact(told=True), _fact(told=False), _fact(told=True))

    assert rolled_since(facts, 1)
    assert rolled_since(facts, 0)
    assert not rolled_since(facts, 3)
    assert not rolled_since(facts[:2], 1)


@pytest.mark.parametrize("engine_id", ENGINE_IDS)
def test_an_engine_paints_its_dice_through_variables_theme_css_reads(engine_id: EngineId) -> None:
    """theme.css reads `var(--game-die-*)` off the engine's palette; a rename must fail here."""
    css = Path(aidm.ui.theme.__file__).with_name("theme.css").read_text()
    palette = ENGINES_BUILT[engine_id].look.palette

    assert all(key in palette for key in DIE_KEYS)
    assert all(f"var(--{key})" in css for key in DIE_KEYS)
