import pytest
from support.table import TUNNELGOONS, game, narrowed
from support.tunnelgoons import ENGINE

from aidm.core.entities import Refusal
from aidm.engines.seam import AnyEngine
from aidm.engines.tunnelgoons.engine import STARTING_ITEM_LIST
from aidm.engines.tunnelgoons.world import TunnelGoonsGame

PICKS = {
    "brute": "1",
    "skulker": "1",
    "erudite": "1",
    "item-1": "Rope",
    "item-2": "Torch",
    "item-3": "Melee Weapon (dagger)",
}


def _tunnelgoons_game() -> tuple[AnyEngine, TunnelGoonsGame]:
    engine, state = game(TUNNELGOONS)
    state = narrowed(state, TunnelGoonsGame)
    return engine, state


def test_the_shipped_game_begins_on_the_maps_start_with_the_starting_items() -> None:
    _, state = _tunnelgoons_game()
    assert state.packs == ()
    world = state.payload
    assert world.visits[0] == world.current.id
    assert {item.name for item in world.carried(world.player.id)} == {
        "Pry Bar (melee weapon)",
        "Rope",
        "Torch",
    }


def test_creation_steps_cover_the_abilities_and_the_three_items() -> None:
    steps = ENGINE.creation_steps({})
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
    character = ENGINE.create_character("Kael", "A wiry scavenger", PICKS)
    assert character.payload.kit == ("Rope", "Torch", "Melee Weapon (dagger)")
    assert character.payload.require_sheet().abilities == {"brute": 1, "skulker": 1, "erudite": 1}


def test_a_sum_not_equal_to_three_is_refused() -> None:
    """Each pick is legal on its own, so only the sheet's own rule can say no, and it must read."""
    with pytest.raises(Refusal, match="share exactly 3 points"):
        _ = ENGINE.create_character("Kael", "A wiry scavenger", dict(PICKS, brute="3", skulker="3"))


def test_a_missing_item_is_refused() -> None:
    bad = dict(PICKS)
    del bad["item-2"]
    with pytest.raises(Refusal, match="unanswered"):
        _ = ENGINE.create_character("Kael", "A wiry scavenger", bad)


def test_preview_character_rows() -> None:
    character = ENGINE.create_character("Kael", "A wiry scavenger", PICKS)
    rows = ENGINE.preview_character(character)
    assert ("Items", "Rope, Torch, Melee Weapon (dagger)") in rows
