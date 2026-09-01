from twentyfourxx_test_support import LOCKPICKS, small_world

from aidm.core.views import PanelRow
from aidm.engines.twentyfourxx.views import gear_detail, master_sections, narrator_view, player_view
from aidm.engines.twentyfourxx.world import Item


def test_gear_detail_of_a_plain_item_is_empty() -> None:
    assert gear_detail(Item(name="Lockpick set")) == ""


def test_gear_detail_of_a_bulky_item() -> None:
    assert gear_detail(Item(name="Crate", bulky=True)) == "bulky"


def test_gear_detail_of_a_broken_item() -> None:
    assert gear_detail(Item(name="Scanner", broken_times=1)) == "broken"


def test_gear_detail_of_a_multi_break_partly_broken_item() -> None:
    item = Item(name="Battle armor", breaks=3, broken_times=1)
    assert gear_detail(item) == "broken 1/3"


def test_narrator_view_lists_only_known_entities() -> None:
    view = narrator_view(small_world())
    assert [subject.name for subject in view.subjects] == ["Rook", "Kestrel"]


def test_player_view_shows_the_way_on_row_only_when_settled() -> None:
    game = small_world()
    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert "Way on" not in [row.label for row in scene.rows]

    game.payload.world.run.settled = True
    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert "Way on" in [row.label for row in scene.rows]


def test_player_view_gear_panel_lists_items() -> None:
    view = player_view(small_world())
    gear = next(panel for panel in view.panels if panel.title == "Gear")
    assert PanelRow(label="Lockpick set", detail="") in gear.rows


def test_master_sections_shows_hidden_entities_and_the_secret() -> None:
    game = small_world()
    game.payload.world.run.scene = game.payload.world.current.model_copy(
        update={"secret": "Sable already took the cargo."}
    )
    sections = dict(master_sections(game))
    assert "Sable" in sections["HIDDEN HERE (the player has not found these)"]
    assert sections["THE SCENE'S SECRET (never narrate this)"] == "Sable already took the cargo."


def test_master_sections_gear_shows_none_for_empty_gear() -> None:
    game = small_world()
    game.payload.world.player.items = {}
    sections = dict(master_sections(game))
    assert sections["GEAR"] == "- (none)"


def test_master_sections_gear_lists_items_with_key_and_detail() -> None:
    game = small_world()
    sections = dict(master_sections(game))
    assert sections["GEAR"] == f"- Lockpick set[{LOCKPICKS}]"
