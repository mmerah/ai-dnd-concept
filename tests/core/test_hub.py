import pytest

from aidm.core.entities import EntityId, Refusal
from aidm.core.play import ChapterRecord, SceneRecord
from aidm.core.views import Panel
from aidm.engines.base import Thing
from aidm.engines.hub import (
    TAKE_JOB,
    Attempt,
    Campaign,
    Job,
    Offer,
    check_kind,
    named_unmet,
    place_unmet,
    question_heading,
)

HUB = "hub"
BOARD = (Offer(title="B", pitch="Do b"), Offer(title="C", pitch="Do c"))
DONE_A = Job(
    title="A1",
    place="a1",
    finished=True,
    debrief="Finished A",
    attempts=[Attempt(started=1, returned=2)],
)


def _campaign(*jobs: Job) -> Campaign:
    return Campaign(place=HUB, board=BOARD, jobs=list(jobs))


def _record(title: str) -> SceneRecord:
    return SceneRecord(title=title, question="What happens next?")


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


def test_an_open_job_that_is_not_the_last_is_refused() -> None:
    with pytest.raises(ValueError, match="is open and is not the last"):
        _ = _campaign(
            Job(title="A1", place="a1", attempts=[Attempt(started=1)]),
            Job(title="B1", place="b1", attempts=[Attempt(started=3)]),
        )


def test_a_debrief_on_an_unwalked_job_is_refused() -> None:
    with pytest.raises(ValueError, match="before it was walked"):
        _ = _campaign(
            Job(title="A1", place="a1", finished=True, debrief="Done.", attempts=[Attempt()])
        )


def test_an_attempt_other_than_the_last_without_returned_is_refused() -> None:
    with pytest.raises(ValueError, match="other than the last"):
        _ = _campaign(
            Job(
                title="A1",
                place="a1",
                attempts=[Attempt(started=1), Attempt(started=3, returned=4)],
            )
        )


def test_an_attempt_returned_without_started_is_refused() -> None:
    with pytest.raises(ValueError, match="returned after it started"):
        _ = Attempt(returned=2)


def test_walk_on_a_walked_attempt_is_refused() -> None:
    job = Job(title="A1", place="a1", attempts=[Attempt(started=1)])
    with pytest.raises(Refusal, match="not waiting to be walked"):
        job.walk(5)


def test_check_spans_refuses_a_started_at_the_hub() -> None:
    campaign = _campaign(Job(title="A1", place="a1", attempts=[Attempt(started=0)]))
    with pytest.raises(Refusal, match="started at the hub"):
        campaign.check_spans([HUB, "a1"])


def test_check_spans_refuses_a_returned_away_from_the_hub() -> None:
    campaign = _campaign(Job(title="A1", place="a1", attempts=[Attempt(started=0, returned=1)]))
    with pytest.raises(Refusal, match="returned away from the hub"):
        campaign.check_spans(["a1", "a1"])


def test_job_closed_names_a_finished_job() -> None:
    fact = DONE_A.closed()

    assert fact.card == "Job done: A1\nFinished A"
    assert fact.trace == "the job A1 closed (done)"


def test_job_closed_names_a_job_left_open() -> None:
    job = Job(
        title="A1",
        place="a1",
        debrief="Ran out of time.",
        attempts=[Attempt(started=1, returned=2)],
    )
    fact = job.closed()

    assert fact.card == "Job left open: A1\nRan out of time."
    assert fact.trace == "the job A1 closed (left open)"


def test_board_rows_plays_take_job_with_the_title_and_keeps_the_pitch() -> None:
    offer = Offer(title="Deck 9 Crate Run", pitch="Crates off Deck 9, no manifest, half up front.")

    row, _ = Campaign(place=HUB, board=(offer, BOARD[0])).board_rows()

    assert row.label == "Deck 9 Crate Run"
    assert row.detail == "Crates off Deck 9, no manifest, half up front."
    assert row.intent == TAKE_JOB.format(title="Deck 9 Crate Run")


