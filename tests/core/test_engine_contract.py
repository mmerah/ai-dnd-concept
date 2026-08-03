from random import Random

from core_test_support import character, initialized

from aidm.actions import TakeItem
from aidm.base import ENGINE_IDS, PLAYER_ID, ActorEntity, EntityId, ItemEntity
from aidm.engine import ENGINES
from aidm.engines.story.access import actor_of, item_of, player_rules
from aidm.engines.story.direction import Risk, StoryDirection
from aidm.engines.story.state import DEFAULT_APPROACHES, StoryCharacterData
from aidm.world import GameState


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()
    sheet = character().overlay.character
    assert isinstance(sheet, StoryCharacterData)

    assert state.engine == engine.id
    assert player_rules(state).approaches == sheet.approaches
    engine.validate_state(state)

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

    first = engine.resolve(direction, state, Random(19))
    second = engine.resolve(direction, state, Random(19))

    assert first == second
    assert state.model_dump_json() == before
    assert {fact.fact for fact in first.facts} >= {"entity_discovered", "item_moved", "risk-rolled"}
    assert first.state.model_dump_json() != before
    engine.validate_state(first.state)
    for fact in first.facts:
        assert fact.trace_summary
        rendered = fact.narrator_summary
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
        _ = working.add(entity, engine.default_rules(entity))
    grown = working.committed()

    assert actor_of(grown, actor.id)[1].approaches == DEFAULT_APPROACHES
    assert item_of(grown, item.id)[1].gear is None


def test_every_engine_id_has_a_builder() -> None:
    """`ENGINES` is data, so no `match` fails when a new `EngineId` arrives without a builder."""
    assert set(ENGINES) == set(ENGINE_IDS)
