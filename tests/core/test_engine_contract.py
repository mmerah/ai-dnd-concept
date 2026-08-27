from collections.abc import Mapping
from random import Random

import pytest
from core_test_support import LONER3E, character, initialized, scenario, updated
from pydantic import JsonValue

from aidm.engines.core import Engine, apply_to_draft
from aidm.engines.loner3e.engine import Loner3eEngine
from aidm.engines.loner3e.rules import RULES, Mechanics, Pack, Sheet, apply_restore_luck
from aidm.engines.registry import ENGINES, begin_game, build_engine
from aidm.state import actions
from aidm.state.entities import PLAYER_ID, EngineId, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.model import Game, WorldState


def _turn(state: Game) -> tuple[Game, tuple[Fact, ...]]:
    """A core action and an engine action on one draft, so a shallow copy shows up in either."""
    draft = state.draft()
    facts = [
        *actions.move(draft, EntityId("vault-map"), PLAYER_ID),
        *apply_restore_luck(draft, PLAYER_ID),
    ]
    return draft.committed(), tuple(facts)


def _spent(state: Game) -> Game:
    """Luck short of full, so the engine's own action has something to restore."""
    draft = state.draft()
    Mechanics.of_game(draft).sheets[PLAYER_ID].luck.current = 1
    return draft.committed()


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()

    assert state.engine == engine.id
    assert Mechanics.of_game(state).sheets[PLAYER_ID].luck.current == RULES.luck_max
    engine.validate(state)

    assert engine.restored(state.model_dump_json()) == state


def test_action_resolution_is_pure_and_renders_every_fact() -> None:
    engine, state = initialized()
    state = _spent(state)
    before = state.model_dump_json()

    first_state, first_facts = _turn(state)

    assert (first_state, first_facts) == _turn(state)
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

    mechanics = Mechanics.of_game(grown)
    assert mechanics.sheets[actor.id] == Sheet()
    assert item.id not in mechanics.sheets


def test_rules_on_an_entity_created_in_play_reach_its_sheet() -> None:
    engine, state = initialized()
    hostile = Entity(
        id=EntityId("grown-hostile"),
        kind="actor",
        name="A Grown Hostile",
        brief="Written into the world by a growth pass.",
        known=True,
        parent_id=state.player_location,
        rules={"concept": "A Bloated Cloister Rat", "skills": ["Bites and Holds On"]},
    )
    working = state.draft()
    _ = working.add(hostile)
    grown = working.committed()

    engine.seed(grown, hostile, Random(0))

    sheet = Mechanics.of_game(grown).sheets[hostile.id]
    assert sheet.concept == "A Bloated Cloister Rat"
    assert sheet.skills == ("Bites and Holds On",)


def test_authored_rules_reach_the_sheet_of_whatever_carries_them() -> None:
    """Every actor is rollable; anything else carries mechanics only where a scenario wrote them."""
    engine, shipped = build_engine(LONER3E), scenario()
    authored = updated(
        shipped,
        world=updated(
            shipped.world,
            entities=[
                updated(entity, rules={"concept": "a chart that remembers"})
                if entity.id == EntityId("vault-map")
                else entity
                for entity in shipped.world.entities
            ],
        ),
    )

    state = begin_game(engine, "whispering-vault", authored, character())

    sheets = Mechanics.of_game(state).sheets
    assert sheets[EntityId("vault-map")].concept == "a chart that remembers"
    assert sheets[EntityId("tomas")].concept == "A Deaf Old Porter"
    assert EntityId("lantern") not in sheets
    engine.validate(state)


def test_an_engine_that_declares_nothing_is_refused_before_it_plays() -> None:
    class Undeclared(Engine):
        id = EngineId("undeclared")
        badge = ("UNDECLARED", "grey-6")
        engine_dir = Loner3eEngine.engine_dir

        def overlay_rows(self, rules: dict[str, JsonValue]) -> tuple[tuple[str, str], ...]:
            del rules
            return ()

        def opening_mechanics(
            self, world: WorldState, player_rules: dict[str, JsonValue]
        ) -> Mechanics:
            del world, player_rules
            return Mechanics()

        def validate(self, state: Game) -> None:
            del state

        def describe(self, state: Game, entity: Entity) -> str:
            del state, entity
            return ""

        def sheet_rows(self, state: Game) -> tuple[tuple[str, str], ...]:
            del state
            return ()

        def pack_models(self) -> Mapping[str, Pack]:
            return {}

    with pytest.raises(AttributeError, match="mechanics_type|pack_type"):
        _ = Undeclared()


def test_settle_facts_land_in_what_apply_to_draft_returns() -> None:
    settled = Fact(kind="counter_changed", trace="the rules settled it")

    class Settling(Loner3eEngine):
        def settle(self, draft: Game) -> tuple[Fact, ...]:
            del draft
            return (settled,)

    _, state = initialized()
    landed = apply_to_draft(Settling(), state.draft(), lambda draft, rng: (), Random(0))

    assert settled in landed


def test_every_registered_engine_builds_itself() -> None:
    assert len({engine.id for engine in ENGINES}) == len(ENGINES)
    for engine in ENGINES:
        assert "srd" in build_engine(engine.id).pack_ids
