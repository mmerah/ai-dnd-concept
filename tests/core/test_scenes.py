import pytest

from aidm.core.entities import EntityId
from aidm.core.play import Exchange
from aidm.core.views import PanelRow
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import HOME_ROW, HUB_ROW, Debrief, Job, Offer
from aidm.engines.scenes.drafts import NextDraft
from aidm.engines.scenes.world import (
    Scene,
    SceneRun,
    SceneWorld,
    check_hub,
)

HUB = "hub"
PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = EntityId("mara")
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
DONE = Debrief(text="Finished the job.", finished=True)
JOB = "Count the crates and haul them clear before the shift change; she pays on drop."
BOARD = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))


def _run(place: str, title: str, *, debrief: Debrief | None = None, told: bool = False) -> SceneRun:
    scene = Scene(
        place=place,
        title=title,
        question="What happens next here?",
        situation=SITUATION,
        debrief=debrief,
    )
    exchanges = [Exchange(prompt=title, lines=())] if told else []
    return SceneRun(scene=scene, exchanges=exchanges)


def test_the_job_walk_reads_job_runs_jobs_and_exchange_headings() -> None:
    world = SceneWorld[Person, Person](
        player=PLAYER,
        runs=[
            _run(HUB, "Hub", told=True),
            _run("a1", "A1", told=True),
            _run("a1", "A2", told=True),
            _run(HUB, "Hub", debrief=DONE, told=True),
            _run("b1", "B1", told=True),
        ],
        hub=HUB,
        board=BOARD,
    )

    assert world.job_runs() == world.runs[3:]
    assert world.jobs() == (Job(title="A1", place="a1", debrief=DONE),)
    assert [exchange.prompt for exchange in world.exchanges()] == ["Hub", "A1", "A2", "Hub", "B1"]


def test_job_done_is_true_when_any_run_of_the_open_job_has_it() -> None:
    world = SceneWorld[Person, Person](
        player=PLAYER,
        runs=[
            _run(HUB, "Hub"),
            _run("a1", "A1"),
            _run(HUB, "Hub", debrief=DONE),
            _run("b1", "B1"),
        ],
        hub=HUB,
        board=BOARD,
    )
    world.runs[1].job_done = True  # belongs to the job the debrief above already closed
    assert world.job_done is False

    world.runs[-1].job_done = True
    assert world.job_done is True


def test_check_hub_on_the_base_refuses_a_debrief_away_from_the_hub() -> None:
    with pytest.raises(ValueError, match="away from the hub with a debrief"):
        check_hub(HUB, BOARD, [_run(HUB, "Hub"), _run("a1", "A1", debrief=DONE)])


def test_check_hub_refuses_a_job_done_where_no_job_is_open() -> None:
    at_hub = _run(HUB, "Hub")
    at_hub.job_done = True
    with pytest.raises(ValueError, match="run 0 has a job done with no job open"):
        check_hub(HUB, BOARD, [at_hub])

    one_shot = _run("a1", "A1")
    one_shot.job_done = True
    with pytest.raises(ValueError, match="run 0 has a job done with no job open"):
        check_hub(None, (), [one_shot])


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
    away = _run("a1", "A1")
    away.scene = away.scene.model_copy(update={"job": JOB})
    world = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub"), away], hub=HUB, board=BOARD
    )

    assert world.scene_rows()[1] == PanelRow(label="The job", detail=JOB)


def _travelling() -> SceneWorld[Person, Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    run = _run("a1", "A1")
    run.present = [MARA]
    return SceneWorld[Person, Person](player=PLAYER, cast={MARA: mara}, runs=[run], party=[MARA])


def test_a_party_member_leaves_the_scene_only_through_leave_party() -> None:
    world = _travelling()
    with pytest.raises(ValueError, match="leaves through `leave_party`"):
        _ = world.leave(MARA)
    assert world.run.present == [MARA]


def test_killing_a_party_member_drops_them_from_the_party() -> None:
    world = _travelling()
    facts = world.kill(MARA)
    assert world.party == []
    assert not world.cast[MARA].alive
    assert any(fact.card == "Mara is dead" for fact in facts)


def test_a_party_member_who_is_not_in_this_scene_is_refused() -> None:
    world = _travelling()
    world.run.present.remove(MARA)
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
