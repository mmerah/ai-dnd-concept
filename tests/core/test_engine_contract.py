from random import Random

from core_test_support import TestDirection as _TestDirection
from core_test_support import initialized

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.events import RuleEvent
from aidm.domain.reducer import apply
from aidm.domain.state import GameState


def test_engine_initialization_and_payload_contract() -> None:
    engine, state = initialized()

    assert state.engine.id == engine.descriptor.ref.id
    assert state.engine.rules_version == engine.descriptor.ref.rules_version
    assert state.engine.schema_version == engine.descriptor.schema_version
    assert state.player.rules is not None
    for entity in state.world.entities.values():
        if entity.rules is not None:
            assert entity.rules.engine == state.engine.id
            assert entity.rules.schema_version == state.engine.schema_version
    engine.rules.validate_state(state)

    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_engine_resolution_is_pure_seeded_and_core_applies_every_event() -> None:
    engine, state = initialized()
    direction = _TestDirection(intent="Wait.", tone="quiet")
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


def test_engine_initializes_creator_actor_and_item_rules() -> None:
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

    actor_rules = engine.lifecycle.rules_for_created_entity(actor, state)
    item_rules = engine.lifecycle.rules_for_created_entity(item, state)

    assert actor_rules is not None
    assert item_rules is not None
    assert actor_rules.engine == state.engine.id
    assert item_rules.schema_version == state.engine.schema_version
