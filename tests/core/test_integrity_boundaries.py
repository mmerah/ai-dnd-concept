import json

import pytest
from core_test_support import (
    LONER3E,
    begin_game,
    character,
    initialized,
    scenario,
    updated,
    with_entity,
)
from pydantic import ValidationError

from aidm.content.authored import Character, CharacterOverlay, CharacterProfile, ScenarioWorld
from aidm.content.store import SavedGame
from aidm.engines.loner3e.mechanics import LUCK_MAX, Mechanics
from aidm.state.base import PLAYER_ID, Entity, EntityId
from aidm.state.world import Game, Hook

HELD = EntityId("frayed_rope")
UNHELD = EntityId("silk_rope")
MARA = EntityId("mara")
ELENA = EntityId("elena")
_HALL = {"id": "hall", "kind": "location", "name": "the hall", "brief": "A hall.", "known": True}
_DOUBLED = json.dumps(
    {
        "meta": {"title": "Twice Over", "premise": "One id, authored twice."},
        "starting_location_id": "hall",
        "entities": [_HALL, {**_HALL, "name": "the hall again"}],
    }
)


def _character(*, holds: Entity, gear_for: EntityId) -> Character:
    return Character(
        id="test-character",
        engine=LONER3E,
        profile=CharacterProfile(
            name="Test Character",
            brief="A character built only for this test.",
            items=(holds,),
        ),
        overlay=CharacterOverlay(character={}, entities={gear_for: {}}),
    )


def _rope(item_id: EntityId, *, known: bool = True) -> Entity:
    return Entity(
        id=item_id,
        kind="item",
        name="rope",
        brief="A length of rope.",
        known=known,
        parent_id=PLAYER_ID,
    )


def test_world_and_game_state_reject_inconsistent_topology() -> None:
    _, state = initialized()
    twice = state.world.require(PLAYER_ID).model_dump(round_trip=True)
    with pytest.raises(ValidationError, match="duplicate entity ids"):
        type(state.world).model_validate({"entities": [twice, twice]})

    with pytest.raises(ValueError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, parent_id=EntityId("missing")))

    carried = state.world.children(PLAYER_ID, "item")[0]
    with pytest.raises(ValidationError, match="cannot be inside anything"):
        with_entity(state, updated(carried, kind="location"))


def test_an_engine_refuses_an_authored_payload_it_cannot_read() -> None:
    """Only actors carry engine mechanics now, so the overlay's forbid-extra guard fires on one of
    them — and it has to fire at launch, not on the turn that first reads the entity."""
    engine, _ = initialized()
    authored = scenario()
    entities = authored.world.world.entities
    actor = next(entity for entity in entities if entity.kind == "actor")
    poisoned = updated(authored, overlay={"entities": {actor.id: {"gear": None}}})

    with pytest.raises(ValueError, match="gear"):
        begin_game(engine, poisoned, character())


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario().world, starting_location_id=EntityId("missing"))
    with pytest.raises(ValidationError, match="duplicate entity ids"):
        # Keyed by id from a flat array, so the duplicate has to be caught before it collapses.
        ScenarioWorld.model_validate_json(_DOUBLED)


def test_a_location_no_walk_reaches_is_refused() -> None:
    world = scenario().world
    undercroft = Entity(
        id=EntityId("undercroft"),
        kind="location",
        name="the undercroft",
        brief="A chamber no passage names.",
        known=False,
    )
    with pytest.raises(ValidationError, match=r"no walk.*undercroft"):
        updated(world, entities=(*world.entities, undercroft))


def test_world_state_rejects_broken_exits_and_party() -> None:
    world = scenario().world.world
    study = world.require(EntityId("study"))
    exposed = updated(study, exits=(*study.exits, {"to": "bell_tower", "known": True}))
    with pytest.raises(ValidationError, match="has not met"):
        updated(world, entities=tuple(exposed if e.id == study.id else e for e in world.entities))

    with pytest.raises(ValidationError, match="without being met"):
        updated(world, party=(ELENA,))
    with pytest.raises(ValidationError, match="cannot travel with themselves"):
        updated(world, party=(PLAYER_ID,))

    mara = world.require(MARA)
    wandering = updated(mara, exits=({"to": "study"},))
    with pytest.raises(ValidationError, match="cannot have exits"):
        updated(world, entities=tuple(wandering if e.id == mara.id else e for e in world.entities))


def test_a_hook_waiting_on_an_unauthored_id_is_refused() -> None:
    world = scenario().world
    ghost = Hook(id="ghost-sighted", on_discover=EntityId("ghost"))
    with pytest.raises(ValidationError, match=r"never fire.*ghost"):
        updated(world, hooks=(*world.hooks, ghost))


def test_a_hook_revealing_an_unauthored_id_is_refused() -> None:
    world = scenario().world
    haunted = Hook(id="vault-haunted", on_discover=EntityId("vault"), reveals=(EntityId("ghost"),))
    with pytest.raises(ValidationError, match=r"vault-haunted.*ghost"):
        updated(world, hooks=(*world.hooks, haunted))


def test_a_scenario_starts_the_party_it_authors() -> None:
    """A scenario holds no player, so the tie to one is named as an id and made at composition."""
    engine, _ = initialized()
    authored = scenario()
    started = updated(authored, world=updated(authored.world, starting_party=(MARA,)))

    assert begin_game(engine, started, character()).world.party == [MARA]
    with pytest.raises(ValidationError, match="who they set out with"):
        updated(authored.world, starting_party=(ELENA,))


def test_an_overlay_may_not_name_an_entity_the_author_never_wrote() -> None:
    """An overlay keys off authored ids, so a typo must fail at load, not go silently unread."""
    with pytest.raises(ValidationError, match="unauthored ids"):
        _character(holds=_rope(HELD), gear_for=UNHELD)


def test_a_character_knows_the_gear_they_start_with() -> None:
    """Unknown carried gear would be hidden canon inside the inventory the Narrator is shown."""
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False), gear_for=HELD)


def _luck(state: Game) -> int:
    return Mechanics.of(state).sheets[PLAYER_ID].luck.current


def test_a_mechanics_mutation_lands_on_the_commit_and_nowhere_else() -> None:
    _, state = initialized()
    draft = state.draft()
    Mechanics.of(draft).sheets[PLAYER_ID].luck.current = 1

    committed = draft.committed()

    assert _luck(committed) == 1
    assert SavedGame.of(committed).mechanics != SavedGame.of(state).mechanics
    assert _luck(state) == LUCK_MAX
