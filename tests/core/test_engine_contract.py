from core_test_support import initialized, settings
from story_test_support import story_game

from aidm.core.base import PLAYER_ID, Entity, EntityId
from aidm.core.effects import AdjustCounter, MoveItem, apply_effect
from aidm.core.engine import Engine
from aidm.core.facts import Fact
from aidm.core.registry import build_engine, engine_ids, plugins
from aidm.core.sheet import Sheet, player_sheet
from aidm.core.world import GameState, rules_of


def _turn(
    engine: Engine[Sheet], state: GameState[Sheet]
) -> tuple[GameState[Sheet], tuple[Fact, ...]]:
    draft = state.draft()
    facts = [
        *apply_effect(draft, MoveItem(item_id=EntityId("vault_map")), engine.default_rules),
        *apply_effect(
            draft,
            AdjustCounter(
                entity_id=PLAYER_ID, counter="stress", delta=1, reason="the strain of prying"
            ),
            engine.default_rules,
        ),
    ]
    return draft.committed(), tuple(facts)


def test_engine_initialization_and_state_contract() -> None:
    engine, state = story_game()

    assert state.engine == engine.id
    assert player_sheet(state).numbers["bold"] == 2
    engine.validate_state(state)

    restored = engine.state_type.model_validate_json(state.model_dump_json())
    assert restored == state


def test_effect_resolution_is_pure_and_renders_every_fact() -> None:
    """Load-bearing: a draft that shallow-copies would corrupt the committed state silently, so the
    turn has to touch both a core action and engine state to be worth asserting.
    """
    engine, state = story_game()
    before = state.model_dump_json()

    first_state, first_facts = _turn(engine, state)

    assert (first_state, first_facts) == _turn(engine, state)
    assert state.model_dump_json() == before
    assert {fact.kind for fact in first_facts} >= {
        "entity_discovered",
        "entity_moved",
        "counter_changed",
    }
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
    actor_sheet = rules_of(grown.world.record(actor.id), Sheet)
    item_sheet = rules_of(grown.world.record(item.id), Sheet)
    assert "stress" in actor_sheet.counters
    assert set(actor_sheet.numbers) == {"bold", "subtle", "clever", "empathetic"}
    assert not item_sheet.numbers
    assert not item_sheet.counters


def test_every_registered_engine_builds_itself() -> None:
    """Registration is data: a new engine is one line in `ENGINE_MODULES` and its own package."""
    config = settings()
    registered = plugins()

    assert engine_ids() == tuple(plugin.id for plugin in registered)
    for plugin in registered:
        built = build_engine(plugin.id, config)
        assert built.id == plugin.id
        assert all(plugin.badge)
