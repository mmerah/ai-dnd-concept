import pytest

from aidm.core.entities import EntityId
from aidm.core.play import Exchange
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import HOME_ROW, HUB_ROW, Debrief, Job, Offer
from aidm.engines.scenes import (
    SCENE_TURN_CAP,
    SPENT_NOTE,
    Scene,
    SceneRun,
    SceneWorld,
    check_hub,
    kill,
    leave,
    record_exchange,
    scene_rows,
)

HUB = "hub"
PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = EntityId("mara")
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
DONE = Debrief(text="Finished the job.", finished=True)
BOARD = (Offer(title="A", pitch="Do a"), Offer(title="B", pitch="Do b"))


def _run(place: str, title: str, *, debrief: Debrief | None = None, told: bool = False) -> SceneRun:
    scene = Scene(
        place=place,
        title=title,
        question="What happens next here?",
        situation=SITUATION,
        debrief=debrief,
    )
    exchanges = [Exchange(prompt="p", lines=())] if told else []
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
    assert [exchange.where for exchange in world.exchanges()] == [
        "Hub",
        "A1",
        "A1 — A2",
        "Hub",
        "B1",
    ]


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


def test_record_exchange_files_the_turn_and_stays_silent_at_the_hub_and_when_settled() -> None:
    at_hub = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub", told=True)], hub=HUB, board=BOARD
    )
    at_hub.run.spent = "the door is barred"
    assert record_exchange(at_hub, "p", (), (), "", someone_dead=False) == ()
    assert [one.prompt for one in at_hub.run.exchanges] == ["p", "p"]

    settled = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1", told=True)])
    settled.run.spent = "the door is barred"
    settled.run.settled = True
    assert record_exchange(settled, "p", (), (), "", someone_dead=False) == ()

    opening = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
    opening.run.spent = "the door is barred"
    assert record_exchange(opening, "p", (), (), "", someone_dead=False) == ()


def test_record_exchange_names_the_run_the_dead_or_the_turn_cap_as_the_spent_reason() -> None:
    def note(*, spent: str = "", someone_dead: bool = False, turns: int = 1) -> tuple[str, ...]:
        world = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
        world.run.exchanges = [Exchange(prompt="p", lines=()) for _ in range(turns)]
        world.run.spent = spent
        return record_exchange(world, "p", (), (), "", someone_dead=someone_dead)

    assert note(spent="the door is barred") == (SPENT_NOTE.format(reason="the door is barred"),)
    assert note(someone_dead=True) == (SPENT_NOTE.format(reason="someone here is dead"),)
    assert note(turns=SCENE_TURN_CAP - 1) == (
        SPENT_NOTE.format(reason=f"{SCENE_TURN_CAP} turns have passed here"),
    )
    assert note() == ()


def test_scene_rows_shows_the_hub_row_and_the_way_on_and_home_rows_when_settled() -> None:
    at_hub = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub")], hub=HUB, board=BOARD
    )
    assert scene_rows(at_hub)[-1] == HUB_ROW

    campaign = SceneWorld[Person, Person](
        player=PLAYER, runs=[_run(HUB, "Hub"), _run("a1", "A1")], hub=HUB, board=BOARD
    )
    campaign.run.settled = True
    settled = scene_rows(campaign)
    assert any(row.label == "Way on" for row in settled)
    assert settled[-1] == HOME_ROW

    one_shot = SceneWorld[Person, Person](player=PLAYER, runs=[_run("a1", "A1")])
    one_shot.run.settled = True
    assert HOME_ROW not in scene_rows(one_shot)


def _travelling() -> SceneWorld[Person, Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    run = _run("a1", "A1")
    run.present = [MARA]
    return SceneWorld[Person, Person](player=PLAYER, cast={MARA: mara}, runs=[run], party=[MARA])


def test_a_party_member_leaves_the_scene_only_through_leave_party() -> None:
    world = _travelling()
    with pytest.raises(ValueError, match="leaves through `leave_party`"):
        _ = leave(world, MARA)
    assert world.run.present == [MARA]


def test_killing_a_party_member_drops_them_from_the_party() -> None:
    world = _travelling()
    facts = kill(world, MARA)
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
