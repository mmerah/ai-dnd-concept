from support.twentyfourxx import ENGINE, LOCKPICKS, small_world

from aidm.core.views import PanelRow
from aidm.engines.twentyfourxx.world import Gear


def test_item_detail_of_a_plain_item_is_empty() -> None:
    assert Gear(name="Lockpick set").detail() == ""


def test_item_detail_of_a_bulky_item() -> None:
    assert Gear(name="Crate", bulky=True).detail() == "bulky"


def test_item_detail_of_a_broken_item() -> None:
    assert Gear(name="Scanner", broken_times=1).detail() == "broken"


def test_item_detail_of_a_multi_break_partly_broken_item() -> None:
    item = Gear(name="Battle armor", breaks=3, broken_times=1)
    assert item.detail() == "broken 1/3"


def test_narrator_view_lists_only_known_entities() -> None:
    view = ENGINE.narrator_view(small_world())
    assert [subject.label for subject in view.subjects] == ["Rook", "Kestrel"]


def test_player_view_character_panel_lists_gear() -> None:
    view = ENGINE.player_view(small_world())
    character = next(panel for panel in view.panels if panel.title == "Character")
    assert PanelRow(label="Gear", detail="Lockpick set") in character.rows


def test_master_sections_shows_hidden_entities() -> None:
    game = small_world()
    sections = dict(ENGINE.master_sections(game))
    assert "Sable" in sections["HIDDEN HERE (the player has not found these)"]


def test_master_sections_gear_shows_none_for_empty_gear() -> None:
    game = small_world()
    game.payload.player.dice().items.clear()
    sections = dict(ENGINE.master_sections(game))
    assert sections["GEAR"] == "- (none)"


def test_master_sections_gear_lists_items_with_key_and_detail() -> None:
    game = small_world()
    sections = dict(ENGINE.master_sections(game))
    assert sections["GEAR"] == f"- Lockpick set[{LOCKPICKS}]"
