from random import Random

from core_test_support import character, initialized, settings, tool_context, turn_context

from aidm.core.base import PLAYER_ID, Entity, EntityId
from aidm.core.facts import Fact
from aidm.core.registry import AnyEngine, build_engine, engine_ids, plugins
from aidm.core.tools import take_item
from aidm.core.world import EngineRules, GameState
from aidm.engines.story.state import (
    DEFAULT_APPROACHES,
    StoryCharacterData,
    actor_of,
    item_of,
)
from aidm.engines.story.tools import risk


def _turn(
    engine: AnyEngine, state: GameState[EngineRules]
) -> tuple[GameState[EngineRules], tuple[Fact, ...]]:
    context = turn_context(engine, state, Random(19))
    run = tool_context(context)
    _ = take_item(run, EntityId("vault_map"))
    _ = risk(run, approach="bold", difficulty=2)
    return context.draft.committed(), tuple(context.facts)


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()
    sheet = StoryCharacterData.model_validate(character().overlay.character)

    assert state.engine == engine.id
    assert actor_of(state, PLAYER_ID).approaches == sheet.approaches
    engine.validate_state(state)

    restored = engine.state_type.model_validate_json(state.model_dump_json())
    assert restored == state


def test_tool_resolution_is_pure_seeded_and_renders_every_fact() -> None:
    """Load-bearing: a draft that shallow-copies would corrupt the committed state silently, so the
    turn has to touch both a core action and engine state to be worth asserting.
    """
    engine, state = initialized()
    before = state.model_dump_json()

    first_state, first_facts = _turn(engine, state)

    assert (first_state, first_facts) == _turn(engine, state)
    assert state.model_dump_json() == before
    assert {fact.kind for fact in first_facts} >= {
        "entity_discovered",
        "entity_moved",
        "risk_rolled",
    }
    assert {fact.source for fact in first_facts} == {"core", engine.id}
    assert first_state.model_dump_json() != before
    engine.validate_state(first_state)
    for fact in first_facts:
        assert fact.trace
        assert fact.narrator is None or str(fact.data) not in fact.narrator


def test_a_created_entity_gains_engine_state_in_the_same_commit() -> None:
    engine, state = initialized()
    actor = Entity(
        id=EntityId("created-actor"),
        kind="actor",
        name="A New Actor",
        brief="Newly introduced.",
        known=True,
        parent_id=state.player_location,
    )
    item = Entity(
        id=EntityId("created-item"),
        kind="item",
        name="A New Item",
        brief="Newly introduced.",
        known=True,
        parent_id=PLAYER_ID,
    )

    working = state.draft()
    for entity in (actor, item):
        _ = working.add(entity, engine.default_rules(entity))
    grown = working.committed()

    engine.validate_state(grown)
    assert actor_of(grown, actor.id).approaches == DEFAULT_APPROACHES
    assert item_of(grown, item.id).gear is None


def test_every_registered_engine_builds_itself() -> None:
    """Registration is data: a new engine is one line in `ENGINE_MODULES` and its own package."""
    config = settings()
    registered = plugins()

    assert engine_ids() == tuple(plugin.id for plugin in registered)
    for plugin in registered:
        built = build_engine(plugin.id, config)
        assert built.id == plugin.id
        assert all(plugin.badge)
