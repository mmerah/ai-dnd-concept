from support.breathless import DAX, small_world
from support.table import BREATHLESS, ENGINES_BUILT

from aidm.core.views import PanelRow
from aidm.engines.base import Person

ENGINE = ENGINES_BUILT[BREATHLESS]


def test_the_player_views_backpack_panel_lists_items_and_the_med_kit() -> None:
    game = small_world()
    game.payload.player.med_kit = True
    view = ENGINE.player_view(game)
    backpack = next(panel for panel in view.panels if panel.title == "Backpack")
    assert PanelRow(label="Wrench", detail="d10") in backpack.rows
    assert PanelRow(label="Med kit", detail="held") in backpack.rows


def test_master_sections_never_lists_the_player_under_here() -> None:
    sections = dict(ENGINE.master_sections(small_world()))
    assert "Jax" not in sections["HERE WITH THE PLAYER"]
    assert "Mira" in sections["HERE WITH THE PLAYER"]


def test_master_sections_lists_the_backpack() -> None:
    game = small_world()
    game.payload.player.med_kit = True
    sections = dict(ENGINE.master_sections(game))
    assert sections["BACKPACK"] == "- Wrench[wrench] — d10\n- med kit"


def test_narrator_view_lists_only_known_entities_player_first() -> None:
    view = ENGINE.narrator_view(small_world())
    assert [subject.name for subject in view.subjects] == ["Jax", "Mira"]


def test_entity_line_marks_a_dead_one_after_the_brief() -> None:
    dead = Person(id=DAX, name="Dax", brief="A looter", known=True, alive=False)
    line = dead.line()
    assert line.startswith("- Dax[dax] — A looter (dead)")
