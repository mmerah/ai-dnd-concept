from core_test_support import (
    ENGINE_IDS,
    ENGINES_BUILT,
    LONER3E,
    character,
    initialized,
    loner_sheet,
    scenario,
    updated,
)

from aidm.engines.core import mechanics_of, rules
from aidm.engines.loner3e.rules import LUCK_MAX, Loner3eState, Sheet, apply_restore_luck
from aidm.engines.registry import begin_game
from aidm.state.entities import PLAYER_ID, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.model import Game
from aidm.world import actions
from aidm.world.topology import player_location


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
    with rules(draft.world, Loner3eState) as game:
        game.sheets[PLAYER_ID].luck.current = 1
    return draft.committed()


def test_engine_initialization_and_state_contract() -> None:
    engine, state = initialized()

    assert state.engine == engine.id
    assert loner_sheet(state, PLAYER_ID).luck.current == LUCK_MAX
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


def test_rules_on_an_entity_created_in_play_are_its_sheet() -> None:
    engine, state = initialized()
    hostile = Entity(
        id=EntityId("grown-hostile"),
        kind="actor",
        name="A Grown Hostile",
        brief="Written into the world by a growth pass.",
        known=True,
        parent_id=player_location(state),
    )
    working = state.draft()
    _ = working.add(hostile)
    with rules(working.world, Loner3eState) as game:
        game.sheets[hostile.id] = Sheet(
            concept="A Bloated Cloister Rat", skills=("Bites and Holds On",)
        )
    grown = working.committed()

    engine.validate(grown)

    sheet = loner_sheet(grown, hostile.id)
    assert sheet.concept == "A Bloated Cloister Rat"
    assert sheet.skills == ("Bites and Holds On",)


def test_authored_rules_are_the_sheet_of_whatever_carries_them() -> None:
    """Every actor is rollable; anything else is described only where a scenario wrote rules."""
    engine, shipped = ENGINES_BUILT[LONER3E], scenario()
    authored = updated(
        shipped,
        world=updated(
            shipped.world,
            mechanics=engine.mechanics_patch(
                shipped.world.mechanics,
                {"sheets": {"vault-map": {"concept": "a chart that remembers"}}},
                (),
            ),
        ),
    )

    state = begin_game(engine, "whispering-vault", authored, character())

    assert loner_sheet(state, EntityId("vault-map")).concept == "a chart that remembers"
    assert loner_sheet(state, EntityId("tomas")).concept == "A Deaf Old Porter"
    assert EntityId("lantern") not in mechanics_of(state.world, Loner3eState).sheets
    engine.validate(state)


def test_every_registered_engine_builds_itself_under_its_own_id() -> None:
    for engine_id in ENGINE_IDS:
        assert ENGINES_BUILT[engine_id].id == engine_id
