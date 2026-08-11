import pytest
from core_test_support import (
    STORY,
    begin_game,
    character,
    initialized,
    scenario,
    updated,
    with_entity,
)
from pydantic import ValidationError

from aidm.content.authored import (
    Character,
    CharacterOverlay,
    CharacterProfile,
)
from aidm.state.base import PLAYER_ID, Entity, EntityId

HELD = EntityId("frayed_rope")
UNHELD = EntityId("silk_rope")


def _character(*, holds: Entity, gear_for: EntityId) -> Character:
    return Character(
        id="test-character",
        engine=STORY,
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
    player = state.world.require(PLAYER_ID)
    with pytest.raises(ValidationError, match="keys disagree"):
        type(state.world).model_validate(
            {"entities": {"wrong-key": player.model_dump(round_trip=True)}}
        )

    with pytest.raises(ValidationError, match="player entity must be known"):
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
    actor = next(entity for entity in authored.world.entities if entity.kind == "actor")
    poisoned = updated(authored, overlay={"entities": {actor.id: {"gear": None}}})

    with pytest.raises(ValueError, match="gear"):
        begin_game(engine, poisoned, character())


def test_scenario_topology_is_validated() -> None:
    with pytest.raises(ValidationError, match="starting_location_id"):
        updated(scenario().world, starting_location_id=EntityId("missing"))


def test_an_overlay_may_not_name_an_entity_the_author_never_wrote() -> None:
    """An overlay keys off authored ids, so a typo must fail at load, not go silently unread."""
    with pytest.raises(ValidationError, match="unauthored ids"):
        _character(holds=_rope(HELD), gear_for=UNHELD)


def test_a_character_knows_the_gear_they_start_with() -> None:
    """Unknown carried gear would be hidden canon inside the inventory the Narrator is shown."""
    with pytest.raises(ValidationError, match="knows the gear they start with"):
        _character(holds=_rope(HELD, known=False), gear_for=HELD)
