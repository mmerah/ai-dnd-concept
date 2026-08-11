from core_test_support import initialized, settings
from story_test_support import story_game

from aidm.app.session import build_engine
from aidm.engines.counters import CounterChange
from aidm.engines.loader import Engine, plugins
from aidm.engines.story.mechanics import Adventurer, read
from aidm.engines.story.mechanics import apply as story_apply
from aidm.state.base import PLAYER_ID, Entity, EntityId
from aidm.state.effects import Move
from aidm.state.facts import Fact
from aidm.state.world import GameState


def _turn(engine: Engine, state: GameState) -> tuple[GameState, tuple[Fact, ...]]:
    del engine
    draft = state.draft()
    facts = [
        *story_apply(draft, Move(entity_id=EntityId("vault_map"))),
        *story_apply(
            draft,
            CounterChange(
                mode="adjust",
                entity_id=PLAYER_ID,
                counter="stress",
                amount=1,
                why="the strain of prying",
            ),
        ),
    ]
    return draft.committed(), tuple(facts)


def test_engine_initialization_and_state_contract() -> None:
    engine, state = story_game()

    assert state.engine == engine.id
    assert read(state).actors[PLAYER_ID].bold == 2
    engine.commit(state)

    restored = GameState.model_validate_json(state.model_dump_json())
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
    engine.commit(first_state)
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
        _ = working.add(entity)
    grown = working.committed()
    engine.commit(grown)

    mechanics = read(grown)
    assert mechanics.actors[actor.id] == Adventurer()
    assert item.id not in mechanics.actors


def test_every_registered_engine_builds_itself() -> None:
    """Registration is data: a new engine is one line in `ENGINE_MODULES` and its own package."""
    config = settings()
    for plugin in plugins():
        _ = build_engine(plugin.id, config)
