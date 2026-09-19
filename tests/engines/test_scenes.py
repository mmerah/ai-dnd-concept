from collections.abc import Sequence
from random import Random

import pytest
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    LONER3E,
    SCENARIO_MODELS,
    game,
    narrowed,
    scenario_for,
)

from aidm.core.entities import Refusal, Slug
from aidm.core.model import Commission
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.world import Loner3eEntity, Loner3eGame
from aidm.engines.scenes.engine import MOVE_ON
from aidm.engines.scenes.world import NextProposal, Scene, SceneWorld
from aidm.engines.scenes.worldsmith import MEANWHILE_NUDGE, check_scene

PLAYER = Person(id=PLAYER_ID, name="Player", brief="", known=True)
MARA = "mara"
SITUATION = "A long enough situation to satisfy the minimum length the model demands, twice over."
RECAP = "A long enough recap to satisfy the minimum length the model demands for what happened."
ARC = "A few lines on what waits farther in, long enough to satisfy the model's own minimum."


def _world(*scenes: Scene, **fields: object) -> SceneWorld[Person]:
    return SceneWorld[Person].model_validate({"player": PLAYER, "scenes": list(scenes), **fields})


def _scene(place: str, title: str, *, here: Sequence[Slug] = ()) -> Scene:
    return Scene(
        place=place,
        title=title,
        focus="What happens next here?",
        situation=SITUATION,
        here=list(here),
    )


def _travelling() -> SceneWorld[Person]:
    """The player, one companion in the cast, and a scene the pair stand in."""
    mara = Person(id=MARA, name="Mara", brief="A guide", known=True)
    return _world(_scene("a1", "A1", here=[MARA]), cast={MARA: mara}, party=[MARA])


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


def test_render_next_carries_the_meanwhile_nudge_only_when_armed_and_install_clears_it() -> None:
    engine, state = game(LONER3E)
    assert isinstance(engine, Loner3eEngine)
    draft = narrowed(state, Loner3eGame).draft()

    assert MEANWHILE_NUDGE not in engine.render_next(draft, "Down the stair.")

    draft.world.meanwhile_due = True
    assert MEANWHILE_NUDGE in engine.render_next(draft, "Down the stair.")

    scene = NextProposal[Loner3eEntity](place="a2", title="A2", situation=SITUATION, recap=RECAP)
    engine.install(draft, scene)

    assert draft.world.meanwhile_due is False


def test_entering_someone_hidden_is_refused_reveal_makes_them_present() -> None:
    mara = Person(id=MARA, name="Mara", brief="A guide", known=False)
    world = _world(_scene("a1", "A1", here=[MARA]), cast={MARA: mara})
    with pytest.raises(Refusal, match="already here"):
        _ = world.enter(MARA)
    _ = world.reveal_hidden(MARA)
    assert MARA in world.present()


def test_a_next_draft_naming_no_one_but_the_player_passes_and_installs() -> None:
    world = _world(_scene("a1", "A1"))
    draft = NextProposal[Person](
        place="a2",
        title="A2",
        focus="What happens next here?",
        situation=SITUATION,
        recap=RECAP,
    )

    check_scene(draft, world)

    world.apply_scene(draft)

    assert world.scenes[-1].title == "A2"


def test_a_departure_over_an_offer_requests_the_crossing_and_leaves_the_offer() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    _ = engine.tools["next_scene"].call(draft, {}, Random(0))

    _ = engine.tools["next_scene"].call(draft, {"pursuit": "Down the stair."}, Random(0))

    assert draft.commission is not None
    assert draft.commission.detail == "Down the stair."


def test_a_scene_engine_refuses_to_write_an_operation_not_its_own() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()
    draft.commission = Commission(operation="hire", detail="Hire a fixer.")

    with pytest.raises(Refusal, match="writes no 'hire'"):
        engine.validate(draft)


def test_an_action_the_scene_no_longer_offers_is_refused_and_notes_nothing() -> None:
    engine, state = game(LONER3E)
    draft = narrowed(state, Loner3eGame).draft()

    with pytest.raises(Refusal, match="the way on has changed"):
        engine.act(draft, MOVE_ON.id, "Down the stair.")

    assert draft.notes == []


def test_beginning_the_game_does_not_mutate_the_authored_scenario() -> None:
    engine = ENGINES_BUILT[LONER3E]
    scenario_id = scenario_for(LONER3E)
    scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    before = scenario.opening.model_dump()
    character = LIBRARY.read_character("kael", engine.id, engine.character)
    draft = engine.begin(scenario_id, scenario, character)
    world = narrowed(draft, Loner3eGame).world

    world.cast[MARA].name = "Someone else"

    assert scenario.opening.model_dump() == before
