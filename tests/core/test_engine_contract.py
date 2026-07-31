from random import Random

from core_test_support import character, initialized

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, ItemEntity
from aidm.domain.state import GameState
from aidm.engines import narrator_fact, trace_fact
from aidm_story.actions import TakeItem
from aidm_story.direction import Risk, StoryDirection
from aidm_story.models import DEFAULT_APPROACHES, StoryCharacterData
from aidm_story.state import story_state


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()
    sheet = character().overlay.character
    assert isinstance(sheet, StoryCharacterData)

    assert state.engine_id == engine.id
    assert story_state(state).actor(PLAYER_ID).approaches == sheet.approaches
    engine.rules.validate_state(state)

    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_engine_resolution_is_pure_seeded_and_renders_every_fact() -> None:
    """Load-bearing: a draft that shallow-copies would corrupt the committed state silently, so the
    direction has to change state, take a core action and reach engine state to be worth asserting.
    """
    engine, state = initialized()
    direction = StoryDirection(
        intent="Kael pockets the map, then chances it.",
        tone="tense",
        mechanics=[TakeItem(item_id=EntityId("vault_map")), Risk(approach="bold", difficulty=2)],
    )
    before = state.model_dump_json()

    first = engine.rules.resolve(direction, state, Random(19))
    second = engine.rules.resolve(direction, state, Random(19))

    assert first == second
    assert state.model_dump_json() == before
    assert {fact.fact for fact in first.facts} >= {"entity_discovered", "item_moved", "risk-rolled"}
    assert first.state.model_dump_json() != before
    engine.rules.validate_state(first.state)
    for fact in first.facts:
        assert trace_fact(engine, fact)
        rendered = narrator_fact(engine, fact)
        assert rendered is None or str(fact.model_dump()) not in rendered


def test_a_created_entity_gains_engine_state_in_the_same_commit() -> None:
    engine, state = initialized()
    actor = ActorEntity(
        id=EntityId("created-actor"),
        name="A New Actor",
        brief="Newly introduced.",
        known=True,
        location_id=state.player.location_id,
    )
    item = ItemEntity(
        id=EntityId("created-item"),
        name="A New Item",
        brief="Newly introduced.",
        known=True,
        container_id=PLAYER_ID,
    )

    working = state.draft()
    for entity in (actor, item):
        _ = working.add(entity)
        engine.rules.created(working, entity)
    grown = working.committed()

    assert story_state(grown).actor(actor.id).approaches == DEFAULT_APPROACHES
    assert story_state(grown).item(item.id).gear is None
