import pytest

from aidm.core.entities import Refusal
from aidm.engines.tunnelgoons.creation import (
    STARTING_ITEM_LIST,
    create_character,
    creation_steps,
    preview_character,
)
from aidm.engines.tunnelgoons.world import TunnelGoonsCharacterFile

PICKS = {
    "brute": "1",
    "skulker": "1",
    "erudite": "1",
    "item-1": "Rope",
    "item-2": "Torch",
    "item-3": "Melee Weapon (dagger)",
}


def test_creation_steps_cover_the_abilities_and_the_three_items() -> None:
    steps = creation_steps({})
    assert [step.id for step in steps] == [
        "brute",
        "skulker",
        "erudite",
        "item-1",
        "item-2",
        "item-3",
    ]
    assert steps[0].hint == "3 points across the three"
    assert steps[-1].hint == ", ".join(STARTING_ITEM_LIST)


def test_create_character_on_the_legal_path() -> None:
    character = create_character("Kael", "A wiry scavenger", PICKS)
    assert isinstance(character, TunnelGoonsCharacterFile)
    assert character.payload.items == ("Rope", "Torch", "Melee Weapon (dagger)")


def test_a_sum_not_equal_to_three_is_refused() -> None:
    """Each pick is legal on its own, so only the sheet's own rule can say no, and it must read."""
    with pytest.raises(Refusal, match="share exactly 3 points"):
        _ = create_character("Kael", "A wiry scavenger", dict(PICKS, brute="3", skulker="3"))


def test_a_missing_item_is_refused() -> None:
    bad = dict(PICKS)
    del bad["item-2"]
    with pytest.raises(ValueError, match="unanswered"):
        _ = create_character("Kael", "A wiry scavenger", bad)


def test_preview_character_rows() -> None:
    character = create_character("Kael", "A wiry scavenger", PICKS)
    rows = preview_character(character)
    assert ("Items", "Rope, Torch, Melee Weapon (dagger)") in rows
