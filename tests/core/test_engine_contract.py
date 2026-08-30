from core_test_support import ENGINE_IDS, ENGINES_BUILT, initialized, loner_sheet, with_entity

from aidm.engines.loner3e.rules import apply_restore_luck
from aidm.engines.loner3e.state import LUCK_MAX, ActorSheet, Loner3eState, LonerSheet
from aidm.kernel.protocol import Engine as EngineContract
from aidm.kits.scenes.state import Entity
from aidm.kits.scenes.tools import MoveItem, Reveal, apply_change
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import Fact
from aidm.state.model import Game

MAP = EntityId("vault-map")


def _turn(state: Game) -> tuple[Game, tuple[Fact, ...]]:
    """A core change and an engine action on one draft, so a shallow copy shows up in either."""
    draft = state.draft()
    facts = [
        *apply_change(draft.world, Reveal(verb="reveal", entity_id=MAP)),
        *apply_change(draft.world, MoveItem(verb="move_item", item_id=MAP, to=PLAYER_ID)),
        *apply_restore_luck(draft, PLAYER_ID),
    ]
    return draft.committed(), tuple(facts)


def _spent(state: Game) -> Game:
    """Luck short of full, so the engine's own action has something to restore."""
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1
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
    hostile = Entity[LonerSheet](
        id=EntityId("grown-hostile"),
        kind="actor",
        name="A Grown Hostile",
        brief="Written into the world by a later scene.",
        known=True,
        sheet=ActorSheet(concept="A Bloated Cloister Rat", skills=("Bites and Holds On",)),
    )

    grown = with_entity(state, hostile)

    engine.validate(grown)
    sheet = loner_sheet(grown, hostile.id)
    assert sheet.concept == "A Bloated Cloister Rat"
    assert sheet.skills == ("Bites and Holds On",)


def test_an_authored_sheet_rides_the_entity_it_was_written_on() -> None:
    """Every actor is rollable; anything else carries a sheet only where a scenario wrote one."""
    engine, state = initialized()

    assert loner_sheet(state, EntityId("tomas")).concept == "A Deaf Old Porter"
    assert state.world.require(MAP).sheet is None
    engine.validate(state)


def test_every_registered_engine_builds_itself_under_its_own_id() -> None:
    for engine_id in ENGINE_IDS:
        # The annotation is the check: an engine that drifts from the protocol fails to type.
        checked: EngineContract[Loner3eState] = ENGINES_BUILT[engine_id]
        assert checked.id == engine_id
