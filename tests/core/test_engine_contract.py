from random import Random

import pytest
from core_test_support import initialized
from pydantic import ValidationError

from aidm.app.registry import ENGINES
from aidm.app.session import build_engine
from aidm.engines.engine import Engine
from aidm.engines.loner3e.actions import Loner3eBeat, RestoreLuck
from aidm.engines.loner3e.mechanics import LUCK_MAX, Mechanics, Sheet
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.engines.sheets import SheetBase
from aidm.state.base import PLAYER_ID, EngineId, Entity, EntityId, Frozen
from aidm.state.beat import Resolution
from aidm.state.effects import Move, WorldEffect
from aidm.state.facts import Fact
from aidm.state.world import GameState


def _turn(engine: Engine[SheetBase], state: GameState) -> tuple[GameState, tuple[Fact, ...]]:
    draft = state.draft()
    effects: tuple[WorldEffect | RestoreLuck, ...] = (
        Move(entity_id=EntityId("vault_map"), to_id=PLAYER_ID),
        RestoreLuck(actor_id=PLAYER_ID),
    )
    facts = [fact for effect in effects for fact in engine.apply(draft, effect)]
    return draft.committed(), tuple(facts)


def _spent(state: GameState) -> GameState:
    """Luck short of full, so the engine's own effect has something to restore."""
    draft = state.draft()
    draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current = 1
    return draft.committed()


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()

    assert state.engine == engine.id
    assert state.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current == LUCK_MAX
    engine.validate(state)

    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored.model_dump() == state.model_dump()


def test_effect_resolution_is_pure_and_renders_every_fact() -> None:
    """Load-bearing: a draft that shallow-copies would corrupt the committed state silently, so the
    turn has to touch both a core action and engine state to be worth asserting.
    """
    engine, state = initialized()
    state = _spent(state)
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
    engine.validate(first_state)
    for fact in first_facts:
        assert fact.trace
        assert fact.narrator is None or str(fact.data) not in fact.narrator


def test_a_created_actor_is_refused_until_the_engine_seeds_it() -> None:
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

    with pytest.raises(ValueError, match="no character sheet"):
        engine.validate(grown)
    for entity in (actor, item):
        engine.seed(grown, entity, Random(0))
    engine.validate(grown)

    mechanics = grown.mechanics_as(Mechanics)
    assert mechanics.sheets[actor.id] == Sheet()
    assert item.id not in mechanics.sheets


def test_a_sheet_engine_that_declares_nothing_is_refused_before_it_plays() -> None:
    class Undeclared(Engine[Sheet]):
        id = EngineId("undeclared")
        badge = ("UNDECLARED", "grey-6")
        engine_dir = Loner3eEngine.engine_dir

        def new_sheet(self, draft: GameState, rng: Random) -> Sheet:
            return Sheet()

        def describe(self, state: GameState, entity: Entity) -> str:
            return ""

        def sheet_view(self, state: GameState) -> tuple[tuple[str, str], ...]:
            return ()

        def resolve_roll(self, draft: GameState, roll: Frozen, rng: Random) -> Resolution:
            return Resolution()

        def unpack_beat(self, beat: Frozen) -> tuple[Frozen | None, tuple[Frozen, ...]]:
            raise TypeError

    with pytest.raises(AttributeError, match="sheet_type"):
        _ = Undeclared()


def test_a_beat_naming_a_roll_this_engine_has_not_is_refused() -> None:
    """What replaces the deleted translation guard: typed output rejects a roll this engine does
    not have at validation, before the beat ever reaches the engine."""
    with pytest.raises(ValidationError):
        _ = Loner3eBeat.model_validate({"roll": {"op": "attempt", "actor_id": PLAYER_ID}})


def test_every_registered_engine_builds_itself() -> None:
    """Registration is data: a new engine is one line in `app.registry.ENGINES`."""
    assert len({engine.id for engine in ENGINES}) == len(ENGINES)
    for engine in ENGINES:
        _ = build_engine(engine.id)
