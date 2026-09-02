from breathless_test_support import DAX, small_world
from core_test_support import BREATHLESS, ENGINES_BUILT

from aidm.core.views import PanelRow
from aidm.engines.breathless.views import master_sections
from aidm.engines.core import Person
from aidm.engines.scenes.views import narrator_view
from aidm.engines.scenes.world import entity_line

ENGINE = ENGINES_BUILT[BREATHLESS]


def test_the_player_views_backpack_panel_lists_items_and_the_med_kit() -> None:
    game = small_world()
    game.payload.world.player.med_kit = True
    view = ENGINE.player_view(game)
    backpack = next(panel for panel in view.panels if panel.title == "Backpack")
    assert PanelRow(label="Wrench", detail="d10") in backpack.rows
    assert PanelRow(label="Med kit", detail="held") in backpack.rows


def test_the_player_views_here_panel_lists_the_player_first_then_known_cast() -> None:
    view = ENGINE.player_view(small_world())
    here = next(panel for panel in view.panels if panel.title == "Here")
    assert [row.label for row in here.rows] == ["Jax (you)", "Mira"]


def test_master_sections_never_lists_the_player_under_here() -> None:
    sections = dict(master_sections(small_world()))
    assert "Jax" not in sections["HERE WITH THE PLAYER"]
    assert "Mira" in sections["HERE WITH THE PLAYER"]


def test_master_sections_lists_the_backpack() -> None:
    game = small_world()
    game.payload.world.player.med_kit = True
    sections = dict(master_sections(game))
    assert sections["BACKPACK"] == "- Wrench[wrench] — d10\n- med kit"


def test_narrator_view_lists_only_known_entities_player_first() -> None:
    view = narrator_view(small_world())
    assert [subject.name for subject in view.subjects] == ["Jax", "Mira"]


def test_entity_line_marks_a_dead_one_after_the_brief() -> None:
    dead = Person(id=DAX, name="Dax", brief="A looter", known=True, alive=False)
    line = entity_line(dead)
    assert line.startswith("- Dax[dax] — A looter (dead)")
