from functools import partial

import pytest

from aidm.core.views import Panel
from aidm.engines.hub import (
    TAKE_JOB,
    Job,
    Offer,
    board_panel,
    board_rows,
    check_board,
    check_jobs,
    check_kind,
    hub_sections,
    job_closed,
    jobs_panel,
    ledger,
    master_tail,
    place_unmet,
    question_heading,
)

HUB = "hub"
DONE_A = Job(title="A1", place="a1", started=1, finished=True, debrief="Finished A")
DONE_B = Job(title="B1", place="b1", started=3, finished=True, debrief="Finished B")


def test_check_board_refuses_a_board_with_the_wrong_shape() -> None:
    offer = Offer(title="A job", pitch="Do the thing")

    with pytest.raises(ValueError):
        check_board(None, (offer,))


def test_check_kind_refuses_a_kind_and_hub_mismatch() -> None:
    with pytest.raises(ValueError):
        check_kind("campaign", None)
    with pytest.raises(ValueError):
        check_kind("one-shot", "bar")

    check_kind("campaign", "bar")
    check_kind("one-shot", None)


def test_check_jobs_refuses_a_job_with_no_hub() -> None:
    with pytest.raises(ValueError, match="job with no hub"):
        check_jobs(None, [Job(title="A1", place="a1")], 1)


def test_check_jobs_refuses_an_earlier_job_without_a_debrief() -> None:
    with pytest.raises(ValueError, match="has no debrief and is not the last"):
        check_jobs(
            HUB,
            [
                Job(title="A1", place="a1", started=1, finished=True),
                Job(title="B1", place="b1", started=3),
            ],
            4,
        )


def test_check_jobs_refuses_a_debrief_on_an_unwalked_job() -> None:
    with pytest.raises(ValueError, match="before it was walked"):
        check_jobs(HUB, [Job(title="A1", place="a1", finished=True, debrief="Done.")], 1)


def test_check_jobs_refuses_a_job_started_past_the_walk() -> None:
    with pytest.raises(ValueError, match="started past the walk"):
        check_jobs(HUB, [Job(title="A1", place="a1", started=2)], 2)


def test_job_closed_names_a_finished_job() -> None:
    job = Job(title="A1", place="a1", started=1, finished=True, debrief="Finished the job.")

    fact = job_closed(job)

    assert fact.card == "Job done: A1\nFinished the job."
    assert fact.trace == "the job A1 closed (done)"


def test_job_closed_names_a_job_left_open() -> None:
    job = Job(title="A1", place="a1", started=1, debrief="Ran out of time.")

    fact = job_closed(job)

    assert fact.card == "Job left open: A1\nRan out of time."
    assert fact.trace == "the job A1 closed (left open)"


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
    jobs = (DONE_A,)
    board = (Offer(title="B", pitch="Do b"),)
    open_job = Job(title="A2", place="a2", terms="Clear the warehouse", started=1)

    away = dict(master_tail(HUB, False, board, jobs, open_job))
    assert away["THE JOB"] == "Clear the warehouse"
    assert "A1" in away["JOBS SO FAR"]
    assert "THE BOARD" not in away

    at_hub = dict(master_tail(HUB, True, board, jobs, None))
    assert "THE JOB" not in at_hub
    assert "B" in at_hub["THE BOARD"]

    one_shot = dict(master_tail(None, False, (), (), None))
    assert one_shot == {}


def test_board_panel_is_shown_only_at_the_hub() -> None:
    offer = Offer(title="A", pitch="Do a")

    assert board_panel(True, (offer,)) == (Panel(title="Board", rows=board_rows((offer,))),)
    assert board_panel(False, (offer,)) == ()


def test_jobs_panel_is_shown_only_when_there_is_a_job() -> None:
    assert jobs_panel(()) == ()

    (panel,) = jobs_panel((DONE_A,))
    assert panel.title == "Jobs"
    assert len(panel.rows) == 1


def test_ledger_shows_the_job_line_only_under_an_open_job_with_terms() -> None:
    open_with_terms = Job(
        title="A1",
        place="a1",
        started=1,
        debrief="Ran out of time.",
        terms="Clear the warehouse by dawn.",
    )
    finished_with_terms = Job(
        title="B1",
        place="b1",
        started=1,
        finished=True,
        debrief="Finished B",
        terms="Escort the courier.",
    )
    open_no_terms = Job(title="C1", place="c1", started=1, debrief="Ran out of time.")

    assert "  the job: Clear the warehouse by dawn." in ledger((open_with_terms,))
    assert "  the job:" not in ledger((finished_with_terms,))
    assert "  the job:" not in ledger((open_no_terms,))
