from core_test_support import the_campaign
from tunnelgoons_test_support import HALL, MIRA, START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId
from aidm.engines.base import PLAYER_ID
from aidm.engines.hub import Job
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.views import REPORT_ROW
from aidm.engines.tunnelgoons.world import Item, Visit

ENGINE = TunnelGoonsEngine()


def test_narrator_view_names_nothing_unknown_here() -> None:
    view = ENGINE.narrator_view(small_world())
    assert all(subject.name != "Robo Mantis" for subject in view.subjects)


def test_speakers_exclude_a_known_but_dead_npc() -> None:
    state = small_world()
    state.payload.npcs[MIRA].alive = False
    view = ENGINE.narrator_view(state)
    assert any(subject.id == MIRA for subject in view.subjects)
    assert not any(speaker.id == MIRA for speaker in view.speakers)


def test_player_view_has_the_five_panels_in_order_and_here_carries_icons() -> None:
    view = ENGINE.player_view(small_world())
    assert [panel.title for panel in view.panels] == [
        "Character",
        "Here",
        "Carrying",
        "Ways out",
        "Trail",
    ]
    here = next(panel for panel in view.panels if panel.title == "Here")
    assert here.rows[0].icon_id == PLAYER_ID


def test_master_sections_names_the_hidden_npc_and_the_locked_way() -> None:
    state = small_world()
    world = state.payload
    world.visits.append(Visit(place=HALL))
    sections = dict(ENGINE.master_sections(state))
    assert "Robo Mantis" in sections["HIDDEN HERE (the player has not found these)"]
    assert "locked" in sections["WAYS OUT"]


def test_master_sections_lists_an_item_an_npc_here_is_holding() -> None:
    state = small_world()
    world = state.payload
    on_a_string = EntityId("mira-key")
    world.items[on_a_string] = Item(
        id=on_a_string, name="Mira's Key", brief="On a string", known=True, on=MIRA
    )
    sections = dict(ENGINE.master_sections(state))
    assert "Mira's Key" in sections["HERE WITH THE PLAYER"]


def test_a_stroll_with_no_job_open_shows_the_board_not_report_in() -> None:
    state = hub_world()
    world = state.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START), Visit(place=TAVERN)]

    view = ENGINE.player_view(state)

    board = next(panel for panel in view.panels if panel.title == "Board")
    assert board.rows == the_campaign(world.campaign).board_rows()
    assert not any(panel.title == "Jobs" for panel in view.panels)


def test_a_job_open_at_the_hub_shows_only_report_in_on_the_board() -> None:
    state = hub_world()
    world = state.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START), Visit(place=TAVERN)]
    the_campaign(world.campaign).jobs = [Job(title="Bandits", place=START, started=1)]

    view = ENGINE.player_view(state)

    board = next(panel for panel in view.panels if panel.title == "Board")
    assert board.rows == (REPORT_ROW,)


def test_entity_line_marks_a_dead_npc_and_the_players_carried_over_score() -> None:
    state = small_world()
    world = state.payload
    world.npcs[MIRA].alive = False
    assert "(dead)" in world.line(world.npcs[MIRA]).splitlines()[0]
    assert "inventory: 2/8" in world.line(world.player).lower()
