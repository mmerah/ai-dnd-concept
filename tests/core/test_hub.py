from functools import partial

import pytest

from aidm.core.views import Panel
from aidm.engines.hub import (
    TAKE_JOB,
    Debrief,
    Job,
    Offer,
    Stop,
    board_panel,
    board_rows,
    check_board,
    check_kind,
    closed_jobs,
    hub_sections,
    job_closed,
    job_start,
    job_titles,
    jobs_panel,
    ledger,
    master_tail,
    place_unmet,
    question_heading,
)
from aidm.engines.scenes.world import Scene, SceneRun, check_hub

HUB = "hub"
DONE = Debrief(text="Finished the job.", finished=True)
DONE_A = Debrief(text="Finished A", finished=True)
DONE_B = Debrief(text="Finished B", finished=True)
DONE_TAVERN = Debrief(text="Done", finished=True)


def _stops() -> tuple[Stop, ...]:
    return (
        Stop(place=HUB, title="Hub"),
        Stop(place="a1", title="A1"),
        Stop(place="a2", title="A2"),
        Stop(place=HUB, title="Hub", debrief=DONE_A),
        Stop(place="b1", title="B1"),
        Stop(place=HUB, title="Hub", debrief=DONE_B),
        Stop(place="c1", title="C1"),
    )


def _tunnel_goons_stops() -> tuple[Stop, ...]:
    return (
        Stop(place="tavern", title="Tavern"),
        Stop(place="a", title="A"),
        Stop(place="b", title="B"),
        Stop(place="tavern", title="Tavern"),
        Stop(place="tavern", title="Tavern", debrief=DONE_TAVERN),
    )


def test_the_job_walk_reads_titles_closed_jobs_and_start() -> None:
    stops = _stops()

    assert job_titles(HUB, stops) == ("", "A1", "A1", "", "B1", "", "C1")
    assert closed_jobs(HUB, stops) == (
        Job(title="A1", place="a1", debrief=DONE_A),
        Job(title="B1", place="b1", debrief=DONE_B),
    )
    assert job_start(stops) == 5


def test_the_job_walk_on_tunnel_goons_stops() -> None:
    stops = _tunnel_goons_stops()

    assert closed_jobs("tavern", stops) == (Job(title="A", place="a", debrief=DONE_TAVERN),)
    assert job_start(stops) == 4


def test_check_board_refuses_a_board_with_the_wrong_shape() -> None:
    offer = Offer(title="A job", pitch="Do the thing")

    with pytest.raises(ValueError):
        check_board(None, (offer,))
    with pytest.raises(ValueError):
        check_board(HUB, (offer,))
    with pytest.raises(ValueError):
        check_board(HUB, (offer, offer, offer, offer))


def test_check_board_accepts_two_or_three_offers_at_a_hub() -> None:
    offer = Offer(title="A job", pitch="Do the thing")

    check_board(HUB, (offer, offer))
    check_board(HUB, (offer, offer, offer))


def test_check_kind_refuses_a_kind_and_hub_mismatch() -> None:
    with pytest.raises(ValueError):
        check_kind("campaign", None)
    with pytest.raises(ValueError):
        check_kind("one-shot", "bar")

    check_kind("campaign", "bar")
    check_kind("one-shot", None)


def test_job_closed_names_a_finished_job() -> None:
    job = Job(title="A1", place="a1", debrief=DONE)

    fact = job_closed(job)

    assert fact.card == "Job done: A1\nFinished the job."
    assert fact.trace == "the job A1 closed (done)"


def test_job_closed_names_a_job_left_open() -> None:
    job = Job(title="A1", place="a1", debrief=Debrief(text="Ran out of time.", finished=False))

    fact = job_closed(job)

    assert fact.card == "Job left open: A1\nRan out of time."
    assert fact.trace == "the job A1 closed (left open)"


def _run(place: str, debrief: Debrief | None = None) -> SceneRun:
    scene = Scene(
        place=place,
        title="A scene",
        question="What happens next here?",
        situation="A long enough situation to satisfy the minimum length the model demands.",
        debrief=debrief,
    )
    return SceneRun(scene=scene)


def test_check_hub_refuses_a_debrief_with_no_hub() -> None:
    with pytest.raises(ValueError):
        check_hub(None, (), (_run("somewhere", DONE),))


def test_check_hub_refuses_a_hub_run_right_after_a_hub_run() -> None:
    board = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))

    with pytest.raises(ValueError):
        check_hub(HUB, board, (_run(HUB), _run(HUB, DONE)))


def test_check_hub_accepts_a_job_between_two_hub_visits() -> None:
    board = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))

    check_hub(HUB, board, (_run(HUB), _run("a1"), _run(HUB, DONE)))


