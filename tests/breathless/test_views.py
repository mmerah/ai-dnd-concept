from breathless_test_support import DAX, JOB, hub_world, small_world

from aidm.core.views import PanelRow
from aidm.engines.breathless.views import entity_line, master_sections, narrator_view, player_view
from aidm.engines.breathless.world import Npc
from aidm.engines.hub import HOME_ROW, HUB_ROW, TAKE_JOB, Debrief


def test_the_player_views_backpack_panel_lists_items_and_the_med_kit() -> None:
    game = small_world()
    game.payload.world.player.med_kit = True
    view = player_view(game)
    backpack = next(panel for panel in view.panels if panel.title == "Backpack")
    assert PanelRow(label="Wrench", detail="d10") in backpack.rows
    assert PanelRow(label="Med kit", detail="held") in backpack.rows


def test_the_player_views_here_panel_lists_the_player_first_then_known_cast() -> None:
    view = player_view(small_world())
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
    dead = Npc(id=DAX, name="Dax", brief="A looter", known=True, alive=False)
    line = entity_line(dead)
    assert line.startswith("- Dax[dax] — A looter (dead)")


def test_player_view_shows_the_board_panel_and_hub_row_at_the_hub() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    view = player_view(game)
    board = next(panel for panel in view.panels if panel.title == "Board")
    assert [row.label for row in board.rows] == ["Job One", "Job Two"]
    scene = next(panel for panel in view.panels if panel.title == "This scene")
    assert HUB_ROW.label in [row.label for row in scene.rows]


def test_player_view_shows_home_row_only_when_settled_away_from_the_hub() -> None:
    game = hub_world()
    world = game.payload.world

    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert HOME_ROW.label not in [row.label for row in scene.rows]

    at_hub = hub_world()
    at_hub.payload.world.runs = [at_hub.payload.world.runs[0]]
    scene = next(panel for panel in player_view(at_hub).panels if panel.title == "This scene")
    assert HOME_ROW.label not in [row.label for row in scene.rows]

    world.run.settled = True
    scene = next(panel for panel in player_view(game).panels if panel.title == "This scene")
    assert HOME_ROW.label in [row.label for row in scene.rows]


def test_player_view_jobs_panel_has_a_row_after_a_return() -> None:
    game = hub_world()
    world = game.payload.world
    debrief = Debrief(text="The pharmacy is cleared.", finished=True)
    returned = world.runs[0].model_copy(
        update={"scene": world.runs[0].scene.model_copy(update={"debrief": debrief})}
    )
    world.runs.append(returned)
    jobs = next(panel for panel in player_view(game).panels if panel.title == "Jobs")
    assert len(jobs.rows) == 1


def test_player_view_board_rows_play_take_job_intents() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    view = player_view(game)
    board = next(panel for panel in view.panels if panel.title == "Board")
    assert [row.intent for row in board.rows] == [
        TAKE_JOB.format(title="Job One"),
        TAKE_JOB.format(title="Job Two"),
    ]


def test_master_sections_has_jobs_so_far_in_a_campaign_and_the_board_at_the_hub() -> None:
    game = hub_world()
    game.payload.world.runs = [game.payload.world.runs[0]]
    sections = dict(master_sections(game))
    assert "JOBS SO FAR" in sections
    assert "Job One" in sections["THE BOARD"]


def test_master_sections_has_the_job_away_from_the_hub_and_the_hub_heading_at_the_hub() -> None:
    game = hub_world()
    sections = dict(master_sections(game))
    assert sections["THE JOB"] == JOB
    assert "THE QUESTION THIS SCENE SETTLES" in sections

    at_hub = hub_world()
    at_hub.payload.world.runs = [at_hub.payload.world.runs[0]]
    hub_sections_dict = dict(master_sections(at_hub))
    assert "WHAT THIS PLACE IS ABOUT" in hub_sections_dict
    assert "THE QUESTION THIS SCENE SETTLES" not in hub_sections_dict
