from collections.abc import Sequence

import pytest

from aidm.core.entities import EntityId, Refusal
from aidm.core.play import ChapterRecord, Exchange, SceneRecord
from aidm.core.views import PanelRow
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.hub import HOME_ROW, HUB_ROW, Campaign, Job, Offer
from aidm.engines.scenes.drafts import JobDraft, NextDraft, ReturnDraft
from aidm.engines.scenes.world import SceneCanon, SceneRun, SceneWorld
from aidm.engines.scenes.worldsmith import scene_refusal

HUB = "hub"
PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = EntityId("mara")
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
ARC = "A few lines on what waits farther in, long enough to satisfy the model's own minimum."
DONE = "Finished the job."
JOB = "Count the crates and haul them clear before the shift change; she pays on drop, in full."
SUMMARY = (
    "A paragraph on the whole job, in the third person, long enough to satisfy the model's own "
    "minimum length for a summary written for the game master alone."
)
BOARD = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))


def _campaign(*jobs: Job) -> Campaign:
    return Campaign(place=HUB, board=BOARD, jobs=list(jobs))


def _world(*runs: SceneRun, **fields: object) -> SceneWorld[Person, Person]:
    return SceneWorld[Person, Person].model_validate(
        {"player": PLAYER, "runs": list(runs), **fields}
    )


def _run(
    place: str,
    title: str,
    *,
    job: str = "",
    played: bool = False,
    here: Sequence[EntityId] = (),
) -> SceneRun:
    exchanges = [Exchange(prompt=title, lines=())] if played else []
    return SceneRun(
        place=place,
        title=title,
        question="What happens next here?",
        situation=SITUATION,
        here=list(here),
        exchanges=exchanges,
        job=job,
    )


def test_the_job_walk_reads_job_runs_jobs_and_exchange_headings() -> None:
    world = _world(
        _run(HUB, "Hub", played=True),
        _run("a1", "A1", job="A1", played=True),
        _run("a1", "A2", job="A1", played=True),
        _run(HUB, "Hub", played=True),
        _run("b1", "B1", job="B1", played=True),
        campaign=_campaign(
            Job(title="A1", place="a1", finished=True, debrief=DONE),
            Job(title="B1", place="b1", open=True),
        ),
    )

    assert world.job_runs() == world.runs[4:]
    assert [exchange.prompt for exchange in world.exchanges()] == ["Hub", "A1", "A2", "Hub", "B1"]


def test_a_finished_verdict_reads_the_open_job_not_a_closed_one() -> None:
    campaign = _campaign(
        Job(title="A1", place="a1", finished=True, debrief=DONE),
        Job(title="B1", place="b1", open=True),
    )
    assert campaign.finished is False  # the finished job above is already closed

    campaign.jobs[-1].finished = True
    assert campaign.finished is True


def test_a_world_opening_away_from_the_hub_is_refused() -> None:
    with pytest.raises(ValueError, match="does not open at hub"):
        _ = _world(_run("a1", "A1"), campaign=_campaign())


def test_a_hub_run_that_takes_the_job_is_refused_a_mid_job_visit_is_not() -> None:
    with pytest.raises(ValueError, match="run 2 takes 'A1' at the hub"):
        _ = _world(
            _run(HUB, "Hub"),
            _run("a1", "A1"),
            _run(HUB, "Hub", job="A1"),
            campaign=_campaign(Job(title="A1", place="a1", open=True)),
        )

    world = _world(
        _run(HUB, "Hub"),
        _run("a1", "A1", job="A1"),
        _run(HUB, "Hub", job="A1"),
        campaign=_campaign(Job(title="A1", place="a1", open=True)),
    )
    assert world.job_runs() == world.runs[1:]


def test_a_canon_with_jobs_walked_or_opening_away_from_the_hub_is_refused() -> None:
    with pytest.raises(ValueError, match="jobs walked"):
        _ = SceneCanon[Person](
            opening=_run(HUB, "Hub"),
            campaign=_campaign(Job(title="A1", place="a1", open=True)),
        )
    with pytest.raises(ValueError, match="not at hub"):
        _ = SceneCanon[Person](opening=_run("a1", "A1"), campaign=_campaign())


def test_a_canon_opening_with_play_in_it_is_refused() -> None:
    opening = _run("a1", "A1", played=True)
    with pytest.raises(ValueError, match="an opening with play in it"):
        _ = SceneCanon[Person](opening=opening)


def test_settle_refuses_a_job_done_where_no_job_is_open() -> None:
    at_hub = _world(_run(HUB, "Hub"), campaign=_campaign())
    with pytest.raises(Refusal, match="no job is open here"):
        _ = at_hub.settle(True, "")

    one_shot = _world(_run("a1", "A1"))
    with pytest.raises(Refusal, match="no job is open here"):
        _ = one_shot.settle(True, "")


def test_scene_rows_shows_the_hub_row_and_the_way_on_and_home_rows_when_settled() -> None:
    at_hub = _world(_run(HUB, "Hub"), campaign=_campaign())
    assert at_hub.scene_rows()[-1] == HUB_ROW

    campaign = _world(_run(HUB, "Hub"), _run("a1", "A1"), campaign=_campaign())
    campaign.run.left = ""
    settled = campaign.scene_rows()
    assert any(row.label == "Way on" for row in settled)
    assert settled[-1] == HOME_ROW

    one_shot = _world(_run("a1", "A1"))
    one_shot.run.left = ""
    assert HOME_ROW not in one_shot.scene_rows()

    pursuing = _world(_run("a1", "A1"))
    pursuing.run.left = "the maintenance grate"
    pursued = pursuing.scene_rows()
    assert any(
        row
        == PanelRow(label="Go on", detail="the maintenance grate", intent="the maintenance grate")
        for row in pursued
    )
    assert not any(row.label == "Way on" for row in pursued)


