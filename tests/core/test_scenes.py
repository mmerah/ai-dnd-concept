from collections.abc import Sequence
from random import Random

import pytest
from support.table import LONER3E, game, narrowed

from aidm.core.entities import EntityId, Refusal
from aidm.core.play import Exchange
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet
from aidm.engines.scenes.drafts import NextDraft
from aidm.engines.scenes.tools import NextScene
from aidm.engines.scenes.world import MOVE_ON, SceneCanon, SceneRun, SceneWorld
from aidm.engines.scenes.worldsmith import scene_refusal

PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = EntityId("mara")
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
ARC = "A few lines on what waits farther in, long enough to satisfy the model's own minimum."


def _world(*runs: SceneRun, **fields: object) -> SceneWorld[Person, Person]:
    return SceneWorld[Person, Person].model_validate(
        {"player": PLAYER, "runs": list(runs), **fields}
    )


def _run(
    place: str, title: str, *, played: bool = False, here: Sequence[EntityId] = ()
) -> SceneRun:
    exchanges = [Exchange(prompt=title, lines=())] if played else []
    return SceneRun(
        place=place,
        title=title,
        focus="What happens next here?",
        situation=SITUATION,
        here=list(here),
        exchanges=exchanges,
    )


def _travelling() -> SceneWorld[Person, Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    return _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara}, party=[MARA])


def test_a_canon_opening_with_play_in_it_is_refused() -> None:
    opening = _run("a1", "A1", played=True)
    with pytest.raises(ValueError, match="an opening with play in it"):
        _ = SceneCanon[Person](opening=opening)


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


def test_the_next_scene_prompt_carries_the_scene_as_it_stands() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    run = narrowed(state, Loner3eGame).payload.run

    prompt = engine.render_next(state, "Down the stair.")

    assert f"THE SCENE NOW:\n{run.title} [{run.place}]\n{run.situation}" in prompt
    assert "present: Mara[mara]\nhidden: the vault map[vault-map]" in prompt


def test_apply_scene_with_a_next_draft_stamps_the_recap_on_the_run_left() -> None:
    world = _travelling()
    world.party = []
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        present=(MARA,),
        recap=RECAP,
        arc=ARC,
    )

    world.apply_scene(draft)

    assert world.runs[0].recap == RECAP
    assert world.runs[-1].recap == ""
    assert world.arc == ARC


def test_apply_scene_with_an_empty_arc_keeps_the_worlds_arc() -> None:
    world = _travelling()
    world.arc = ARC
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        present=(MARA,),
        recap=RECAP,
    )

    world.apply_scene(draft)

    assert world.arc == ARC


def test_entering_someone_hidden_is_refused_reveal_makes_them_present() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=False)
    world = _world(_run("a1", "A1", here=[MARA]), cast={MARA: mara})
    with pytest.raises(Refusal, match="already here"):
        _ = world.enter(MARA)
    _ = world.reveal_hidden(MARA)
    assert MARA in world.present()


def test_a_next_draft_naming_no_one_but_the_player_passes_and_installs() -> None:
    world = _world(_run("a1", "A1"))
    draft = NextDraft[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        recap=RECAP,
    )

    assert scene_refusal(draft, world) is None

    world.apply_scene(draft)

    assert world.runs[-1].title == "A2"


def test_next_scene_refuses_a_pursuit_and_a_complication_together() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    draft = narrowed(state, Loner3eGame).draft()

    with pytest.raises(Refusal, match="not both"):
        _ = engine.next_scene(
            draft,
            NextScene(pursuit="Down the stair.", complication="A second crew breaks in."),
            Random(0),
        )


def test_a_departure_over_an_offer_requests_the_crossing_and_leaves_the_offer() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    _ = engine.tools["next_scene"].call(draft, {}, Random(0))

    _ = engine.tools["next_scene"].call(draft, {"pursuit": "Down the stair."}, Random(0))

    assert draft.generation is not None
    assert draft.generation.brief == "Down the stair."


def test_an_action_the_scene_no_longer_offers_is_refused_and_notes_nothing() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()

    with pytest.raises(Refusal, match="the way on has changed"):
        engine.act(draft, MOVE_ON.id, "Down the stair.")

    assert draft.notes == []


def test_the_dead_stay_in_the_scene_but_do_not_speak() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    _ = draft.payload.kill(MARA)

    view = engine.narrator_view(draft)

    assert MARA in [subject.id for subject in view.subjects]
    assert MARA not in view.speakers


def test_a_scene_without_a_focus_installs_and_shows_no_scene_panel() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    draft = narrowed(state, Loner3eGame).draft()
    scene = NextDraft[Loner3eSheet](place="a2", title="A2", situation=SITUATION, recap=RECAP)

    _ = engine.install(draft, scene)

    assert "This scene" not in [panel.title for panel in engine.player_view(draft).panels]
    assert "WHAT THIS SCENE IS ABOUT" not in str(engine.master_sections(draft))