def test_the_board_marks_a_left_open_offer() -> None:
    offer = Offer(title="B", pitch="Do b")
    left_open_job = Job(title="B", place="b1", attempts=[Attempt(started=1, returned=2)])
    campaign = _campaign(left_open_job)

    row = next(row for row in campaign.board_rows() if row.label.startswith("B"))
    assert row.label == "B" + " (left open)"
    assert row.detail == offer.pitch
    assert row.intent == TAKE_JOB.format(title="B")
    assert "B (left open): Do b" in campaign.board_lines()


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
    campaign = _campaign(Job(title="B1", place="b1", attempts=[Attempt(started=1)]))
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


def test_named_unmet_finds_multi_word_names_case_folded_and_bare_ids() -> None:
    text = "The Bell Tower looms over the square; a bell rings, and old-tom watches."
    entities = [
        Thing(id=EntityId("bell-tower"), name="Bell Tower", brief=""),
        Thing(id=EntityId("the-bell"), name="Bell", brief=""),
        Thing(id=EntityId("town-square"), name="town square", brief=""),
        Thing(id=EntityId("old-tom"), name="Tom", brief=""),
    ]
    assert named_unmet(text, entities) == ["Bell Tower", "Tom"]


def test_tail_shows_the_job_away_and_the_board_at_the_hub() -> None:
    open_job = Job(
        title="A2", place="a2", terms="Clear the warehouse", attempts=[Attempt(started=3)]
    )

    away = dict(_campaign(DONE_A, open_job).tail(at_hub=False))
    assert away["THE JOB"] == "Clear the warehouse"
    assert "A1" in away["JOBS SO FAR"]
    assert "THE BOARD" not in away

    at_hub = dict(_campaign(DONE_A).tail(at_hub=True))
    assert "THE JOB" not in at_hub
    assert "B" in at_hub["THE BOARD"]


def test_job_row_adds_so_far_from_the_reopened_jobs_summary() -> None:
    open_job = Job(
        title="A2",
        place="a2",
        terms="Clear the warehouse",
        summary="Found the ledger, lost the guard.",
        attempts=[Attempt(started=3)],
    )

    row = dict(_campaign(open_job).job_row())["THE JOB"]

    assert row == "Clear the warehouse\nso far: Found the ledger, lost the guard."


def test_board_panel_is_shown_only_at_the_hub() -> None:
    campaign = _campaign()

    assert campaign.board_panel(at_hub=True) == (Panel(title="Board", rows=campaign.board_rows()),)
    assert campaign.board_panel(at_hub=False) == ()


def test_jobs_panel_is_shown_only_when_a_job_is_closed() -> None:
    assert _campaign(Job(title="A1", place="a1", attempts=[Attempt(started=1)])).jobs_panel() == ()

    (panel,) = _campaign(DONE_A).jobs_panel()
    assert panel.title == "Jobs"
    assert len(panel.rows) == 1


def test_since_start_reads_the_walking_attempts_start_or_the_hubs_last() -> None:
    walked = ["hub", "a1", "a2", "hub"]

    assert _campaign(
        DONE_A, Job(title="B1", place="b1", attempts=[Attempt(started=2)])
    ).since_start(walked) == ["a2", "hub"]
    assert _campaign(DONE_A).since_start(walked) == ["hub"]


def test_ledger_shows_the_job_line_only_under_an_open_job_with_terms() -> None:
    open_with_terms = Job(
        title="A1",
        place="a1",
        debrief="Ran out of time.",
        terms="Clear the warehouse by dawn.",
        attempts=[Attempt(started=1, returned=2)],
    )
    finished_with_terms = Job(
        title="B1",
        place="b1",
        finished=True,
        debrief="Finished B",
        terms="Escort the courier.",
        attempts=[Attempt(started=1, returned=2)],
    )
    open_no_terms = Job(
        title="C1",
        place="c1",
        debrief="Ran out of time.",
        attempts=[Attempt(started=1, returned=2)],
    )

    assert "  the job: Clear the warehouse by dawn." in _campaign(open_with_terms).ledger()
    assert "  the job:" not in _campaign(finished_with_terms).ledger()
    assert "  the job:" not in _campaign(open_no_terms).ledger()


def test_the_ledger_prints_the_summary() -> None:
    job = Job(
        title="A1",
        place="a1",
        summary="She got the crates out, but the fixer wants a cut now.",
        attempts=[Attempt(started=1, returned=2)],
    )

    assert "She got the crates out, but the fixer wants a cut now." in _campaign(job).ledger()