def test_scene_rows_lists_the_open_job_under_the_question() -> None:
    world = _world(
        _run(HUB, "Hub"),
        _run("a1", "A1", job="A1"),
        campaign=_campaign(Job(title="A1", place="a1", terms=JOB, open=True)),
    )

    assert world.scene_rows()[1] == PanelRow(label="The job", detail=JOB)


def _travelling() -> SceneWorld[Person, Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    return _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara}, party=[MARA])


def test_a_party_member_leaves_the_scene_only_through_leave_party() -> None:
    world = _travelling()
    with pytest.raises(Refusal, match="leaves through `leave_party`"):
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
        _ = _world(*world.runs, cast=world.cast, party=[MARA])


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
        arc=ARC,
    )

    world.apply_scene(draft)

    assert world.runs[0].recap == RECAP
    assert world.runs[-1].recap == ""
    assert world.arc == ARC


def test_scenes_chapters_a_closed_job_and_keeps_the_open_ones_scene_by_scene() -> None:
    job_a = Job(title="A1", place="a1", finished=True, debrief=DONE, summary="Job one is done.")
    job_b = Job(title="B1", place="b1")
    world = _world(
        _run(HUB, "Hub", played=True),
        _run("a1", "A1", job="A1", played=True),
        _run("a1", "A2", job="A1", played=True),
        _run(HUB, "Hub", played=True),
        _run("b1", "B1", job="B1", played=True),
        _run(HUB, "Hub", played=True),
        campaign=_campaign(job_a, job_b),
    )

    scenes = world.scenes()

    assert isinstance(scenes[1], ChapterRecord)
    assert (scenes[1].title, scenes[1].scenes) == ("A1", ("A1", "A2"))
    assert [record.title for record in (scenes[0], *scenes[2:])] == ["Hub", "Hub", "B1", "Hub"]
    assert all(isinstance(record, SceneRecord) for record in (scenes[0], *scenes[2:]))


def test_apply_scene_with_reopening_reopens_the_job_instead_of_appending() -> None:
    job = Job(title="B1", place="b1", debrief=DONE)
    world = _world(
        _run(HUB, "Hub", played=True),
        _run("b1", "B1", job="B1", played=True),
        _run(HUB, "Hub"),
        campaign=_campaign(job),
    )
    draft = JobDraft[Person](
        place="b1",
        title="B1",
        question="What happens next here?",
        situation=SITUATION,
        recap=RECAP,
        arc=ARC,
        job=JOB,
    )

    world.apply_scene(draft, reopening=job)

    campaign = world.campaign
    assert campaign is not None
    assert [j.title for j in campaign.jobs] == ["B1"]  # not appended a second time
    assert campaign.jobs[-1] is job
    assert job.open
    assert job.finished is False
    assert job.terms == JOB
    assert world.runs[-1].job == "B1"


def test_apply_scene_with_a_return_draft_closes_the_job_and_stores_summary_and_recap() -> None:
    world = _world(
        _run(HUB, "Hub", played=True),
        _run("b1", "B1", job="B1", played=True),
        campaign=_campaign(Job(title="B1", place="b1", open=True)),
    )
    draft = ReturnDraft[Person](
        place=HUB,
        title="Hub",
        question="What does she do next?",
        situation=SITUATION,
        offers=BOARD,
        debrief="She counts the take twice before she says a word.",
        recap=RECAP,
        summary=SUMMARY,
    )

    world.apply_scene(draft)

    campaign = world.campaign
    assert campaign is not None
    job = campaign.jobs[-1]
    assert (job.debrief, job.summary) == (draft.debrief, SUMMARY)
    assert job.open is False
    assert world.runs[-1].job == ""
    assert world.runs[1].recap == RECAP


def test_a_world_whose_job_returns_away_from_the_hub_is_refused() -> None:
    with pytest.raises(ValueError, match="run 2 returns from 'A1' away from the hub"):
        _ = _world(
            _run(HUB, "Hub"),
            _run("a1", "A1", job="A1"),
            _run("a1", "A2"),
            campaign=_campaign(Job(title="A1", place="a1")),
        )


def test_entering_someone_hidden_is_refused_reveal_makes_them_present() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=False)
    world = _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara})
    with pytest.raises(Refusal, match="already here"):
        _ = world.enter(MARA)
    _ = world.reveal_hidden(MARA)
    assert MARA in world.present()


def test_scene_refusal_refuses_a_job_title_taken_before_unless_it_is_the_reopening() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    world = _world(
        _run(HUB, "Hub", here=[MARA]),
        _run("b1", "B1", job="B1"),
        _run(HUB, "Hub", here=[MARA]),
        cast={MARA: mara},
        campaign=_campaign(Job(title="B1", place="b1", debrief=DONE)),
    )
    campaign = world.campaign
    assert campaign is not None
    job = campaign.left_open("B1")
    assert job is not None
    draft = JobDraft[Person](
        place="b1",
        title="b1",
        question="What happens next here?",
        situation=SITUATION,
        present=(MARA,),
        recap=RECAP,
        arc=ARC,
        job=JOB,
    )

    assert scene_refusal(draft, world) == (
        "the scene needs a title no job on JOBS SO FAR carries: 'B1' was taken before"
    )
    assert scene_refusal(draft, world, (), job) is None
