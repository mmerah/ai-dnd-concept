from random import Random

from story_test_support import initial_story_game, setback_direction

from aidm.domain.base import PLAYER_ID
from aidm.domain.entities import ItemEntity
from aidm.domain.facts import EntityCreated
from aidm_story.advancement import AcquireGear, IncreaseMaximumStress
from aidm_story.facts import Revived
from aidm_story.models import StoryGearTag
from aidm_story.state import story_state


def test_story_gear_advancement_creates_one_carried_core_item() -> None:
    engine, state = initial_story_game()
    for _ in range(3):
        state = engine.rules.resolve(setback_direction(), state, Random(2)).state
    assert engine.advancement.available(state)

    decision = AcquireGear(
        item_name="a silver compass",
        item_brief="Its needle points toward unfinished promises.",
        gear=StoryGearTag(
            name="Promise Compass",
            description="It finds paths connected to a sincere vow.",
        ),
    )
    transition = engine.advancement.advance(state, decision, Random(0))
    created = [fact for fact in transition.facts if isinstance(fact, EntityCreated)]
    assert len(created) == 1

    after = transition.state
    entity = after.world.require(created[0].entity.id)
    assert isinstance(entity, ItemEntity)
    assert entity.container_id == PLAYER_ID
    assert story_state(after).item(entity.id).gear == decision.gear
    assert story_state(after).actor(PLAYER_ID).growth_marks == 0
    assert not engine.advancement.available(after)


def test_increasing_maximum_stress_revives_a_taken_out_player() -> None:
    # F54: leaving taken-out must be as observable as entering it. Five setbacks with
    # Random(2) (the deterministic setback seed every other Story test uses) mark three
    # growth and stack five stress, exactly reaching Kael's default max_stress of 5.
    engine, state = initial_story_game()
    for _ in range(5):
        state = engine.rules.resolve(setback_direction(take_stress=True), state, Random(2)).state
    before = story_state(state).actor(PLAYER_ID)
    assert (before.stress, before.max_stress, before.taken_out) == (5, 5, True)
    assert engine.advancement.available(state)

    transition = engine.advancement.advance(state, IncreaseMaximumStress(), Random(0))
    assert len([fact for fact in transition.facts if isinstance(fact, Revived)]) == 1

    player = story_state(transition.state).actor(PLAYER_ID)
    assert (player.stress, player.max_stress) == (5, 6)
    assert player.taken_out is False
