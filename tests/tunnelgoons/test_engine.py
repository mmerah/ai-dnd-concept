import pytest
from core_test_support import TUNNELGOONS, game, updated

from aidm.engines.core import AnyEngine
from aidm.engines.tunnelgoons.engine import validate
from aidm.engines.tunnelgoons.world import TunnelGoonsGame


def _tunnelgoons_game() -> tuple[AnyEngine, TunnelGoonsGame]:
    engine, state = game(TUNNELGOONS)
    if not isinstance(state, TunnelGoonsGame):
        raise AssertionError("the Tunnel Goons engine began another game type")
    return engine, state


def test_the_shipped_game_begins_on_the_maps_start_with_the_starting_items() -> None:
    _, state = _tunnelgoons_game()
    assert state.packs == ()
    world = state.payload.world
    assert world.visits[0].place == world.player.place
    assert {item.name for item in world.carried(world.player.id)} == {
        "Pry Bar (melee weapon)",
        "Rope",
        "Torch",
    }


def test_a_scenario_with_a_pack_is_refused_by_validate() -> None:
    _, state = _tunnelgoons_game()
    with pytest.raises(ValueError, match="no table sets"):
        validate(updated(state, packs=("srd",)))


def test_restored_round_trips() -> None:
    engine, state = _tunnelgoons_game()
    assert engine.restored(state.model_dump_json()) == state
