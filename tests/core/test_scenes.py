from collections.abc import Sequence

import pytest

from aidm.core.entities import EntityId
from aidm.core.play import Exchange
from aidm.core.views import PanelRow
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import HOME_ROW, HUB_ROW, Job, Offer
from aidm.engines.scenes.drafts import NextDraft
from aidm.engines.scenes.world import (
    SceneCanon,
    SceneRun,
    SceneWorld,
    check_hub,
)

HUB = "hub"
PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = EntityId("mara")
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
DONE = "Finished the job."
JOB = "Count the crates and haul them clear before the shift change; she pays on drop."
BOARD = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))


def _run(place: str, title: str, *, told: bool = False, here: Sequence[EntityId] = ()) -> SceneRun:
    exchanges = [Exchange(prompt=title, lines=())] if told else []
    return SceneRun(
        place=place,
        title=title,
        question="What happens next here?",
        situation=SITUATION,
        here=list(here),
        exchanges=exchanges,
    )


def test_the_job_walk_reads_job_runs_jobs_and_exchange_headings() -> None:
    world = SceneWorld[Person, Person](
        player=PLAYER,
        runs=[
            _run(HUB, "Hub", told=True),
            _run("a1", "A1", told=True),
            _run("a1", "A2", told=True),
            _run(HUB, "Hub", told=True),
            _run("b1", "B1", told=True),
        ],
        hub=HUB,
        board=BOARD,
        jobs=[
            Job(title="A1", place="a1", started=1, finished=True, debrief=DONE),
            Job(title="B1", place="b1", started=4),
        ],
    )

    assert world.job_runs() == world.runs[4:]
    assert world.closed_jobs() == (
        Job(title="A1", place="a1", started=1, finished=True, debrief=DONE),
    )
    assert [exchange.prompt for exchange in world.exchanges()] == ["Hub", "A1", "A2", "Hub", "B1"]


def test_job_done_reads_the_open_jobs_finished() -> None:
    world = SceneWorld[Person, Person](
        player=PLAYER,
        runs=[
            _run(HUB, "Hub"),
            _run("a1", "A1"),
            _run(HUB, "Hub"),
            _run("b1", "B1"),
        ],
        hub=HUB,
        board=BOARD,
        jobs=[
            Job(title="A1", place="a1", started=1, finished=True, debrief=DONE),
            Job(title="B1", place="b1", started=3),
        ],
    )
    assert world.job_done is False  # the finished job above is already closed

    world.jobs[-1].finished = True
    assert world.job_done is True


def test_check_hub_refuses_an_opening_away_from_the_hub() -> None:
    with pytest.raises(ValueError, match="does not open at hub"):
        check_hub(HUB, BOARD, [_run("a1", "A1")], [])


def test_check_hub_refuses_a_hub_run_no_closed_job_explains() -> None:
    with pytest.raises(ValueError, match="closed jobs disagree"):
        check_hub(
            HUB,
            BOARD,
            [_run(HUB, "Hub"), _run("a1", "A1"), _run(HUB, "Hub")],
            [Job(title="A1", place="a1", started=1)],
        )


def test_a_canon_opening_with_play_in_it_is_refused() -> None:
    played = _run("a1", "A1", told=True)
    with pytest.raises(ValueError, match="an opening with play in it"):
        _ = SceneCanon[Person](opening=played)


def test_a_stored_board_of_one_offer_is_refused() -> None:
    with pytest.raises(ValueError, match="board"):
        _ = SceneWorld[Person, Person](
            player=PLAYER, runs=[_run(HUB, "Hub")], hub=HUB, board=BOARD[:1]
        )


def test_settle_refuses_a_job_done_where_no_job_is_open() -> None:
    at_hub = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub")], hub=HUB, board=BOARD
    )
    with pytest.raises(ValueError, match="no job is open here"):
        _ = at_hub.settle(True, "")

    one_shot = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
    with pytest.raises(ValueError, match="no job is open here"):
        _ = one_shot.settle(True, "")


def test_scene_rows_shows_the_hub_row_and_the_way_on_and_home_rows_when_settled() -> None:
    at_hub = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub")], hub=HUB, board=BOARD
    )
    assert at_hub.scene_rows()[-1] == HUB_ROW

    campaign = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub"), _run("a1", "A1")], hub=HUB, board=BOARD
    )
    campaign.run.left = ""
    settled = campaign.scene_rows()
    assert any(row.label == "Way on" for row in settled)
    assert settled[-1] == HOME_ROW

    one_shot = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
    one_shot.run.left = ""
    assert HOME_ROW not in one_shot.scene_rows()

    pursuing = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
    pursuing.run.left = "the maintenance grate"
    pursued = pursuing.scene_rows()
    assert any(
        row
        == PanelRow(label="Go on", detail="the maintenance grate", intent="the maintenance grate")
        for row in pursued
    )
    assert not any(row.label == "Way on" for row in pursued)


def test_scene_rows_lists_the_open_job_under_the_question() -> None:
    world = SceneWorld[Person, Person](
        player=PLAYER,
        runs=[_run(HUB, "Hub"), _run("a1", "A1")],
        hub=HUB,
        board=BOARD,
        jobs=[Job(title="A1", place="a1", terms=JOB, started=1)],
    )

    assert world.scene_rows()[1] == PanelRow(label="The job", detail=JOB)


def _travelling() -> SceneWorld[Person, Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    run = _run("a1", "A1", here=[MARA])
    return SceneWorld[Person, Person](player=PLAYER, cast={MARA: mara}, runs=[run], party=[MARA])


def test_a_party_member_leaves_the_scene_only_through_leave_party() -> None:
    world = _travelling()
    with pytest.raises(ValueError, match="leaves through `leave_party`"):
        _ = world.leave(MARA)
    assert world.present() == [MARA]


def test_killing_a_party_member_drops_them_from_the_party() -> None:
    world = _travelling()
    facts = world.kill(MARA)
    assert world.party == []
    assert not world.cast[MARA].alive
    assert any(fact.card == "Mara is dead" for fact in facts)


def test_a_party_member_who_is_not_in_this_scene_is_refused() -> None:
    world = _travelling()
    world.run.here.remove(MARA)
    with pytest.raises(ValueError, match="the party is in every scene"):
        _ = SceneWorld[Person, Person](
            player=PLAYER, cast=world.cast, runs=world.runs, party=[MARA]
        )


def test_apply_scene_with_a_next_draft_stamps_the_recap_on_the_run_left() -> None:
    world = _travelling()
    world.party = []
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        question="What happens next here?",
        situation=SITUATION,
        present=(MARA,),
        recap=RECAP,
    )

    world.apply_scene(draft)

    assert world.runs[0].recap == RECAP
    assert world.runs[-1].recap == ""


def test_entering_someone_hidden_is_refused_reveal_makes_them_present() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=False)
    world = SceneWorld[Person, Person](
        player=PLAYER, cast={MARA: mara}, runs=[_run("a1", "A1", here=[MARA])]
    )
    with pytest.raises(ValueError, match="already here"):
        _ = world.enter(MARA)
    _ = world.reveal_hidden(MARA)
    assert MARA in world.present()