def test_board_rows_plays_take_job_with_the_title_and_keeps_the_pitch() -> None:
    offer = Offer(title="Deck 9 Crate Run", pitch="Crates off Deck 9, no manifest, half up front.")

    (row,) = board_rows((offer,))

    assert row.label == "Deck 9 Crate Run"
    assert row.detail == "Crates off Deck 9, no manifest, half up front."
    assert row.intent == TAKE_JOB.format(title="Deck 9 Crate Run")


def test_hub_sections_picks_the_brief_by_moment() -> None:
    rows = partial(hub_sections, "The Amber Tap", HUB, (), (), finished=False)
    taking = dict(rows(at_hub=True, returning=False))
    away = dict(rows(at_hub=False, returning=False))
    returning = dict(rows(at_hub=False, returning=True))

    assert taking["THE HUB"].startswith("The player is leaving The Amber Tap")
    assert away["THE HUB"].startswith("The hub is The Amber Tap")
    assert returning["THE HUB"].startswith("Write the hub scene there.")
    assert "THE VERDICT" not in taking
    assert "THE VERDICT" not in away


def test_hub_sections_returning_adds_the_verdict_by_finished() -> None:
    rows = partial(hub_sections, "The Amber Tap", HUB, (), (), at_hub=False, returning=True)
    open_verdict = dict(rows(finished=False))
    finished_verdict = dict(rows(finished=True))

    assert open_verdict["THE VERDICT"] == "left open"
    assert finished_verdict["THE VERDICT"] == "finished"


def test_place_unmet_refuses_the_wrong_place_for_the_moment() -> None:
    assert place_unmet(HUB, HUB, returning=False) == (
        "a place away from the hub: home is reached by going home"
    )
    assert place_unmet("a1", HUB, returning=True) == (
        f"the hub's place {HUB!r}: this scene is home"
    )


def test_place_unmet_allows_the_hub_returning_away_and_the_opening_with_no_hub() -> None:
    assert place_unmet(HUB, HUB, returning=True) is None
    assert place_unmet("a1", HUB, returning=False) is None
    assert place_unmet("a1", None, returning=False) is None


def test_question_heading_switches_by_at_hub() -> None:
    assert question_heading(True) == "WHAT THIS PLACE IS ABOUT"
    assert question_heading(False) == "THE QUESTION THIS SCENE SETTLES"


def test_master_tail_shows_the_job_away_and_the_board_at_the_hub() -> None:
    jobs = (Job(title="A1", place="a1", debrief=DONE_A),)
    board = (Offer(title="B", pitch="Do b"),)

    away = dict(master_tail(HUB, False, board, jobs, "Clear the warehouse"))
    assert away["THE JOB"] == "Clear the warehouse"
    assert "A1" in away["JOBS SO FAR"]
    assert "THE BOARD" not in away

    at_hub = dict(master_tail(HUB, True, board, jobs, ""))
    assert "THE JOB" not in at_hub
    assert "B" in at_hub["THE BOARD"]

    one_shot = dict(master_tail(None, False, (), (), ""))
    assert one_shot == {}


def test_board_panel_is_shown_only_at_the_hub() -> None:
    offer = Offer(title="A", pitch="Do a")

    assert board_panel(True, (offer,)) == (Panel(title="Board", rows=board_rows((offer,))),)
    assert board_panel(False, (offer,)) == ()


def test_jobs_panel_is_shown_only_when_there_is_a_job() -> None:
    assert jobs_panel(()) == ()

    job = Job(title="A1", place="a1", debrief=DONE_A)
    (panel,) = jobs_panel((job,))
    assert panel.title == "Jobs"
    assert len(panel.rows) == 1


def test_closed_jobs_carries_the_terms_the_leaving_scene_wrote() -> None:
    stops = (
        Stop(place=HUB, title="Hub"),
        Stop(place="a1", title="A1", job="Clear the warehouse by dawn."),
        Stop(place=HUB, title="Hub", debrief=DONE_A),
    )

    assert closed_jobs(HUB, stops) == (
        Job(title="A1", place="a1", debrief=DONE_A, job="Clear the warehouse by dawn."),
    )


def test_ledger_shows_the_job_line_only_under_an_open_job_with_terms() -> None:
    open_with_terms = Job(
        title="A1",
        place="a1",
        debrief=Debrief(text="Ran out of time.", finished=False),
        job="Clear the warehouse by dawn.",
    )
    finished_with_terms = Job(title="B1", place="b1", debrief=DONE_B, job="Escort the courier.")
    open_no_terms = Job(
        title="C1", place="c1", debrief=Debrief(text="Ran out of time.", finished=False)
    )

    assert "  the job: Clear the warehouse by dawn." in ledger((open_with_terms,))
    assert "  the job:" not in ledger((finished_with_terms,))
    assert "  the job:" not in ledger((open_no_terms,))
