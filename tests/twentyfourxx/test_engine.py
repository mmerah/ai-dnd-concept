import pytest
from support.table import TWENTYFOURXX, change, game, narrowed, updated
from support.twentyfourxx import ENGINE, LOCKPICKS, small_world

from aidm.core.entities import Refusal
from aidm.core.views import PanelRow
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import Gear, TwentyfourxxGame

COMM = "comm"
CLIMBING_GEAR = "climbing-gear"
NIGHT_VISION_GOGGLES = "night-vision-goggles"
VESSA = "vessa-rune"


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    state = narrowed(state, TwentyfourxxGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_operators_gear() -> None:
    _, state = _twentyfourxx_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload
    assert list(world.player.require_sheet().items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.run.place == "docking-ring"
    assert PLAYER_ID not in world.present()


def test_join_party_lands_a_party_joined_fact_and_adds_the_member() -> None:
    engine, state = _twentyfourxx_game()
    draft = state.draft()

    _ = change(engine, draft, "join_party", entity_id=VESSA)

    assert VESSA in draft.payload.party


def test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(Refusal, match="not installed"):
        engine.validate(updated(state, packs=(SRD_PACK, "uninstalled")))


def test_item_detail_of_a_plain_item_is_empty() -> None:
    assert Gear(name="Lockpick set").notes() == ""


def test_item_detail_of_a_bulky_item() -> None:
    assert Gear(name="Crate", bulky=True).notes() == "bulky"


def test_item_detail_of_a_broken_item() -> None:
    assert Gear(name="Scanner", broken_times=1).notes() == "broken"


def test_item_detail_of_a_multi_break_partly_broken_item() -> None:
    item = Gear(name="Battle armor", breaks=3, broken_times=1)
    assert item.notes() == "broken 1/3"


def test_player_view_character_panel_lists_gear() -> None:
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
