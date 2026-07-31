from random import Random

from core_test_support import character, initialized

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.events import EntityCreated, RuleEvent
from aidm.domain.reducer import apply
from aidm.domain.state import GameState
from aidm_story.direction import StoryDirection
from aidm_story.models import DEFAULT_APPROACHES, StoryCharacterData
from aidm_story.state import story_state


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()
    sheet = character().engine_data
    assert isinstance(sheet, StoryCharacterData)

    assert state.engine_id == engine.id
    assert story_state(state).actor(PLAYER_ID).approaches == sheet.approaches
    engine.rules.validate_state(state)

    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_engine_resolution_is_pure_seeded_and_core_applies_every_event() -> None:
    engine, state = initialized()
    direction = StoryDirection(intent="Wait.", tone="quiet")
    before = state.model_dump_json()

    first = engine.rules.resolve(direction, state, Random(19))
    second = engine.rules.resolve(direction, state, Random(19))

    assert first == second
    assert state.model_dump_json() == before
    provisional = state
    for event in first:
        provisional = apply(provisional, [event], engine.rules)
        engine.rules.validate_state(provisional)
        if isinstance(event, RuleEvent):
            assert engine.presentation.trace_event(event)
            rendered = engine.presentation.narrator_event(event)
            assert rendered is None or str(event.payload) not in rendered


def test_a_created_entity_gains_engine_state_in_the_same_commit() -> None:
    engine, state = initialized()
    actor = ActorEntity(
        id=EntityId("created-actor"),
        name="A New Actor",
        brief="Newly introduced.",
        known=True,
        authored=False,
        location_id=state.player.location_id,
    )
    item = ItemEntity(
        id=EntityId("created-item"),
        name="A New Item",
        brief="Newly introduced.",
        known=True,
        authored=False,
        container_id=PLAYER_ID,
    )

    grown = apply(state, [EntityCreated(entity=actor), EntityCreated(entity=item)], engine.rules)

    assert story_state(grown).actor(actor.id).approaches == DEFAULT_APPROACHES
    assert story_state(grown).item(item.id).gear is None
