import pytest
from core_test_support import STORY, character, initialized, scenario, updated, with_entity
from pydantic import ValidationError

from aidm.core.base import PLAYER_ID, Entity, EntityId
from aidm.core.content import (
    AuthoredEntity,
    AuthoredWorld,
    Character,
    CharacterOverlay,
    CharacterProfile,
    authored_world,
)
from aidm.core.sheet import SheetDefinition, SheetTag

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
        overlay=CharacterOverlay(
            character=SheetDefinition().model_dump(mode="json"),
            entities={
                gear_for: SheetDefinition(
                    tags=(SheetTag(id="silk-rope", name="Silk Rope", text="(gear) Braided silk."),)
                ).model_dump(mode="json")
            },
        ),
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
    player_record = state.world.record(PLAYER_ID)
    with pytest.raises(ValidationError, match="keys disagree"):
        type(state.world).model_validate(
            {"records": {"wrong-key": player_record.model_dump(round_trip=True)}}
        )

    with pytest.raises(ValidationError, match="player entity must be known"):
        with_entity(state, updated(state.player, known=False))

    with pytest.raises(ValidationError, match="not in a valid location"):
        with_entity(state, updated(state.player, parent_id=EntityId("missing")))

    carried = state.world.children(PLAYER_ID, "item")[0]
    with pytest.raises(ValidationError, match="is a location with item rules"):
        with_entity(state, updated(carried, kind="location"))


def test_an_engine_refuses_an_authored_payload_it_cannot_read() -> None:
    """Every kind takes a sheet now, so forbid-extra on the authored overlay is what is left of the
    guard — and it has to fire at launch, not on the turn that first reads the entity."""
    engine, _ = initialized()
    selected = character()
    authored = authored_world(scenario(), selected)
    location = next(
        record for record in authored.entities.values() if record.entity.kind == "location"
    )
    poisoned = AuthoredWorld(
        entities={
            **authored.entities,
            location.entity.id: AuthoredEntity(entity=location.entity, rules={"gear": None}),
        }
    )

    with pytest.raises(ValueError, match="gear"):
        engine.initial_world(poisoned, selected.overlay.character)


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
