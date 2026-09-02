import pytest

from aidm.engines.hub import (
    TAKE_JOB,
    Debrief,
    Job,
    Offer,
    Stop,
    board_rows,
    check_board,
    check_kind,
    closed_jobs,
    hub_sections,
    job_closed,
    job_start,
    job_titles,
    open_job,
)
from aidm.engines.scenes import Scene, SceneRun, check_hub

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


def test_the_job_walk_reads_titles_closed_jobs_open_job_and_start() -> None:
    stops = _stops()

    assert job_titles(HUB, stops) == ("", "A1", "A1", "", "B1", "", "C1")
    assert closed_jobs(HUB, stops) == (
        Job(title="A1", place="a1", debrief=DONE_A),
        Job(title="B1", place="b1", debrief=DONE_B),
    )
    assert open_job(HUB, stops) == "C1"
    assert job_start(HUB, stops) == 5


def test_the_job_walk_on_tunnel_goons_stops() -> None:
    stops = _tunnel_goons_stops()

    assert closed_jobs("tavern", stops) == (Job(title="A", place="a", debrief=DONE_TAVERN),)
    assert open_job("tavern", stops) is None
    assert job_start("tavern", stops) == 4


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
    assert fact.trace == "the job A1 closed (done): Finished the job."


def test_job_closed_names_a_job_left_open() -> None:
    job = Job(title="A1", place="a1", debrief=Debrief(text="Ran out of time.", finished=False))

    fact = job_closed(job)

    assert fact.card == "Job left open: A1\nRan out of time."
    assert fact.trace == "the job A1 closed (left open): Ran out of time."


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
    taking = dict(hub_sections("The Amber Tap", HUB, (), (), moment="taking"))
    away = dict(hub_sections("The Amber Tap", HUB, (), (), moment="away"))
    returning = dict(hub_sections("The Amber Tap", HUB, (), (), moment="returning"))

    assert taking["THE HUB"].startswith("The player is leaving The Amber Tap")
    assert away["THE HUB"].startswith("The hub is The Amber Tap")
    assert returning["THE HUB"].startswith("Write the hub scene there.")
