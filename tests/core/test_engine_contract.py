from random import Random

from core_test_support import character, initialized, settings

from aidm.actions import TakeItem
from aidm.base import PLAYER_ID, ActorEntity, EntityId, ItemEntity
from aidm.engines.story.access import actor_state, item_state, player_state
from aidm.engines.story.direction import Risk, StoryDirection, dump_direction
from aidm.engines.story.state import DEFAULT_APPROACHES, StoryCharacterData
from aidm.registry import engine_ids, plugins
from aidm.world import GameState


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()
    sheet = StoryCharacterData.model_validate(character().overlay.character)

    assert state.engine == engine.id
    assert player_state(state).approaches == sheet.approaches
    engine.validate_state(state)

    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_engine_resolution_is_pure_seeded_and_renders_every_fact() -> None:
    """Load-bearing: a draft that shallow-copies would corrupt the committed state silently, so the
    direction has to change state, take a core action and reach engine state to be worth asserting.
    """
    engine, state = initialized()
    direction = dump_direction(
        StoryDirection(
            intent="Kael pockets the map, then chances it.",
            tone="tense",
            mechanics=[
                TakeItem(item_id=EntityId("vault_map")),
                Risk(approach="bold", difficulty=2),
            ],
        )
    )
    before = state.model_dump_json()

    first = engine.resolve(direction, state, Random(19))
    second = engine.resolve(direction, state, Random(19))

    assert first == second
    assert state.model_dump_json() == before
    assert {fact.kind for fact in first.facts} >= {
        "entity_discovered",
        "item_moved",
        "risk_rolled",
    }
    assert {fact.source for fact in first.facts} == {"core", engine.id}
    assert first.state.model_dump_json() != before
    engine.validate_state(first.state)
    for fact in first.facts:
        assert fact.trace
        assert fact.narrator is None or str(fact.data) not in fact.narrator


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

    engine.validate_state(grown)
    assert actor_state(grown.world.actor(actor.id).rules).approaches == DEFAULT_APPROACHES
    assert item_state(grown.world.item(item.id).rules).gear is None


def test_every_registered_engine_builds_itself() -> None:
    """Registration is data: a new engine is one line in `ENGINE_MODULES` and its own package."""
    config = settings()
    registered = plugins()

    assert engine_ids() == tuple(plugin.id for plugin in registered)
    for plugin in registered:
        built = plugin.build(config)
        assert built.id == plugin.id
        assert all(plugin.badge)
