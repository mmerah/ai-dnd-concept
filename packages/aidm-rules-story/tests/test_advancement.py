from random import Random

from aidm.domain.base import PLAYER_ID
from aidm.domain.entities import ItemEntity
from aidm.domain.events import EntityCreated, RuleEvent
from aidm.domain.reducer import apply
from aidm_story.advancement import AcquireGear, IncreaseMaximumStress
from aidm_story.codecs import ACTOR_STATE_CODEC, ITEM_STATE_CODEC
from aidm_story.models import StoryGearTag
from story_test_support import initial_story_game, setback_direction


def test_story_gear_advancement_creates_one_carried_core_item() -> None:
    engine, state = initial_story_game()
    for _ in range(3):
        events = engine.rules.resolve(setback_direction(), state, Random(2))
        state = apply(state, events, engine.rules)
    assert engine.advancement.available(state)

    decision = AcquireGear(
        item_name="a silver compass",
        item_brief="Its needle points toward unfinished promises.",
        gear=StoryGearTag(
            name="Promise Compass",
            description="It finds paths connected to a sincere vow.",
        ),
    )
    events = engine.advancement.advance(state, decision, Random(0))
    created = [event for event in events if isinstance(event, EntityCreated)]
    assert len(created) == 1

    after = apply(state, events, engine.rules)
    entity = after.world.require(created[0].entity.id)
    assert isinstance(entity, ItemEntity)
    assert entity.container_id == PLAYER_ID
    assert entity.rules is not None
    assert ITEM_STATE_CODEC.decode(entity.rules).gear == decision.gear
    assert after.player.rules is not None
    assert ACTOR_STATE_CODEC.decode(after.player.rules).growth_marks == 0
    assert not engine.advancement.available(after)


def test_increasing_maximum_stress_revives_a_taken_out_player() -> None:
    # F54: leaving taken-out must be as observable as entering it. Five setbacks with
    # Random(2) (the deterministic setback seed every other Story test uses) mark three
    # growth and stack five stress, exactly reaching Kael's default max_stress of 5.
    engine, state = initial_story_game()
    for _ in range(5):
        events = engine.rules.resolve(setback_direction(take_stress=True), state, Random(2))
        state = apply(state, events, engine.rules)
    assert state.player.rules is not None
    before = ACTOR_STATE_CODEC.decode(state.player.rules)
    assert (before.stress, before.max_stress, before.taken_out) == (5, 5, True)
    assert engine.advancement.available(state)

    events = engine.advancement.advance(state, IncreaseMaximumStress(), Random(0))
    revived = [
        event for event in events if isinstance(event, RuleEvent) and event.name == "revived"
    ]
    assert len(revived) == 1

    after = apply(state, events, engine.rules)
    assert after.player.rules is not None
    updated_player = ACTOR_STATE_CODEC.decode(after.player.rules)
    assert (updated_player.stress, updated_player.max_stress) == (5, 6)
    assert updated_player.taken_out is False
