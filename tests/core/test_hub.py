import pytest

from aidm.core.entities import Refusal
from aidm.core.views import Panel
from aidm.engines.hub import (
    TAKE_JOB,
    Campaign,
    Job,
    Offer,
    check_kind,
    place_unmet,
    question_heading,
)

HUB = "hub"
BOARD = (Offer(title="B", pitch="Do b"), Offer(title="C", pitch="Do c"))
DONE_A = Job(title="A1", place="a1", started=1, finished=True, debrief="Finished A")


def _campaign(*jobs: Job) -> Campaign:
    return Campaign(place=HUB, board=BOARD, jobs=list(jobs))


def test_a_board_of_one_offer_is_refused() -> None:
    with pytest.raises(ValueError, match="board"):
        _ = Campaign(place=HUB, board=BOARD[:1])


def test_check_kind_refuses_a_kind_and_campaign_mismatch() -> None:
    with pytest.raises(Refusal):
        check_kind("campaign", None)
    with pytest.raises(Refusal):
        check_kind("one-shot", _campaign())

    check_kind("campaign", _campaign())
    check_kind("one-shot", None)


def test_an_earlier_job_without_a_debrief_is_refused() -> None:
    with pytest.raises(ValueError, match="has no debrief and is not the last"):
        _ = _campaign(
            Job(title="A1", place="a1", started=1, finished=True),
            Job(title="B1", place="b1", started=3),
        )


def test_a_debrief_on_an_unwalked_job_is_refused() -> None:
    with pytest.raises(ValueError, match="before it was walked"):
        _ = _campaign(Job(title="A1", place="a1", finished=True, debrief="Done."))


def test_check_walked_refuses_a_job_started_past_the_walk() -> None:
    with pytest.raises(Refusal, match="started past the walk"):
        _campaign(Job(title="A1", place="a1", started=2)).check_walked(2)


def test_job_closed_names_a_finished_job() -> None:
    fact = Job(
        title="A1", place="a1", started=1, finished=True, debrief="Finished the job."
    ).closed()

    assert fact.card == "Job done: A1\nFinished the job."
    assert fact.trace == "the job A1 closed (done)"


def test_job_closed_names_a_job_left_open() -> None:
    fact = Job(title="A1", place="a1", started=1, debrief="Ran out of time.").closed()

    assert fact.card == "Job left open: A1\nRan out of time."
    assert fact.trace == "the job A1 closed (left open)"


def test_board_rows_plays_take_job_with_the_title_and_keeps_the_pitch() -> None:
    offer = Offer(title="Deck 9 Crate Run", pitch="Crates off Deck 9, no manifest, half up front.")

    row, _ = Campaign(place=HUB, board=(offer, BOARD[0])).board_rows()

    assert row.label == "Deck 9 Crate Run"
    assert row.detail == "Crates off Deck 9, no manifest, half up front."
    assert row.intent == TAKE_JOB.format(title="Deck 9 Crate Run")


def test_sections_picks_the_brief_by_moment() -> None:
    campaign = _campaign()
    taking = dict(campaign.sections("The Amber Tap", at_hub=True, returning=False))
    away = dict(campaign.sections("The Amber Tap", at_hub=False, returning=False))
    returning = dict(campaign.sections("The Amber Tap", at_hub=False, returning=True))

    assert taking["THE HUB"].startswith("The player is leaving The Amber Tap")
    assert away["THE HUB"].startswith("The hub is The Amber Tap")
    assert returning["THE HUB"].startswith("Write the hub scene there.")
    assert "THE VERDICT" not in taking
    assert "THE VERDICT" not in away


def test_sections_returning_adds_the_verdict_by_the_open_jobs_finished() -> None:
    campaign = _campaign(Job(title="B1", place="b1", started=1))
    assert (
        dict(campaign.sections("Tap", at_hub=False, returning=True))["THE VERDICT"] == "left open"
    )

    campaign.jobs[-1].finished = True
    assert dict(campaign.sections("Tap", at_hub=False, returning=True))["THE VERDICT"] == "finished"


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


def test_tail_shows_the_job_away_and_the_board_at_the_hub() -> None:
    open_job = Job(title="A2", place="a2", terms="Clear the warehouse", started=3)

    away = dict(_campaign(DONE_A, open_job).tail(at_hub=False))
    assert away["THE JOB"] == "Clear the warehouse"
    assert "A1" in away["JOBS SO FAR"]
    assert "THE BOARD" not in away

    at_hub = dict(_campaign(DONE_A).tail(at_hub=True))
    assert "THE JOB" not in at_hub
    assert "B" in at_hub["THE BOARD"]


def test_board_panel_is_shown_only_at_the_hub() -> None:
    campaign = _campaign()

    assert campaign.board_panel(at_hub=True) == (Panel(title="Board", rows=campaign.board_rows()),)
    assert campaign.board_panel(at_hub=False) == ()


def test_jobs_panel_is_shown_only_when_a_job_is_closed() -> None:
    assert _campaign(Job(title="A1", place="a1", started=1)).jobs_panel() == ()

    (panel,) = _campaign(DONE_A).jobs_panel()
    assert panel.title == "Jobs"
    assert len(panel.rows) == 1


def test_since_start_reads_the_open_jobs_walk_or_the_hubs_last() -> None:
    walked = ["hub", "a1", "a2", "hub"]

    assert _campaign(DONE_A, Job(title="B1", place="b1", started=2)).since_start(walked) == [
        "a2",
        "hub",
    ]
    assert _campaign(DONE_A).since_start(walked) == ["hub"]


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

    assert "  the job: Clear the warehouse by dawn." in _campaign(open_with_terms).ledger()
    assert "  the job:" not in _campaign(finished_with_terms).ledger()
    assert "  the job:" not in _campaign(open_no_terms).ledger()
