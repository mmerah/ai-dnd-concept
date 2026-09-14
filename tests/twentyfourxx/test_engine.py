import pytest
from support.table import TWENTYFOURXX, game, narrowed
from support.twentyfourxx import ENGINE, LOCKPICKS, small_world

from aidm.core.model import PackSelection
from aidm.core.views import PanelRow
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import Gear, TwentyfourxxGame

COMM = "comm"
CLIMBING_GEAR = "climbing-gear"
NIGHT_VISION_GOGGLES = "night-vision-goggles"


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    state = narrowed(state, TwentyfourxxGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_operators_gear() -> None:
    _, state = _twentyfourxx_game()
    assert state.packs == PackSelection(ids=(SRD_PACK,))
    world = state.payload
    assert list(world.player.require_sheet().items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.run.place == "docking-ring"
    assert PLAYER_ID not in world.present()


@pytest.mark.parametrize(
    ("gear", "expected"),
    [
        (Gear(name="Lockpick set"), ""),
        (Gear(name="Crate", bulky=True), "bulky"),
        (Gear(name="Scanner", broken_times=1), "broken"),
        (Gear(name="Battle armor", breaks=3, broken_times=1), "broken 1/3"),
    ],
)
def test_gear_notes(gear: Gear, expected: str) -> None:
    assert gear.notes() == expected


def test_player_view_character_panel_carries_the_gear_row() -> None:
    view = ENGINE.player_view(small_world())
    character = next(panel for panel in view.panels if panel.title == "Character")
    assert PanelRow(label="Gear", detail="Lockpick set") in character.rows


def test_master_sections_shows_hidden_entities() -> None:
    world = small_world()
    sections = dict(ENGINE.master_sections(world))
    assert "Sable" in sections["HIDDEN HERE (the player has not found these)"]


def test_master_sections_gear_shows_none_for_empty_gear() -> None:
    world = small_world()
    world.payload.player.require_sheet().items.clear()
    sections = dict(ENGINE.master_sections(world))
    assert sections["GEAR"] == "- (none)"


def test_master_sections_gear_lists_items_with_key_and_detail() -> None:
    world = small_world()
    sections = dict(ENGINE.master_sections(world))
    assert sections["GEAR"] == f"- Lockpick set[{LOCKPICKS}]"
