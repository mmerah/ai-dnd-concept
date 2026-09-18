from support.table import TWENTYFOURXX, game, narrowed
from support.twentyfourxx import ENGINE, small_world

from aidm.engines.engine import AnyEngine
from aidm.engines.packs import SRD_PACK
from aidm.engines.twentyfourxx.world import TwentyfourxxGame

COMM = "comm"
CLIMBING_GEAR = "climbing-gear"
NIGHT_VISION_GOGGLES = "night-vision-goggles"


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    state = narrowed(state, TwentyfourxxGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_operators_gear() -> None:
    _, state = _twentyfourxx_game()
    assert state.pack_id == SRD_PACK
    world = state.world
    assert list(world.player.require_sheet().items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.scene.place == "docking-ring"


def test_master_sections_shows_hidden_entities() -> None:
    world = small_world()
    sections = dict(ENGINE.master_sections(world))
    assert "Sable" in sections["HIDDEN HERE (the player has not found these)"]