def test_returns_counts_returned_attempts_across_all_jobs() -> None:
    campaign = _campaign(
        Job(
            title="A1",
            place="a1",
            attempts=[Attempt(started=0, returned=1), Attempt(started=2, returned=3)],
        ),
        Job(title="B1", place="b1", attempts=[Attempt(started=4)]),
    )

    assert campaign.returns() == 2


def test_records_of_spans_two_attempts_and_keeps_a_mid_job_hub_visit() -> None:
    records = [
        _record("Depart"),
        _record("Tavern"),  # a mid-job hub visit, inside the first attempt's span
        _record("Push On"),
        _record("Report In"),  # the return itself; outside both spans
        _record("Deeper"),
        _record("Clear"),
    ]
    job = Job(
        title="A1",
        place="a1",
        attempts=[Attempt(started=0, returned=3), Attempt(started=4)],
    )
    campaign = _campaign(job)

    assert campaign.records_of(job, records) == (
        records[0],
        records[1],
        records[2],
        records[4],
        records[5],
    )
    assert campaign.job_records(records) == campaign.records_of(job, records)


def test_history_collapses_a_returned_attempt_before_the_last_two_only() -> None:
    records = [_record(f"R{i}") for i in range(5)]
    collapsing = Job(
        title="Job A",
        place="a1",
        finished=True,
        attempts=[Attempt(started=0, returned=2)],
    )
    standing = Job(
        title="Job B",
        place="b1",
        attempts=[Attempt(started=2, returned=4)],
    )
    campaign = _campaign(collapsing, standing)

    history = campaign.history(records)

    assert history[0] == ChapterRecord(
        title="Job A", verdict="done", summary="", scenes=("R0", "R1")
    )
    assert history[1:] == (records[2], records[3], records[4])


def test_history_emits_two_chapters_for_a_job_returned_twice() -> None:
    records = [_record(f"R{i}") for i in range(6)]
    job = Job(
        title="Job A",
        place="a1",
        finished=True,
        summary="Two trips out.",
        attempts=[Attempt(started=0, returned=2), Attempt(started=2, returned=4)],
    )
    campaign = _campaign(job)

    history = campaign.history(records)

    assert history == (
        ChapterRecord(
            title="Job A", verdict="left open", summary="Two trips out.", scenes=("R0", "R1")
        ),
        ChapterRecord(title="Job A", verdict="done", summary="Two trips out.", scenes=("R2", "R3")),
        records[4],
        records[5],
    )


def test_taken_finds_a_left_open_job_by_its_take_job_line_not_free_text() -> None:
    job = Job(title="Bandits", place="a1", attempts=[Attempt(started=1, returned=2)])
    campaign = _campaign(job)

    assert campaign.taken(TAKE_JOB.format(title="Bandits")) == job
    assert campaign.taken("Bandits") is None


def test_left_open_and_reopen_move_the_job_last_and_keep_its_summary_and_debrief() -> None:
    other = Job(title="Other", place="a1", attempts=[Attempt(started=1, returned=2)])
    bandits = Job(
        title="Bandits",
        place="a1",
        summary="Cornered them once already.",
        debrief="They scattered.",
        attempts=[Attempt(started=3, returned=4)],
    )
    campaign = _campaign(bandits, other)

    found = campaign.left_open("bandits")
    assert found is not None
    assert found == bandits

    campaign.reopen(found, started=None)

    assert campaign.jobs[-1] is found
    assert campaign.jobs[0].title == "Other"
    assert found.open
    assert found.attempts[-1].started is None
    assert found.finished is False
    assert found.summary == "Cornered them once already."
    assert found.debrief == "They scattered."


def test_swap_out_drops_a_fresh_job_and_the_attempt_of_a_reopened_one() -> None:
    campaign = _campaign(Job(title="Fresh", place="a1", attempts=[Attempt()]))
    campaign.swap_out()
    assert campaign.jobs == []

    campaign = _campaign(
        Job(title="Bandits", place="a1", attempts=[Attempt(started=1, returned=2), Attempt()])
    )
    campaign.swap_out()
    assert len(campaign.jobs) == 1
    assert len(campaign.jobs[0].attempts) == 1
    assert campaign.jobs[0].attempts[-1].returned == 2
